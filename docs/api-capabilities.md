# Airwallex API capabilities

Capability discovery probes a bounded request for each known feature and records the result per settings document. Discovery is advisory: it does not enable a module and does not guarantee every operation or field is available.

| Capability | Probe |
|---|---|
| Balances | `/api/v1/balances/current` |
| Financial transactions | `/api/v1/financial_transactions` |
| Spend expenses | `/api/v1/spend/expenses` |
| Bills | `/api/v1/spend/bills` |
| Reimbursements | `/api/v1/spend/reimbursement_reports` |
| Transfers | `/api/v1/transfers` |
| Webhooks | `/api/v1/webhooks` |

Statuses are Available, Unavailable, Beta, Missing Permission, Not Configured, or Error. Re-run discovery after Airwallex product enrolment, credential-scope changes, account/login-as changes, or API-version changes.

## Beta APIs

Bills, reimbursements, supplier-payment representations, receipt access, and some Spend webhook families may be Beta or account dependent. Release notes and marketplace material must label these limitations. Never treat a successful probe as permission to enable accounting posting automatically.

## Versioning

This release uses production and demo base URLs supplied by Airwallex and requires Spend webhook API version `2025-11-11` or newer. Future endpoint changes should be isolated in the client/service layer and covered by sanitized response fixtures.
