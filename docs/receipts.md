# Receipts

Receipts are stored as private Frappe **File** records attached to the relevant Bank Transaction. Source identifiers and content hashes prevent duplicate attachments.

## Providers

- **Airwallex** — downloads receipt content exposed by the Airwallex expense API when available to the account.
- **Compatibility API** — accepts receipt content from an existing trusted integration during migration. It requires a per-connection secret and deduplicates by expense ID, message ID, attachment ID, and content hash.
- **IMAP** — optional generic mailbox provider. Credentials are stored in Password fields; matching is scored from message metadata and attachments.
- **Manual** — preserves manual attachment workflows.
- **Disabled** — no automated receipt discovery.

## Compatibility status

Native Airwallex receipt availability differs by product and account. The compatibility path should remain deployed until native Airwallex or IMAP parity has been tested against real receipts, including duplicates, multiple attachments, unsupported content types, and delayed delivery. Removing an external receipt workflow before that validation risks losing evidence.

## Security

Keep files private, restrict access through ERPNext roles, avoid logging attachment content, and rotate the compatibility secret after cutover. IMAP accounts should use a dedicated mailbox and least-privilege credentials.

## Troubleshooting

A receipt state of pending means the expense was imported before attachment processing completed. Missing means no provider candidate was attached. Attached includes a newly created private File; skipped generally indicates an already-known attachment. Review the Receipt Match and Sync Log records before retrying.
