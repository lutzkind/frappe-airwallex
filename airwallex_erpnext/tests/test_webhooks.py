from __future__ import annotations

import json

import frappe
import pytest

from airwallex_erpnext.services.webhooks import process_event, store_event
from airwallex_erpnext.tests import fixtures
from airwallex_erpnext.tests.fixtures import webhook_payload


def store(settings, payload):
    raw = json.dumps(payload)
    return store_event(settings.name, payload, raw, "1700000000000", "signature")


def test_store_event_recognizes_duplicate_delivery():
    settings = fixtures.insert_settings()
    payload = webhook_payload()

    first = store(settings, payload)
    second = store(settings, payload)

    assert first.name == second.name
    assert second.duplicate_event == 1
    assert len(frappe.get_all("Airwallex Webhook Event", pluck="name")) == 1


def test_process_event_ignores_unsupported_event_and_is_idempotent():
    settings = fixtures.insert_settings()
    event = store(settings, webhook_payload(name="wallet.transaction.created"))

    result = process_event(event.name)

    assert result == {"status": "ignored", "reason": "unsupported_event"}
    processed = frappe.get_doc("Airwallex Webhook Event", event.name)
    assert processed.status == "Ignored"
    assert process_event(event.name) == {"status": "Ignored"}
    assert frappe.get_doc("Airwallex Webhook Event", event.name).attempts == 1


def test_process_event_retries_after_crash_without_duplicating(monkeypatch, no_receipts):
    settings = fixtures.insert_settings()
    fixtures.insert_company()
    fixtures.insert_account_mapping("USD")
    event = store(settings, webhook_payload())

    from airwallex_erpnext.services import webhooks

    real_import = webhooks.import_expense
    calls = {"count": 0}

    def flaky(settings_arg, client_arg, data):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("worker crashed")
        return real_import(settings_arg, client_arg, data)

    monkeypatch.setattr(webhooks, "import_expense", flaky)

    with pytest.raises(RuntimeError):
        process_event(event.name)

    failed = frappe.get_doc("Airwallex Webhook Event", event.name)
    assert failed.status == "Retrying"
    assert "RuntimeError" in failed.last_error
    assert failed.attempts == 1

    result = process_event(event.name)

    assert result["status"] == "processed"
    processed = frappe.get_doc("Airwallex Webhook Event", event.name)
    assert processed.status == "Processed"
    assert processed.attempts == 2
    assert processed.processed_at is not None
    assert len(frappe.get_all("Bank Transaction", pluck="name")) == 1


def test_process_event_dead_letters_when_attempts_exhausted(monkeypatch):
    settings = fixtures.insert_settings(webhook_max_attempts=1)
    event = store(settings, webhook_payload())
    frappe.db.set_value("Airwallex Webhook Event", event.name, "attempts", 1)

    from airwallex_erpnext.services import webhooks

    def boom(*args, **kwargs):
        raise RuntimeError("permanent failure")

    monkeypatch.setattr(webhooks, "import_expense", boom)

    with pytest.raises(RuntimeError):
        process_event(event.name)

    failed = frappe.get_doc("Airwallex Webhook Event", event.name)
    assert failed.status == "Dead Letter"
    assert failed.attempts == 2
