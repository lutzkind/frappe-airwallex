from __future__ import annotations

import base64
from collections import defaultdict
from typing import Any

import frappe
from frappe.utils.file_manager import get_content_hash as frappe_content_hash
from frappe.utils.file_manager import save_file

from airwallex_erpnext.providers.receipts.airwallex import AirwallexReceiptProvider
from airwallex_erpnext.providers.receipts.base import ReceiptCandidate
from airwallex_erpnext.providers.receipts.frappe_email import FrappeEmailReceiptProvider
from airwallex_erpnext.providers.receipts.imap import IMAPReceiptProvider
from airwallex_erpnext.utils import content_hash


def attach_provider_receipts(settings, client, resource: dict[str, Any], doctype: str, docname: str) -> dict[str, Any]:
    provider_name = str(settings.receipt_provider or "Disabled")
    result: dict[str, Any] = {
        "provider": provider_name,
        "status": "missing",
        "attached": 0,
        "skipped": 0,
        "errors": [],
        "candidates": 0,
    }
    if provider_name in {"Disabled", "Manual"}:
        result["status"] = "manual" if provider_name == "Manual" else "disabled"
        return result

    try:
        candidates = _provider_candidates(settings, client, resource, provider_name)
    except Exception as exc:
        result["status"] = "error"
        result["errors"].append(f"provider: {type(exc).__name__}: {str(exc)[:500]}")
        _record_match(
            settings=settings,
            resource=resource,
            bank_transaction=docname,
            provider=provider_name,
            status="Held",
            details=result,
        )
        return result

    result["candidates"] = len(candidates)
    selected, ambiguous = _select_candidates(provider_name, candidates)
    if ambiguous:
        result["status"] = "ambiguous"
        result["candidate_groups"] = ambiguous
        _record_match(
            settings=settings,
            resource=resource,
            bank_transaction=docname,
            provider=provider_name,
            status="Held",
            confidence=float(ambiguous[0]["confidence"]),
            details=result,
        )
        return result

    for candidate in selected:
        try:
            outcome = _attach_candidate(candidate=candidate, doctype=doctype, docname=docname)
            result[outcome] += 1
        except Exception as exc:
            result["errors"].append(f"{candidate.source_id}: {type(exc).__name__}: {str(exc)[:500]}")

    if result["attached"] or result["skipped"]:
        result["status"] = "attached"
    elif result["errors"]:
        result["status"] = "error"

    source_message_id = _source_message_id(selected[0]) if selected else None
    confidence = max((candidate.confidence for candidate in selected), default=0.0)
    _record_match(
        settings=settings,
        resource=resource,
        bank_transaction=docname,
        provider=provider_name,
        source_message_id=source_message_id,
        confidence=confidence,
        status="Attached" if result["status"] == "attached" else "Held",
        details=result,
    )
    return result


def attach_airwallex_receipts(settings, client, resource: dict[str, Any], doctype: str, docname: str) -> dict[str, Any]:
    """Backward-compatible wrapper for callers outside the app."""
    original = settings.receipt_provider
    try:
        settings.receipt_provider = "Airwallex"
        return attach_provider_receipts(settings, client, resource, doctype, docname)
    finally:
        settings.receipt_provider = original


def _provider_candidates(settings, client, resource: dict[str, Any], provider_name: str) -> list[ReceiptCandidate]:
    # Compatibility API is migrated to Airwallex. Treat it as Airwallex during a
    # rolling deployment so no external compatibility service is required.
    if provider_name in {"Airwallex", "Compatibility API"}:
        return AirwallexReceiptProvider(client).candidates(resource)

    if provider_name == "Frappe Email Account":
        return FrappeEmailReceiptProvider(settings.receipt_email_account).candidates(resource)

    if provider_name == "Airwallex + Frappe Email Account":
        airwallex = AirwallexReceiptProvider(client).candidates(resource)
        if airwallex:
            return airwallex
        return FrappeEmailReceiptProvider(settings.receipt_email_account).candidates(resource)

    if provider_name == "IMAP":
        provider = IMAPReceiptProvider(
            host=settings.imap_host,
            username=settings.imap_username,
            password=settings.get_password("imap_password", raise_exception=False),
            mailbox=settings.imap_mailbox or "INBOX",
            port=int(settings.imap_port or 993),
        )
        return provider.candidates(resource)

    return []


