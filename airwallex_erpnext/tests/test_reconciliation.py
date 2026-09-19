from __future__ import annotations

import frappe

from airwallex_erpnext.services.reconciliation import propose_for_bank_transaction
from airwallex_erpnext.tests import fixtures


def insert_bank_transaction(name="BT-0001", *, deposit=100.0, withdrawal=0, **overrides):
    values = {
        "doctype": "Bank Transaction",
        "name": name,
        "deposit": deposit,
        "withdrawal": withdrawal,
        "currency": "USD",
    }
    values.update(overrides)
    return frappe.get_doc(values).insert(ignore_permissions=True)


def insert_invoice(name, *, outstanding=100.0, docstatus=1, **overrides):
    values = {
        "doctype": "Purchase Invoice",
        "name": name,
        "docstatus": docstatus,
        "outstanding_amount": outstanding,
        "posting_date": "2026-08-01",
    }
    values.update(overrides)
    return frappe.get_doc(values).insert(ignore_permissions=True)


def test_explicit_link_scores_highest():
    fixtures.insert_settings()
    insert_bank_transaction(custom_airwallex_purchase_invoice="PI-0002")
    insert_invoice("PI-0002", outstanding=50.0)

    candidates = propose_for_bank_transaction("BT-0001")

    assert [(candidate.doctype, candidate.name, candidate.score) for candidate in candidates] == [
        ("Purchase Invoice", "PI-0002", 100)
    ]
    assert candidates[0].reasons == ("explicit_link",)


def test_amount_match_proposal_is_persisted_once():
    fixtures.insert_settings()
    insert_bank_transaction()
    insert_invoice("PI-0001")

    first = propose_for_bank_transaction("BT-0001")
    second = propose_for_bank_transaction("BT-0001")

    assert [candidate.name for candidate in first] == ["PI-0001"]
    assert first[0].score == 50
    assert "amount_match" in first[0].reasons
    assert len(second) == 1
    proposals = frappe.get_all("Airwallex Reconciliation Proposal", fields=["reference_name", "status", "score"])
    assert len(proposals) == 1
    assert proposals[0].reference_name == "PI-0001"
    assert proposals[0].status == "Proposed"


def test_unrelated_amount_is_not_proposed():
    fixtures.insert_settings()
    insert_bank_transaction(deposit=10.0, withdrawal=10.0)
    insert_invoice("PI-0001", outstanding=999.0)

    assert propose_for_bank_transaction("BT-0001") == []
    assert frappe.get_all("Airwallex Reconciliation Proposal", pluck="name") == []
