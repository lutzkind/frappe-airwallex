from __future__ import annotations

from airwallex_erpnext.providers.receipts.base import ReceiptProvider


class CompatibilityReceiptProvider(ReceiptProvider):
    def candidates(self, resource):
        # Receipts arrive through the authenticated compatibility API.
        return []
