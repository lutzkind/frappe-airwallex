# Accounting model

## Bank Transactions first

Wallet financial transactions and Spend card expenses are represented as ERPNext **Bank Transaction** records by default. This gives operators an import and reconciliation surface without automatically creating or submitting accounting documents.

A wallet financial transaction is unique by `custom_airwallex_financial_transaction_id`. A card expense is unique by `custom_airwallex_expense_id`. Card-purchase source types are excluded from the wallet feed because Spend owns those movements.

## Currency and bank accounts

Every imported currency requires an Airwallex Account Mapping to an ERPNext ledger account and Bank Account. Missing mappings hold records. Optional account auto-provisioning is separately controlled and is suppressed during dry runs.

## Spend and card expenses

The app imports the full expense, creates or updates its Bank Transaction lineage, resolves mapping rules, and attempts receipt attachment according to the selected provider. Accounting strategies other than Bank Transaction Only are evaluated only for approved expense states.

## Bills and supplier payments

Bills may map to Purchase Invoices when the module and posting controls permit it. Supplier resolution prefers explicit mappings and aliases. Supplier creation is off by default. Transfer-backed bill payments may map to Payment Entries; card-backed payments are held to avoid double booking, and external payments require an explicit bank-account path.

## Reimbursements

Reimbursements can map to Expense Claims after an employee is resolved and an expense-claim type is configured. Missing employee or type mappings hold the item.

## Transfers and FX

Transfers may map to Payment Entries only when enabled and mapped. FX discovery groups paired conversion legs. Journal Entry creation requires `enable_fx_journals`; discovery alone does not post a journal.

## Reconciliation

The reconciliation service scores candidate ERPNext references for a Bank Transaction and stores proposals. It does not silently reconcile low-confidence candidates. Conflicts remain reviewable.

## Posting guards

The following controls must remain independent:

- create accounting documents
- submit accounting documents
- create suppliers
- create FX journals
- mark expenses synced in Airwallex
- mark bills synced in Airwallex

Tests enforce that their schema defaults are disabled.
