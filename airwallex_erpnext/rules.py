from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from airwallex_erpnext.utils import normalize_merchant, normalize_text


@dataclass(frozen=True)
class RuleResult:
    company: str | None = None
    cost_center: str | None = None
    project: str | None = None
    expense_account: str | None = None
    supplier: str | None = None
    tax_template: str | None = None
    item_code: str | None = None
    business_unit: str | None = None
    source_rule: str | None = None


def _value_for(record: dict[str, Any], field: str) -> str:
    if field == "merchant":
        return normalize_merchant(record.get("merchant"))
    if field.startswith("accounting."):
        wanted = field.split(".", 1)[1].casefold()
        for selection in record.get("accounting_field_selections") or []:
            if str(selection.get("type") or selection.get("name") or "").casefold() == wanted:
                return normalize_text(selection.get("external_id") or selection.get("value") or selection.get("value_label"))
        return ""
    return normalize_text(record.get(field))


def rule_matches(rule: dict[str, Any], record: dict[str, Any]) -> bool:
    actual = _value_for(record, str(rule.get("match_field") or ""))
    expected = normalize_text(rule.get("match_value"))
    operator = str(rule.get("operator") or "Equals")

    if operator == "Equals":
        return actual.casefold() == expected.casefold()
    if operator == "Contains":
        return expected.casefold() in actual.casefold()
    if operator == "Starts With":
        return actual.casefold().startswith(expected.casefold())
    if operator == "Regex":
        return bool(re.search(expected, actual, flags=re.IGNORECASE))
    if operator == "Any":
        return True
    return False


def resolve_rules(rules: Iterable[dict[str, Any]], record: dict[str, Any], defaults: dict[str, Any] | None = None) -> RuleResult:
    merged: dict[str, Any] = dict(defaults or {})
    source_rule = None
    ordered = sorted(rules, key=lambda r: (int(r.get("priority") or 1000), str(r.get("name") or "")))
    for rule in ordered:
        if not rule.get("enabled", True) or not rule_matches(rule, record):
            continue
        source_rule = str(rule.get("name") or "")
        for field in (
            "company",
            "cost_center",
            "project",
            "expense_account",
            "supplier",
            "tax_template",
            "item_code",
            "business_unit",
        ):
            value = rule.get(field)
            if value not in (None, ""):
                merged[field] = value
        if rule.get("stop_processing", True):
            break
    merged["source_rule"] = source_rule
    return RuleResult(**{k: merged.get(k) for k in RuleResult.__dataclass_fields__})
