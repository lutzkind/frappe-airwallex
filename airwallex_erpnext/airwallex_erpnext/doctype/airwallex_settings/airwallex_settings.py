import frappe
from frappe.model.document import Document


class AirwallexSettings(Document):
    def validate(self):
        if self.submit_accounting_documents and not self.create_accounting_documents:
            frappe.throw("Create Accounting Documents must be enabled before automatic submission")
        if self.mark_expenses_synced and not self.enable_expenses:
            frappe.throw("Card Expenses must be enabled before marking expenses synced")
        if self.webhook_tolerance_seconds and int(self.webhook_tolerance_seconds) < 30:
            frappe.throw("Webhook replay tolerance must be at least 30 seconds")
