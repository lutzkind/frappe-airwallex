# Receipts

Receipts are stored as private Frappe **File** records attached to the relevant Bank Transaction. Source identifiers and content hashes prevent duplicate attachments.

## Providers

- **Airwallex** — downloads receipt content exposed by the Airwallex expense API.
- **Airwallex + Frappe Email Account** — prefers native Airwallex attachments and falls back to a mailbox managed by Frappe when Airwallex has no attachment.
- **Frappe Email Account** — searches received Frappe Communication records and their private File attachments. The selected Email Account owns Gmail OAuth or IMAP credentials.
- **IMAP** — optional direct generic mailbox provider using credentials stored in Airwallex Settings.
- **Manual** — preserves manual attachment workflows.
- **Disabled** — no automated receipt discovery.

The former Compatibility API provider is migrated automatically to **Airwallex**. It is not required at runtime and no external orchestration script is needed.

## Frappe Email Account setup

1. Create an incoming **Email Account** in ERPNext and authorize Gmail OAuth or configure IMAP there.
2. Confirm **Enable Incoming** is active and allow Frappe to synchronize the mailbox.
3. Select that account in **Airwallex Settings → Receipt Email Account**.
4. Choose **Airwallex + Frappe Email Account** for native attachments with mailbox fallback, or **Frappe Email Account** for mailbox-only discovery.

Mailbox matching uses merchant, amount, currency, and transaction date. Multiple attachments from one high-confidence message are kept together. Competing messages with nearly equal confidence are recorded as held Receipt Matches instead of attaching uncertain evidence.

## Scheduling and webhooks

Receipt recovery runs inside Frappe together with the application’s native webhook queue, hourly incremental recovery, and daily full recovery. Windmill, cron wrappers, and external receipt-forwarding scripts are not part of the production architecture.

## Security

Keep files private and restrict access through ERPNext roles. For Gmail, prefer a standard Frappe Email Account with OAuth rather than copying credentials into the Airwallex integration. Attachment content is not logged. Source IDs, message IDs, and content hashes are stored only for traceability and duplicate prevention.

## Troubleshooting

A receipt state of `pending` means the expense was imported before attachment processing completed. `missing` means the selected provider found no candidate. `ambiguous` means multiple mailbox messages were too close to choose safely. `attached` includes a newly created private File or an already-known duplicate. Review **Receipt Matches** and **Sync Logs** before retrying.
