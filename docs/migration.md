# Migration

The migration service adopts existing Airwallex-linked ERPNext records without recreating them.

## Existing-data adoption

`adopt_legacy_records(settings_name, dry_run=True)` scans Bank Transactions carrying an Airwallex expense ID or financial-transaction ID. Records already assigned to the target settings document are left unchanged. A live adoption writes only the missing settings reference. It also reports private File attachments attached to Bank Transactions.

Run a dry run first and preserve the reported counts. After adoption, repeat the report: `records_to_adopt` should be zero while expense, financial-transaction, and private-file counts remain stable.

## Cutover sequence

1. Back up the site and record enabled settings and mappings.
2. Install the tagged standalone app and migrate the schema.
3. Confirm the installed version and tagged commit.
4. Run existing-data adoption in dry-run mode.
5. Run adoption live once and repeat it to prove idempotency.
6. Run a background synchronization dry run.
7. Keep accounting-document and write-back controls disabled.
8. Run a guarded live synchronization and repeat it.
9. Compare Bank Transaction, receipt, and negative-posting counts.
10. Retain receipt compatibility until native parity is tested.

## Windmill transition

Existing Windmill integrations may continue to trigger synchronization or deliver receipts during cutover. Accounting creation must remain owned by the Frappe app, not duplicated in Windmill. Remove only obsolete accounting logic; retain the receipt compatibility scripts until a tested native provider replaces them.

## Rollback

Rollback the image to the previous pinned build without deleting the app's DocTypes or custom fields. Restore the database only when schema/data rollback is required. Do not remove Airwallex lineage fields while records depend on them.
