def settings_updated(doc, method=None):
    if doc.has_value_changed("api_key") or doc.has_value_changed("client_id"):
        doc.db_set("last_connection_status", "Not Tested", update_modified=False)
