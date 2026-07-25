# Configuration

## Connection model

Each **Airwallex Settings** document represents one Airwallex login/account context and one ERPNext company. Create separate settings documents when companies, Airwallex account IDs, credentials, legal entities, posting policies, or currency mappings differ.

Credentials are stored through Frappe Password fields. The account ID is used for the Airwallex login-as context. Production and Demo use their official API base URLs; custom URLs should be restricted to controlled test environments.

## Company and currency mapping

Set the ERPNext company, default currency, default cost center, and optional default expense account. Create **Airwallex Account Mapping** records for every wallet currency to be imported. Each mapping links:

- Airwallex connection
- currency
- optional Airwallex account identifier
- ERPNext ledger account
- ERPNext Bank Account
- optional opening synchronization date

USD and AUD require distinct mappings even when they belong to the same Airwallex connection. A missing mapping holds a transaction instead of guessing an account.

## Multi-company and multi-account rules

Do not share one settings document across ERPNext companies. Mapping rules and merchant aliases are scoped to a settings document. Background tasks enumerate enabled settings independently, which prevents one connection's cursor or posting policy from being reused by another.

## Modules

Banking and card expenses are enabled by default in a newly created schema, while bills, supplier payments, reimbursements, transfers, automatic currency-account provisioning, and FX journal creation are disabled. Capability discovery does not enable a module; it records whether the account and credential scope appear able to use it.

## Mapping rules

Rules are evaluated by priority and can match resource type, field, operator, and value. Outputs may set company, cost center, project, expense account, supplier, tax template, item, and business unit. Deterministic rules should be narrow and reviewable. Unknown fields do not match.

## Posting controls

The expense strategy can be Bank Transaction Only, Purchase Invoice, Paid Purchase Invoice, or Expense Claim. A non-default strategy still cannot create documents unless `create_accounting_documents` is enabled. Submission requires the separate `submit_accounting_documents` control.

Supplier creation, FX journals, expense sync write-back, and bill sync write-back have separate controls. Treat all six controls as production change controls and record approvals outside the application.

## Synchronization bounds

Set a start date, overlap hours, and maximum records per sync. Incremental runs use the last successful sync minus the overlap. A new connection without a start date defaults to a bounded 30-day lookback. Overlap and stable Airwallex identifiers provide recovery without duplicates.

## Receipt configuration

Receipt collection is managed inside Frappe. Choose **Airwallex** for native attachments, or **Airwallex + Frappe Email Account** to fall back to an incoming Frappe mailbox. The linked Email Account must have incoming email enabled and owns its own Gmail OAuth or IMAP authentication. The legacy Compatibility API value is migrated to Airwallex and requires no external script.
