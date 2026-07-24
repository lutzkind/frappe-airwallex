from __future__ import annotations

from typing import Any

import frappe


def sync_balances(settings, client, *, provision_missing: bool = False) -> dict[str, Any]:
    payload = client.request("GET", "/api/v1/balances/current")
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("available_amount") or payload.get("balances") or payload.get("items") or []
    else:
        items = []
    if isinstance(items, dict):
        items = [{"currency": currency, "amount": amount} for currency, amount in items.items()]
    results = []
    for item in items:
        currency = str(item.get("currency") or "")
        if not currency:
            continue
        name = frappe.db.get_value("Airwallex Account Mapping", {"settings": settings.name, "currency": currency}, "name")
        if not name and provision_missing:
            name = provision_mapping(settings, currency)
        if name:
            frappe.db.set_value(
                "Airwallex Account Mapping",
                name,
                {
                    "last_balance": item.get("amount") or item.get("available_amount") or item.get("balance"),
                    "last_balance_at": frappe.utils.now_datetime(),
                },
                update_modified=False,
            )
            results.append({"currency": currency, "mapping": name, "status": "updated"})
        else:
            results.append({"currency": currency, "status": "missing_mapping"})
    return {"balances": results}


def provision_mapping(settings, currency: str) -> str:
    if not settings.auto_provision_currency_accounts:
        raise ValueError(f"No mapping exists for {currency} and automatic provisioning is disabled")

    company_abbr = frappe.db.get_value("Company", settings.company, "abbr")
    parent = frappe.db.get_value(
        "Account",
        {"company": settings.company, "root_type": "Asset", "account_type": "Bank", "is_group": 1},
        "name",
    )
    if not parent:
        parent = frappe.db.get_value("Account", {"company": settings.company, "root_type": "Asset", "is_group": 1}, "name")
    account_name = f"Airwallex {currency}"
    ledger = frappe.db.get_value("Account", {"company": settings.company, "account_name": account_name}, "name")
    if not ledger:
        ledger = frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": account_name,
                "parent_account": parent,
                "company": settings.company,
                "account_type": "Bank",
                "account_currency": currency,
                "is_group": 0,
            }
        ).insert(ignore_permissions=True).name

    bank = frappe.db.get_value("Bank", "Airwallex", "name")
    if not bank:
        bank = frappe.get_doc({"doctype": "Bank", "bank_name": "Airwallex"}).insert(ignore_permissions=True).name
    bank_account_name = f"Airwallex {currency}"
    bank_account = frappe.db.get_value(
        "Bank Account",
        {"account_name": bank_account_name, "company": settings.company},
        "name",
    )
    if not bank_account:
        bank_account = frappe.get_doc(
            {
                "doctype": "Bank Account",
                "account_name": bank_account_name,
                "bank": bank,
                "company": settings.company,
                "account": ledger,
                "is_company_account": 1,
            }
        ).insert(ignore_permissions=True).name

    mapping = frappe.get_doc(
        {
            "doctype": "Airwallex Account Mapping",
            "settings": settings.name,
            "enabled": 1,
            "currency": currency,
            "account_id": settings.account_id,
            "ledger_account": ledger,
            "bank_account": bank_account,
            "opening_sync_date": settings.sync_start_date,
        }
    ).insert(ignore_permissions=True)
    return mapping.name
