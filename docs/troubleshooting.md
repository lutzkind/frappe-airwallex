# Troubleshooting

## Authentication fails

Confirm environment, API base URL, Client ID, API key, account/login-as ID, credential scope, and server clock. Re-enter Password fields rather than copying masked values.

## Capability is unavailable or missing permission

Capability discovery probes known endpoints with a minimal request. Unavailable may mean the product is not enabled in the region/account. Missing Permission usually means the credential scope is insufficient. Beta means the endpoint responded but requires additional validation.

## Transactions are held

Common reasons are missing external ID, unsettled status, missing currency/account mapping, unsupported payment type, missing supplier or employee mapping, or disabled posting controls. Held records are intentional; fix configuration and rerun with overlap.

## Duplicate concern

Check the relevant Airwallex custom ID on Bank Transaction or accounting documents. Repeated runs should return exists/processed states without increasing record counts. Card purchases must not be imported from both wallet and Spend feeds.

## Receipts are missing

Check receipt provider, account capability, compatibility secret, IMAP credentials, private File permissions, and Sync Log errors. Do not remove compatibility delivery until native parity is demonstrated.

## Webhooks retry or dead-letter

Check signature secret, timestamp tolerance, API version, account match, event payload, worker availability, and the last bounded error. Recovery polling can safely re-fetch missed data.

## Long sync appears stuck

Inspect long-queue workers and the compact job state. Synchronizations are bounded by maximum records. A failed job should not advance `last_successful_sync`.

## Migration count differs

Run the migration report for the same settings document. Confirm custom fields exist, records are not assigned to another connection, and private files are attached to Bank Transaction. Do not infer adoption from aggregate Bank Transaction counts alone.
