from decimal import Decimal

from airwallex_erpnext.utils import as_decimal, normalize_merchant, payload_hash


def test_normalization_and_hashing():
    assert normalize_merchant(" Cloudflare, Inc. ") == "cloudflare inc"
    assert as_decimal("10.50") == Decimal("10.50")
    assert payload_hash({"b": 2, "a": 1}) == payload_hash({"a": 1, "b": 2})
