#!/usr/bin/env python3
"""Package experiment runs into a checksummed release artifact.

Trajectories and plots stay out of git; this script turns a set of run
directories into one zip with an index and per-file SHA-256 checksums so a
report or paper can cite an immutable artifact.

Usage::

    python scripts/package_results.py \
        --runs experiments/benchmark/seed_42 experiments/benchmark/seed_123 \
        --output dist/benchmark-2026-10.zip

Each tracked file's hash is listed in ``SHA256SUMS``. ``INDEX.json`` records the
run metadata and headline metrics for quick inspection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Iterable

INCLUDED_FILES = ("result.json", "manifest.json", "trajectories.jsonl")
METRIC_KEYS = (
    ("energy", "total_cost"),
    ("energy", "grid_import_kwh"),
    ("energy", "peak_demand_kw"),
    ("service", "ev_completion_rate"),
    ("grid", "voltage_violations_count"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_run_dirs(roots: Iterable[str]) -> list[Path]:
    found: dict[Path, None] = {}
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            raise FileNotFoundError(root)
        if (root_path / "result.json").is_file():
            found[root_path.resolve()] = None
            continue
        for result_file in root_path.rglob("result.json"):
            found[result_file.parent.resolve()] = None
    return sorted(found)


def summarize(run_dir: Path) -> dict:
    summary: dict = {"run_dir": run_dir.name}
    result_path = run_dir / "result.json"
    if result_path.is_file():
        try:
            result = json.loads(result_path.read_text())
            summary.update({
                "run_id": result.get("run_id"),
                "scenario_id": result.get("scenario_id"),
                "random_seed": result.get("random_seed"),
                "controller": result.get("controller_config"),
            })
            for block, key in METRIC_KEYS:
                value = (result.get(block) or {}).get(key)
                if value is not None:
                    summary[f"{block}.{key}"] = value
        except json.JSONDecodeError:
            summary["error"] = "result.json is not valid JSON"
    manifest_path = run_dir / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text())
            summary["git_commit"] = manifest.get("git_commit")
            summary["scenario_config_sha256"] = manifest.get("scenario_config_sha256")
        except json.JSONDecodeError:
            pass
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="+", required=True,
                        help="Run directories, or parent directories to search recursively")
    parser.add_argument("--output", required=True, help="Destination .zip path")
    parser.add_argument("--include-plots", action="store_true",
                        help="Also include plots/ directories")
    args = parser.parse_args()

    run_dirs = find_run_dirs(args.runs)
    if not run_dirs:
        print("[package] no runs found (looked for result.json)", file=sys.stderr)
        return 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    index: list[dict] = []
    checksums: list[tuple[str, str]] = []

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for run_dir in run_dirs:
            summary = summarize(run_dir)
            index.append(summary)
            arc_root = f"runs/{run_dir.name}"

            for name in INCLUDED_FILES:
                path = run_dir / name
                if not path.is_file():
                    continue
                arcname = f"{arc_root}/{name}"
                archive.write(path, arcname)
                checksums.append((arcname, sha256_file(path)))

            if args.include_plots:
                for plot in sorted(run_dir.glob("plots/*")):
                    if plot.is_file():
                        arcname = f"{arc_root}/plots/{plot.name}"
                        archive.write(plot, arcname)
                        checksums.append((arcname, sha256_file(plot)))

        sums_payload = "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums))
        archive.writestr("SHA256SUMS", sums_payload)
        archive.writestr(
            "INDEX.json",
            json.dumps({"created_by": "scripts/package_results.py", "runs": index}, indent=2),
        )

    print(f"[package] {len(run_dirs)} run(s), {len(checksums)} file(s) -> {output}")
    print(f"[package] size {output.stat().st_size / (1024 * 1024):.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
