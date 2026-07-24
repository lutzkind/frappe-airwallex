# Development

## Local setup

Use Python 3.12+ and a Frappe 16 development bench.

```bash
git clone https://github.com/lutzkind/frappe-airwallex.git
cd frappe-airwallex
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
ruff check .
python -m compileall -q airwallex_erpnext
pytest
python -m build
```

Unit tests use fake clients and sanitized fixtures; no live Airwallex credentials are required. Integration tests that contact Airwallex must remain opt-in and must never run for pull requests from forks.

## Design requirements

Every importer must use a stable external ID, return explicit held/excluded/exists/created states, support dry run where applicable, and remain idempotent under an overlap window. New posting behavior requires a separate disabled-by-default guard and negative tests.

Do not log secrets, raw attachment content, or full financial payloads. Raw webhook payload storage is deliberate and must remain permission restricted.

## Pull requests

Open an issue for material behavior changes. Add tests and documentation, update the changelog, and describe migration and rollback impact. CI must pass syntax, lint, secret/private-value scan, unit/fixture tests, package build, and the feasible Frappe v16 compatibility check.
