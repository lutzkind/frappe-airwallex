"""In-memory Frappe runtime used by the unit tests.

The repository CI installs the package without a Frappe/ERPNext site, so the
service modules are exercised against a small deterministic test double. It
implements the document/database surface the integration uses: documents with
insert/submit/cancel/db_set, filtered ``frappe.db`` reads and writes, Currency
Exchange lookups, scheduler enqueue capture, and datetime helpers.

It is not a general Frappe emulator. When the real ``frappe`` package is
importable (a bench test run) it is left untouched.
"""

from __future__ import annotations

import json
import re
import sys
import types
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace


class DoesNotExistError(Exception):
    pass


class DuplicateEntryError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class ValidationError(Exception):
    pass


class FakeDocument:
    def __init__(self, api, doctype, values=None, name=None):
        object.__setattr__(self, "_api", api)
        object.__setattr__(self, "_fields", {})
        object.__setattr__(self, "doctype", doctype)
        fields = dict(values or {})
        fields.pop("doctype", None)
        resolved_name = name or fields.pop("name", None) or self._autoname(fields)
        object.__setattr__(self, "name", resolved_name)
        now = api.utils.now_datetime()
        fields.setdefault("creation", now)
        fields.setdefault("modified", now)
        fields.setdefault("docstatus", 0)
        fields.setdefault("owner", "Administrator")
        self._fields.update(fields)
        self._fields["name"] = resolved_name

    def _autoname(self, fields):
        if self.doctype == "Airwallex Settings":
            return str(fields.get("settings_name") or "Airwallex Settings")
        self._api.name_counters[self.doctype] = self._api.name_counters.get(self.doctype, 0) + 1
        prefix = "".join(part[0] for part in self.doctype.split() if part).upper() or "DOC"
        return f"{prefix}-{self._api.name_counters[self.doctype]:04d}"

    def __getattr__(self, key):
        if key.startswith("_") or key == "doctype":
            raise AttributeError(key)
        if key == "name":
            return object.__getattribute__(self, "name")
        return self._fields.get(key)

    def __setattr__(self, key, value):
        if key in {"_fields", "_api", "doctype", "name"}:
            object.__setattr__(self, key, value)
            if key == "name":
                self._fields["name"] = value
            return
        self._fields[key] = value

    def get(self, key, default=None):
        return self._fields.get(key, default)

    def update(self, values=None, **kwargs):
        for key, value in {**(values or {}), **kwargs}.items():
            if key != "doctype":
                self._fields[key] = value

    def insert(self, ignore_permissions=False, **kwargs):
        table = self._api.db.docs.setdefault(self.doctype, {})
        if self.name in table:
            raise DuplicateEntryError(f"{self.doctype} {self.name} already exists")
        table[self.name] = self
        return self

    def submit(self):
        if int(self._fields.get("docstatus") or 0) != 0:
            raise ValidationError("Only draft documents can be submitted")
        self._fields["docstatus"] = 1
        self._fields["modified"] = self._api.utils.now_datetime()
        if self.doctype == "Payment Entry":
            self._api._apply_payment_entry(self, sign=-1)

    def cancel(self):
        if int(self._fields.get("docstatus") or 0) != 1:
            raise ValidationError("Only submitted documents can be cancelled")
        self._fields["docstatus"] = 2
        self._fields["modified"] = self._api.utils.now_datetime()
        if self.doctype == "Payment Entry":
            self._api._apply_payment_entry(self, sign=1)

    def delete(self):
        self._api.db.docs.get(self.doctype, {}).pop(self.name, None)

    def save(self):
        if int(self._fields.get("docstatus") or 0) != 0:
            raise ValidationError("Only draft documents can be saved")
        self._fields["modified"] = self._api.utils.now_datetime()
        return self

    def db_set(self, fieldname, value=None, update_modified=True):
        if isinstance(fieldname, dict):
            self._fields.update(fieldname)
        else:
            self._fields[fieldname] = value
        if update_modified:
            self._fields["modified"] = self._api.utils.now_datetime()
        return self

    def get_password(self, fieldname, raise_exception=False):
        return self._fields.get(fieldname)

    def as_dict(self):
        return {"doctype": self.doctype, "name": self.name, **self._fields}


