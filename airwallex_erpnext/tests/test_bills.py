from __future__ import annotations

import frappe

from airwallex_erpnext.services.bills import import_bill, sync_bills
from airwallex_erpnext.tests import fixtures
from airwallex_erpnext.tests.fixtures import bill_payload


def prepare_settings(**overrides):
    settings = fixtures.insert_settings(**{"create_accounting_documents": 1, **overrides})
    fixtures.insert_company()
    fixtures.insert_account_mapping("USD")
    frappe.get_doc({"doctype": "Supplier", "name": "Acme Supplies", "supplier_name": "Acme Supplies"}).insert()
    return settings


def test_bill_created_and_reimport_is_idempotent(no_receipts):
    settings = prepare_settings()
    bill = bill_payload()

    first = import_bill(settings, None, bill)
    second = import_bill(settings, None, bill)

    assert first["status"] == "created"
    assert first["id"] == "bill_001"
    assert second["status"] == "exists"
    invoices = frappe.get_all("Purchase Invoice", pluck="name")
    assert len(invoices) == 1
    invoice = frappe.get_doc("Purchase Invoice", invoices[0])
    assert invoice.custom_airwallex_bill_id == "bill_001"
    assert invoice.supplier == "Acme Supplies"


def test_bill_guarded_when_posting_disabled(no_receipts):
    settings = prepare_settings(create_accounting_documents=0)
    bill = bill_payload()

    result = import_bill(settings, None, bill)

    assert result["status"] == "guarded"
    assert frappe.get_all("Purchase Invoice", pluck="name") == []


def test_bill_held_for_unapproved_status(no_receipts):
    settings = prepare_settings()
    bill = bill_payload(status="DRAFT")

    result = import_bill(settings, None, bill)

    assert result["status"] == "held"
    assert result["reason"] == "bill_status:DRAFT"


def test_bill_held_without_supplier_mapping(no_receipts):
    settings = prepare_settings()
    frappe.db.delete("Supplier")
    bill = bill_payload()

    result = import_bill(settings, None, bill)

    assert result["status"] == "held"
    assert result["reason"] == "supplier_mapping_required"


def test_sync_bills_fetches_full_bill_for_each_summary(no_receipts):
    settings = prepare_settings()
    summaries = [{"id": "bill_001"}, {"id": "bill_002"}]
    details = {
        "bill_001": bill_payload("bill_001"),
        "bill_002": bill_payload("bill_002", amount="50.00"),
    }

    class Client:
        def paginate_bookmark(self, path, params=None, max_items=None):
            yield from summaries

        def request(self, method, path, params=None, body=None):
            return details[path.rsplit("/", 1)[-1]]

    result = sync_bills(settings, Client(), from_created_at="2026-08-01T00:00:00Z", max_items=100)

    assert result["total"] == 2
    assert len(frappe.get_all("Purchase Invoice", pluck="name")) == 2
