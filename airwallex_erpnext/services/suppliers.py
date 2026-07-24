from __future__ import annotations

import frappe

from airwallex_erpnext.utils import normalize_merchant


def resolve_supplier(settings, merchant: str | None, explicit_supplier: str | None = None) -> str | None:
    if explicit_supplier:
        return explicit_supplier
    normalized = normalize_merchant(merchant)
    if not normalized:
        return None

    alias = frappe.db.get_value(
        "Airwallex Merchant Alias",
        {"settings": settings.name, "normalized_alias": normalized, "enabled": 1},
        "supplier",
    )
    if alias:
        return alias

    exact = frappe.db.get_value("Supplier", {"supplier_name": merchant}, "name")
    if exact:
        _remember(settings.name, merchant, normalized, exact)
        return exact

    if not settings.create_suppliers:
        return None

    supplier = frappe.get_doc(
        {
            "doctype": "Supplier",
            "supplier_name": merchant or "Unknown Airwallex Merchant",
            "supplier_group": settings.supplier_group or "All Supplier Groups",
            "supplier_type": "Company",
        }
    )
    supplier.insert(ignore_permissions=True)
    _remember(settings.name, merchant, normalized, supplier.name)
    return supplier.name


def _remember(settings: str, alias: str, normalized: str, supplier: str):
    if frappe.db.exists("Airwallex Merchant Alias", {"settings": settings, "normalized_alias": normalized}):
        return
    frappe.get_doc(
        {
            "doctype": "Airwallex Merchant Alias",
            "settings": settings,
            "alias": alias,
            "normalized_alias": normalized,
            "supplier": supplier,
            "enabled": 1,
            "confirmed": 1,
        }
    ).insert(ignore_permissions=True)
