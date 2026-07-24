from __future__ import annotations

from airwallex_erpnext.providers.receipts.base import ReceiptCandidate, ReceiptProvider


class AirwallexReceiptProvider(ReceiptProvider):
    def __init__(self, client):
        self.client = client

    def candidates(self, resource):
        results = []
        for attachment in resource.get("attachments") or []:
            if not attachment.get("file_url"):
                continue
            content, _ = self.client.download(attachment["file_url"])
            results.append(
                ReceiptCandidate(
                    source_id=str(attachment.get("id") or attachment["file_url"]),
                    file_name=attachment.get("file_name") or "airwallex-receipt",
                    content=content,
                    metadata={"content_type": attachment.get("content_type")},
                )
            )
        return results
