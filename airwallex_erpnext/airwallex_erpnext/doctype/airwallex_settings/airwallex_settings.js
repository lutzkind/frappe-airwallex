frappe.ui.form.on("Airwallex Settings", {
    refresh(frm) {
        if (frm.is_new()) return;

        frm.add_custom_button(__("Discover Capabilities"), () => {
            frappe.call({
                method: "airwallex_erpnext.api.discover_capabilities",
                args: { settings: frm.doc.name },
                freeze: true,
                callback: () => frm.reload_doc(),
            });
        });

        frm.add_custom_button(__("Sync Now"), () => {
            frappe.call({
                method: "airwallex_erpnext.api.sync_now",
                args: { settings: frm.doc.name, module: "all", dry_run: 0 },
                freeze: true,
                callback: (r) => show_result(__("Airwallex Sync"), r.message),
            });
        });

        frm.add_custom_button(__("Check Webhook"), () => {
            frappe.call({
                method: "airwallex_erpnext.api.webhook_status",
                args: { settings: frm.doc.name },
                freeze: true,
                callback: (r) => {
                    show_result(__("Airwallex Webhook"), r.message);
                    frm.reload_doc();
                },
            });
        }, __("Webhooks"));

        frm.add_custom_button(__("Create / Repair Webhook"), () => {
            frappe.call({
                method: "airwallex_erpnext.api.ensure_webhook_subscription",
                args: { settings: frm.doc.name },
                freeze: true,
                callback: (r) => {
                    show_result(__("Airwallex Webhook"), r.message);
                    frm.reload_doc();
                },
            });
        }, __("Webhooks"));

        frm.add_custom_button(__("Remove Webhook"), () => {
            frappe.confirm(
                __("Remove the Airwallex webhook subscription for this ERPNext endpoint? Scheduled API recovery will remain active."),
                () => {
                    frappe.call({
                        method: "airwallex_erpnext.api.remove_webhook_subscription",
                        args: { settings: frm.doc.name },
                        freeze: true,
                        callback: (r) => {
                            show_result(__("Airwallex Webhook"), r.message);
                            frm.reload_doc();
                        },
                    });
                },
            );
        }, __("Webhooks"));
    },

    environment(frm) {
        frm.set_value("api_base_url", frm.doc.environment === "Demo" ? "https://api-demo.airwallex.com" : "https://api.airwallex.com");
    },
});

function show_result(title, result) {
    frappe.msgprint({
        title,
        message: `<pre>${frappe.utils.escape_html(JSON.stringify(result, null, 2))}</pre>`,
    });
}
