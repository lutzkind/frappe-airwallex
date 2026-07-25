from datetime import UTC, datetime

from airwallex_erpnext.providers.receipts.frappe_email import _amount_tokens, _score_fields


def test_amount_tokens_normalize_common_formats():
    assert _amount_tokens({"billing_amount": "20.920"}) == {"20.920", "20.92"}


def test_frappe_email_scoring_accepts_specific_receipt():
    score = _score_fields(
        subject="Cloudflare receipt USD 20.92",
        sender="receipts@example.invalid",
        body="Thank you for your payment.",
        communication_date=datetime(2026, 7, 16, tzinfo=UTC),
        resource={
            "merchant": "Cloudflare",
            "billing_amount": "20.92",
            "billing_currency": "USD",
            "settled_at": "2026-07-15T10:00:00Z",
        },
    )
    assert score == 1.0


def test_frappe_email_scoring_rejects_merchant_only_match():
    score = _score_fields(
        subject="Cloudflare account notice",
        sender="notices@example.invalid",
        body="General account information.",
        communication_date=datetime(2026, 7, 15, tzinfo=UTC),
        resource={
            "merchant": "Cloudflare",
            "billing_amount": "20.92",
            "billing_currency": "USD",
            "settled_at": "2026-07-15T10:00:00Z",
        },
    )
    assert score < 0.75
