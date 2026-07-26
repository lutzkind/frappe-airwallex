# Webhooks

The webhook endpoint is:

```text
/api/method/airwallex_erpnext.api.webhook
```

Webhook subscriptions are managed from the **Airwallex Settings** form. Use the **Webhooks** button group to:

- **Check Webhook** — compare Airwallex with the URL, API version, event set, and secret stored in Frappe.
- **Create / Repair Webhook** — create the subscription, adopt a matching one, or replace outdated and duplicate subscriptions for this exact ERPNext URL.
- **Remove Webhook** — remove only subscriptions that target this exact ERPNext URL and clear their local signing metadata.

The app does not modify unrelated Airwallex subscriptions. The signing secret returned by Airwallex is stored only in the Frappe Password field. Subscription ID, URL, events, status, and last-check time are visible as read-only metadata.

## Processing model

Webhook delivery is acknowledged into an **Airwallex Webhook Event** record with event ID, account, API version, payload hash, signature metadata, raw payload, status, attempts, and bounded error details. Processing occurs through the queue so web requests do not perform long synchronization work.

Duplicate event IDs are recognized. Duplicate delivery may update duplicate-delivery metadata, but it does not create a second integration record. Failed events can retry up to the configured attempt limit and then move to a dead-letter state.

## API version and events

Spend webhooks require an Airwallex API version of `2025-11-11` or newer. The managed subscription follows the enabled modules:

- **Card Expenses** subscribes to all published `spend.expense.*` lifecycle events.
- **Reimbursements** subscribes to all published `spend.reimbursement_report.*` lifecycle events.

Airwallex does not allow an existing subscription's event set or API version to be changed. When either differs, the app replaces only the subscription for this exact callback URL and then verifies the resulting state through the Airwallex API.

## Operations

Use HTTPS, avoid query-string secrets, rotate webhook secrets after suspected exposure, and restrict the endpoint at the reverse proxy only in ways compatible with Airwallex delivery. Monitor retrying, failed, and dead-letter events. Scheduled recovery remains enabled because webhooks are notifications rather than the sole data source.
