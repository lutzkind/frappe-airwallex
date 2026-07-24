from __future__ import annotations

from typing import Any

import frappe

from airwallex_erpnext.constants import EXPENSE_APPROVED_STATES
from airwallex_erpnext.services.mappings import account_mapping, resolve
from airwallex_erpnext.services.receipts import attach_airwallex_receipts
from airwallex_erpnext.services.suppliers import resolve_supplier
from airwallex_erpnext.utils import as_float, iso_to_date, payload_hash


def import_expense(settings, client, expense: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    expense_id = str(expense.get("id") or "")
    if not expense_id:
        return {"status": "held", "reason": "missing_id"}

    bank_transaction = frappe.db.get_value("Bank Transaction", {"custom_airwallex_expense_id": expense_id}, "name")
    mapped = resolve(settings, "Expense", expense)
    currency = str(expense.get("billing_currency") or settings.default_currency)
    mapping = account_mapping(settings.name, currency)
    if not mapping:
        return {"status": "held", "reason": f"missing_account_mapping:{currency}", "id": expense_id}

    amount = as_float(expense.get("billing_amount"))
    if not bank_transaction:
        values = {
            "doctype": "Bank Transaction",
            "date": iso_to_date(expense.get("settled_at") or expense.get("created_at")),
            "bank_account": mapping.bank_account,
            "currency": currency,
            "deposit": 0,
            "withdrawal": abs(amount),
            "description": expense.get("merchant") or expense.get("description") or "Airwallex card expense",
            "reference_number": expense_id,
            "custom_airwallex_settings": settings.name,
            "custom_airwallex_expense_id": expense_id,
            "custom_airwallex_source_id": expense_id,
            "custom_airwallex_source_type": "CARD_PURCHASE",
            "custom_airwallex_transaction_type": "ISSUING_CAPTURE",
            "custom_airwallex_business": mapped.business_unit,
            "custom_airwallex_cost_center": mapped.cost_center,
            "custom_airwallex_expense_account": mapped.expense_account,
            "custom_airwallex_raw_hash": payload_hash(expense),
            "custom_airwallex_receipt_state": "pending",
        }
        if dry_run:
            bank_transaction = "DRY-RUN"
        else:
            bank_transaction = frappe.get_doc(values).insert(ignore_permissions=True).name
    elif not dry_run:
        frappe.db.set_value(
            "Bank Transaction",
            bank_transaction,
            {
                "custom_airwallex_business": mapped.business_unit,
                "custom_airwallex_cost_center": mapped.cost_center,
                "custom_airwallex_expense_account": mapped.expense_account,
                "custom_airwallex_raw_hash": payload_hash(expense),
            },
            update_modified=False,
        )

    strategy = settings.expense_posting_strategy or "Bank Transaction Only"
    accounting = {"status": "not_requested"}
    if strategy != "Bank Transaction Only":
        accounting = _create_accounting_document(settings, expense, mapped, bank_transaction, strategy, dry_run=dry_run)

    receipt = {"attached": 0, "skipped": 0, "errors": []}
    if not dry_run and bank_transaction and settings.receipt_provider in {"Airwallex", "Compatibility API"}:
        receipt = attach_airwallex_receipts(settings, client, expense, "Bank Transaction", bank_transaction)
        state = "attached" if receipt["attached"] or receipt["skipped"] else "missing"
        frappe.db.set_value("Bank Transaction", bank_transaction, "custom_airwallex_receipt_state", state, update_modified=False)

    if (
        not dry_run
        and settings.mark_expenses_synced
        and expense.get("status") in EXPENSE_APPROVED_STATES
        and accounting.get("status") in {"created", "exists", "not_requested"}
    ):
        client.request("POST", f"/api/v1/spend/expenses/{expense_id}/sync", body={"sync_status": "SYNCED"})

    return {
        "status": "processed",
        "id": expense_id,
        "bank_transaction": bank_transaction,
        "accounting": accounting,
        "receipt": receipt,
    }


def _create_accounting_document(settings, expense, mapped, bank_transaction, strategy: str, *, dry_run: bool):
    if expense.get("status") not in EXPENSE_APPROVED_STATES:
        return {"status": "held", "reason": f"expense_status:{expense.get('status')}"}
    if not settings.create_accounting_documents:
        return {"status": "guarded"}

    if strategy == "Expense Claim":
        return _create_expense_claim(settings, expense, mapped, bank_transaction, dry_run=dry_run)

    existing = frappe.db.get_value("Purchase Invoice", {"custom_airwallex_expense_id": expense.get("id")}, "name")
    if existing:
        return {"status": "exists", "name": existing}

    supplier = resolve_supplier(settings, expense.get("merchant"), mapped.supplier)
    if not supplier:
        return {"status": "held", "reason": "supplier_mapping_required"}
    if not mapped.expense_account:
        return {"status": "held", "reason": "expense_account_required"}

    amount = as_float(expense.get("billing_amount"))
    values = {
        "doctype": "Purchase Invoice",
        "company": mapped.company or settings.company,
        "supplier": supplier,
        "posting_date": iso_to_date(expense.get("settled_at") or expense.get("created_at")),
        "bill_date": iso_to_date(expense.get("created_at")),
        "bill_no": f"AWX-EXP-{expense.get('id')}",
        "currency": expense.get("billing_currency") or settings.default_currency,
        "custom_airwallex_settings": settings.name,
        "custom_airwallex_expense_id": expense.get("id"),
        "custom_airwallex_business": mapped.business_unit,
        "custom_airwallex_bank_transaction": bank_transaction if bank_transaction != "DRY-RUN" else None,
        "custom_airwallex_sync_status": expense.get("sync_status"),
        "custom_airwallex_raw_hash": payload_hash(expense),
        "items": [
            {
                "item_name": expense.get("merchant") or "Airwallex expense",
                "description": expense.get("description") or expense.get("merchant") or "Airwallex expense",
                "qty": 1,
                "rate": amount,
                "expense_account": mapped.expense_account,
                "cost_center": mapped.cost_center,
                "project": mapped.project,
            }
        ],
    }
    if strategy == "Paid Purchase Invoice":
        mapping = account_mapping(settings.name, values["currency"])
        values.update({"is_paid": 1, "cash_bank_account": mapping.ledger_account if mapping else None})
    if dry_run:
        return {"status": "would_create", "values": values}
    doc = frappe.get_doc(values)
    doc.insert(ignore_permissions=True)
    if settings.submit_accounting_documents:
        doc.submit()
    if bank_transaction:
        frappe.db.set_value("Bank Transaction", bank_transaction, "custom_airwallex_purchase_invoice", doc.name, update_modified=False)
    return {"status": "created", "name": doc.name, "submitted": bool(doc.docstatus == 1)}


def _create_expense_claim(settings, expense, mapped, bank_transaction, *, dry_run: bool):
    expense_id = str(expense.get("id") or "")
    existing = frappe.db.get_value("Expense Claim", {"custom_airwallex_reimbursement_id": expense_id}, "name")
    if existing:
        return {"status": "exists", "name": existing}
    cardholder = expense.get("cardholder") or expense.get("user") or {}
    email = cardholder.get("email") if isinstance(cardholder, dict) else str(cardholder or "")
    employee = None
    if email:
        employee = frappe.db.get_value("Employee", {"company_email": email}, "name") or frappe.db.get_value("Employee", {"personal_email": email}, "name")
    if not employee:
        return {"status": "held", "reason": f"employee_mapping_required:{email or 'unknown'}"}
    if not settings.default_expense_claim_type:
        return {"status": "held", "reason": "default_expense_claim_type_required"}
    amount = as_float(expense.get("billing_amount"))
    values = {
        "doctype": "Expense Claim",
        "employee": employee,
        "company": mapped.company or settings.company,
        "posting_date": iso_to_date(expense.get("settled_at") or expense.get("created_at")),
        "remark": f"Airwallex card expense {expense_id}",
        "custom_airwallex_settings": settings.name,
        "custom_airwallex_reimbursement_id": expense_id,
        "custom_airwallex_sync_status": expense.get("sync_status"),
        "custom_airwallex_raw_hash": payload_hash(expense),
        "expenses": [{
            "expense_date": iso_to_date(expense.get("settled_at") or expense.get("created_at")),
            "expense_type": settings.default_expense_claim_type,
            "description": expense.get("description") or expense.get("merchant") or "Airwallex card expense",
            "amount": amount,
            "sanctioned_amount": amount,
            "cost_center": mapped.cost_center,
            "project": mapped.project,
        }],
    }
    if dry_run:
        return {"status": "would_create", "values": values}
    doc = frappe.get_doc(values).insert(ignore_permissions=True)
    if settings.submit_accounting_documents:
        doc.submit()
    return {"status": "created", "name": doc.name, "submitted": bool(doc.docstatus == 1)}


def sync_expenses(settings, client, *, from_created_at: str, max_items: int, dry_run: bool = False):
    results = []
    for summary in client.paginate_bookmark(
        "/api/v1/spend/expenses",
        params={"from_created_at": from_created_at},
        max_items=max_items,
    ):
        expense_id = summary.get("id")
        item = client.request("GET", f"/api/v1/spend/expenses/{expense_id}") if expense_id else summary
        results.append(import_expense(settings, client, item, dry_run=dry_run))
    return {"total": len(results), "results": results[:100]}
