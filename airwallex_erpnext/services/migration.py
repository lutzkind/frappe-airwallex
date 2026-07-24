from __future__ import annotations

from typing import Any

import frappe


def adopt_legacy_records(settings_name: str, *, dry_run: bool = True) -> dict[str, Any]:
    settings = frappe.get_doc("Airwallex Settings", settings_name)
    expenses = frappe.get_all(
        "Bank Transaction",
        filters={"custom_airwallex_expense_id": ["!=", ""]},
        fields=["name", "custom_airwallex_expense_id", "custom_airwallex_settings"],
        limit_page_length=0,
    )
    financial = frappe.get_all(
        "Bank Transaction",
        filters={"custom_airwallex_financial_transaction_id": ["!=", ""]},
        fields=["name", "custom_airwallex_financial_transaction_id", "custom_airwallex_settings"],
        limit_page_length=0,
    )
    updates = []
    for row in [*expenses, *financial]:
        if row.custom_airwallex_settings == settings.name:
            continue
        updates.append(row.name)
        if not dry_run:
            frappe.db.set_value("Bank Transaction", row.name, "custom_airwallex_settings", settings.name, update_modified=False)

    files = frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Bank Transaction", "is_private": 1},
        fields=["name", "attached_to_name", "content_hash"],
        limit_page_length=0,
    )
    report = {
        "settings": settings.name,
        "expense_bank_transactions": len(expenses),
        "financial_bank_transactions": len(financial),
        "records_to_adopt": len(updates),
        "private_files_seen": len(files),
        "dry_run": dry_run,
    }
    if not dry_run:
        frappe.db.commit()
    return report