CHILD_TABLES = {"Payment Entry Reference": ("Payment Entry", "references")}

_OPERATORS = {"in", "<", "<=", ">", ">=", "!=", "between", "like"}


class AttrDict(dict):
    """dict rows with Frappe ``_dict`` attribute access."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None


def _matches(row, filters):
    if not filters:
        return True
    if isinstance(filters, str):
        return row.get("name") == filters
    for field, condition in filters.items():
        value = row.get(field)
        if isinstance(condition, (list, tuple)) and len(condition) == 2 and str(condition[0]).lower() in _OPERATORS:
            operator, operand = str(condition[0]).lower(), condition[1]
            if operator == "in":
                if value not in operand:
                    return False
            elif operator == "between":
                if value is None or not (operand[0] <= value <= operand[1]):
                    return False
            elif operator == "like":
                pattern = "^" + re.escape(str(operand)).replace("%", ".*").replace("_", ".") + "$"
                if not re.match(pattern, str(value or "")):
                    return False
            elif operator == "<":
                if value is None or not value < operand:
                    return False
            elif operator == "<=":
                if value is None or not value <= operand:
                    return False
            elif operator == ">":
                if value is None or not value > operand:
                    return False
            elif operator == ">=":
                if value is None or not value >= operand:
                    return False
            elif operator == "!=":
                if value == operand:
                    return False
        elif value != condition:
            return False
    return True


class FakeDB:
    def __init__(self, api):
        self.api = api
        self.docs = {}

    def _rows(self, doctype):
        if doctype in CHILD_TABLES:
            parent_doctype, child_field = CHILD_TABLES[doctype]
            rows = []
            for parent in self.docs.get(parent_doctype, {}).values():
                for child in parent.get(child_field) or []:
                    payload = child if isinstance(child, dict) else child._fields
                    rows.append({"parent": parent.name, "parenttype": parent_doctype, **payload})
            return rows
        return [dict(doc._fields) for doc in self.docs.get(doctype, {}).values()]

    def _sort(self, rows, order_by):
        if not order_by:
            return rows
        keys = []
        for clause in order_by.split(","):
            parts = clause.strip().split()
            keys.append((parts[0], parts[1].lower() if len(parts) > 1 else "asc"))
        for field, direction in reversed(keys):
            rows = sorted(rows, key=lambda row: (row.get(field) is None, row.get(field)), reverse=direction == "desc")
        return rows

    def get_all(self, doctype, filters=None, fields=None, pluck=None, order_by=None, limit=None,
                limit_page_length=None, **kwargs):
        rows = [row for row in self._rows(doctype) if _matches(row, filters)]
        rows = self._sort(rows, order_by)
        effective_limit = limit if limit not in (None, 0) else limit_page_length
        if effective_limit:
            rows = rows[: int(effective_limit)]
        if pluck:
            return [row.get(pluck) for row in rows]
        if fields:
            return [AttrDict((field, row.get(field)) for field in fields) for row in rows]
        return [AttrDict(row) for row in rows]

    def get_value(self, doctype, filters=None, fieldname="name", as_dict=False, order_by=None, **kwargs):
        rows = self.get_all(doctype, filters=filters, order_by=order_by)
        if not rows:
            return None
        row = rows[0]
        if as_dict:
            return row
        if isinstance(fieldname, (list, tuple)):
            return tuple(row.get(field) for field in fieldname)
        return row.get(fieldname)

    def set_value(self, doctype, name, fieldname, value=None, update_modified=True):
        doc = self.docs.get(doctype, {}).get(name)
        if doc is None:
            raise DoesNotExistError(f"{doctype} {name} does not exist")
        doc.db_set(fieldname, value, update_modified=update_modified)
        return doc

    def exists(self, doctype, name=None):
        if doctype == "DocType":
            return True
        if name is None:
            return bool(self.docs.get(doctype))
        if isinstance(name, str):
            return name in self.docs.get(doctype, {})
        return any(_matches(row, name) for row in self._rows(doctype))

    def delete(self, doctype, filters=None):
        for row in self._rows(doctype):
            if _matches(row, filters):
                self.docs.get(doctype, {}).pop(row.get("name"), None)

    def commit(self):
        pass

    def rollback(self):
        pass


class FakeFrappeAPI:
    def __init__(self):
        self.name_counters = {}
        self.db = FakeDB(self)
        self.utils = _build_utils()
        self.local = SimpleNamespace(
            response=SimpleNamespace(http_status_code=200),
            flags=SimpleNamespace(),
        )
        self.jobs = []
        self.AuthenticationError = AuthenticationError
        self.ValidationError = ValidationError
        self.DoesNotExistError = DoesNotExistError
        self.DuplicateEntryError = DuplicateEntryError

    def get_doc(self, *args, **kwargs):
        if args and isinstance(args[0], dict):
            payload = dict(args[0])
            return FakeDocument(self, payload.get("doctype"), payload)
        if args and isinstance(args[0], str):
            doctype = args[0]
            name = args[1] if len(args) > 1 else kwargs.get("name")
            doc = self.db.docs.get(doctype, {}).get(name)
            if doc is None:
                raise DoesNotExistError(f"{doctype} {name} does not exist")
            return doc
        raise TypeError("get_doc expects a doctype/name or a values dict")

    def get_all(self, *args, **kwargs):
        return self.db.get_all(*args, **kwargs)

    def get_value(self, *args, **kwargs):
        return self.db.get_value(*args, **kwargs)

    def get_cached_value(self, *args, **kwargs):
        return self.db.get_value(*args, **kwargs)

    def get_cached_doc(self, *args, **kwargs):
        return self.get_doc(*args, **kwargs)

    def enqueue(self, func, **kwargs):
        self.jobs.append({"func": func, "kwargs": kwargs})

    def as_json(self, value):
        return json.dumps(value, default=str)

    def throw(self, message="", exc=None, **kwargs):
        if isinstance(exc, type) and issubclass(exc, Exception):
            raise exc(message)
        raise ValidationError(message)

    def only_for(self, *args, **kwargs):
        return None

    def whitelist(self, *wargs, **wkwargs):
        if len(wargs) == 1 and callable(wargs[0]) and not wkwargs:
            return wargs[0]

        def decorator(function):
            return function

        return decorator

    def _apply_payment_entry(self, doc, sign):
        for ref in doc.get("references") or []:
            if ref.get("reference_doctype") != "Purchase Invoice":
                continue
            invoice = self.db.docs.get("Purchase Invoice", {}).get(ref.get("reference_name"))
            if invoice is None:
                continue
            outstanding = Decimal(str(invoice.get("outstanding_amount") or 0))
            outstanding += sign * Decimal(str(ref.get("allocated_amount") or 0))
            invoice._fields["outstanding_amount"] = outstanding


def _build_utils():
    module = types.ModuleType("frappe.utils")
    module.now_datetime = datetime.now
    module.nowdate = lambda: datetime.now().date().isoformat()
    module.today = module.nowdate
    module.add_days = lambda value, days: value + timedelta(days=days)
    module.get_system_timezone = lambda: "UTC"
    module.get_datetime_str = lambda value: str(value)
    module.flt = lambda value, precision=None: float(value or 0)
    module.cint = lambda value=0: int(value or 0)
    module.cstr = lambda value="": str(value or "")
    file_manager = types.ModuleType("frappe.utils.file_manager")
    file_manager.save_file = lambda *args, **kwargs: (_ for _ in ()).throw(NotImplementedError("save_file"))
    file_manager.get_content_hash = lambda *args, **kwargs: ""
    module.file_manager = file_manager
    sys.modules["frappe.utils"] = module
    sys.modules["frappe.utils.file_manager"] = file_manager
    return module


_MODULE = None


def install():
    global _MODULE
    if _MODULE is None:
        _MODULE = types.ModuleType("frappe")
        _MODULE.__path__ = []
    api = FakeFrappeAPI()
    for key in dir(FakeFrappeAPI):
        if not key.startswith("__"):
            setattr(_MODULE, key, getattr(api, key))
    for key, value in vars(api).items():
        setattr(_MODULE, key, value)
    _MODULE._api = api
    sys.modules["frappe"] = _MODULE
    return api


def reset():
    return install()


def get_api():
    return _MODULE._api


def age_document(doctype, name, **delta):
    doc = get_api().db.docs[doctype][name]
    doc._fields["modified"] = datetime.now() - timedelta(**delta)
    return doc
