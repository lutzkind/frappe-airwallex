from __future__ import annotations

from typing import Any

try:
    import frappe
except ImportError:
    frappe = None


def require_frappe():
    if frappe is None:
        raise RuntimeError("Frappe runtime is required")
    return frappe


def get_settings(name: str):
    return require_frappe().get_doc("Airwallex Settings", name)


def get_client(settings):
    from airwallex_erpnext.client import AirwallexClient
    api_key = settings.get_password("api_key", raise_exception=False)
    if not api_key:
        raise ValueError(f"Airwallex Settings {settings.name} has no API key")
    return AirwallexClient(base_url=settings.api_base_url, client_id=settings.client_id, api_key=api_key, login_as=settings.account_id or None, timeout_seconds=int(settings.timeout_seconds or 30))


def log_sync(settings_name: str, module: str, status: str, **values: Any):
    f = require_frappe()
    doc = f.get_doc({"doctype": "Airwallex Sync Log", "settings": settings_name, "module": module, "status": status, "started_at": f.utils.now_datetime(), **values})
    doc.insert(ignore_permissions=True)
    return doc
