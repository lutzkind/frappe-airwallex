from __future__ import annotations

import frappe

from airwallex_erpnext.services.transfers import import_transfer
from airwallex_erpnext.tests import fixtures
from airwallex_erpnext.tests.fixtures import transfer_payload


def prepare_settings(**overrides):
    settings = fixtures.insert_settings(**{"enable_transfers": 1, "create_accounting_documents": 1, **overrides})
    fixtures.insert_company()
    fixtures.insert_account_mapping("USD")
    fixtures.insert_account_mapping("AUD")
    frappe.get_doc({"doctype": "Supplier", "name": "Acme Supplies", "supplier_name": "Acme Supplies"}).insert()
    return settings


def test_transfer_created_and_reimport_is_idempotent():
    settings = prepare_settings()

    first = import_transfer(settings, transfer_payload())
    second = import_transfer(settings, transfer_payload())

    assert first["status"] == "created"
    assert second["status"] == "exists"
    entries = frappe.get_all("Payment Entry", fields=["name", "paid_amount", "source_exchange_rate"])
    assert len(entries) == 1
    assert entries[0].paid_amount == 100.0
    assert entries[0].source_exchange_rate == 1


def test_cross_currency_transfer_uses_currency_exchange_rate():
    settings = prepare_settings()
    fixtures.insert_currency_exchange("AUD", "USD", "0.66")

    result = import_transfer(settings, transfer_payload(amount="100.00", source_currency="AUD"))

    assert result["status"] == "created"
    entry = frappe.get_doc("Payment Entry", frappe.get_all("Payment Entry", pluck="name")[0])
    assert entry.source_exchange_rate == 0.66
    assert entry.target_exchange_rate == 1
    assert entry.received_amount == 66.0


def test_cross_currency_transfer_fails_closed_without_rate():
    settings = prepare_settings()

    result = import_transfer(settings, transfer_payload(amount="100.00", source_currency="AUD"))

    assert result["status"] == "held"
    assert result["reason"] == "missing_exchange_rate:AUD->USD"
    assert frappe.get_all("Payment Entry", pluck="name") == []


def test_transfer_guarded_when_disabled():
    settings = prepare_settings(enable_transfers=0)

    result = import_transfer(settings, transfer_payload())

    assert result["status"] == "guarded"
    assert frappe.get_all("Payment Entry", pluck="name") == []
