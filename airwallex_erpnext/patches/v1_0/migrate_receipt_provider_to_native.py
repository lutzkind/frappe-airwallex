from __future__ import annotations

import frappe


def execute():
    """Remove runtime dependency on the retired external compatibility service.

    Existing private File attachments and Receipt Match records are preserved.
    Connections can later opt into the Frappe Email Account provider from the
    Airwallex Settings form after an incoming mailbox has been authorized.
    """
    names = frappe.get_all(
        "Airwallex Settings",
        filters={"receipt_provider": "Compatibility API"},
        pluck="name",
        limit_page_length=1000,
    )
    for name in names:
        frappe.db.set_value(
            "Airwallex Settings",
            name,
            "receipt_provider",
            "Airwallex",
            update_modified=False,
        )
