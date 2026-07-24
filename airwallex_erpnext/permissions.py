from __future__ import annotations

import frappe


def _is_admin(user: str | None = None) -> bool:
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    return bool({"System Manager", "Airwallex Administrator"} & roles)


def event_query(user: str | None = None) -> str:
    return "" if _is_admin(user) else "1=0"


def sync_log_query(user: str | None = None) -> str:
    roles = set(frappe.get_roles(user or frappe.session.user))
    return "" if roles & {"System Manager", "Airwallex Administrator", "Airwallex Accountant", "Airwallex Reviewer"} else "1=0"


def settings_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
    roles = set(frappe.get_roles(user or frappe.session.user))
    if permission_type in {"write", "create", "delete", "submit", "cancel"}:
        return bool(roles & {"System Manager", "Airwallex Administrator"})
    return bool(roles & {"System Manager", "Airwallex Administrator", "Airwallex Accountant", "Airwallex Reviewer", "Airwallex Read Only"})
