# Changelog

All notable changes are documented here.

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

- Frappe 16 and ERPNext 16.
- Transitional compatibility receipt endpoint retained pending tested native receipt parity.

### Known limitations

- Airwallex product and Beta API availability varies by account and region.
- Native receipt access and supplier-payment representations require account-specific validation.
- Marketplace approval has not been requested or granted.
