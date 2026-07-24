# Architecture

The app is a conventional Frappe application. It stores connection configuration and audit records in dedicated DocTypes, adds Airwallex lineage fields to selected ERPNext documents, and separates external API access from accounting services.

## Main layers

1. **Client** — authenticates, caches the access token in process memory, performs bounded requests and downloads, maps HTTP errors, and supports bookmark and numbered pagination.
2. **Capability discovery** — probes only known Airwallex endpoints and stores Available, Unavailable, Beta, Missing Permission, Not Configured, or Error status per connection.
3. **Services** — banking, balances, expenses, bills, payments, reimbursements, transfers, FX, receipts, migration, reconciliation, and webhook processing.
4. **Frappe API** — whitelisted methods for capability discovery, queued sync, job polling, webhook ingestion, migration reporting, catalog export, and reconciliation proposals.
5. **Background execution** — potentially long synchronizations are enqueued on the long queue; compact job state is cached for safe polling. Scheduler tasks process webhooks and recovery runs.
6. **Audit and lineage** — Airwallex identifiers, source types, payload hashes, settings references, sync logs, and webhook events make retries inspectable.

## Data ownership

Card purchases are owned by the Spend expense feed and excluded from wallet financial-transaction ingestion, preventing a second Bank Transaction for the same card movement. Wallet transactions use the Airwallex financial-transaction ID. Spend expenses use the Airwallex expense ID.

## Failure behavior

Missing identifiers, mappings, suppliers, employees, capabilities, or approved statuses produce held/excluded results rather than speculative posting. API failures mark the sync log failed and preserve the previous successful-sync timestamp. Webhook events move through explicit processing states and retain a bounded error description.

## Extension points

Receipt providers implement a small candidate interface. Mapping rules are data driven. New modules should preserve stable external IDs, dry-run parity, bounded pagination, per-connection scoping, and independent posting controls.
