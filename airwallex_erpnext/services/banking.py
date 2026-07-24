from __future__ import annotations

from typing import Any

import frappe

from airwallex_erpnext.constants import CARD_PURCHASE_SOURCE_TYPES, SETTLED_FINANCIAL_STATES
from airwallex_erpnext.services.mappings import account_mapping, resolve
from airwallex_erpnext.utils import as_float, iso_to_date, payload_hash


def import_financial_transaction(settings, item: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    transaction_id = str(item.get("id") or "")
    if not transaction_id:
        return {"status": "held", "reason": "missing_id"}
    if item.get("source_type") in CARD_PURCHASE_SOURCE_TYPES:
        return {"status": "excluded", "reason": "card_purchase_owned_by_spend", "id": transaction_id}
    if settings.settled_only and item.get("status") not in SETTLED_FINANCIAL_STATES:
        return {"status": "held", "reason": "not_settled", "id": transaction_id}

    existing = frappe.db.get_value(
        "Bank Transaction",
        {"custom_airwallex_financial_transaction_id": transaction_id},
        "name",
    )
    if existing:
        return {"status": "exists", "name": existing, "id": transaction_id}

    currency = str(item.get("currency") or settings.default_currency)
    mapping = account_mapping(settings.name, currency)
    if not mapping:
        return {"status": "held", "reason": f"missing_account_mapping:{currency}", "id": transaction_id}

    amount = as_float(item.get("net", item.get("amount", 0)))
    mapped = resolve(settings, "Financial Transaction", item)
    values = {
        "doctype": "Bank Transaction",
        "date": iso_to_date(item.get("settled_at") or item.get("created_at")),
        "bank_account": mapping.bank_account,
        "currency": currency,
        "deposit": amount if amount > 0 else 0,
        "withdrawal": abs(amount) if amount < 0 else 0,
        "description": item.get("description") or f"Airwallex {item.get('transaction_type') or item.get('source_type') or 'transaction'}",
        "reference_number": item.get("source_id") or transaction_id,
        "custom_airwallex_settings": settings.name,
        "custom_airwallex_financial_transaction_id": transaction_id,
        "custom_airwallex_source_id": item.get("source_id"),
        "custom_airwallex_source_type": item.get("source_type"),
        "custom_airwallex_transaction_type": item.get("transaction_type"),
        "custom_airwallex_batch_id": item.get("batch_id"),
        "custom_airwallex_business": mapped.business_unit,
        "custom_airwallex_cost_center": mapped.cost_center,
        "custom_airwallex_expense_account": mapped.expense_account,
        "custom_airwallex_raw_hash": payload_hash(item),
    }
    if dry_run:
        return {"status": "would_create", "values": values}
    doc = frappe.get_doc(values)
    doc.insert(ignore_permissions=True)
    return {"status": "created", "name": doc.name, "id": transaction_id}


def sync_financial_transactions(settings, client, *, from_created_at: str, max_items: int, dry_run: bool = False):
    results = []
    for item in client.paginate_numbered(
        "/api/v1/financial_transactions",
        params={"from_created_at": from_created_at},
        max_items=max_items,
    ):
        results.append(import_financial_transaction(settings, item, dry_run=dry_run))
    return _summary(results)


def _summary(results):
    counts = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    return {"counts": counts, "results": results[:100], "total": len(results)}
