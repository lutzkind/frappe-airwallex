frappe.ui.form.on("Airwallex Settings", {
    refresh(frm) {
        if (!frm.is_new()) {
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
                    callback: (r) => frappe.msgprint({ title: __("Airwallex Sync"), message: `<pre>${frappe.utils.escape_html(JSON.stringify(r.message, null, 2))}</pre>` }),
                });
            });
        }
    },
    environment(frm) {
        frm.set_value("api_base_url", frm.doc.environment === "Demo" ? "https://api-demo.airwallex.com" : "https://api.airwallex.com");
    },
});
