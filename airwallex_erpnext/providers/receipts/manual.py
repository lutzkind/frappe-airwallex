from __future__ import annotations

from airwallex_erpnext.providers.receipts.base import ReceiptProvider


class ManualReceiptProvider(ReceiptProvider):
    def candidates(self, resource):
        return []
