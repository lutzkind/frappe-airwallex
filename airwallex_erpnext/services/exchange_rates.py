from __future__ import annotations

from decimal import Decimal

import frappe

from airwallex_erpnext.utils import as_decimal

PAYLOAD_RATE_KEYS = ("fx_rate", "exchange_rate", "conversion_rate")


def get_company_currency(company: str | None) -> str | None:
    if not company:
        return None
    return frappe.db.get_value("Company", company, "default_currency")


def resolve_exchange_rate(
    from_currency: str | None,
    to_currency: str | None,
    *,
    posting_date: str | None = None,
    payload_rate=None,
) -> Decimal | None:
    """Return units of ``to_currency`` per one unit of ``from_currency``.

    Follows ERPNext's Currency Exchange convention. A non-identity rate that
    cannot be established returns ``None`` so callers fail closed instead of
    booking a fictitious 1:1 movement.
    """
    source = str(from_currency or "").strip().upper()
    target = str(to_currency or "").strip().upper()
    if not source or not target:
        return None
    if source == target:
        return Decimal(1)
    if payload_rate not in (None, ""):
        rate = as_decimal(payload_rate)
        return rate if rate > 0 else None
    direct = _currency_exchange_rate(source, target, posting_date)
    if direct:
        return direct
    inverse = _currency_exchange_rate(target, source, posting_date)
    if inverse:
        return Decimal(1) / inverse
    return None


def payload_rate(payment: dict, transfer: dict, from_currency: str | None, to_currency: str | None):
    """Return a source-system rate only when its currency pair matches.

    Airwallex transfer/payment payloads may carry an FX rate but not always the
    pair it applies to. Using it for a different pair would be worse than
    failing closed, so the pair must match when the payload states one.
    """
    source = str(from_currency or "").strip().upper()
    target = str(to_currency or "").strip().upper()
    payload_source = str(transfer.get("source_currency") or "").strip().upper()
    payload_target = str(transfer.get("target_currency") or "").strip().upper()
    if payload_source and payload_target and (payload_source, payload_target) != (source, target):
        return None
    for container in (transfer, payment):
        for key in PAYLOAD_RATE_KEYS:
            value = container.get(key)
            if value not in (None, ""):
                return value
    return None


def _currency_exchange_rate(from_currency: str, to_currency: str, posting_date: str | None) -> Decimal | None:
    if not posting_date:
        return None
    value = frappe.db.get_value(
        "Currency Exchange",
        {"from_currency": from_currency, "to_currency": to_currency, "date": ["<=", posting_date]},
        "exchange_rate",
        order_by="date desc",
    )
    rate = as_decimal(value) if value is not None else Decimal(0)
    return rate if rate > 0 else None
