from datetime import UTC, datetime
from decimal import Decimal

from airwallex_erpnext.utils import as_decimal, as_utc_iso, normalize_merchant, payload_hash


def test_normalization_and_hashing():
    assert normalize_merchant(" Cloudflare, Inc. ") == "cloudflare inc"
    assert as_decimal("10.50") == Decimal("10.50")
    assert payload_hash({"b": 2, "a": 1}) == payload_hash({"a": 1, "b": 2})


def test_naive_site_datetime_is_converted_to_utc():
    value = datetime(2026, 7, 22, 18, 13, 12, 755498)
    assert as_utc_iso(value, "Asia/Bangkok") == "2026-07-22T11:13:12.755498Z"


def test_aware_datetime_keeps_its_instant():
    value = datetime(2026, 7, 22, 11, 13, 12, 755498, tzinfo=UTC)
    assert as_utc_iso(value, "Asia/Bangkok") == "2026-07-22T11:13:12.755498Z"
