from __future__ import annotations

import frappe

from airwallex_erpnext.services.expenses import import_expense
from airwallex_erpnext.tests import fixtures
from airwallex_erpnext.tests.fixtures import expense_payload
from airwallex_erpnext.utils import payload_hash


def prepare_settings(**overrides):
    settings = fixtures.insert_settings(**overrides)
    fixtures.insert_company()
    fixtures.insert_account_mapping("USD")
    frappe.get_doc({"doctype": "Supplier", "name": "Cloudflare", "supplier_name": "Cloudflare"}).insert()
    return settings


def test_expense_creates_bank_transaction_and_updates_in_place(no_receipts):
    settings = prepare_settings()
    expense = expense_payload()

    first = import_expense(settings, object(), expense)
    second = import_expense(settings, object(), expense_payload(merchant="Cloudflare Inc"))

    assert first["status"] == "processed"
    assert second["status"] == "processed"
    transactions = frappe.get_all("Bank Transaction", fields=["name", "withdrawal", "custom_airwallex_raw_hash"])
    assert len(transactions) == 1
    assert transactions[0].withdrawal == 20.92
    assert transactions[0].custom_airwallex_raw_hash == payload_hash(expense_payload(merchant="Cloudflare Inc"))


def test_expense_purchase_invoice_is_idempotent(no_receipts):
    settings = prepare_settings(
        expense_posting_strategy="Purchase Invoice",
        create_accounting_documents=1,
        submit_accounting_documents=1,
    )
    expense = expense_payload()

    first = import_expense(settings, object(), expense)
    second = import_expense(settings, object(), expense)

    assert first["accounting"]["status"] == "created"
    assert second["accounting"]["status"] == "exists"
    invoices = frappe.get_all("Purchase Invoice", pluck="name")
    assert len(invoices) == 1
    invoice = frappe.get_doc("Purchase Invoice", invoices[0])
    assert invoice.custom_airwallex_expense_id == "exp_001"
    assert invoice.docstatus == 1


def test_expense_held_without_account_mapping(no_receipts):
    settings = prepare_settings()
    frappe.db.delete("Airwallex Account Mapping")
    expense = expense_payload()

    result = import_expense(settings, object(), expense)

    assert result["status"] == "held"
    assert result["reason"] == "missing_account_mapping:USD"


def test_unapproved_expense_does_not_post_invoice(no_receipts):
    settings = prepare_settings(
        expense_posting_strategy="Purchase Invoice",
        create_accounting_documents=1,
    )
    expense = expense_payload(status="DRAFT")

    result = import_expense(settings, object(), expense)

    assert result["accounting"]["status"] == "held"
    assert result["accounting"]["reason"] == "expense_status:DRAFT"
    assert frappe.get_all("Purchase Invoice", pluck="name") == []
