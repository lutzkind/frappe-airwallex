from __future__ import annotations

from typing import Any

import frappe

from airwallex_erpnext.constants import BILL_APPROVED_STATES
from airwallex_erpnext.services.mappings import resolve
from airwallex_erpnext.services.payments import import_bill_payments
from airwallex_erpnext.services.receipts import attach_airwallex_receipts
from airwallex_erpnext.services.suppliers import resolve_supplier
from airwallex_erpnext.utils import as_float, iso_to_date, payload_hash


def import_bill(settings, client, bill: dict[str, Any], *, dry_run: bool = False):
    bill_id = str(bill.get("id") or "")
    if not bill_id:
        return {"status": "held", "reason": "missing_id"}
    existing = frappe.db.get_value("Purchase Invoice", {"custom_airwallex_bill_id": bill_id}, "name")
    if existing:
        return {"status": "exists", "name": existing, "id": bill_id}
    if bill.get("status") not in BILL_APPROVED_STATES:
        return {"status": "held", "reason": f"bill_status:{bill.get('status')}", "id": bill_id}
    if not settings.enable_bills or not settings.create_accounting_documents:
        return {"status": "guarded", "id": bill_id}

    mapped = resolve(settings, "Bill", bill)
    vendor = bill.get("vendor") or {}
    supplier = resolve_supplier(settings, vendor.get("name") or bill.get("vendor_name"), mapped.supplier)
    if not supplier:
        return {"status": "held", "reason": "supplier_mapping_required", "id": bill_id}

    line_items = bill.get("line_items") or []
    items = []
    for line in line_items:
        account = mapped.expense_account
        items.append(
            {
                "item_name": line.get("description") or vendor.get("name") or "Airwallex bill",
                "description": line.get("description") or "Airwallex bill line",
                "qty": as_float(line.get("quantity") or 1),
                "rate": as_float(line.get("unit_price") or line.get("amount") or 0),
                "expense_account": account,
                "cost_center": mapped.cost_center,
                "project": mapped.project,
            }
        )
    if not items:
        items = [{
            "item_name": vendor.get("name") or "Airwallex bill",
            "description": bill.get("description") or "Airwallex bill",
            "qty": 1,
            "rate": as_float(bill.get("amount") or bill.get("total_amount") or 0),
            "expense_account": mapped.expense_account,
            "cost_center": mapped.cost_center,
            "project": mapped.project,
        }]

    values = {
        "doctype": "Purchase Invoice",
        "company": mapped.company or settings.company,
        "supplier": supplier,
        "posting_date": iso_to_date(bill.get("invoice_date") or bill.get("created_at")),
        "due_date": iso_to_date(bill.get("due_date")),
        "bill_no": bill.get("invoice_number") or f"AWX-BILL-{bill_id}",
        "bill_date": iso_to_date(bill.get("invoice_date") or bill.get("created_at")),
        "currency": bill.get("currency") or settings.default_currency,
        "custom_airwallex_settings": settings.name,
        "custom_airwallex_bill_id": bill_id,
        "custom_airwallex_business": mapped.business_unit,
        "custom_airwallex_sync_status": bill.get("sync_status"),
        "custom_airwallex_raw_hash": payload_hash(bill),
        "items": items,
    }
    if dry_run:
        return {"status": "would_create", "values": values}

    doc = frappe.get_doc(values).insert(ignore_permissions=True)
    if settings.submit_accounting_documents:
        doc.submit()
    attach_airwallex_receipts(settings, client, bill, "Purchase Invoice", doc.name)
    payments = import_bill_payments(settings, doc.name, bill, dry_run=False)
    if settings.mark_bills_synced:
        client.request("POST", f"/api/v1/spend/bills/{bill_id}/sync", body={"sync_status": "SYNCED"})
    return {"status": "created", "name": doc.name, "id": bill_id, "payments": payments}


def sync_bills(settings, client, *, from_created_at: str, max_items: int, dry_run: bool = False):
    results = []
    for summary in client.paginate_bookmark(
        "/api/v1/spend/bills",
        params={"from_created_at": from_created_at},
        max_items=max_items,
    ):
        bill_id = summary.get("id")
        bill = client.request("GET", f"/api/v1/spend/bills/{bill_id}") if bill_id else summary
        results.append(import_bill(settings, client, bill, dry_run=dry_run))
    return {"total": len(results), "results": results[:100]}
