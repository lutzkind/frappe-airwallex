from __future__ import annotations

from typing import Any

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ROLES = (
    "Airwallex Administrator",
    "Airwallex Accountant",
    "Airwallex Reviewer",
    "Airwallex Read Only",
)

CUSTOM_FIELDS: dict[str, list[dict[str, Any]]] = {
    "Bank Transaction": [
        {"fieldname": "custom_airwallex_section", "label": "Airwallex", "fieldtype": "Section Break", "insert_after": "description", "collapsible": 1},
        {"fieldname": "custom_airwallex_settings", "label": "Airwallex Settings", "fieldtype": "Link", "options": "Airwallex Settings", "insert_after": "custom_airwallex_section"},
        {"fieldname": "custom_airwallex_financial_transaction_id", "label": "Financial Transaction ID", "fieldtype": "Data", "unique": 1, "insert_after": "custom_airwallex_settings"},
        {"fieldname": "custom_airwallex_expense_id", "label": "Expense ID", "fieldtype": "Data", "unique": 1, "insert_after": "custom_airwallex_financial_transaction_id"},
        {"fieldname": "custom_airwallex_source_id", "label": "Source ID", "fieldtype": "Data", "insert_after": "custom_airwallex_expense_id"},
        {"fieldname": "custom_airwallex_source_type", "label": "Source Type", "fieldtype": "Data", "insert_after": "custom_airwallex_source_id"},
        {"fieldname": "custom_airwallex_transaction_type", "label": "Transaction Type", "fieldtype": "Data", "insert_after": "custom_airwallex_source_type"},
        {"fieldname": "custom_airwallex_batch_id", "label": "Batch ID", "fieldtype": "Data", "insert_after": "custom_airwallex_transaction_type"},
        {"fieldname": "custom_airwallex_business", "label": "Business Unit", "fieldtype": "Data", "insert_after": "custom_airwallex_batch_id"},
        {"fieldname": "custom_airwallex_cost_center", "label": "Mapped Cost Center", "fieldtype": "Link", "options": "Cost Center", "insert_after": "custom_airwallex_business"},
        {"fieldname": "custom_airwallex_expense_account", "label": "Mapped Expense Account", "fieldtype": "Link", "options": "Account", "insert_after": "custom_airwallex_cost_center"},
        {"fieldname": "custom_airwallex_purchase_invoice", "label": "Purchase Invoice", "fieldtype": "Link", "options": "Purchase Invoice", "insert_after": "custom_airwallex_expense_account"},
        {"fieldname": "custom_airwallex_receipt_state", "label": "Receipt State", "fieldtype": "Data", "insert_after": "custom_airwallex_purchase_invoice"},
        {"fieldname": "custom_airwallex_raw_hash", "label": "Payload Hash", "fieldtype": "Data", "read_only": 1, "insert_after": "custom_airwallex_receipt_state"},
    ],
    "Purchase Invoice": [
        {"fieldname": "custom_airwallex_section", "label": "Airwallex", "fieldtype": "Section Break", "insert_after": "remarks", "collapsible": 1},
        {"fieldname": "custom_airwallex_settings", "label": "Airwallex Settings", "fieldtype": "Link", "options": "Airwallex Settings", "insert_after": "custom_airwallex_section"},
        {"fieldname": "custom_airwallex_expense_id", "label": "Airwallex Expense ID", "fieldtype": "Data", "unique": 1, "insert_after": "custom_airwallex_settings"},
        {"fieldname": "custom_airwallex_bill_id", "label": "Airwallex Bill ID", "fieldtype": "Data", "unique": 1, "insert_after": "custom_airwallex_expense_id"},
        {"fieldname": "custom_airwallex_business", "label": "Business Unit", "fieldtype": "Data", "insert_after": "custom_airwallex_bill_id"},
        {"fieldname": "custom_airwallex_bank_transaction", "label": "Bank Transaction", "fieldtype": "Link", "options": "Bank Transaction", "insert_after": "custom_airwallex_business"},
        {"fieldname": "custom_airwallex_sync_status", "label": "Airwallex Sync Status", "fieldtype": "Data", "insert_after": "custom_airwallex_bank_transaction"},
        {"fieldname": "custom_airwallex_raw_hash", "label": "Payload Hash", "fieldtype": "Data", "read_only": 1, "insert_after": "custom_airwallex_sync_status"},
    ],
    "Payment Entry": [
        {"fieldname": "custom_airwallex_section", "label": "Airwallex", "fieldtype": "Section Break", "insert_after": "remarks", "collapsible": 1},
        {"fieldname": "custom_airwallex_settings", "label": "Airwallex Settings", "fieldtype": "Link", "options": "Airwallex Settings", "insert_after": "custom_airwallex_section"},
        {"fieldname": "custom_airwallex_payment_id", "label": "Airwallex Payment ID", "fieldtype": "Data", "unique": 1, "insert_after": "custom_airwallex_settings"},
        {"fieldname": "custom_airwallex_financial_transaction_id", "label": "Financial Transaction ID", "fieldtype": "Data", "insert_after": "custom_airwallex_payment_id"},
    ],
    "Expense Claim": [
        {"fieldname": "custom_airwallex_section", "label": "Airwallex", "fieldtype": "Section Break", "insert_after": "remark", "collapsible": 1},
        {"fieldname": "custom_airwallex_settings", "label": "Airwallex Settings", "fieldtype": "Link", "options": "Airwallex Settings", "insert_after": "custom_airwallex_section"},
        {"fieldname": "custom_airwallex_reimbursement_id", "label": "Airwallex Reimbursement ID", "fieldtype": "Data", "unique": 1, "insert_after": "custom_airwallex_settings"},
        {"fieldname": "custom_airwallex_sync_status", "label": "Airwallex Sync Status", "fieldtype": "Data", "insert_after": "custom_airwallex_reimbursement_id"},
        {"fieldname": "custom_airwallex_raw_hash", "label": "Payload Hash", "fieldtype": "Data", "read_only": 1, "insert_after": "custom_airwallex_sync_status"},
    ],
    "Journal Entry": [
        {"fieldname": "custom_airwallex_section", "label": "Airwallex", "fieldtype": "Section Break", "insert_after": "user_remark", "collapsible": 1},
        {"fieldname": "custom_airwallex_settings", "label": "Airwallex Settings", "fieldtype": "Link", "options": "Airwallex Settings", "insert_after": "custom_airwallex_section"},
        {"fieldname": "custom_airwallex_conversion_id", "label": "Airwallex Conversion ID", "fieldtype": "Data", "unique": 1, "insert_after": "custom_airwallex_settings"},
        {"fieldname": "custom_airwallex_raw_hash", "label": "Payload Hash", "fieldtype": "Data", "read_only": 1, "insert_after": "custom_airwallex_conversion_id"},
    ],
    "File": [
        {"fieldname": "custom_airwallex_attachment_id", "label": "Airwallex Attachment ID", "fieldtype": "Data", "insert_after": "content_hash"},
        {"fieldname": "custom_airwallex_source_message_id", "label": "Receipt Source Message ID", "fieldtype": "Data", "insert_after": "custom_airwallex_attachment_id"},
    ],
}


