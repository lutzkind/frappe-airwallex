from __future__ import annotations

import json

import frappe

from airwallex_erpnext.security import verify_webhook_signature
from airwallex_erpnext.services.compatibility import ingest_receipt
from airwallex_erpnext.services.sync import run_sync
from airwallex_erpnext.services.webhooks import store_event


@frappe.whitelist()
def discover_capabilities(settings: str):
    frappe.only_for(("System Manager", "Airwallex Administrator"))
    from airwallex_erpnext.services.capabilities import discover

    return discover(settings)


@frappe.whitelist()
def sync_now(settings: str, module: str = "all", dry_run: int = 0):
    frappe.only_for(("System Manager", "Airwallex Administrator", "Airwallex Accountant"))
    return run_sync(settings, module=module, dry_run=bool(int(dry_run)))


@frappe.whitelist()
def webhook_status(settings: str):
    frappe.only_for(("System Manager", "Airwallex Administrator"))
    from airwallex_erpnext.services.webhook_management import inspect_subscription

    return inspect_subscription(settings)


@frappe.whitelist()
def ensure_webhook_subscription(settings: str):
    frappe.only_for(("System Manager", "Airwallex Administrator"))
    from airwallex_erpnext.services.webhook_management import ensure_subscription

    return ensure_subscription(settings)


@frappe.whitelist()
def remove_webhook_subscription(settings: str):
    frappe.only_for(("System Manager", "Airwallex Administrator"))
    from airwallex_erpnext.services.webhook_management import remove_subscription

    return remove_subscription(settings)


@frappe.whitelist(allow_guest=True)
def webhook():
    request = frappe.request
    raw = request.get_data(cache=False) or b""
    timestamp = request.headers.get("x-timestamp", "")
    signature = request.headers.get("x-signature", "")

    # Verify the original bytes before JSON parsing. Each Airwallex webhook URL has
    # its own secret; for multi-connection sites we try enabled connections until
    # one validates. A failed request is never parsed or persisted.
    settings = _verify_against_enabled_connections(raw, timestamp, signature)
    try:
        preview = json.loads(raw.decode("utf-8"))
    except Exception:
        frappe.local.response.http_status_code = 400
        return {"ok": False, "error": "invalid_json"}

    event = store_event(settings.name, preview, raw.decode("utf-8"), timestamp, signature)
    frappe.enqueue(
        "airwallex_erpnext.services.webhooks.process_event",
        queue="short",
        event_name=event.name,
        enqueue_after_commit=True,
        job_name=f"airwallex-webhook-{event.name}",
    )
    return {"ok": True, "event": event.name, "duplicate": bool(event.duplicate_event)}


@frappe.whitelist(allow_guest=True)
def ingest_compatibility_receipt():
    payload = frappe.request.get_json(silent=True) or {}
    settings_name = str(payload.get("settings") or "")
    if not settings_name:
        frappe.throw("settings is required")
    settings = frappe.get_doc("Airwallex Settings", settings_name)
    supplied = frappe.request.headers.get("x-airwallex-compatibility-secret", "")
    expected = settings.get_password("compatibility_secret", raise_exception=False)
    import hmac

    if not expected or not hmac.compare_digest(str(supplied), str(expected)):
        frappe.local.response.http_status_code = 401
        return {"ok": False, "error": "unauthorized"}
    return ingest_receipt(settings, payload)


@frappe.whitelist()
def migration_report(settings: str, apply: int = 0):
    frappe.only_for(("System Manager", "Airwallex Administrator"))
    from airwallex_erpnext.services.migration import adopt_legacy_records

    return adopt_legacy_records(settings, dry_run=not bool(int(apply)))


@frappe.whitelist()
def export_accounting_catalog(settings: str):
    frappe.only_for(("System Manager", "Airwallex Administrator", "Airwallex Accountant"))
    from airwallex_erpnext.services.catalog import export_csv

    return export_csv(settings)


@frappe.whitelist()
def propose_reconciliation(bank_transaction: str):
    frappe.only_for(("System Manager", "Airwallex Administrator", "Airwallex Accountant", "Airwallex Reviewer"))
    from airwallex_erpnext.services.reconciliation import propose_for_bank_transaction

    return [candidate.__dict__ for candidate in propose_for_bank_transaction(bank_transaction)]


def _verify_against_enabled_connections(raw: bytes, timestamp: str, signature: str):
    settings_names = frappe.get_all(
        "Airwallex Settings",
        filters={"enabled": 1},
        pluck="name",
        limit_page_length=0,
    )
    for name in settings_names:
        settings = frappe.get_doc("Airwallex Settings", name)
        secret = settings.get_password("webhook_secret", raise_exception=False)
        if not secret:
            continue
        try:
            verify_webhook_signature(
                raw_body=raw,
                timestamp=timestamp,
                signature=signature,
                secret=secret,
                tolerance_seconds=int(settings.webhook_tolerance_seconds or 300),
            )
            return settings
        except Exception:
            continue
    frappe.local.response.http_status_code = 401
    frappe.throw("Invalid Airwallex webhook signature", frappe.AuthenticationError)
