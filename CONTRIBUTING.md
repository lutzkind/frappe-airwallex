# Contributing

Contributions are welcome through GitHub issues and pull requests.

Before coding, search existing issues and open one for material changes. Keep integrations generic and do not include customer data, credentials, private domains, company mappings, or deployment paths. Use sanitized fixtures.

Run:

```bash
ruff check .
python -m compileall -q airwallex_erpnext
pytest
python -m build
```

A pull request must explain behavior, risks, tests, migration impact, rollback, and documentation changes. New importers need stable external IDs and idempotency tests. New posting behavior needs an independent disabled-by-default control and negative-posting tests. Maintainers may request changes before merge and may decline changes that weaken safety, portability, or unofficial/community positioning.
