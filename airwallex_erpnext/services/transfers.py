from __future__ import annotations

from typing import Any

import frappe

from airwallex_erpnext.services.mappings import account_mapping
from airwallex_erpnext.utils import as_float, iso_to_date


def import_transfer(settings, transfer: dict[str, Any], *, dry_run: bool = False):
    transfer_id = str(transfer.get("id") or "")
    if not transfer_id:
        return {"status": "held", "reason": "missing_id"}
    existing = frappe.db.get_value("Payment Entry", {"custom_airwallex_payment_id": transfer_id}, "name")
    if existing:
        return {"status": "exists", "name": existing, "id": transfer_id}
    if not settings.enable_transfers or not settings.create_accounting_documents:
        return {"status": "guarded", "id": transfer_id}

    source_currency = transfer.get("source_currency") or settings.default_currency
    mapping = account_mapping(settings.name, source_currency)
    if not mapping:
        return {"status": "held", "reason": f"missing_account_mapping:{source_currency}", "id": transfer_id}
    amount = as_float(transfer.get("amount_payer_pays") or transfer.get("source_amount") or transfer.get("transfer_amount"))
    beneficiary = transfer.get("beneficiary") or {}
    supplier = frappe.db.get_value("Supplier", {"supplier_name": beneficiary.get("name") or transfer.get("beneficiary_name")}, "name")
    if not supplier:
        return {"status": "held", "reason": "supplier_mapping_required", "id": transfer_id}
    values = {
        "doctype": "Payment Entry",
        "payment_type": "Pay",
        "company": settings.company,
        "posting_date": iso_to_date(transfer.get("created_at")),
        "party_type": "Supplier",
        "party": supplier,
        "paid_from": mapping.ledger_account,
        "paid_amount": amount,
        "received_amount": amount,
        "source_exchange_rate": 1,
        "target_exchange_rate": 1,
        "reference_no": transfer_id,
        "reference_date": iso_to_date(transfer.get("created_at")),
        "custom_airwallex_settings": settings.name,
        "custom_airwallex_payment_id": transfer_id,
        "remarks": f"Airwallex transfer {transfer_id}",
    }
    if dry_run:
        return {"status": "would_create", "values": values}
    doc = frappe.get_doc(values).insert(ignore_permissions=True)
    if settings.submit_accounting_documents:
        doc.submit()
    return {"status": "created", "name": doc.name, "id": transfer_id}


def sync_transfers(settings, client, *, from_created_at: str, max_items: int, dry_run: bool = False):
    results = []
    for transfer in client.paginate_bookmark(
        "/api/v1/transfers",
        params={"from_created_at": from_created_at},
        max_items=max_items,
    ):
        results.append(import_transfer(settings, transfer, dry_run=dry_run))
    return {"total": len(results), "results": results[:100]}
