from __future__ import annotations

import email
import imaplib
from email.header import decode_header
from typing import Any

from airwallex_erpnext.providers.receipts.base import ReceiptCandidate, ReceiptProvider
from airwallex_erpnext.utils import normalize_merchant


class IMAPReceiptProvider(ReceiptProvider):
    """Generic optional provider. Credentials are supplied by deployment code, never stored in code."""

    def __init__(self, host: str, username: str, password: str, mailbox: str = "INBOX", port: int = 993):
        self.host = host
        self.username = username
        self.password = password
        self.mailbox = mailbox
        self.port = port

    def candidates(self, resource: dict[str, Any]) -> list[ReceiptCandidate]:
        merchant = normalize_merchant(resource.get("merchant"))
        if not merchant:
            return []
        client = imaplib.IMAP4_SSL(self.host, self.port)
        try:
            client.login(self.username, self.password)
            client.select(self.mailbox, readonly=True)
            # Restrict search to a merchant token and perform final scoring locally.
            token = merchant.split()[0]
            status, data = client.search(None, "TEXT", f'"{token}"')
            if status != "OK":
                return []
            ids = (data[0] or b"").split()[-50:]
            candidates: list[ReceiptCandidate] = []
            for message_id in reversed(ids):
                status, raw = client.fetch(message_id, "(RFC822)")
                if status != "OK" or not raw or not isinstance(raw[0], tuple):
                    continue
                message = email.message_from_bytes(raw[0][1])
                score = _score(message, resource)
                if score < 0.75:
                    continue
                for part in message.walk():
                    filename = part.get_filename()
                    disposition = str(part.get("Content-Disposition") or "")
                    if not filename or "attachment" not in disposition.casefold():
                        continue
                    content = part.get_payload(decode=True)
                    if content:
                        candidates.append(
                            ReceiptCandidate(
                                source_id=f"imap:{message_id.decode()}:{filename}",
                                file_name=_decode(filename),
                                content=content,
                                confidence=score,
                                metadata={"message_id": message.get("Message-ID")},
                            )
                        )
            return candidates
        finally:
            try:
                client.logout()
            except Exception:
                pass


def _decode(value: str) -> str:
    decoded = decode_header(value)
    return "".join(
        part.decode(charset or "utf-8", errors="replace") if isinstance(part, bytes) else part
        for part, charset in decoded
    )


def _score(message, resource: dict[str, Any]) -> float:
    haystack = " ".join([message.get("Subject", ""), message.get("From", "")]).casefold()
    merchant = normalize_merchant(resource.get("merchant"))
    score = 0.5 if merchant and merchant.split()[0] in haystack else 0.0
    amount = str(resource.get("billing_amount") or resource.get("amount") or "")
    if amount and amount in haystack:
        score += 0.3
    currency = str(resource.get("billing_currency") or resource.get("currency") or "").casefold()
    if currency and currency in haystack:
        score += 0.2
    return min(1.0, score)
