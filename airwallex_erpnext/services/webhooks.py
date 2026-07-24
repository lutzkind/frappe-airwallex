from __future__ import annotations

import json
from typing import Any

import frappe

from airwallex_erpnext.services.bills import import_bill
from airwallex_erpnext.services.expenses import import_expense
from airwallex_erpnext.services.reimbursements import import_reimbursement
from airwallex_erpnext.frappe_support import get_client
from airwallex_erpnext.utils import payload_hash


def store_event(settings: str, payload: dict[str, Any], raw_payload: str, timestamp: str, signature: str):
    event_id = str(payload.get("id") or payload_hash(payload))
    existing = frappe.db.get_value("Airwallex Webhook Event", {"event_id": event_id}, "name")
    if existing:
        doc = frappe.get_doc("Airwallex Webhook Event", existing)
        doc.db_set("duplicate_event", 1, update_modified=False)
        doc.duplicate_event = 1
        return doc

    return frappe.get_doc(
        {
            "doctype": "Airwallex Webhook Event",
            "settings": settings,
            "event_id": event_id,
            "event_name": payload.get("name") or payload.get("type"),
            "event_created_at": payload.get("created_at"),
            "api_version": payload.get("version"),
            "account_id": (payload.get("data") or {}).get("account_id") or payload.get("account_id") or payload.get("org_id"),
            "status": "Received",
            "attempts": 0,
            "raw_payload": raw_payload,
            "payload_hash": payload_hash(payload),
            "received_timestamp": timestamp,
            "signature_prefix": signature[:12],
        }
    ).insert(ignore_permissions=True)


def process_event(event_name: str):
    event = frappe.get_doc("Airwallex Webhook Event", event_name)
    if event.status in {"Processed", "Ignored"}:
        return {"status": event.status}
    event.db_set("status", "Processing", update_modified=False)
    event.db_set("attempts", int(event.attempts or 0) + 1, update_modified=False)

    settings = frappe.get_doc("Airwallex Settings", event.settings)
    client = get_client(settings)
    payload = json.loads(event.raw_payload)
    name = str(event.event_name or "")
    data = payload.get("data") or {}

    try:
        if name.startswith("spend.expense."):
            result = import_expense(settings, client, data)
        elif name.startswith("spend.bill."):
            result = import_bill(settings, client, data)
        elif name.startswith("spend.reimbursement_report."):
            result = import_reimbursement(settings, client, data)
        else:
            result = {"status": "ignored", "reason": "unsupported_event"}
        event.db_set("status", "Ignored" if result.get("status") == "ignored" else "Processed", update_modified=False)
        event.db_set("processed_at", frappe.utils.now_datetime(), update_modified=False)
        event.db_set("result_json", frappe.as_json(result), update_modified=False)
        return result
    except Exception as exc:
        retry = int(event.attempts or 0) < int(settings.webhook_max_attempts or 5)
        event.db_set("status", "Retrying" if retry else "Dead Letter", update_modified=False)
        event.db_set("last_error", f"{type(exc).__name__}: {str(exc)[:2000]}", update_modified=False)
        # The five-minute queue scheduler retries records in Retrying state.
        # Avoid in-request sleep or unsupported delayed job semantics.
        raise
