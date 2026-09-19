from __future__ import annotations

import importlib.util

import pytest

from airwallex_erpnext.tests import frappe_stub

# The repository CI runs pytest without a Frappe site. Install the in-memory
# test double only when the real framework is unavailable so bench runs keep
# using the real runtime.
USING_STUB = importlib.util.find_spec("frappe") is None
if USING_STUB:
    frappe_stub.install()


@pytest.fixture(autouse=True)
def fresh_frappe_state():
    if USING_STUB:
        frappe_stub.reset()
    yield
    if USING_STUB:
        frappe_stub.reset()


@pytest.fixture
def no_receipts(monkeypatch):
    def disabled(*args, **kwargs):
        return {"provider": "Disabled", "status": "disabled", "attached": 0, "skipped": 0, "errors": []}

    monkeypatch.setattr("airwallex_erpnext.services.bills.attach_airwallex_receipts", disabled)
    monkeypatch.setattr("airwallex_erpnext.services.reimbursements.attach_airwallex_receipts", disabled)
    monkeypatch.setattr("airwallex_erpnext.services.expenses.attach_provider_receipts", disabled)


@pytest.fixture
def settings_doc():
    from airwallex_erpnext.tests import fixtures

    return fixtures.insert_settings()
