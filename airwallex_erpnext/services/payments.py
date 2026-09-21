from __future__ import annotations

from decimal import Decimal
from typing import Any

import frappe

from airwallex_erpnext.services.exchange_rates import get_company_currency, payload_rate, resolve_exchange_rate
from airwallex_erpnext.services.mappings import account_mapping
from airwallex_erpnext.utils import as_float, as_money, iso_to_date

TERMINAL_PAYMENT_STATES = {"CANCELLED", "VOIDED", "DELETED", "TRASHED"}
SUPPORTED_PAYMENT_TYPES = {"TRANSFER", "EXTERNAL"}


def import_bill_payment(
    settings,
    invoice_name: str,
    bill_id: str,
    payment: dict[str, Any],
    *,
    dry_run: bool = False,
):
    """Mirror one Airwallex bill payment into an ERPNext Payment Entry.

    Airwallex exposes payments inside the full Bill payload. Transfer payments
    are safe to mirror. Card payments are held because the Spend expense and
    card wallet feed own that movement and creating another Payment Entry can
    double-book it. External payments are also held unless an explicit bank
    account is available.

    Re-running on an updated bill is idempotent: an existing Payment Entry is
    left alone when unchanged, updated while still draft, amended when already
    submitted, and cancelled or deleted when the payment disappears.
    """
    payment_id = _payment_id(payment)
    if not payment_id:
        return {"status": "held", "reason": "missing_payment_id", "bill_id": bill_id}
    existing = frappe.db.get_value("Payment Entry", {"custom_airwallex_payment_id": payment_id}, "name")
    if existing:
        return _reconcile_existing_payment(settings, invoice_name, bill_id, payment_id, payment, existing, dry_run=dry_run)
    if not settings.enable_supplier_payments:
        return {"status": "guarded", "id": payment_id}
    payment_type = str(payment.get("type") or "").upper()
    if payment_type == "CARD_TRANSACTION":
        return {"status": "held", "reason": "card_payment_owned_by_spend", "id": payment_id}
    if payment_type not in SUPPORTED_PAYMENT_TYPES:
        return {"status": "held", "reason": f"unsupported_payment_type:{payment_type}", "id": payment_id}

    invoice = frappe.get_doc("Purchase Invoice", invoice_name)
    if invoice.docstatus != 1:
        return {"status": "held", "reason": "purchase_invoice_not_submitted", "id": payment_id}

    built = _build_payment_values(settings, invoice, bill_id, payment)
    if built["status"] != "ok":
        return {**built, "id": payment_id}
    values = built["values"]
    if dry_run:
        return {"status": "would_create", "values": values}
    doc = frappe.get_doc(values).insert(ignore_permissions=True)
    if settings.submit_accounting_documents:
        doc.submit()
    return {"status": "created", "name": doc.name, "id": payment_id, "submitted": bool(doc.docstatus == 1)}


def import_bill_payments(settings, invoice_name: str, bill: dict[str, Any], *, dry_run: bool = False):
    """Reconcile every payment observed on a bill, including withdrawals.

    ``bill_payments`` being absent means the payload did not include payment
    data (for example a partial summary), so nothing is considered withdrawn.
    """
    observations = [payment for payment in (bill.get("bill_payments") or []) if isinstance(payment, dict)]
    results = [
        import_bill_payment(settings, invoice_name, str(bill.get("id") or ""), payment, dry_run=dry_run)
        for payment in observations
    ]
    if "bill_payments" not in bill:
        return {"total": len(results), "results": results}

    observed_ids = {_payment_id(payment) for payment in observations}
    for row in _linked_payment_entries(settings.name, invoice_name):
        payment_id = str(row.custom_airwallex_payment_id or row.reference_no or "")
        if not payment_id or payment_id in observed_ids:
            continue
        if dry_run:
            results.append({"status": "would_remove", "name": row.name, "id": payment_id, "reason": "payment_not_in_bill"})
            continue
        removed = _remove_payment_entry(frappe.get_doc("Payment Entry", row.name))
        results.append({"status": removed, "name": row.name, "id": payment_id, "reason": "payment_not_in_bill"})
    return {"total": len(results), "results": results}


def import_supplier_payment(settings, payment: dict[str, Any], *, dry_run: bool = False):
    """Backward-compatible wrapper for integrations that provide bill_id."""
    bill_id = str(payment.get("bill_id") or "")
    invoice = frappe.db.get_value("Purchase Invoice", {"custom_airwallex_bill_id": bill_id}, "name")
    if not invoice:
        return {"status": "held", "reason": "purchase_invoice_not_found", "id": payment.get("id")}
    return import_bill_payment(settings, invoice, bill_id, payment, dry_run=dry_run)


