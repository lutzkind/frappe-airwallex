from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from airwallex_erpnext.providers.receipts.base import ReceiptCandidate, ReceiptProvider
from airwallex_erpnext.utils import normalize_merchant


class FrappeEmailReceiptProvider(ReceiptProvider):
    """Discover receipt attachments from an incoming Frappe Email Account.

    The mailbox connection and OAuth or password credentials remain owned by
    Frappe's standard Email Account DocType. This provider only searches the
    resulting received Communication and private File records.
    """

    def __init__(self, email_account: str, *, lookback_days: int = 45, max_messages: int = 500):
        self.email_account = str(email_account or "").strip()
        self.lookback_days = max(1, min(int(lookback_days or 45), 365))
        self.max_messages = max(25, min(int(max_messages or 500), 2000))

    def candidates(self, resource: dict[str, Any]) -> list[ReceiptCandidate]:
        import frappe

        if not self.email_account:
            return []

        expense_time = _resource_datetime(resource)
        earliest = (expense_time - timedelta(days=14)) if expense_time else (datetime.now(UTC) - timedelta(days=self.lookback_days))
        filters = {
            "communication_medium": "Email",
            "sent_or_received": "Received",
            "has_attachment": 1,
            "email_account": self.email_account,
            "communication_date": [">=", earliest.replace(tzinfo=None)],
        }
        rows = frappe.get_all(
            "Communication",
            filters=filters,
            fields=[
                "name",
                "subject",
                "sender",
                "text_content",
                "content",
                "communication_date",
                "message_id",
            ],
            order_by="communication_date desc",
            limit_page_length=self.max_messages,
        )

        results: list[ReceiptCandidate] = []
        for row in rows:
            score = _score_fields(
                subject=str(row.get("subject") or ""),
                sender=str(row.get("sender") or ""),
                body=str(row.get("text_content") or row.get("content") or ""),
                communication_date=row.get("communication_date"),
                resource=resource,
            )
            if score < 0.75:
                continue

            files = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "Communication",
                    "attached_to_name": row.get("name"),
                    "is_folder": 0,
                },
                fields=["name", "file_name", "file_url", "is_private", "content_hash"],
                order_by="creation asc",
                limit_page_length=25,
            )
            for file_row in files:
                file_doc = frappe.get_doc("File", file_row.get("name"))
                content = file_doc.get_content()
                if isinstance(content, str):
                    content = content.encode("utf-8")
                if not content:
                    continue
                message_id = str(row.get("message_id") or row.get("name") or "")
                results.append(
                    ReceiptCandidate(
                        source_id=f"frappe-email:{message_id}:{file_row.get('name')}",
                        file_name=str(file_row.get("file_name") or "receipt"),
                        content=bytes(content),
                        confidence=score,
                        metadata={
                            "provider": "Frappe Email Account",
                            "message_id": message_id,
                            "communication": row.get("name"),
                            "email_account": self.email_account,
                            "source_file": file_row.get("name"),
                        },
                    )
                )
        return results


def _resource_datetime(resource: dict[str, Any]) -> datetime | None:
    for key in ("settled_at", "created_at", "updated_at", "date"):
        value = resource.get(key)
        if not value:
            continue
        if isinstance(value, datetime):
            parsed = value
        else:
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def _amount_tokens(resource: dict[str, Any]) -> set[str]:
    value = resource.get("billing_amount") or resource.get("amount")
    if value in (None, ""):
        return set()
    raw = str(value).replace(",", "").strip()
    tokens = {raw}
    try:
        amount = Decimal(raw)
        tokens.add(f"{amount:.2f}")
        tokens.add(format(amount.normalize(), "f"))
    except (InvalidOperation, ValueError):
        pass
    return {token.casefold() for token in tokens if token}


def _score_fields(
    *,
    subject: str,
    sender: str,
    body: str,
    communication_date: Any,
    resource: dict[str, Any],
) -> float:
    haystack = " ".join([subject, sender, body]).casefold()
    merchant = normalize_merchant(resource.get("merchant"))
    merchant_tokens = [token for token in merchant.split() if len(token) >= 3]
    score = 0.0

    if merchant and merchant in haystack:
        score += 0.55
    elif merchant_tokens:
        matched = sum(1 for token in merchant_tokens if token in haystack)
        if matched:
            score += min(0.45, 0.2 + 0.1 * matched)

    if any(token in haystack for token in _amount_tokens(resource)):
        score += 0.25

    currency = str(resource.get("billing_currency") or resource.get("currency") or "").casefold()
    if currency and currency in haystack:
        score += 0.1

    expense_time = _resource_datetime(resource)
    message_time = _coerce_datetime(communication_date)
    if expense_time and message_time:
        delta_days = abs((message_time - expense_time).total_seconds()) / 86400
        if delta_days <= 7:
            score += 0.1
        elif delta_days <= 30:
            score += 0.05

    return min(1.0, score)


def _coerce_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
