from email.message import EmailMessage

from airwallex_erpnext.providers.receipts.imap import _score


def test_imap_scoring():
    message = EmailMessage()
    message["Subject"] = "Cloudflare receipt USD 20.92"
    message["From"] = "receipts@example.invalid"
    score = _score(message, {"merchant": "Cloudflare", "billing_amount": "20.92", "billing_currency": "USD"})
    assert score == 1.0