def _reconcile_existing_payment(settings, invoice_name, bill_id, payment_id, payment, existing, *, dry_run):
    pe = frappe.get_doc("Payment Entry", existing)
    payment_type = str(payment.get("type") or "").upper()
    if str(payment.get("status") or "").upper() in TERMINAL_PAYMENT_STATES:
        return _withdraw_payment(pe, payment_id, dry_run, reason="payment_trashed")
    if payment_type and payment_type not in SUPPORTED_PAYMENT_TYPES:
        return _withdraw_payment(pe, payment_id, dry_run, reason=f"unsupported_payment_type:{payment_type}")

    invoice = frappe.get_doc("Purchase Invoice", invoice_name)
    if invoice.docstatus != 1:
        return {"status": "held", "reason": "purchase_invoice_not_submitted", "id": payment_id}
    built = _build_payment_values(settings, invoice, bill_id, payment, exclude=pe.name)
    if built["status"] != "ok":
        return {**built, "id": payment_id}
    values = built["values"]
    if _payment_entry_matches(pe, values):
        return {"status": "exists", "name": pe.name, "id": payment_id}
    if dry_run:
        return {"status": "would_update", "name": pe.name, "id": payment_id, "values": values}
    if int(pe.docstatus or 0) == 0:
        pe.update({key: value for key, value in values.items() if key != "doctype"})
        pe.save()
        return {"status": "updated", "name": pe.name, "id": payment_id}
    if int(pe.docstatus or 0) == 1:
        return _amend_payment(settings, pe, values, payment_id)
    return {"status": "held", "reason": f"payment_entry_docstatus:{pe.docstatus}", "id": payment_id}


def _withdraw_payment(pe, payment_id, dry_run, *, reason: str):
    if dry_run:
        return {"status": "would_remove", "name": pe.name, "id": payment_id, "reason": reason}
    removed = _remove_payment_entry(pe)
    return {"status": removed, "name": pe.name, "id": payment_id, "reason": reason}


def _remove_payment_entry(pe) -> str:
    docstatus = int(pe.docstatus or 0)
    if docstatus == 0:
        pe.delete()
        return "deleted"
    if docstatus == 1:
        pe.db_set("custom_airwallex_payment_id", None, update_modified=False)
        pe.cancel()
        return "cancelled"
    return "already_cancelled"


def _amend_payment(settings, pe, values, payment_id):
    previous = pe.name
    pe.db_set("custom_airwallex_payment_id", None, update_modified=False)
    pe.cancel()
    amended_values = {**values, "amended_from": previous}
    doc = frappe.get_doc(amended_values).insert(ignore_permissions=True)
    if settings.submit_accounting_documents:
        doc.submit()
    return {"status": "amended", "name": doc.name, "previous": previous, "id": payment_id}


def _build_payment_values(settings, invoice, bill_id: str, payment: dict[str, Any], *, exclude: str | None = None):
    transfer = payment.get("transfer") or {}
    source_currency = str(transfer.get("source_currency") or payment.get("currency") or invoice.currency or settings.default_currency)
    mapping = account_mapping(settings.name, source_currency)
    if not mapping:
        return {"status": "held", "reason": f"missing_account_mapping:{source_currency}"}

    amount = as_money(payment.get("amount") or transfer.get("source_amount") or payment.get("source_amount"))
    if amount <= 0:
        return {"status": "held", "reason": "invalid_payment_amount"}
    posting_date = iso_to_date(transfer.get("transfer_date") or payment.get("created_at") or payment.get("paid_at"))
    company_currency = get_company_currency(invoice.company) or settings.default_currency
    source_rate = resolve_exchange_rate(
        source_currency,
        company_currency,
        posting_date=posting_date,
        payload_rate=payload_rate(payment, transfer, source_currency, company_currency),
    )
    if source_rate is None:
        return {"status": "held", "reason": f"missing_exchange_rate:{source_currency}->{company_currency}"}
    target_currency = _invoice_account_currency(invoice) or str(invoice.currency or company_currency)
    if target_currency.upper() == source_currency.upper():
        target_rate = source_rate
    else:
        target_rate = resolve_exchange_rate(target_currency, company_currency, posting_date=posting_date)
    if target_rate is None:
        return {"status": "held", "reason": f"missing_exchange_rate:{target_currency}->{company_currency}"}
    invoice_currency = str(invoice.currency or company_currency)
    if invoice_currency.upper() == source_currency.upper():
        invoice_rate = source_rate
    else:
        invoice_rate = resolve_exchange_rate(invoice_currency, company_currency, posting_date=posting_date)
    if invoice_rate is None:
        return {"status": "held", "reason": f"missing_exchange_rate:{invoice_currency}->{company_currency}"}

    base_amount = amount * source_rate
    received_amount = as_money(base_amount / target_rate)
    invoice_amount = as_money(base_amount / invoice_rate)
    outstanding = _available_outstanding(settings.name, invoice, exclude=exclude)
    if outstanding <= 0:
        allocated = Decimal(0)
    else:
        allocated = min(invoice_amount, outstanding)
    references = []
    if allocated > 0:
        references.append(
            {
                "reference_doctype": "Purchase Invoice",
                "reference_name": invoice.name,
                "allocated_amount": as_float(allocated),
            }
        )
    values = {
        "doctype": "Payment Entry",
        "payment_type": "Pay",
        "company": invoice.company,
        "posting_date": posting_date,
        "party_type": "Supplier",
        "party": invoice.supplier,
        "paid_from": mapping.ledger_account,
        "paid_amount": as_float(amount),
        "received_amount": as_float(received_amount),
        "source_exchange_rate": as_float(source_rate),
        "target_exchange_rate": as_float(target_rate),
        "reference_no": _payment_id(payment),
        "reference_date": posting_date,
        "custom_airwallex_settings": settings.name,
        "custom_airwallex_payment_id": _payment_id(payment),
        "custom_airwallex_bill_id": bill_id,
        "references": references,
        "remarks": f"Airwallex bill payment for {bill_id}",
    }
    mode_of_payment = _mode_of_payment(payment, transfer)
    if mode_of_payment:
        values["mode_of_payment"] = mode_of_payment
    return {"status": "ok", "values": values}