def _select_candidates(
    provider_name: str,
    candidates: list[ReceiptCandidate],
) -> tuple[list[ReceiptCandidate], list[dict[str, Any]]]:
    if not candidates:
        return [], []
    if provider_name in {"Airwallex", "Compatibility API"} or all(
        (candidate.metadata or {}).get("provider") == "Airwallex" for candidate in candidates
    ):
        return candidates, []

    groups: dict[str, list[ReceiptCandidate]] = defaultdict(list)
    for candidate in candidates:
        groups[_source_message_id(candidate) or candidate.source_id].append(candidate)

    ranked = sorted(
        groups.items(),
        key=lambda item: max(candidate.confidence for candidate in item[1]),
        reverse=True,
    )
    top_key, top_candidates = ranked[0]
    top_confidence = max(candidate.confidence for candidate in top_candidates)
    ambiguity = [
        {
            "source_message_id": key,
            "confidence": max(candidate.confidence for candidate in group),
            "files": [candidate.file_name for candidate in group],
        }
        for key, group in ranked[:5]
        if key != top_key and max(candidate.confidence for candidate in group) >= top_confidence - 0.05
    ]
    if ambiguity:
        ambiguity.insert(
            0,
            {
                "source_message_id": top_key,
                "confidence": top_confidence,
                "files": [candidate.file_name for candidate in top_candidates],
            },
        )
        return [], ambiguity
    return top_candidates, []


def _attach_candidate(*, candidate: ReceiptCandidate, doctype: str, docname: str) -> str:
    metadata = candidate.metadata or {}
    attachment_id = str(metadata.get("attachment_id") or candidate.source_id or "")[:140]
    source_message_id = _source_message_id(candidate)

    if attachment_id and frappe.db.exists("File", {"custom_airwallex_attachment_id": attachment_id}):
        return "skipped"

    digest = content_hash(candidate.content)
    filters = {"content_hash": digest, "attached_to_doctype": doctype, "attached_to_name": docname}
    if frappe.db.exists("File", filters):
        return "skipped"

    file_doc = save_file(candidate.file_name, candidate.content, doctype, docname, is_private=1)
    if attachment_id:
        file_doc.db_set("custom_airwallex_attachment_id", attachment_id, update_modified=False)
    if source_message_id:
        file_doc.db_set("custom_airwallex_source_message_id", source_message_id[:140], update_modified=False)
    return "attached"


def _source_message_id(candidate: ReceiptCandidate) -> str | None:
    metadata = candidate.metadata or {}
    value = metadata.get("message_id") or metadata.get("source_message_id")
    return str(value) if value else None


def _record_match(
    *,
    settings,
    resource: dict[str, Any],
    bank_transaction: str,
    provider: str,
    status: str,
    source_message_id: str | None = None,
    confidence: float = 0.0,
    details: dict[str, Any] | None = None,
) -> None:
    expense_id = str(resource.get("id") or "")
    if not expense_id or not frappe.db.exists("DocType", "Airwallex Receipt Match"):
        return

    filters = {
        "settings": settings.name,
        "expense_id": expense_id,
        "source_provider": provider,
        "source_message_id": source_message_id or "",
    }
    existing = frappe.db.get_value("Airwallex Receipt Match", filters, "name")
    values = {
        "bank_transaction": bank_transaction,
        "confidence": float(confidence or 0),
        "status": status,
        "details": frappe.as_json(details or {}),
    }
    if existing:
        frappe.db.set_value("Airwallex Receipt Match", existing, values, update_modified=False)
        return

    frappe.get_doc({"doctype": "Airwallex Receipt Match", **filters, **values}).insert(ignore_permissions=True)


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
