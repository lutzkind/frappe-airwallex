from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import frappe

from airwallex_erpnext.frappe_support import get_client, get_settings, log_sync
from airwallex_erpnext.services.balances import sync_balances
from airwallex_erpnext.services.banking import sync_financial_transactions
from airwallex_erpnext.services.bills import sync_bills
from airwallex_erpnext.services.expenses import sync_expenses
from airwallex_erpnext.services.fx import sync_fx
from airwallex_erpnext.services.reimbursements import sync_reimbursements
from airwallex_erpnext.services.transfers import sync_transfers


def run_sync(settings_name: str, module: str = "all", dry_run: bool = False) -> dict[str, Any]:
    settings = get_settings(settings_name)
    if not settings.enabled:
        return {"ok": False, "status": "disabled", "settings": settings.name}
    client = get_client(settings)
    log = log_sync(settings.name, module, "Running")
    from_created_at = _start_time(settings, module)
    max_items = int(settings.max_records_per_sync or 5000)
    results: dict[str, Any] = {}

    try:
        modules = _modules(module)
        if "banking" in modules and settings.enable_banking:
            results["balances"] = sync_balances(settings, client, provision_missing=bool(settings.auto_provision_currency_accounts and not dry_run))
            results["banking"] = sync_financial_transactions(settings, client, from_created_at=from_created_at, max_items=max_items, dry_run=dry_run)
        if "expenses" in modules and settings.enable_expenses:
            results["expenses"] = sync_expenses(settings, client, from_created_at=from_created_at, max_items=max_items, dry_run=dry_run)
        if "bills" in modules and settings.enable_bills:
            results["bills"] = sync_bills(settings, client, from_created_at=from_created_at, max_items=max_items, dry_run=dry_run)
        if "reimbursements" in modules and settings.enable_reimbursements:
            results["reimbursements"] = sync_reimbursements(settings, client, from_created_at=from_created_at, max_items=max_items, dry_run=dry_run)
        if "fx" in modules and settings.enable_fx:
            results["fx"] = sync_fx(settings, client, from_created_at=from_created_at, max_items=max_items, dry_run=dry_run)
        if "transfers" in modules and settings.enable_transfers:
            results["transfers"] = sync_transfers(settings, client, from_created_at=from_created_at, max_items=max_items, dry_run=dry_run)

        if not dry_run:
            settings.db_set("last_successful_sync", frappe.utils.now_datetime(), update_modified=False)
        log.db_set("status", "Success", update_modified=False)
        log.db_set("finished_at", frappe.utils.now_datetime(), update_modified=False)
        log.db_set("result_json", frappe.as_json(results), update_modified=False)
        return {"ok": True, "settings": settings.name, "module": module, "dry_run": dry_run, "results": results}
    except Exception as exc:
        log.db_set("status", "Failed", update_modified=False)
        log.db_set("finished_at", frappe.utils.now_datetime(), update_modified=False)
        log.db_set("error", f"{type(exc).__name__}: {str(exc)[:5000]}", update_modified=False)
        raise


def _start_time(settings, module: str) -> str:
    now = datetime.now(UTC)
    if module in {"incremental", "all"} and settings.last_successful_sync:
        start = settings.last_successful_sync - timedelta(hours=int(settings.overlap_hours or 24))
    elif settings.sync_start_date:
        start = datetime.combine(settings.sync_start_date, datetime.min.time(), tzinfo=UTC)
    else:
        start = now - timedelta(days=30)
    return start.isoformat().replace("+00:00", "Z")


def _modules(module: str) -> set[str]:
    if module in {"all", "incremental"}:
        return {"banking", "expenses", "bills", "reimbursements", "fx", "transfers"}
    aliases = {
        "wallet": "banking",
        "financial_transactions": "banking",
        "spend": "expenses",
        "supplier_payments": "bills",
        "payments": "bills",
    }
    return {aliases.get(module, module)}
