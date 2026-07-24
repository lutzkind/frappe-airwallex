from __future__ import annotations

from typing import Any

import frappe

from airwallex_erpnext.rules import resolve_rules


def get_rule_rows(settings_name: str, resource_type: str) -> list[dict[str, Any]]:
    return frappe.get_all(
        "Airwallex Mapping Rule",
        filters={"settings": settings_name, "enabled": 1, "resource_type": ["in", [resource_type, "Any"]]},
        fields=[
            "name", "priority", "enabled", "resource_type", "match_field", "operator", "match_value",
            "company", "cost_center", "project", "expense_account", "supplier", "tax_template",
            "item_code", "business_unit", "stop_processing",
        ],
        order_by="priority asc, name asc",
    )


def resolve(settings, resource_type: str, record: dict[str, Any]):
    defaults = {
        "company": settings.company,
        "cost_center": settings.default_cost_center,
        "expense_account": settings.default_expense_account,
        "business_unit": settings.default_business_unit,
    }
    return resolve_rules(get_rule_rows(settings.name, resource_type), record, defaults)


def account_mapping(settings_name: str, currency: str):
    name = frappe.db.get_value(
        "Airwallex Account Mapping",
        {"settings": settings_name, "currency": currency, "enabled": 1},
        "name",
    )
    if not name:
        return None
    return frappe.get_doc("Airwallex Account Mapping", name)
