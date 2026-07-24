from __future__ import annotations

from dataclasses import dataclass
import frappe


@dataclass(frozen=True)
class Candidate:
    doctype: str
    name: str
    score: int
    reasons: tuple[str, ...]


def propose_for_bank_transaction(bank_transaction: str) -> list[Candidate]:
    tx = frappe.get_doc("Bank Transaction", bank_transaction)
    candidates: list[Candidate] = []

    if tx.custom_airwallex_purchase_invoice:
        candidates.append(Candidate("Purchase Invoice", tx.custom_airwallex_purchase_invoice, 100, ("explicit_link",)))

    if tx.custom_airwallex_expense_id:
        invoice = frappe.db.get_value("Purchase Invoice", {"custom_airwallex_expense_id": tx.custom_airwallex_expense_id}, "name")
        if invoice:
            candidates.append(Candidate("Purchase Invoice", invoice, 100, ("expense_id",)))

    if tx.custom_airwallex_financial_transaction_id:
        payment = frappe.db.get_value(
            "Payment Entry",
            {"custom_airwallex_financial_transaction_id": tx.custom_airwallex_financial_transaction_id},
            "name",
        )
        if payment:
            candidates.append(Candidate("Payment Entry", payment, 100, ("financial_transaction_id",)))

    if not candidates:
        amount = float(tx.deposit or tx.withdrawal or 0)
        invoices = frappe.get_all(
            "Purchase Invoice",
            filters={"docstatus": 1, "outstanding_amount": ["between", [amount - 0.01, amount + 0.01]]},
            fields=["name", "posting_date"],
            limit=20,
        )
        for invoice in invoices:
            candidates.append(Candidate("Purchase Invoice", invoice.name, 50, ("amount_match",)))

    _persist(tx, candidates)
    return sorted(candidates, key=lambda c: (-c.score, c.doctype, c.name))


def _persist(tx, candidates):
    for candidate in candidates:
        existing = frappe.db.exists(
            "Airwallex Reconciliation Proposal",
            {"bank_transaction": tx.name, "reference_doctype": candidate.doctype, "reference_name": candidate.name},
        )
        if existing:
            continue
        frappe.get_doc(
            {
                "doctype": "Airwallex Reconciliation Proposal",
                "settings": tx.custom_airwallex_settings,
                "bank_transaction": tx.name,
                "reference_doctype": candidate.doctype,
                "reference_name": candidate.name,
                "score": candidate.score,
                "reasons": "\n".join(candidate.reasons),
                "status": "Proposed",
            }
        ).insert(ignore_permissions=True)
