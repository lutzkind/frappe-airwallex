from __future__ import annotations

import hashlib
import hmac
import time

from airwallex_erpnext.exceptions import SignatureVerificationError


def verify_webhook_signature(*, raw_body: bytes, timestamp: str, signature: str, secret: str, tolerance_seconds: int = 300, now_ms: int | None = None) -> None:
    if not timestamp or not signature or not secret:
        raise SignatureVerificationError("Missing webhook signature inputs")
    message = timestamp.encode("utf-8") + raw_body
    expected = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise SignatureVerificationError("Invalid webhook signature")
    try:
        sent_ms = int(timestamp)
    except (TypeError, ValueError) as exc:
        raise SignatureVerificationError("Invalid webhook timestamp") from exc
    current_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    if abs(current_ms - sent_ms) > max(1, tolerance_seconds) * 1000:
        raise SignatureVerificationError("Webhook timestamp outside replay tolerance")
