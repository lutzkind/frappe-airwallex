from __future__ import annotations

from typing import Any

import frappe

from airwallex_erpnext.services.receipts import attach_compatibility_content


def ingest_receipt(settings, payload: dict[str, Any]):
    expense_id = str(payload.get("expense_id") or "")
    if not expense_id:
        frappe.throw("expense_id is required")
    bank_transaction = frappe.db.get_value("Bank Transaction", {"custom_airwallex_expense_id": expense_id}, "name")
    if not bank_transaction:
        frappe.throw(f"No Bank Transaction found for Airwallex expense {expense_id}")

    files = payload.get("files") or []
    results = []
    for file in files:
        results.append(
            attach_compatibility_content(
                doctype="Bank Transaction",
                docname=bank_transaction,
                file_name=file["file_name"],
                content_b64=file["content_base64"],
                attachment_id=file.get("attachment_id"),
                source_message_id=payload.get("source_message_id"),
            )
        )

    state = "attached" if any(r["status"] in {"attached", "exists"} for r in results) else "missing"
    frappe.db.set_value("Bank Transaction", bank_transaction, "custom_airwallex_receipt_state", state, update_modified=False)
    match = frappe.get_doc(
        {
            "doctype": "Airwallex Receipt Match",
            "settings": settings.name,
            "expense_id": expense_id,
            "bank_transaction": bank_transaction,
            "source_provider": "Windmill",
            "source_message_id": payload.get("source_message_id"),
            "confidence": payload.get("confidence"),
            "status": "Attached" if state == "attached" else "Held",
            "details": frappe.as_json({"files": results}),
        }
    )
    match.insert(ignore_permissions=True)
    return {"ok": True, "bank_transaction": bank_transaction, "files": results, "receipt_match": match.name}
