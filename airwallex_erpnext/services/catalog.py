from __future__ import annotations

import csv
import io

import frappe


def export_rows(settings_name: str):
    settings = frappe.get_doc("Airwallex Settings", settings_name)
    accounts = frappe.get_all(
        "Account",
        filters={"company": settings.company, "root_type": "Expense", "is_group": 0, "disabled": 0},
        fields=["name", "account_name", "parent_account", "account_currency", "root_type", "account_type"],
        order_by="lft asc",
    )
    cost_centers = frappe.get_all(
        "Cost Center",
        filters={"company": settings.company, "disabled": 0},
        fields=["name", "cost_center_name", "parent_cost_center", "is_group"],
        order_by="lft asc",
    )
    return {
        "expense_accounts": [
            {
                "external_id": row.name,
                "display_name": row.account_name,
                "category_type": "GENERAL_LEDGER_ACCOUNT",
                "parent": row.parent_account,
                "currency": row.account_currency,
            }
            for row in accounts
        ],
        "cost_centers": [
            {
                "external_id": row.name,
                "display_name": row.cost_center_name,
                "category_type": "OTHER",
                "field_name": "Cost Center",
                "parent": row.parent_cost_center,
            }
            for row in cost_centers
        ],
    }


def export_csv(settings_name: str) -> dict[str, str]:
    rows = export_rows(settings_name)
    return {key: _csv(value) for key, value in rows.items()}


def _csv(rows):
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def compare_selections(settings_name: str, resources: list[dict]) -> dict:
    local = export_rows(settings_name)
    known = {row["external_id"] for rows in local.values() for row in rows}
    used = set()
    for resource in resources:
        for selection in resource.get("accounting_field_selections") or []:
            if selection.get("external_id"):
                used.add(selection["external_id"])
        for line in resource.get("line_items") or []:
            for selection in line.get("accounting_field_selections") or []:
                if selection.get("external_id"):
                    used.add(selection["external_id"])
    return {
        "known_external_ids": len(known),
        "used_external_ids": len(used),
        "missing_in_erpnext": sorted(used - known),
        "unused_in_airwallex_sample": sorted(known - used),
    }
