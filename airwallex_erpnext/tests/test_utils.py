from datetime import UTC, datetime
from decimal import Decimal

from airwallex_erpnext.utils import as_decimal, as_float, as_money, as_utc_iso, normalize_merchant, payload_hash


def test_normalization_and_hashing():
    assert normalize_merchant(" Cloudflare, Inc. ") == "cloudflare inc"
    assert as_decimal("10.50") == Decimal("10.50")
    assert payload_hash({"b": 2, "a": 1}) == payload_hash({"a": 1, "b": 2})


def test_as_money_rounds_half_up_at_currency_precision():
    assert as_money("10.005") == Decimal("10.01")
    assert as_money("10.004") == Decimal("10.00")
    assert as_money("0.125") == Decimal("0.13")
    assert as_money(2.675) == Decimal("2.68")
    assert as_money(-1.005) == Decimal("-1.01")


def test_as_money_preserves_precision_for_large_amounts():
    raw = "900719925474099.11"
    assert as_money(raw) == Decimal(raw)
    # Binary float arithmetic on the same value loses the cent.
    assert Decimal(str(float(raw))) != Decimal(raw)


def test_decimal_money_arithmetic_has_no_binary_drift():
    assert as_money("0.1") + as_money("0.2") == as_money("0.3")
    assert sum((as_money("0.1") for _ in range(3)), Decimal("0")) == as_money("0.3")
    assert as_money("100.00") - as_money("33.33") - as_money("33.33") == as_money("33.34")


def test_as_float_is_the_document_boundary():
    assert as_float(as_money("1234.565")) == 1234.57
    assert isinstance(as_float("1.25"), float)


def test_as_money_rejects_invalid_values_with_default():
    assert as_money(None) == Decimal("0.00")
    assert as_money("not-money") == Decimal("0.00")
    assert as_money(float("nan")) == Decimal("0.00")
    assert as_money("Infinity") == Decimal("0.00")


def test_naive_site_datetime_is_converted_to_utc():
    value = datetime(2026, 7, 22, 18, 13, 12, 755498)
    assert as_utc_iso(value, "Asia/Bangkok") == "2026-07-22T11:13:12.755498Z"


def test_aware_datetime_keeps_its_instant():
    value = datetime(2026, 7, 22, 11, 13, 12, 755498, tzinfo=UTC)
    assert as_utc_iso(value, "Asia/Bangkok") == "2026-07-22T11:13:12.755498Z"
