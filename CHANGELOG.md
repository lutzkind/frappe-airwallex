# Changelog

All notable changes are documented here.

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
