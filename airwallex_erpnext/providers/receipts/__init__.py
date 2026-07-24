from airwallex_erpnext.providers.receipts.airwallex import AirwallexReceiptProvider
from airwallex_erpnext.providers.receipts.compatibility import CompatibilityReceiptProvider
from airwallex_erpnext.providers.receipts.imap import IMAPReceiptProvider
from airwallex_erpnext.providers.receipts.manual import ManualReceiptProvider

PROVIDERS = {
    "Airwallex": AirwallexReceiptProvider,
    "Compatibility API": CompatibilityReceiptProvider,
    "IMAP": IMAPReceiptProvider,
    "Manual": ManualReceiptProvider,
}
