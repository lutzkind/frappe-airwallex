import hashlib
import hmac

import pytest

from airwallex_erpnext.exceptions import SignatureVerificationError
from airwallex_erpnext.security import verify_webhook_signature


def test_webhook_signature_and_replay_window():
    body = b'{"id":"evt_1"}'
    timestamp = "1700000000000"
    secret = "secret"
    signature = hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256).hexdigest()
    verify_webhook_signature(raw_body=body, timestamp=timestamp, signature=signature, secret=secret, now_ms=1700000000000)


def test_webhook_signature_rejects_modified_body():
    body = b'{"id":"evt_1"}'
    timestamp = "1700000000000"
    secret = "secret"
    signature = hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256).hexdigest()
    with pytest.raises(SignatureVerificationError):
        verify_webhook_signature(raw_body=b'{"id":"evt_2"}', timestamp=timestamp, signature=signature, secret=secret, now_ms=1700000000000)
