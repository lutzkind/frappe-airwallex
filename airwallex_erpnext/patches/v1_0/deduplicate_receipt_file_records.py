from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe


def execute():
    """Remove duplicate File rows without deleting their shared private blobs.

    A historical SHA-256/MD5 mismatch allowed two File documents to reference
    the same receipt blob on the same Bank Transaction. Only groups with the
    same target, Frappe content hash, private flag, and file URL are eligible.
    The identity-bearing record is retained and the redundant database row is
    removed directly so the shared file on disk remains intact.
    """
    rows = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Bank Transaction",
            "is_private": 1,
            "content_hash": ["is", "set"],
            "file_url": ["is", "set"],
        },
        fields=[
            "name",
            "attached_to_name",
            "content_hash",
            "file_url",
            "custom_airwallex_attachment_id",
            "custom_airwallex_source_message_id",
            "creation",
        ],
        order_by="creation asc",
        limit_page_length=5000,
    )

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("attached_to_name") or ""),
            str(row.get("content_hash") or ""),
            str(row.get("file_url") or ""),
        )
        if all(key):
            groups[key].append(row)

    for group in groups.values():
        if len(group) < 2:
            continue
        keeper = max(group, key=_keeper_rank)
        for row in group:
            if row.get("name") == keeper.get("name"):
                continue
            frappe.db.delete("File", {"name": row.get("name")})


def _keeper_rank(row: dict[str, Any]) -> tuple[int, int, str]:
    return (
        int(bool(row.get("custom_airwallex_attachment_id"))),
        int(bool(row.get("custom_airwallex_source_message_id"))),
        str(row.get("creation") or ""),
    )
