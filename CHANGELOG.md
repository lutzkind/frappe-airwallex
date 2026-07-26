# Changelog

All notable changes are documented here.

## [1.0.11] - 2026-07-26

### Added

- Queue a strict post-migration webhook verification job after the database transaction commits.
- Make an unhealthy enabled subscription fail visibly in the normal Frappe worker logs while keeping hourly recovery best-effort.

## [1.0.10] - 2026-07-26

### Added

- Automatically reconcile enabled Airwallex webhook subscriptions after site migration and every hour.
- Retry temporary Airwallex API failures without blocking ERPNext startup or scheduled transaction recovery.
- Persist a bounded connection status and emit a sanitized reconciliation summary for operations.

## [1.0.9] - 2026-07-26

### Added

- Manage the Airwallex webhook subscription directly from Airwallex Settings.
- Check, create, adopt, repair, deduplicate, verify, and remove the ERPNext webhook without external scripts.
- Store the Airwallex signing secret and subscription state in Frappe Password and read-only metadata fields.

### Security

- Restrict webhook management actions to System Manager and Airwallex Administrator roles.
- Verify the exact callback URL, API version, event set, signing secret, and post-deletion state through the Airwallex API.

## [1.0.8] - 2026-07-25

### Fixed

- Populate the Airwallex Banking workspace with renderable Frappe v16 cards and shortcuts.

## [1.0.7] - 2026-07-25

### Fixed

- Compare receipt bytes against Frappe's MD5 `File.content_hash` instead of the integration's SHA-256 payload hash.
- Prevent duplicate private File records when a receipt is reprocessed.
- Remove only exact historical duplicate File rows that share the same Bank Transaction, content hash, and private file URL while preserving the identity-bearing record and physical blob.

## [1.0.6] - 2026-07-25

### Added

- Add a Frappe Email Account receipt provider that uses ERPNext-managed incoming email and private Communication attachments.
- Add a combined Airwallex-first provider with Frappe mailbox fallback.
- Record mailbox matches and ambiguous candidates in Airwallex Receipt Match.

### Changed

- Run all receipt discovery through providers owned by the Frappe application.
- Migrate legacy Compatibility API settings to native Airwallex attachment retrieval.
- Keep webhook processing, hourly recovery, daily recovery, and receipt collection inside Frappe without external orchestration scripts.

## [1.0.5] - 2026-07-24

### Fixed

- Convert timezone-naive Frappe `Datetime` sync cursors from the configured site timezone to UTC before calling Airwallex.
- Prevent `invalid_argument` failures when incremental Spend expense synchronization sends `from_created_at`.
- Add regression tests for site-local and timezone-aware timestamp normalization.

## [1.0.4] - 2026-07-24

### Added

- Initial standalone community Release 1.
- Banking balances and wallet financial-transaction ingestion.
- Spend card-expense ingestion and private receipt attachment providers.
- Bills, supplier-payment, reimbursement, transfer, and FX service layers.
- Signed webhook queue, scheduled recovery, and long-queue background synchronization.
- Existing-data adoption, reconciliation proposals, duplicate prevention, and payload lineage.
- Independent posting, submission, supplier, FX-journal, and Airwallex write-back safeguards.

### Compatibility

- Frappe v16 / ERPNext v16.
- Python 3.12+ within the versions supported by Frappe v16.
