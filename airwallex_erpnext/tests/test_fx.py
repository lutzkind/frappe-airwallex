from airwallex_erpnext.services.fx import group_conversions


def test_conversion_pairing():
    rows = [
        {"id": "1", "source_type": "CONVERSION", "source_id": "c1", "amount": -100, "currency": "AUD"},
        {"id": "2", "source_type": "CONVERSION", "source_id": "c1", "amount": 65, "currency": "USD"},
        {"id": "3", "source_type": "CARD_PURCHASE", "source_id": "x"},
    ]
    assert list(group_conversions(rows)) == ["c1"]
    assert len(group_conversions(rows)["c1"]) == 2
