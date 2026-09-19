from __future__ import annotations

import frappe

from airwallex_erpnext.services.bills import import_bill
from airwallex_erpnext.tests import fixtures
from airwallex_erpnext.tests.fixtures import bill_payload, transfer_payment


def prepare_settings(**overrides):
    settings = fixtures.insert_settings(
        **{"create_accounting_documents": 1, "submit_accounting_documents": 1, **overrides}
    )
    fixtures.insert_company()
    fixtures.insert_account_mapping("USD")
    frappe.get_doc({"doctype": "Supplier", "name": "Acme Supplies", "supplier_name": "Acme Supplies"}).insert()
    return settings


def test_bill_payment_created_with_bill(no_receipts):
    settings = prepare_settings()
    bill = bill_payload(payments=[transfer_payment()])

    result = import_bill(settings, None, bill)

    assert result["status"] == "created"
    payments = result["payments"]["results"]
    assert payments[0]["status"] == "created"
    entries = frappe.get_all("Payment Entry", fields=["name", "paid_amount", "custom_airwallex_payment_id"])
    assert len(entries) == 1
    assert entries[0].custom_airwallex_payment_id == "bpmt_001"
    assert entries[0].paid_amount == 100.0
    entry = frappe.get_doc("Payment Entry", entries[0].name)
    assert entry.source_exchange_rate == 1
    assert entry.target_exchange_rate == 1


def test_cross_currency_payment_uses_currency_exchange_rate(no_receipts):
    settings = prepare_settings()
    fixtures.insert_currency_exchange("AUD", "USD", "0.66")
    fixtures.insert_account_mapping("AUD")
    bill = bill_payload(
        currency="AUD",
        amount="100.00",
        payments=[transfer_payment(amount="100.00", currency="AUD")],
    )

    result = import_bill(settings, None, bill)

    assert result["payments"]["results"][0]["status"] == "created"
    entry = frappe.get_doc("Payment Entry", frappe.get_all("Payment Entry", pluck="name")[0])
    assert entry.source_exchange_rate == 0.66
    assert entry.target_exchange_rate == 0.66
    assert entry.paid_amount == 100.0
    assert entry.received_amount == 100.0


def test_cross_currency_payment_uses_payload_fx_rate(no_receipts):
    settings = prepare_settings()
    fixtures.insert_account_mapping("AUD")
    bill = bill_payload(
        currency="AUD",
        amount="100.00",
        payments=[
            transfer_payment(
                amount="100.00",
                currency="AUD",
                target_currency="USD",
                fx_rate="0.65",
            )
        ],
    )

    result = import_bill(settings, None, bill)

    assert result["payments"]["results"][0]["status"] == "created"
    entry = frappe.get_doc("Payment Entry", frappe.get_all("Payment Entry", pluck="name")[0])
    assert entry.source_exchange_rate == 0.65


def test_cross_currency_payment_fails_closed_without_rate(no_receipts):
    settings = prepare_settings()
    fixtures.insert_account_mapping("AUD")
    bill = bill_payload(
        currency="AUD",
        amount="100.00",
        payments=[transfer_payment(amount="100.00", currency="AUD")],
    )

    result = import_bill(settings, None, bill)

    held = result["payments"]["results"][0]
    assert held["status"] == "held"
    assert held["reason"] == "missing_exchange_rate:AUD->USD"
    assert frappe.get_all("Payment Entry", pluck="name") == []


def test_bill_and_payment_reimport_is_idempotent(no_receipts):
    settings = prepare_settings()
    bill = bill_payload(payments=[transfer_payment()])

    import_bill(settings, None, bill)
    second = import_bill(settings, None, bill)

    assert second["status"] == "exists"
    assert len(frappe.get_all("Purchase Invoice", pluck="name")) == 1
    assert len(frappe.get_all("Payment Entry", pluck="name")) == 1


def test_partial_payments_allocate_without_drift(no_receipts):
    settings = prepare_settings()
    bill = bill_payload(
        amount="100.00",
        payments=[transfer_payment("bpmt_001", amount="40.00"), transfer_payment("bpmt_002", amount="60.00")],
    )

    result = import_bill(settings, None, bill)

    assert [item["status"] for item in result["payments"]["results"]] == ["created", "created"]
    assert len(frappe.get_all("Payment Entry", pluck="name")) == 2
    invoice = frappe.get_doc("Purchase Invoice", frappe.get_all("Purchase Invoice", pluck="name")[0])
    assert float(invoice.outstanding_amount) == 0.0


def test_card_payment_is_held_to_avoid_double_booking(no_receipts):
    settings = prepare_settings()
    bill = bill_payload(payments=[transfer_payment("bpmt_card", payment_type="CARD_TRANSACTION")])

    result = import_bill(settings, None, bill)

    assert result["payments"]["results"][0]["status"] == "held"
    assert result["payments"]["results"][0]["reason"] == "card_payment_owned_by_spend"
    assert frappe.get_all("Payment Entry", pluck="name") == []


def test_supplier_payments_guarded_when_disabled(no_receipts):
    settings = prepare_settings(enable_supplier_payments=0)
    bill = bill_payload(payments=[transfer_payment()])

    result = import_bill(settings, None, bill)

    assert result["payments"]["results"][0]["status"] == "guarded"
    assert frappe.get_all("Payment Entry", pluck="name") == []


def test_payment_held_without_account_mapping(no_receipts):
    settings = prepare_settings()
    bill = bill_payload(payments=[transfer_payment("bpmt_aud", currency="AUD")])

    result = import_bill(settings, None, bill)

    assert result["payments"]["results"][0]["status"] == "held"
    assert result["payments"]["results"][0]["reason"] == "missing_account_mapping:AUD"


def test_payment_held_when_invoice_not_submitted(no_receipts):
    settings = prepare_settings(submit_accounting_documents=0)
    bill = bill_payload(payments=[transfer_payment()])

    result = import_bill(settings, None, bill)

    assert result["payments"]["results"][0]["status"] == "held"
    assert result["payments"]["results"][0]["reason"] == "purchase_invoice_not_submitted"