def after_install():
    create_roles()
    create_fields()
    create_workspace()
    create_default_document_types()


def after_migrate():
    create_roles()
    create_fields()
    create_workspace()


def create_roles():
    for role in ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


def create_fields():
    # HRMS-owned DocTypes such as Expense Claim are optional in ERPNext v16.
    # Install all available integration fields without making the whole app
    # installation fail when an optional app is absent.
    available = {
        doctype: fields
        for doctype, fields in CUSTOM_FIELDS.items()
        if frappe.db.exists("DocType", doctype)
    }
    create_custom_fields(available, update=True)


def create_workspace():
    name = "Airwallex Banking"
    if frappe.db.exists("Workspace", name):
        return
    doc = frappe.get_doc(
        {
            "doctype": "Workspace",
            "title": name,
            "label": name,
            "module": "Airwallex ERPNext",
            "public": 1,
            "is_hidden": 0,
            "icon": "bank",
            "content": "[]",
            "links": [
                {"type": "Link", "label": "Settings", "link_type": "DocType", "link_to": "Airwallex Settings"},
                {"type": "Link", "label": "Account Mappings", "link_type": "DocType", "link_to": "Airwallex Account Mapping"},
                {"type": "Link", "label": "Mapping Rules", "link_type": "DocType", "link_to": "Airwallex Mapping Rule"},
                {"type": "Link", "label": "Webhook Events", "link_type": "DocType", "link_to": "Airwallex Webhook Event"},
                {"type": "Link", "label": "Sync Logs", "link_type": "DocType", "link_to": "Airwallex Sync Log"},
                {"type": "Link", "label": "Reconciliation Proposals", "link_type": "DocType", "link_to": "Airwallex Reconciliation Proposal"},
                {"type": "Link", "label": "Receipt Matches", "link_type": "DocType", "link_to": "Airwallex Receipt Match"},
                {"type": "Link", "label": "Bank Transactions", "link_type": "DocType", "link_to": "Bank Transaction"},
            ],
        }
    )
    doc.insert(ignore_permissions=True)


def create_default_document_types():
    # Reserved for future seeded document types. Kept idempotent for install contracts.
    return None
