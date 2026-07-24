from __future__ import annotations

from typing import Any

import frappe

from airwallex_erpnext.services.mappings import account_mapping
from airwallex_erpnext.utils import as_float, iso_to_date


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

    currency = str(transfer.get("source_currency") or payment.get("currency") or invoice.currency or settings.default_currency)
    mapping = account_mapping(settings.name, currency)
    if not mapping:
        return {"status": "held", "reason": f"missing_account_mapping:{currency}", "id": payment_id}

    amount = as_float(payment.get("amount") or transfer.get("source_amount") or payment.get("source_amount"))
    if amount <= 0:
        return {"status": "held", "reason": "invalid_payment_amount", "id": payment_id}
    allocated = min(amount, as_float(invoice.outstanding_amount or amount))
    posting_date = iso_to_date(transfer.get("transfer_date") or payment.get("created_at") or payment.get("paid_at"))
    values = {
        "doctype": "Payment Entry",
        "payment_type": "Pay",
        "company": invoice.company,
        "posting_date": posting_date,
        "party_type": "Supplier",
        "party": invoice.supplier,
        "paid_from": mapping.ledger_account,
        "paid_amount": amount,
        "received_amount": amount,
        "source_exchange_rate": 1,
        "target_exchange_rate": 1,
        "reference_no": payment_id,
        "reference_date": posting_date,
        "custom_airwallex_settings": settings.name,
        "custom_airwallex_payment_id": payment_id,
        "references": [{
            "reference_doctype": "Purchase Invoice",
            "reference_name": invoice.name,
            "allocated_amount": allocated,
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
