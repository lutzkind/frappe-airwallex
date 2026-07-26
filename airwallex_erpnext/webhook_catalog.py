from __future__ import annotations

EXPENSE_EVENTS = (
    "spend.expense.draft",
    "spend.expense.awaiting_approval",
    "spend.expense.updated",
    "spend.expense.rejected",
    "spend.expense.approved",
    "spend.expense.archived",
    "spend.expense.deleted",
)

REIMBURSEMENT_EVENTS = (
    "spend.reimbursement_report.draft",
    "spend.reimbursement_report.awaiting_approval",
    "spend.reimbursement_report.awaiting_payment",
    "spend.reimbursement_report.rejected",
    "spend.reimbursement_report.payment_in_progress",
    "spend.reimbursement_report.paid",
    "spend.reimbursement_report.mark_as_paid",
    "spend.reimbursement_report.deleted",
    "spend.reimbursement_report.updated",
)


def desired_events(settings) -> list[str]:
    events: list[str] = []
    if int(settings.enable_expenses or 0):
        events.extend(EXPENSE_EVENTS)
    if int(settings.enable_reimbursements or 0):
        events.extend(REIMBURSEMENT_EVENTS)
    return sorted(set(events))


def normalize_url(value) -> str:
    return str(value or "").strip().rstrip("/")


def subscription_matches(subscription: dict, *, target_url: str, version: str, events: list[str]) -> bool:
    return (
        normalize_url(subscription.get("url")) == normalize_url(target_url)
        and str(subscription.get("version") or "") == str(version)
        and sorted(set(subscription.get("events") or [])) == sorted(set(events))
    )