def _available_outstanding(settings_name: str, invoice, *, exclude: str | None = None) -> Decimal:
    """Amount this payment may still allocate without double-booking.

    ERPNext reduces ``outstanding_amount`` only for submitted Payment Entries,
    so other drafts are subtracted explicitly and the entry being reconciled
    contributes its own submitted allocation back.
    """
    available = as_money(invoice.outstanding_amount or 0)
    for row in _linked_payment_entries(settings_name, invoice.name):
        allocation = _allocation_to_invoice(frappe.get_doc("Payment Entry", row.name), invoice.name)
        if row.name == exclude:
            if int(row.docstatus or 0) == 1:
                available += allocation
            continue
        if int(row.docstatus or 0) == 0:
            available -= allocation
    return available if available > 0 else Decimal(0)


def _allocation_to_invoice(pe, invoice_name: str) -> Decimal:
    total = Decimal(0)
    for ref in pe.get("references") or []:
        if ref.get("reference_doctype") == "Purchase Invoice" and ref.get("reference_name") == invoice_name:
            total += as_money(ref.get("allocated_amount"))
    return total


def _payment_entry_matches(pe, values) -> bool:
    for field in ("paid_amount", "received_amount", "source_exchange_rate", "target_exchange_rate"):
        if as_money(pe.get(field)) != as_money(values.get(field)):
            return False
    if str(pe.get("posting_date") or "") != str(values.get("posting_date") or ""):
        return False
    if str(pe.get("reference_no") or "") != str(values.get("reference_no") or ""):
        return False
    if str(pe.get("mode_of_payment") or "") != str(values.get("mode_of_payment") or ""):
        return False
    references = values.get("references") or []
    expected = as_money(references[0].get("allocated_amount")) if references else Decimal(0)
    actual = Decimal(0)
    for ref in pe.get("references") or []:
        if ref.get("reference_doctype") == "Purchase Invoice":
            actual += as_money(ref.get("allocated_amount"))
    return actual == expected


def _linked_payment_entries(settings_name: str, invoice_name: str):
    parents = frappe.get_all(
        "Payment Entry Reference",
        filters={"reference_doctype": "Purchase Invoice", "reference_name": invoice_name},
        pluck="parent",
        limit=0,
    )
    if not parents:
        return []
    return frappe.get_all(
        "Payment Entry",
        filters={"name": ["in", sorted(set(parents))], "custom_airwallex_settings": settings_name},
        fields=["name", "custom_airwallex_payment_id", "reference_no", "docstatus", "custom_airwallex_bill_id"],
        limit=0,
    )


def _payment_id(payment: dict[str, Any]) -> str:
    transfer = payment.get("transfer") or {}
    card = payment.get("card_transaction") or {}
    return str(payment.get("id") or transfer.get("transfer_id") or card.get("card_transaction_id") or "")


def _mode_of_payment(payment: dict[str, Any], transfer: dict) -> str | None:
    method = str(payment.get("payment_method") or transfer.get("payment_method") or "")
    if method and frappe.db.exists("Mode of Payment", method):
        return method
    return None


def _invoice_account_currency(invoice) -> str | None:
    account = invoice.get("credit_to")
    if not account:
        return None
    currency = frappe.db.get_value("Account", account, "account_currency")
    return str(currency) if currency else None
