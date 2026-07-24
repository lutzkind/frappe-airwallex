from __future__ import annotations

import base64
from typing import Any

import frappe
from frappe.utils.file_manager import save_file

from airwallex_erpnext.utils import content_hash


def attach_airwallex_receipts(settings, client, resource: dict[str, Any], doctype: str, docname: str) -> dict[str, Any]:
    attached = 0
    skipped = 0
    errors: list[str] = []
    for attachment in resource.get("attachments") or []:
        attachment_id = str(attachment.get("id") or "")
        if attachment_id and frappe.db.exists("File", {"custom_airwallex_attachment_id": attachment_id}):
            skipped += 1
            continue
        url = attachment.get("file_url")
        if not url:
            skipped += 1
            continue
        try:
            content, content_type = client.download(str(url))
            digest = content_hash(content)
            if frappe.db.exists("File", {"content_hash": digest, "attached_to_doctype": doctype, "attached_to_name": docname}):
                skipped += 1
                continue
            file_doc = save_file(
                attachment.get("file_name") or f"airwallex-{attachment_id}",
                content,
                doctype,
                docname,
                is_private=1,
            )
            file_doc.db_set("custom_airwallex_attachment_id", attachment_id, update_modified=False)
            attached += 1
        except Exception as exc:
            errors.append(f"{attachment_id or 'attachment'}: {type(exc).__name__}: {str(exc)[:300]}")
    return {"attached": attached, "skipped": skipped, "errors": errors}


def attach_compatibility_content(
    *,
    doctype: str,
    docname: str,
    file_name: str,
    content_b64: str,
    attachment_id: str | None = None,
    source_message_id: str | None = None,
) -> dict[str, Any]:
    content = base64.b64decode(content_b64, validate=True)
    digest = content_hash(content)
    filters = {"content_hash": digest, "attached_to_doctype": doctype, "attached_to_name": docname}
    existing = frappe.db.get_value("File", filters, "name")
    if existing:
        return {"status": "exists", "file": existing, "content_hash": digest}

    file_doc = save_file(file_name, content, doctype, docname, is_private=1)
    if attachment_id:
        file_doc.db_set("custom_airwallex_attachment_id", attachment_id, update_modified=False)
    if source_message_id:
        file_doc.db_set("custom_airwallex_source_message_id", source_message_id, update_modified=False)
    return {"status": "attached", "file": file_doc.name, "content_hash": digest}
