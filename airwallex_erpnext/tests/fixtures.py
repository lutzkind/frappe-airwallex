"""Realistic Airwallex payload fixtures shared by the service tests.

Amounts are strings on purpose: the Airwallex API serializes money as decimal
strings and the services must not turn them into binary floats.
"""

from __future__ import annotations

from types import SimpleNamespace

DEFAULT_SETTINGS = {
    "name": "Airwallex Test",
    "enabled": 1,
    "company": "Test Company",
    "default_currency": "USD",
    "default_cost_center": "Main - TC",
    "default_expense_account": "Expenses - TC",
    "default_business_unit": "Operations",
    "supplier_group": "All Supplier Groups",
    "default_expense_claim_type": "Airwallex Expense",
    "enable_banking": 1,
    "enable_expenses": 1,
    "enable_bills": 1,
    "enable_supplier_payments": 1,
    "enable_reimbursements": 1,
    "enable_fx": 1,
    "enable_transfers": 1,
    "create_accounting_documents": 0,
    "submit_accounting_documents": 0,
    "create_suppliers": 0,
    "mark_expenses_synced": 0,
    "mark_bills_synced": 0,
    "expense_posting_strategy": "Bank Transaction Only",
    "receipt_provider": "Disabled",
    "api_base_url": "https://api-demo.airwallex.com",
    "client_id": "test-client-id",
    "api_key": "test-api-key",
    "account_id": "test-account",
    "timeout_seconds": 30,
    "max_records_per_sync": 5000,
    "overlap_hours": 24,
    "sync_start_date": None,
    "last_successful_sync": None,
    "webhook_max_attempts": 5,
    "webhook_processing_timeout_minutes": 15,
    "webhook_tolerance_seconds": 300,
}


def settings(**overrides):
    values = dict(DEFAULT_SETTINGS)
    values.update(overrides)
    return SimpleNamespace(**values)


def insert_settings(**overrides):
    import frappe

    values = dict(DEFAULT_SETTINGS)
    values.update(overrides)
    name = values.pop("name")
    values["settings_name"] = name
    values.pop("doctype", None)
    values.update({"doctype": "Airwallex Settings", "name": name})
    return frappe.get_doc(values).insert(ignore_permissions=True)


def insert_account_mapping(currency="USD", ledger_account=None, bank_account=None, settings_name="Airwallex Test"):
    import frappe

    values = {
        "doctype": "Airwallex Account Mapping",
        "settings": settings_name,
        "enabled": 1,
        "currency": currency,
        "ledger_account": ledger_account or f"{currency} Bank - TC",
        "bank_account": bank_account or f"{currency} Bank Account",
    }
    return frappe.get_doc(values).insert(ignore_permissions=True)


def insert_currency_exchange(from_currency, to_currency, rate, date="2026-01-01"):
    import frappe

    return frappe.get_doc(
        {
            "doctype": "Currency Exchange",
            "from_currency": from_currency,
            "to_currency": to_currency,
            "exchange_rate": rate,
            "date": date,
        }
    ).insert(ignore_permissions=True)


def insert_company(name="Test Company", default_currency="USD"):
    import frappe

    return frappe.get_doc(
        {"doctype": "Company", "name": name, "default_currency": default_currency}
    ).insert(ignore_permissions=True)


def insert_credit_account(name="Creditors - TC", account_currency="USD"):
    import frappe

    return frappe.get_doc(
        {"doctype": "Account", "name": name, "account_currency": account_currency}
    ).insert(ignore_permissions=True)


def bill_payload(
    bill_id="bill_001",
    *,
    status="AWAITING_PAYMENT",
    amount="100.00",
    currency="USD",
    payments=None,
    **overrides,
):
    payload = {
        "id": bill_id,
        "status": status,
        "currency": currency,
        "amount": amount,
        "total_amount": amount,
        "invoice_number": f"INV-{bill_id}",
        "invoice_date": "2026-08-01",
        "due_date": "2026-08-31",
        "created_at": "2026-08-01T10:00:00Z",
        "description": "Cloud hosting",
        "vendor": {"name": "Acme Supplies"},
        "line_items": [{"description": "Hosting", "quantity": 1, "unit_price": amount}],
        "bill_payments": payments if payments is not None else [],
        "sync_status": "PENDING",
    }
    payload.update(overrides)
    return payload


def transfer_payment(
    payment_id="bpmt_001",
    *,
    amount="100.00",
    currency="USD",
    target_currency=None,
    fx_rate=None,
    status="PAID",
    payment_type="TRANSFER",
    **overrides,
):
    transfer = {
        "transfer_id": f"tr_{payment_id}",
        "source_currency": currency,
        "source_amount": amount,
        "transfer_date": "2026-08-02",
    }
    if target_currency:
        transfer["target_currency"] = target_currency
    if fx_rate is not None:
        transfer["fx_rate"] = fx_rate
    payment = {
        "id": payment_id,
        "type": payment_type,
        "status": status,
        "amount": amount,
        "currency": currency,
        "created_at": "2026-08-02T10:00:00Z",
        "paid_at": "2026-08-02T10:00:00Z",
    }
    if payment_type == "TRANSFER":
        payment["transfer"] = transfer
    if payment_type == "CARD_TRANSACTION":
        payment["card_transaction"] = {"card_transaction_id": f"ctx_{payment_id}"}
    payment.update(overrides)
    return payment


def transfer_payload(
    transfer_id="tr_100",
    *,
    amount="100.00",
    source_currency="USD",
    beneficiary="Acme Supplies",
    **overrides,
):
    payload = {
        "id": transfer_id,
        "source_currency": source_currency,
        "source_amount": amount,
        "amount_payer_pays": amount,
        "created_at": "2026-08-02T10:00:00Z",
        "beneficiary": {"name": beneficiary},
    }
    payload.update(overrides)
    return payload


def expense_payload(
    expense_id="exp_001",
    *,
    amount="20.92",
    currency="USD",
    status="APPROVED",
    merchant="Cloudflare",
    **overrides,
):
    payload = {
        "id": expense_id,
        "status": status,
        "billing_amount": amount,
        "billing_currency": currency,
        "merchant": merchant,
        "description": "Cloudflare subscription",
        "created_at": "2026-08-01T08:00:00Z",
        "settled_at": "2026-08-02T08:00:00Z",
        "cardholder": {"email": "spender@example.com"},
        "sync_status": "PENDING",
    }
    payload.update(overrides)
    return payload


def reimbursement_payload(
    report_id="reimb_001",
    *,
    amount="42.50",
    currency="USD",
    status="AWAITING_PAYMENT",
    **overrides,
):
    payload = {
        "id": report_id,
        "status": status,
        "currency": currency,
        "created_at": "2026-08-01T09:00:00Z",
        "submitted_by": {"email": "employee@example.com"},
        "reimbursements": [
            {"amount": amount, "description": "Taxi", "expense_date": "2026-08-01", "created_at": "2026-08-01"}
        ],
        "sync_status": "PENDING",
    }
    payload.update(overrides)
    return payload


def webhook_payload(event_id="evt_001", *, name="spend.expense.approved", data=None, **overrides):
    payload = {
        "id": event_id,
        "name": name,
        "version": "2025-11-11",
        "created_at": "2026-08-02T08:00:00Z",
        "account_id": "test-account",
        "data": data if data is not None else expense_payload(),
    }
    payload.update(overrides)
    return payload
