from __future__ import annotations

from typing import Any

import frappe

from airwallex_erpnext.services.exchange_rates import get_company_currency, payload_rate, resolve_exchange_rate
from airwallex_erpnext.services.mappings import account_mapping
from airwallex_erpnext.utils import as_float, as_money, iso_to_date


def import_transfer(settings, transfer: dict[str, Any], *, dry_run: bool = False):
    transfer_id = str(transfer.get("id") or "")
    if not transfer_id:
        return {"status": "held", "reason": "missing_id"}
    existing = frappe.db.get_value("Payment Entry", {"custom_airwallex_payment_id": transfer_id}, "name")
    if existing:
        return {"status": "exists", "name": existing, "id": transfer_id}
    if not settings.enable_transfers or not settings.create_accounting_documents:
        return {"status": "guarded", "id": transfer_id}

    source_currency = transfer.get("source_currency") or settings.default_currency
    mapping = account_mapping(settings.name, source_currency)
    if not mapping:
        return {"status": "held", "reason": f"missing_account_mapping:{source_currency}", "id": transfer_id}
    amount = as_money(transfer.get("amount_payer_pays") or transfer.get("source_amount") or transfer.get("transfer_amount"))
    if amount <= 0:
        return {"status": "held", "reason": "invalid_transfer_amount", "id": transfer_id}
    beneficiary = transfer.get("beneficiary") or {}
    supplier = frappe.db.get_value("Supplier", {"supplier_name": beneficiary.get("name") or transfer.get("beneficiary_name")}, "name")
    if not supplier:
        return {"status": "held", "reason": "supplier_mapping_required", "id": transfer_id}
    posting_date = iso_to_date(transfer.get("created_at"))
    company_currency = get_company_currency(settings.company) or settings.default_currency
    source_rate = resolve_exchange_rate(
        source_currency,
        company_currency,
        posting_date=posting_date,
        payload_rate=payload_rate(transfer, transfer, source_currency, company_currency),
    )
    if source_rate is None:
        return {"status": "held", "reason": f"missing_exchange_rate:{source_currency}->{company_currency}", "id": transfer_id}
    target_currency = _payable_currency(supplier, settings.company) or company_currency
    target_rate = resolve_exchange_rate(target_currency, company_currency, posting_date=posting_date)
    if target_rate is None:
        return {"status": "held", "reason": f"missing_exchange_rate:{target_currency}->{company_currency}", "id": transfer_id}
    received_amount = as_money(amount * source_rate / target_rate)
    values = {
        "doctype": "Payment Entry",
        "payment_type": "Pay",
        "company": settings.company,
        "posting_date": posting_date,
        "party_type": "Supplier",
        "party": supplier,
        "paid_from": mapping.ledger_account,
        "paid_amount": as_float(amount),
        "received_amount": as_float(received_amount),
        "source_exchange_rate": as_float(source_rate),
        "target_exchange_rate": as_float(target_rate),
        "reference_no": transfer_id,
        "reference_date": posting_date,
        "custom_airwallex_settings": settings.name,
        "custom_airwallex_payment_id": transfer_id,
        "remarks": f"Airwallex transfer {transfer_id}",
    }
    if dry_run:
        return {"status": "would_create", "values": values}
    doc = frappe.get_doc(values).insert(ignore_permissions=True)
    if settings.submit_accounting_documents:
        doc.submit()
    return {"status": "created", "name": doc.name, "id": transfer_id}


def sync_transfers(settings, client, *, from_created_at: str, max_items: int, dry_run: bool = False):
    results = []
    for transfer in client.paginate_bookmark(
        "/api/v1/transfers",
        params={"from_created_at": from_created_at},
        max_items=max_items,
    ):
        results.append(import_transfer(settings, transfer, dry_run=dry_run))
    return {"total": len(results), "results": results[:100]}


def _payable_currency(supplier: str, company: str | None) -> str | None:
    account = frappe.db.get_value("Party Account", {"parent": supplier, "company": company}, "account")
    if not account:
        account = frappe.db.get_value("Company", company, "default_payable_account")
    if not account:
        return None
    currency = frappe.db.get_value("Account", account, "account_currency")
    return str(currency) if currency else None
