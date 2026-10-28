#!/usr/bin/env python3
"""Fail when generated run artifacts are committed to git.

Generated experiment output (trajectories, plots, result snapshots, logs) is
reproducible from a config + seed, so it belongs in object storage or a release
artifact, not in the repository. This guard is intentionally strict and cheap;
override a specific path by adding it to ALLOWLIST below with a comment that
explains why it is a reproducibility artifact.

Run from the repository root::

    python scripts/check_artifacts.py
"""

from __future__ import annotations

import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Paths that may legitimately contain binary or generated-looking files.
ALLOWLIST_PREFIXES = (
    "frontend/src/assets/",  # application artwork shipped with the UI
    "frontend/public/",      # static public assets
    "docs/assets/",          # documentation images
    "experiments/reference/",  # curated, small reproducibility fixtures
    "results/README.md",     # explains why results/ stays empty in git
    "results/.gitkeep",
)

GENERATED_PATTERNS = (
    "*.jsonl",
    "*.log",
    "*.pyc",
    "*/__pycache__/*",
    "*.png",
    "*.pdf",
)

GENERATED_DIRS = (
    "results/",
    "data/schemas/",
)

# Generated output owns everything under experiments/ except code, docs, configs
# and the curated reference fixtures.
EXPERIMENTS_ALLOWED_SUFFIXES = (".py", ".sh", ".md", ".yml", ".yaml", ".toml", ".gitkeep")

MAX_TRACKED_FILE_MB = 2.0


def tracked_files() -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [item for item in output.split("\0") if item]


def is_allowed(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in ALLOWLIST_PREFIXES)


def collect_problems(files: list[str]) -> list[str]:
    problems: list[str] = []
    for path in files:
        name = Path(path).name
        if name == ".env" and not path.endswith(".env.example"):
            problems.append(f"tracked secret/environment file: {path}")
            continue
        if is_allowed(path):
            continue

        if any(fnmatch(path, pattern) or fnmatch(name, pattern) for pattern in GENERATED_PATTERNS):
            problems.append(f"generated file pattern: {path}")
            continue

        if any(path.startswith(prefix) for prefix in GENERATED_DIRS):
            problems.append(f"generated output directory: {path}")
            continue

        if path.startswith("experiments/"):
            relative = path[len("experiments/"):]
            if "/" in relative or not relative.endswith(EXPERIMENTS_ALLOWED_SUFFIXES):
                problems.append(f"generated run output under experiments/: {path}")
                continue

        absolute = REPO_ROOT / path
        if absolute.is_file():
            size_mb = absolute.stat().st_size / (1024 * 1024)
            if size_mb > MAX_TRACKED_FILE_MB:
                problems.append(f"tracked file larger than {MAX_TRACKED_FILE_MB} MB ({size_mb:.1f} MB): {path}")
    return problems


def main() -> int:
    files = tracked_files()
    problems = collect_problems(files)

    print(f"[artifacts] checked {len(files)} tracked files")
    if not problems:
        print("[artifacts] OK: no generated or oversized artifacts tracked")
        return 0

    print(f"[artifacts] {len(problems)} problem(s):")
    for problem in problems[:50]:
        print(f"  - {problem}")
    if len(problems) > 50:
        print(f"  ... and {len(problems) - 50} more")
    print(
        "\n[artifacts] Keep generated trajectories/plots out of git. "
        "Publish them as release artifacts (or add a curated fixture under "
        "experiments/reference/)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
