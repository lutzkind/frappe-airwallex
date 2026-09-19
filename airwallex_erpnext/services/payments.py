from __future__ import annotations

from typing import Any

import frappe

from airwallex_erpnext.services.exchange_rates import get_company_currency, payload_rate, resolve_exchange_rate
from airwallex_erpnext.services.mappings import account_mapping
from airwallex_erpnext.utils import as_float, as_money, iso_to_date


def import_bill_payment(
    settings,
    invoice_name: str,
    bill_id: str,
    payment: dict[str, Any],
    *,
    dry_run: bool = False,
):
    """Create one ERPNext Payment Entry from an Airwallex bill payment.

    Airwallex exposes payments inside the full Bill payload. Transfer payments
    are safe to mirror. Card payments are held because the Spend expense and
    card wallet feed own that movement and creating another Payment Entry can
    double-book it. External payments are also held unless an explicit bank
    account is available.
    """
    payment_type = str(payment.get("type") or "").upper()
    transfer = payment.get("transfer") or {}
    card = payment.get("card_transaction") or {}
    payment_id = str(payment.get("id") or transfer.get("transfer_id") or card.get("card_transaction_id") or "")
    if not payment_id:
        return {"status": "held", "reason": "missing_payment_id", "bill_id": bill_id}
    existing = frappe.db.get_value("Payment Entry", {"custom_airwallex_payment_id": payment_id}, "name")
    if existing:
        return {"status": "exists", "name": existing, "id": payment_id}
    if not settings.enable_supplier_payments:
        return {"status": "guarded", "id": payment_id}
    if payment_type == "CARD_TRANSACTION":
        return {"status": "held", "reason": "card_payment_owned_by_spend", "id": payment_id}
    if payment_type not in {"TRANSFER", "EXTERNAL"}:
        return {"status": "held", "reason": f"unsupported_payment_type:{payment_type}", "id": payment_id}

    invoice = frappe.get_doc("Purchase Invoice", invoice_name)
    if invoice.docstatus != 1:
        return {"status": "held", "reason": "purchase_invoice_not_submitted", "id": payment_id}

    source_currency = str(transfer.get("source_currency") or payment.get("currency") or invoice.currency or settings.default_currency)
    mapping = account_mapping(settings.name, source_currency)
    if not mapping:
        return {"status": "held", "reason": f"missing_account_mapping:{source_currency}", "id": payment_id}

    amount = as_money(payment.get("amount") or transfer.get("source_amount") or payment.get("source_amount"))
    if amount <= 0:
        return {"status": "held", "reason": "invalid_payment_amount", "id": payment_id}
    posting_date = iso_to_date(transfer.get("transfer_date") or payment.get("created_at") or payment.get("paid_at"))
    company_currency = get_company_currency(invoice.company) or settings.default_currency
    source_rate = resolve_exchange_rate(
        source_currency,
        company_currency,
        posting_date=posting_date,
        payload_rate=payload_rate(payment, transfer, source_currency, company_currency),
    )
    if source_rate is None:
        return {"status": "held", "reason": f"missing_exchange_rate:{source_currency}->{company_currency}", "id": payment_id}
    target_currency = _invoice_account_currency(invoice) or str(invoice.currency or company_currency)
    if target_currency.upper() == source_currency.upper():
        target_rate = source_rate
    else:
        target_rate = resolve_exchange_rate(target_currency, company_currency, posting_date=posting_date)
    if target_rate is None:
        return {"status": "held", "reason": f"missing_exchange_rate:{target_currency}->{company_currency}", "id": payment_id}
    invoice_currency = str(invoice.currency or company_currency)
    if invoice_currency.upper() == source_currency.upper():
        invoice_rate = source_rate
    else:
        invoice_rate = resolve_exchange_rate(invoice_currency, company_currency, posting_date=posting_date)
    if invoice_rate is None:
        return {"status": "held", "reason": f"missing_exchange_rate:{invoice_currency}->{company_currency}", "id": payment_id}

    base_amount = amount * source_rate
    received_amount = as_money(base_amount / target_rate)
    invoice_amount = as_money(base_amount / invoice_rate)
    outstanding = as_money(invoice.outstanding_amount or invoice_amount)
    allocated = min(invoice_amount, outstanding)
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
        "reference_no": payment_id,
        "reference_date": posting_date,
        "custom_airwallex_settings": settings.name,
        "custom_airwallex_payment_id": payment_id,
        "references": [{
            "reference_doctype": "Purchase Invoice",
            "reference_name": invoice.name,
            "allocated_amount": as_float(allocated),
        }],
        "remarks": f"Airwallex bill payment for {bill_id}",
    }
    if dry_run:
        return {"status": "would_create", "values": values}
    doc = frappe.get_doc(values).insert(ignore_permissions=True)
    if settings.submit_accounting_documents:
        doc.submit()
    return {"status": "created", "name": doc.name, "id": payment_id, "submitted": bool(doc.docstatus == 1)}


def import_supplier_payment(settings, payment: dict[str, Any], *, dry_run: bool = False):
    """Backward-compatible wrapper for integrations that provide bill_id."""
    bill_id = str(payment.get("bill_id") or "")
    invoice = frappe.db.get_value("Purchase Invoice", {"custom_airwallex_bill_id": bill_id}, "name")
    if not invoice:
        return {"status": "held", "reason": "purchase_invoice_not_found", "id": payment.get("id")}
    return import_bill_payment(settings, invoice, bill_id, payment, dry_run=dry_run)


def import_bill_payments(settings, invoice_name: str, bill: dict[str, Any], *, dry_run: bool = False):
    results = [
        import_bill_payment(settings, invoice_name, str(bill.get("id") or ""), payment, dry_run=dry_run)
        for payment in (bill.get("bill_payments") or [])
        if isinstance(payment, dict)
    ]
    return {"total": len(results), "results": results}


def _invoice_account_currency(invoice) -> str | None:
    account = invoice.get("credit_to")
    if not account:
        return None
    currency = frappe.db.get_value("Account", account, "account_currency")
    return str(currency) if currency else None
