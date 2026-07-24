# Webhooks

The webhook endpoint is:

```text
/api/method/airwallex_erpnext.api.webhook
```

Configure a unique webhook secret per Airwallex connection. The app verifies the signed body and timestamp within the configured replay tolerance before storing an event.

## Processing model

Webhook delivery is acknowledged into an **Airwallex Webhook Event** record with event ID, account, API version, payload hash, signature metadata, raw payload, status, attempts, and bounded error details. Processing occurs through the queue so web requests do not perform long synchronization work.

Duplicate event IDs are recognized. Duplicate delivery may update duplicate-delivery metadata, but it does not create a second integration record. Failed events can retry up to the configured attempt limit and then move to a dead-letter state.

## API version

Spend webhooks require an Airwallex API version of `2025-11-11` or newer in this release. Account enrolment and event availability may still differ. Treat Beta event families as capability-dependent.

## Operations

Use HTTPS, avoid query-string secrets, rotate webhook secrets after suspected exposure, and restrict the endpoint at the reverse proxy only in ways compatible with Airwallex delivery. Monitor retrying, failed, and dead-letter events. Scheduled recovery remains necessary because webhooks are notifications rather than the sole data source.
