from airwallex_erpnext.rules import resolve_rules


def test_rule_precedence_and_stop():
    rules = [
        {"name": "default", "priority": 100, "enabled": 1, "match_field": "merchant", "operator": "Any", "match_value": "", "expense_account": "Misc", "stop_processing": 1},
        {"name": "hosting", "priority": 10, "enabled": 1, "match_field": "merchant", "operator": "Contains", "match_value": "cloudflare", "expense_account": "Hosting", "cost_center": "Example Operations", "stop_processing": 1},
    ]
    result = resolve_rules(rules, {"merchant": "Cloudflare, Inc."})
    assert result.expense_account == "Hosting"
    assert result.cost_center == "Example Operations"
    assert result.source_rule == "hosting"


def test_unknown_fields_do_not_match():
    result = resolve_rules(
        [{"name": "x", "priority": 1, "enabled": 1, "match_field": "missing", "operator": "Equals", "match_value": "a", "expense_account": "X"}],
        {"merchant": "A"},
        {"expense_account": "Default"},
    )
    assert result.expense_account == "Default"
