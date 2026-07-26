from datetime import date

import frappe
from frappe.model.document import Document

FRAPPE_EMAIL_PROVIDERS = {"Frappe Email Account", "Airwallex + Frappe Email Account"}
MINIMUM_SPEND_WEBHOOK_VERSION = date(2025, 11, 11)


class AirwallexSettings(Document):
    def validate(self):
        if self.submit_accounting_documents and not self.create_accounting_documents:
            frappe.throw("Create Accounting Documents must be enabled before automatic submission")
        if self.mark_expenses_synced and not self.enable_expenses:
            frappe.throw("Card Expenses must be enabled before marking expenses synced")
        if self.webhook_tolerance_seconds and int(self.webhook_tolerance_seconds) < 30:
            frappe.throw("Webhook replay tolerance must be at least 30 seconds")
        self._validate_webhook_version()
        self._validate_receipt_provider()

    def _validate_webhook_version(self):
        version = str(self.webhook_version or "").strip()
        try:
            parsed = date.fromisoformat(version)
        except ValueError:
            frappe.throw("Webhook API Version must use YYYY-MM-DD format")
        if (self.enable_expenses or self.enable_reimbursements) and parsed < MINIMUM_SPEND_WEBHOOK_VERSION:
            frappe.throw("Spend webhooks require Airwallex API version 2025-11-11 or newer")

    def _validate_receipt_provider(self):
        provider = str(self.receipt_provider or "Disabled")
        if provider in FRAPPE_EMAIL_PROVIDERS:
            if not self.receipt_email_account:
                frappe.throw("Receipt Email Account is required for the selected receipt provider")
            account = frappe.get_cached_doc("Email Account", self.receipt_email_account)
            if not account.enable_incoming:
                frappe.throw("The selected Receipt Email Account must have incoming email enabled")

        if provider == "IMAP":
            missing = [
                label
                for label, value in (
                    ("IMAP Host", self.imap_host),
                    ("IMAP Username", self.imap_username),
                    ("IMAP Password", self.get_password("imap_password", raise_exception=False)),
                )
                if not value
            ]
            if missing:
                frappe.throw(f"The IMAP receipt provider requires: {', '.join(missing)}")
