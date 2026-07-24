# Security

## Secrets

Client IDs, API keys, webhook secrets, compatibility secrets, and IMAP passwords belong in Frappe Password fields or deployment secret stores. They must never appear in fixtures, commits, logs, screenshots, issue reports, or support bundles.

The repository contains no production credentials, private account/card identifiers, company mappings, private domains, or deployment resource paths. CI performs pattern and private-value scanning.

## Least privilege

Use separate Airwallex credentials per environment and only the scopes required by discovered modules. Disable unused modules. Apply the provided roles—Administrator, Accountant, Reviewer, and Read Only—according to duties. Limit access to Airwallex Settings, raw webhook payloads, sync logs, and private receipts.

## Webhooks

Signatures are verified against the exact request body and a bounded timestamp window. Replayed or modified bodies are rejected. Rotate the secret when ownership changes or exposure is suspected.

## Outbound requests

Production and Demo API URLs are explicit defaults. Review any custom base URL. The client uses bounded timeouts and maps authentication, permission, rate-limit, and API errors to integration exceptions.

## Accounting safety

Posting and Airwallex write-back controls default to disabled. Enabling one does not enable the others. Production changes should use peer review, a dry run, a bounded live run, and before/after counts.

## Reporting vulnerabilities

Follow [SECURITY.md](../SECURITY.md). Do not open public issues containing secrets, financial records, receipt files, or exploitable details.
