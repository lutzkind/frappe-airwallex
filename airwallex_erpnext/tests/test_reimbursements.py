from __future__ import annotations

import frappe

from airwallex_erpnext.services.reimbursements import import_reimbursement
from airwallex_erpnext.tests import fixtures
from airwallex_erpnext.tests.fixtures import reimbursement_payload


def prepare_settings(**overrides):
    settings = fixtures.insert_settings(
        **{
            "enable_reimbursements": 1,
            "create_accounting_documents": 1,
            "submit_accounting_documents": 1,
            **overrides,
        }
    )
    fixtures.insert_company()
    frappe.get_doc(
        {"doctype": "Employee", "name": "HR-EMP-0001", "company_email": "employee@example.com"}
    ).insert()
    return settings


def test_reimbursement_creates_expense_claim_idempotently(no_receipts):
    settings = prepare_settings()
    report = reimbursement_payload()

    first = import_reimbursement(settings, object(), report)
    second = import_reimbursement(settings, object(), report)

    assert first["status"] == "created"
    assert second["status"] == "exists"
    claims = frappe.get_all("Expense Claim", pluck="name")
    assert len(claims) == 1
    claim = frappe.get_doc("Expense Claim", claims[0])
    assert claim.custom_airwallex_reimbursement_id == "reimb_001"
    assert claim.employee == "HR-EMP-0001"


def test_reimbursement_held_without_employee_mapping(no_receipts):
    settings = prepare_settings()
    frappe.db.delete("Employee")

    result = import_reimbursement(settings, object(), reimbursement_payload())

    assert result["status"] == "held"
    assert result["reason"].startswith("employee_mapping_required")


def test_reimbursement_held_for_unready_status(no_receipts):
    settings = prepare_settings()

    result = import_reimbursement(settings, object(), reimbursement_payload(status="DRAFT"))

    assert result["status"] == "held"
    assert result["reason"] == "status:DRAFT"
