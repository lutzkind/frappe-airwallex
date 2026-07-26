from types import SimpleNamespace

from airwallex_erpnext.services.webhook_management import (
    EXPENSE_EVENTS,
    REIMBURSEMENT_EVENTS,
    _subscription_matches,
    desired_events,
)


def settings(**values):
    defaults = {"enable_expenses": 0, "enable_reimbursements": 0}
    defaults.update(values)
    return SimpleNamespace(**defaults)


def test_desired_events_follow_enabled_modules():
    assert desired_events(settings()) == []
    assert desired_events(settings(enable_expenses=1)) == sorted(EXPENSE_EVENTS)
    assert desired_events(settings(enable_reimbursements=1)) == sorted(REIMBURSEMENT_EVENTS)
    assert desired_events(settings(enable_expenses=1, enable_reimbursements=1)) == sorted(
        set(EXPENSE_EVENTS + REIMBURSEMENT_EVENTS)
    )


def test_subscription_match_requires_exact_url_version_and_events():
    expected_url = "https://erp.example.com/api/method/airwallex_erpnext.api.webhook"
    expected_events = sorted(EXPENSE_EVENTS)
    subscription = {
        "url": expected_url + "/",
        "version": "2025-11-11",
        "events": list(reversed(expected_events)),
    }
    assert _subscription_matches(
        subscription,
        target_url=expected_url,
        version="2025-11-11",
        events=expected_events,
    )
    assert not _subscription_matches(
        {**subscription, "version": "2025-04-25"},
        target_url=expected_url,
        version="2025-11-11",
        events=expected_events,
    )
    assert not _subscription_matches(
        {**subscription, "events": expected_events[:-1]},
        target_url=expected_url,
        version="2025-11-11",
        events=expected_events,
    )
