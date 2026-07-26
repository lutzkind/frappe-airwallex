app_name = "airwallex_erpnext"
app_title = "Frappe Airwallex"
app_publisher = "Frappe Airwallex contributors"
app_description = "Airwallex banking, Spend, AP, reimbursements, FX, receipts, and reconciliation for ERPNext"
app_email = "maintainers@invalid.example"
app_license = "GPL-3.0-or-later"
required_apps = ["erpnext"]

after_install = "airwallex_erpnext.install.after_install"
after_migrate = "airwallex_erpnext.install.after_migrate"

scheduler_events = {
    "cron": {
        "*/5 * * * *": [
            "airwallex_erpnext.tasks.process_webhook_queue",
        ],
        "17 * * * *": [
            "airwallex_erpnext.tasks.hourly_recovery",
        ],
        "47 * * * *": [
            "airwallex_erpnext.services.webhook_management.reconcile_enabled_subscriptions",
        ],
        "35 3 * * *": [
            "airwallex_erpnext.tasks.daily_recovery",
        ],
    },
    "daily": [
        "airwallex_erpnext.tasks.cleanup_old_events",
    ],
}

doc_events = {
    "Airwallex Settings": {
        "on_update": "airwallex_erpnext.events.settings_updated",
    }
}

permission_query_conditions = {
    "Airwallex Webhook Event": "airwallex_erpnext.permissions.event_query",
    "Airwallex Sync Log": "airwallex_erpnext.permissions.sync_log_query",
}

has_permission = {
    "Airwallex Settings": "airwallex_erpnext.permissions.settings_permission",
}

website_route_rules = [
    {"from_route": "/airwallex/webhook", "to_route": "airwallex_erpnext.api.webhook"},
]
