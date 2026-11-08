#!/usr/bin/env python3
"""Prefetch CityLearn datasets into the local cache so CI never downloads at run time.

Why: the Seed Reproducibility job (and anything that constructs a CityLearn
environment on a cold runner) resolves datasets via the GitHub API on cache
miss. GitHub rate-limits that endpoint (HTTP 403), colouring the pipeline red
for an environmental — not determinism — reason.

Fix: vendor datasets into CityLearn's cache (~/.cache/citylearn/<tag>/datasets/)
BEFORE the job runs, with explicit exit codes:

  0  every requested dataset is present in the cache
  1  a dataset could not be vendored (download failed after retries)
  2  post-vendoring verification failed

Sources, in order (first hit wins, zero network when possible):
  1. cache already populated (no-op)
  2. repo-tracked copy under experiments/reference/  (citylearn_challenge_2020_climate_zone_1)
  3. CityLearn's own GitHub download, wrapped in retries (citylearn_challenge_2022_phase_all_plus_evs)

The script prints ``DATASET_SHA256=<sha256>`` per dataset — a deterministic
hash over all dataset files (sorted by relative path) — so CI can assert the
vendored cache is byte-stable across runs (run the script twice, compare).

Usage::

    python scripts/prefetch_citylearn.py \
        --dataset citylearn_challenge_2020_climate_zone_1 \
        --dataset citylearn_challenge_2022_phase_all_plus_evs

    # verify-only (no vendoring): exit 0 if cached, 1 if not
    python scripts/prefetch_citylearn.py --dataset <name> --check
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DIR = REPO_ROOT / "experiments" / "reference"

# Datasets the CI matrix touches. The smoke/agent path uses climate_zone_1
# (repo-tracked, zero network); the Seed Reproducibility job uses
# phase_all_plus_evs (downloaded once, then cached by actions/cache).
CI_DATASETS = (
    "citylearn_challenge_2020_climate_zone_1",
    "citylearn_challenge_2022_phase_all_plus_evs",
)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (5, 15, 45)  # exponential-ish backoff between attempts


def _datasets_cache_dir() -> Path:
    """CityLearn's cache datasets dir, derived from the installed package."""
    try:
        from citylearn.data import DataSet

        return Path(DataSet.DEFAULT_CACHE_DIRECTORY) / "datasets"
    except ImportError:
        # Fallback for python3 without citylearn installed (e.g. lint runners)
        return Path.home() / ".cache" / "citylearn" / "v3.0.2" / "datasets"


def dataset_sha256(dataset_dir: Path) -> str:
    """Deterministic sha256 over all dataset files (sorted by relative path)."""
    digest = hashlib.sha256()
    files = sorted(p for p in dataset_dir.rglob("*") if p.is_file())
    for filepath in files:
        digest.update(str(filepath.relative_to(dataset_dir)).encode())
        with filepath.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _copy_from_reference(name: str, cache_dir: Path) -> bool:
    """Vendor from the repo-tracked reference copy (zero network). Returns True on hit."""
    source = REFERENCE_DIR / name
    if not (source / "schema.json").is_file():
        return False
    target = cache_dir / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    print(f"[prefetch] vendored {name} from repo reference ({REFERENCE_DIR})")
    return True


def _download_via_citylearn(name: str) -> None:
    """Download via CityLearn's own machinery, with retries and backoff."""
    from citylearn.data import DataSet

    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(
                f"[prefetch] downloading {name} via CityLearn "
                f"(attempt {attempt}/{MAX_ATTEMPTS})..."
            )
            DataSet().get_dataset(name)
            return
        except Exception as exc:  # noqa: BLE001 - any network/HTTP failure retries
            last_error = exc
            wait = BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]
            print(f"[prefetch] attempt {attempt} failed: {exc}; retrying in {wait}s")
            if attempt < MAX_ATTEMPTS:
                time.sleep(wait)
    raise RuntimeError(
        f"download failed after {MAX_ATTEMPTS} attempts: {last_error}"
    ) from last_error


def prefetch(name: str, cache_dir: Path) -> str:
    """Ensure `name` is in the CityLearn cache. Returns its deterministic sha256."""
    target = cache_dir / name
    if (target / "schema.json").is_file():
        print(f"[prefetch] {name}: already cached")
        return dataset_sha256(target)

    if not _copy_from_reference(name, cache_dir):
        _download_via_citylearn(name)

    if not (target / "schema.json").is_file():
        print(f"[prefetch] FAIL: {name} still missing after vendoring", file=sys.stderr)
        raise SystemExit(1)

    return dataset_sha256(target)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        action="append",
        default=None,
        help="Dataset name to vendor (repeatable). Defaults to the CI set.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify-only: exit 0 if all requested datasets are cached, 1 otherwise",
    )
    args = parser.parse_args(argv)

    datasets: List[str] = args.dataset if args.dataset else list(CI_DATASETS)
    cache_dir = _datasets_cache_dir()
    print(f"[prefetch] cache directory: {cache_dir}")

    hashes: Dict[str, str] = {}
    try:
        for name in datasets:
            target = cache_dir / name
            if args.check:
                if not (target / "schema.json").is_file():
                    print(
                        f"[prefetch] CHECK FAIL: {name} not in cache",
                        file=sys.stderr,
                    )
                    return 1
                hashes[name] = dataset_sha256(target)
                continue
            hashes[name] = prefetch(name, cache_dir)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - report any failure with exit 1
        print(f"[prefetch] FAIL: {exc}", file=sys.stderr)
        return 1

    for name in datasets:
        print(f"DATASET_SHA256[{name}]={hashes[name]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
