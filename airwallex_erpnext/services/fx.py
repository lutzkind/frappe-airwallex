from __future__ import annotations

from collections import defaultdict
from typing import Any

try:
    import frappe
except ImportError:  # pragma: no cover
    frappe = None  # type: ignore

from airwallex_erpnext.utils import as_float, iso_to_date, payload_hash


def group_conversions(transactions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in transactions:
        if item.get("source_type") == "CONVERSION" and item.get("source_id"):
            groups[str(item["source_id"])].append(item)
    return dict(groups)


def import_conversion(settings, source_id: str, legs: list[dict[str, Any]], *, dry_run: bool = False):
    from airwallex_erpnext.services.mappings import account_mapping
    existing = frappe.db.get_value("Journal Entry", {"custom_airwallex_conversion_id": source_id}, "name")
    if existing:
        return {"status": "exists", "name": existing, "id": source_id}
    if len(legs) != 2:
        return {"status": "held", "reason": f"expected_2_legs_got_{len(legs)}", "id": source_id}
    if not settings.enable_fx_journals:
        return {"status": "guarded", "id": source_id}

    accounts = []
    for leg in legs:
        mapping = account_mapping(settings.name, str(leg.get("currency")))
        if not mapping:
            return {"status": "held", "reason": f"missing_account_mapping:{leg.get('currency')}", "id": source_id}
        amount = as_float(leg.get("net", leg.get("amount", 0)))
        row = {
            "account": mapping.ledger_account,
            "account_currency": leg.get("currency"),
            "exchange_rate": float(leg.get("client_rate") or 1),
            "debit_in_account_currency": amount if amount > 0 else 0,
            "credit_in_account_currency": abs(amount) if amount < 0 else 0,
            "cost_center": settings.default_cost_center,
        }
        accounts.append(row)

    values = {
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "company": settings.company,
        "posting_date": iso_to_date(legs[0].get("settled_at") or legs[0].get("created_at")),
        "user_remark": f"Airwallex FX conversion {source_id}",
        "custom_airwallex_settings": settings.name,
        "custom_airwallex_conversion_id": source_id,
        "custom_airwallex_raw_hash": payload_hash(legs),
        "accounts": accounts,
    }
    if dry_run:
        return {"status": "would_create", "values": values}
    doc = frappe.get_doc(values).insert(ignore_permissions=True)
    if settings.submit_accounting_documents:
        doc.submit()
    return {"status": "created", "name": doc.name, "id": source_id}


def sync_fx(settings, client, *, from_created_at: str, max_items: int, dry_run: bool = False):
    transactions = list(
        client.paginate_numbered(
            "/api/v1/financial_transactions",
            params={"from_created_at": from_created_at, "status": "SETTLED"},
            max_items=max_items,
        )
    )
    results = [
        import_conversion(settings, source_id, legs, dry_run=dry_run)
        for source_id, legs in group_conversions(transactions).items()
    ]
    return {"total": len(results), "results": results[:100]}
