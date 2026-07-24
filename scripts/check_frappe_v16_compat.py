from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fields(path: Path) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(row.get("fieldname")) for row in payload.get("fields", []) if row.get("fieldname")}


def require(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Required Frappe v16 contract path missing: {path}")


def check_external_trees(frappe_tree: Path, erpnext_tree: Path) -> None:
    require(frappe_tree / "frappe" / "__init__.py")
    require(frappe_tree / "frappe" / "utils" / "background_jobs.py")
    require(frappe_tree / "frappe" / "custom" / "doctype" / "custom_field" / "custom_field.py")
    require(erpnext_tree / "erpnext" / "accounts" / "doctype" / "bank_transaction" / "bank_transaction.json")
    require(erpnext_tree / "erpnext" / "accounts" / "doctype" / "purchase_invoice" / "purchase_invoice.json")
    require(erpnext_tree / "erpnext" / "accounts" / "doctype" / "payment_entry" / "payment_entry.json")
    require(erpnext_tree / "erpnext" / "accounts" / "doctype" / "journal_entry" / "journal_entry.json")

    contracts = {
        erpnext_tree / "erpnext" / "accounts" / "doctype" / "bank_transaction" / "bank_transaction.json": {"description"},
        erpnext_tree / "erpnext" / "accounts" / "doctype" / "purchase_invoice" / "purchase_invoice.json": {"remarks"},
        erpnext_tree / "erpnext" / "accounts" / "doctype" / "payment_entry" / "payment_entry.json": {"remarks"},
        erpnext_tree / "erpnext" / "accounts" / "doctype" / "journal_entry" / "journal_entry.json": {"user_remark"},
    }
    for path, expected in contracts.items():
        missing = expected - fields(path)
        if missing:
            raise SystemExit(f"Frappe v16 insert_after contract changed in {path}: missing {sorted(missing)}")


def check_app_contract() -> None:
    namespace: dict[str, object] = {}
    exec((ROOT / "airwallex_erpnext" / "__init__.py").read_text(encoding="utf-8"), namespace)
    if namespace.get("__version__") != "1.0.4":
        raise SystemExit("Runtime version is not 1.0.4")

    hooks_path = ROOT / "airwallex_erpnext" / "hooks.py"
    spec = importlib.util.spec_from_file_location("airwallex_hooks_contract", hooks_path)
    if spec is None or spec.loader is None:
        raise SystemExit("Cannot load hooks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if getattr(module, "required_apps", None) != ["erpnext"]:
        raise SystemExit("required_apps must contain ERPNext")

    for path in (ROOT / "airwallex_erpnext" / "airwallex_erpnext" / "doctype").rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frappe-tree", type=Path)
    parser.add_argument("--erpnext-tree", type=Path)
    args = parser.parse_args()
    check_app_contract()
    if bool(args.frappe_tree) != bool(args.erpnext_tree):
        raise SystemExit("Provide both --frappe-tree and --erpnext-tree")
    if args.frappe_tree and args.erpnext_tree:
        check_external_trees(args.frappe_tree.resolve(), args.erpnext_tree.resolve())
    print("Frappe v16 compatibility contract passed")


if __name__ == "__main__":
    main()
