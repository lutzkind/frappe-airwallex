from __future__ import annotations

import frappe


def enabled_settings():
    return frappe.get_all("Airwallex Settings", filters={"enabled": 1}, pluck="name")


def process_webhook_queue():
    from airwallex_erpnext.services.webhooks import process_event

    names = frappe.get_all(
        "Airwallex Webhook Event",
        filters={"status": ["in", ["Received", "Retrying"]]},
        order_by="creation asc",
        limit=100,
        pluck="name",
    )
    for name in names:
        frappe.enqueue(process_event, queue="short", event_name=name, job_name=f"airwallex-event-{name}")


def hourly_recovery():
    from airwallex_erpnext.services.sync import run_sync

    for settings in enabled_settings():
        frappe.enqueue(run_sync, queue="long", settings_name=settings, module="incremental", job_name=f"airwallex-hourly-{settings}")


def daily_recovery():
    from airwallex_erpnext.services.sync import run_sync

    for settings in enabled_settings():
        frappe.enqueue(run_sync, queue="long", settings_name=settings, module="all", job_name=f"airwallex-daily-{settings}")


def cleanup_old_events():
    cutoff = frappe.utils.add_days(frappe.utils.now_datetime(), -90)
    frappe.db.delete("Airwallex Webhook Event", {"modified": ["<", cutoff], "status": ["in", ["Processed", "Ignored"]]})
    frappe.db.commit()
