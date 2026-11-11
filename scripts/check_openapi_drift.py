#!/usr/bin/env python3
"""Fail when the committed OpenAPI schema drifts from the FastAPI app.

The committed baseline ``backend/openapi.json`` is the contract the frontend
and external consumers see. When an API change regenerates a different
schema, this check fails with the differing paths so the baseline is
updated deliberately in the same PR.

Usage::

    python scripts/check_openapi_drift.py            # compare (CI mode)
    python scripts/check_openapi_drift.py --update   # regenerate the baseline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE = REPO_ROOT / "backend" / "openapi.json"

sys.path.insert(0, str(REPO_ROOT))


def current_schema() -> dict:
    # The backend app imports its routers as top-level `app.*`, so both the
    # repo root (for backend.app.main) and backend/ (for app.routers) must be
    # importable — the same dual path tests/conftest.py sets up.
    for path in (REPO_ROOT, REPO_ROOT / "backend"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from backend.app.main import app

    return app.openapi()


def normalized(schema: dict) -> str:
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def differing_paths(baseline: dict, current: dict, prefix: str = "") -> list[str]:
    """Top-level human-readable pointers to where the two schemas differ."""
    out: list[str] = []
    if isinstance(baseline, dict) and isinstance(current, dict):
        for key in sorted(set(baseline) | set(current)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in baseline:
                out.append(f"added: {path}")
            elif key not in current:
                out.append(f"removed: {path}")
            else:
                out.extend(differing_paths(baseline[key], current[key], path))
    elif baseline != current:
        out.append(prefix or "<root>")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update",
        action="store_true",
        help="Regenerate backend/openapi.json from the app instead of comparing",
    )
    args = parser.parse_args()

    schema = normalized(current_schema())

    if args.update:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(schema, encoding="utf-8")
        print(f"[openapi] baseline written: {BASELINE.relative_to(REPO_ROOT)}")
        return 0

    if not BASELINE.is_file():
        print(
            "[openapi] FAILED — no committed baseline at backend/openapi.json; "
            "run `python scripts/check_openapi_drift.py --update` and commit it",
            file=sys.stderr,
        )
        return 1

    committed = json.loads(BASELINE.read_text(encoding="utf-8-sig"))
    if normalized(committed) == schema:
        print("[openapi] OK — committed schema matches the app")
        return 0

    diffs = differing_paths(committed, json.loads(schema))
    print(
        f"[openapi] FAILED — committed backend/openapi.json does not match the app "
        f"({len(diffs)} differing path(s)); regenerate with "
        f"`python scripts/check_openapi_drift.py --update` and commit the result:",
        file=sys.stderr,
    )
    for diff in diffs[:25]:
        print(f"  - {diff}", file=sys.stderr)
    if len(diffs) > 25:
        print(f"  - ... and {len(diffs) - 25} more", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
