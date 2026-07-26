from __future__ import annotations

import ast
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_release_versions_match():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    tree = ast.parse((ROOT / "airwallex_erpnext" / "__init__.py").read_text(encoding="utf-8"))
    version = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    version = ast.literal_eval(node.value)
    assert project["project"]["version"] == version == "1.0.10"


def test_workspace_has_renderable_layout():
    install_source = (ROOT / "airwallex_erpnext" / "install.py").read_text(encoding="utf-8")
    assert '"type": "card"' in install_source
    assert '"type": "Card Break"' in install_source
    assert '"content": "[]"' not in install_source
    for label in (
        "Settings",
        "Account Mappings",
        "Mapping Rules",
        "Bank Transactions",
        "Sync Logs",
        "Webhook Events",
        "Reconciliation Proposals",
        "Receipt Matches",
    ):
        assert label in install_source


def test_doctype_json_and_safe_defaults():
    documents = []
    for path in (ROOT / "airwallex_erpnext").rglob("*.json"):
        documents.append(json.loads(path.read_text(encoding="utf-8")))
    settings = next(item for item in documents if item.get("name") == "Airwallex Settings")
    fields = {field["fieldname"]: field for field in settings["fields"] if field.get("fieldname")}
    for fieldname in (
        "create_accounting_documents",
        "submit_accounting_documents",
        "enable_fx_journals",
        "create_suppliers",
        "mark_expenses_synced",
        "mark_bills_synced",
    ):
        assert str(fields[fieldname].get("default")) == "0"


def test_required_publication_files_exist():
    required = [
        "docs/installation.md", "docs/configuration.md", "docs/architecture.md",
        "docs/accounting-model.md", "docs/receipts.md", "docs/webhooks.md",
        "docs/migration.md", "docs/security.md", "docs/troubleshooting.md",
        "docs/development.md", "docs/api-capabilities.md", "docs/marketplace.md",
        "GOVERNANCE.md", "SUPPORT.md", "SECURITY.md", "ROADMAP.md",
    ]
    assert not [path for path in required if not (ROOT / path).is_file()]


def test_no_private_deployment_values_or_literal_secrets():
    private_terms = ["luxe" + "illum", "relaunch" + "pilot"]
    private_paths = ["f/" + value for value in ("finance", "personal", "admins", "website-redesign-runner", "website_redesign_runner")]
    banned = re.compile("|".join(re.escape(value) for value in [*private_terms, *private_paths]), re.I)
    literal_secret = re.compile(r"(?i)(api[_-]?key|password|webhook[_-]?secret|client[_-]?secret|access[_-]?token)\s*[:=]\s*[\"'][^<\"']{8,}[\"']")
    findings = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix in {".pyc", ".png", ".jpg", ".gif"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if banned.search(text) or literal_secret.search(text):
            findings.append(path.relative_to(ROOT).as_posix())
    assert not findings
