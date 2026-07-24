from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".json", ".js", ".md", ".toml", ".yml", ".yaml", ".txt", ".in"}
SKIP_PARTS = {".git", "dist", "build", "__pycache__", ".pytest_cache", ".ruff_cache"}

PRIVATE_NAMES = ("luxe" + "illum", "relaunch" + "pilot", "control-center-" + "dashboard")
EMBEDDED_PREFIX = "deployments/erpnext/frappe-airwallex-"
FORBIDDEN_LITERAL = re.compile(
    r"(?i)("
    + "|".join(re.escape(value) for value in PRIVATE_NAMES)
    + r"|"
    + re.escape(EMBEDDED_PREFIX)
    + r"(?:bundle|overlay|hotfix|async)|\bf/(?:finance|personal|admins)/[a-z0-9_/-]+)"
)
REAL_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@(?!example\.invalid\b|invalid\.example\b)[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PRIVATE_URL = re.compile(
    r"https?://(?!(?:github\.com/lutzkind/frappe-airwallex|"
    r"api(?:-demo)?\.airwallex\.com|www\.gnu\.org|fsf\.org|"
    r"example\.invalid|your-site\.example))[^)\s\"'<>]+",
    re.I,
)
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|client[_-]?secret|webhook[_-]?secret|password|access[_-]?token)"
    r"\s*[:=]\s*[\"'][^\"']{8,}[\"']"
)

ALLOW_SECRET_EXAMPLES = {'"secret"', '"abc"', '"example-secret"'}


def main() -> None:
    failures: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern, label in (
            (FORBIDDEN_LITERAL, "deployment-specific literal"),
            (REAL_EMAIL, "non-example email"),
            (PRIVATE_URL, "non-approved URL"),
        ):
            match = pattern.search(text)
            if match:
                failures.append(f"{path.relative_to(ROOT)}: {label}: {match.group(0)}")
        for match in SECRET_ASSIGNMENT.finditer(text):
            value = match.group(0)
            if not any(example in value for example in ALLOW_SECRET_EXAMPLES):
                failures.append(f"{path.relative_to(ROOT)}: possible literal secret: {value[:80]}")
    if failures:
        raise SystemExit("\n".join(failures))
    print("Repository sanitation checks passed")


if __name__ == "__main__":
    main()
