from __future__ import annotations

import frappe

from airwallex_erpnext.utils import payload_hash


def create_purchase_credit_note(settings, original_invoice: str, source_id: str, amount: float, posting_date: str, *, dry_run=False):
    existing = frappe.db.get_value("Purchase Invoice", {"return_against": original_invoice, "custom_airwallex_expense_id": source_id}, "name")
    if existing:
        return {"status": "exists", "name": existing}
    source = frappe.get_doc("Purchase Invoice", original_invoice)
    values = {
        "doctype": "Purchase Invoice",
        "is_return": 1,
        "return_against": source.name,
        "company": source.company,
        "supplier": source.supplier,
        "posting_date": posting_date,
        "bill_no": f"AWX-RETURN-{source_id}",
        "custom_airwallex_settings": settings.name,
        "custom_airwallex_expense_id": source_id,
        "custom_airwallex_raw_hash": payload_hash({"source_id": source_id, "amount": amount}),
        "items": [],
    }
    for row in source.items:
        values["items"].append(
            {
                "item_code": row.item_code,
                "item_name": row.item_name,
                "description": row.description,
                "qty": -abs(row.qty),
                "rate": row.rate,
                "expense_account": row.expense_account,
                "cost_center": row.cost_center,
                "project": row.project,
            }
        )
    if dry_run:
        return {"status": "would_create", "values": values}
    doc = frappe.get_doc(values).insert(ignore_permissions=True)
    if settings.submit_accounting_documents:
        doc.submit()
    return {"status": "created", "name": doc.name}
