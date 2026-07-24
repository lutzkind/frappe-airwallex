from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "airwallex_erpnext" / "tests" / "fixtures"
PRIVATE_NAMES = ("luxe" + "illum", "relaunch" + "pilot", "control-center-" + "dashboard")
FORBIDDEN = re.compile(
    r"(?i)("
    + "|".join(re.escape(value) for value in PRIVATE_NAMES)
    + r"|windmill[/_-]resource|"
    r"https?://(?!example\.invalid|api(?:-demo)?\.airwallex\.com)|"
    r"\b[A-Z0-9._%+-]+@(?!example\.invalid\b)[A-Z0-9.-]+\.[A-Z]{2,}\b)"
)


def main() -> None:
    paths = sorted(FIXTURES.glob("*.json"))
    if not paths:
        raise SystemExit("No fixture files found")
    ids: set[str] = set()
    for path in paths:
        raw = path.read_text(encoding="utf-8")
        if FORBIDDEN.search(raw):
            raise SystemExit(f"Forbidden private-looking value in {path}")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise SystemExit(f"Fixture must be an object: {path}")
        fixture_id = str(payload.get("id") or payload.get("event_id") or "")
        if not fixture_id or "example" not in fixture_id:
            raise SystemExit(f"Fixture ID must be a synthetic example: {path}")
        if fixture_id in ids:
            raise SystemExit(f"Duplicate fixture ID: {fixture_id}")
        ids.add(fixture_id)
    print(f"Validated {len(paths)} sanitized fixture files")


if __name__ == "__main__":
    main()
