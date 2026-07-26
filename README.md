# Frappe Airwallex

Community Airwallex banking, spend-management, payments, and accounting integration for Frappe and ERPNext.

> **Unofficial community project.** This repository is not affiliated with, endorsed by, or supported by Airwallex, Frappe Technologies, or ERPNext. Airwallex API availability varies by account, region, permissions, and product enrolment.

## Supported stack

- Frappe 16
- ERPNext 16
- Python 3.12 or newer within the versions supported by Frappe 16
- Airwallex production and demo environments

## What it covers

The app discovers account capabilities and can integrate wallet balances and financial transactions, corporate-card expenses, private receipt attachments, bills, supplier payments, reimbursements, transfers, FX conversions, webhooks, background recovery, reconciliation proposals, and existing-data migration. Each Airwallex connection maps to one ERPNext company, while multiple connection documents support multi-company and multi-account installations.

Bank Transactions are the safe default. Accounting-document creation, document submission, supplier creation, FX journals, and Airwallex sync-status write-back are disabled by default and independently guarded.

## Installation

```bash
bench get-app https://github.com/lutzkind/frappe-airwallex.git --branch v1.0.9
bench --site your-site.example install-app airwallex_erpnext
bench --site your-site.example migrate
```

Create an **Airwallex Settings** document, enter credentials through Password fields, map the ERPNext company and currencies, then run capability discovery before enabling modules. See [Installation](docs/installation.md) and [Configuration](docs/configuration.md).

## Safety defaults

Keep these disabled until a controlled accounting test has been reviewed:

```text
create_accounting_documents = 0
submit_accounting_documents = 0
enable_fx_journals = 0
create_suppliers = 0
mark_expenses_synced = 0
mark_bills_synced = 0
```

A dry run still contacts Airwallex and evaluates mappings, but it does not create integration records or advance the last-successful-sync timestamp. Balance auto-provisioning is also suppressed during dry runs.

## Key endpoints

```text
/api/method/airwallex_erpnext.api.webhook
/api/method/airwallex_erpnext.api.sync_now
/api/method/airwallex_erpnext.api.sync_job_status
/api/method/airwallex_erpnext.api.discover_capabilities
/api/method/airwallex_erpnext.api.migration_report
```

Receipt discovery, webhook processing, retries, and scheduled recovery run inside the Frappe application. Native Airwallex attachments and Frappe-managed incoming Email Accounts require no Windmill, cron wrapper, or external compatibility service.

The former compatibility receipt endpoint remains available only for rollback compatibility. New installations and upgraded settings do not depend on it.

## Documentation

- [Architecture](docs/architecture.md)
- [Accounting model](docs/accounting-model.md)
- [API capabilities](docs/api-capabilities.md)
- [Receipts](docs/receipts.md)
- [Webhooks](docs/webhooks.md)
- [Migration](docs/migration.md)
- [Security](docs/security.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Development](docs/development.md)
- [Marketplace preparation](docs/marketplace.md)

## Status and limitations

Release 1 is production-oriented but remains community maintained. Airwallex Beta APIs, regional product differences, receipt-source availability, and supplier-payment representations require capability discovery and account-specific validation. Marketplace approval has not been requested or granted.

## License

GPL-3.0-only. See [LICENSE](LICENSE).
