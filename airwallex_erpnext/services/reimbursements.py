from __future__ import annotations

from typing import Any

import frappe

from airwallex_erpnext.constants import REIMBURSEMENT_READY_STATES
from airwallex_erpnext.services.mappings import resolve
from airwallex_erpnext.services.receipts import attach_airwallex_receipts
from airwallex_erpnext.utils import as_float, iso_to_date, payload_hash


def import_reimbursement(settings, client, report: dict[str, Any], *, dry_run: bool = False):
    report_id = str(report.get("id") or "")
    if not report_id:
        return {"status": "held", "reason": "missing_id"}
    if not frappe.db.exists("DocType", "Expense Claim"):
        return {"status": "held", "reason": "expense_claim_doctype_unavailable", "id": report_id}
    existing = frappe.db.get_value("Expense Claim", {"custom_airwallex_reimbursement_id": report_id}, "name")
    if existing:
        return {"status": "exists", "name": existing, "id": report_id}
    if report.get("status") not in REIMBURSEMENT_READY_STATES:
        return {"status": "held", "reason": f"status:{report.get('status')}", "id": report_id}
    if not settings.enable_reimbursements or not settings.create_accounting_documents:
        return {"status": "guarded", "id": report_id}

    submitter = report.get("submitted_by") or report.get("user") or {}
    email = submitter.get("email") if isinstance(submitter, dict) else submitter
    employee = frappe.db.get_value("Employee", {"company_email": email}, "name") or frappe.db.get_value("Employee", {"personal_email": email}, "name")
    if not employee:
        return {"status": "held", "reason": f"employee_mapping_required:{email}", "id": report_id}

    mapped = resolve(settings, "Reimbursement", report)
    expenses = []
    for item in report.get("reimbursements") or report.get("line_items") or []:
        expenses.append(
            {
                "expense_date": iso_to_date(item.get("expense_date") or item.get("created_at")),
                "expense_type": settings.default_expense_claim_type,
                "description": item.get("description") or item.get("merchant") or "Airwallex reimbursement",
                "amount": as_float(item.get("amount") or item.get("transaction_amount")),
                "sanctioned_amount": as_float(item.get("amount") or item.get("transaction_amount")),
                "cost_center": mapped.cost_center,
                "project": mapped.project,
            }
        )
    if not expenses:
        return {"status": "held", "reason": "no_reimbursement_lines", "id": report_id}

    values = {
        "doctype": "Expense Claim",
        "employee": employee,
        "company": mapped.company or settings.company,
        "posting_date": iso_to_date(report.get("created_at")),
        "remark": f"Airwallex reimbursement {report_id}",
        "custom_airwallex_settings": settings.name,
        "custom_airwallex_reimbursement_id": report_id,
        "custom_airwallex_sync_status": report.get("sync_status"),
        "custom_airwallex_raw_hash": payload_hash(report),
        "expenses": expenses,
    }
    if dry_run:
        return {"status": "would_create", "values": values}
    doc = frappe.get_doc(values).insert(ignore_permissions=True)
    if settings.submit_accounting_documents:
        doc.submit()
    attach_airwallex_receipts(settings, client, report, "Expense Claim", doc.name)
    return {"status": "created", "name": doc.name, "id": report_id}


def sync_reimbursements(settings, client, *, from_created_at: str, max_items: int, dry_run: bool = False):
    results = []
    for summary in client.paginate_bookmark(
        "/api/v1/spend/reimbursement_reports",
        params={"from_created_at": from_created_at},
        max_items=max_items,
    ):
        report_id = summary.get("id")
        report = client.request("GET", f"/api/v1/spend/reimbursement_reports/{report_id}")
        reimbursements = list(
            client.paginate_bookmark(
                f"/api/v1/spend/reimbursement_reports/{report_id}/reimbursements",
                max_items=max_items,
            )
        )
        report["reimbursements"] = reimbursements
        results.append(import_reimbursement(settings, client, report, dry_run=dry_run))
    return {"total": len(results), "results": results[:100]}
