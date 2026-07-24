from __future__ import annotations

from typing import Any

import frappe

from airwallex_erpnext.frappe_support import get_client, get_settings

PROBES = {
    "financial_transactions": ("/api/v1/financial_transactions", {"page_size": 1}),
    "expenses": ("/api/v1/spend/expenses", {}),
    "bills": ("/api/v1/spend/bills", {}),
    "reimbursements": ("/api/v1/spend/reimbursement_reports", {}),
    "webhooks": ("/api/v1/webhooks", {}),
    "balances": ("/api/v1/balances/current", {}),
    "transfers": ("/api/v1/transfers", {}),
}


def discover(settings_name: str) -> dict[str, Any]:
    settings = get_settings(settings_name)
    client = get_client(settings)
    results: dict[str, Any] = {}
    for capability, (path, params) in PROBES.items():
        status = "Available"
        message = ""
        try:
            client.request("GET", path, params=params)
        except Exception as exc:
            text = f"{type(exc).__name__}: {str(exc)[:300]}"
            if "403" in text or "Permission" in text:
                status = "Missing Permission"
            elif "404" in text:
                status = "Unavailable"
            else:
                status = "Error"
            message = text
        results[capability] = {"status": status, "message": message}
        _upsert(settings.name, capability, status, message)

    if not frappe.db.exists("DocType", "Expense Claim"):
        results["reimbursements"] = {
            "status": "Not Configured",
            "message": "Airwallex API is reachable, but the optional HRMS Expense Claim DocType is not installed.",
        }
        _upsert(settings.name, "reimbursements", results["reimbursements"]["status"], results["reimbursements"]["message"])

    bills_status = results.get("bills", {}).get("status")
    results["supplier_payments"] = {
        "status": "Available" if bills_status == "Available" else bills_status or "Unavailable",
        "message": "Derived from bill_payments in full Bill responses; no separate Spend payment-list endpoint is required.",
    }
    _upsert(settings.name, "supplier_payments", results["supplier_payments"]["status"], results["supplier_payments"]["message"])
    settings.db_set("last_connection_status", "Connected" if any(v["status"] == "Available" for v in results.values()) else "Failed")
    settings.db_set("last_connection_test", frappe.utils.now_datetime())
    return {"settings": settings.name, "capabilities": results}


def _upsert(settings: str, capability: str, status: str, message: str):
    name = frappe.db.get_value("Airwallex Capability", {"settings": settings, "capability": capability}, "name")
    values = {
        "settings": settings,
        "capability": capability,
        "status": status,
        "message": message,
        "last_checked": frappe.utils.now_datetime(),
    }
    if name:
        frappe.db.set_value(
            "Airwallex Capability",
            name,
            {
                "status": status,
                "message": message,
                "last_checked": values["last_checked"],
            },
            update_modified=False,
        )
    else:
        frappe.get_doc({"doctype": "Airwallex Capability", **values}).insert(ignore_permissions=True)
