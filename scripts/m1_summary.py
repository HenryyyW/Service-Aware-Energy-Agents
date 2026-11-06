#!/usr/bin/env python3
"""Generate M1 pricing-matrix summary for paper table."""

import json
import os
import pathlib
import statistics
from collections import defaultdict

# Resolve project root: env var PROJECT_ROOT, or walk up from this file (scripts/ is one level below repo root)
PROJECT_ROOT = pathlib.Path(
    os.environ.get("PROJECT_ROOT", str(pathlib.Path(__file__).resolve().parents[1]))
)
BASE = PROJECT_ROOT / "experiments" / "m1"
REGIMES = ["pool_tou", "lmp"]


def load_runs(regime):
    base = BASE / regime
    data = defaultdict(list)
    for scen in base.iterdir():
        if not scen.is_dir():
            continue
        for run_dir in scen.iterdir():
            res = run_dir / "result.json"
            if not res.exists():
                continue
            d = json.loads(res.read_text())
            controller = d.get("controller_type")
            # pricing check
            if d.get("pricing_regime") != regime:
                continue
            energy = d.get("energy") or {}
            cost = energy.get("total_cost")
            if cost is None:
                # fallback to kpis
                kpis_file = run_dir / "kpis.json"
                if kpis_file.exists():
                    kpis = json.loads(kpis_file.read_text())
                    cost = kpis.get("energy.total_cost")
            if cost is None:
                continue
            data[controller].append(cost)
    return data


for regime in REGIMES:
    print(f"=== {regime} ===")
    data = load_runs(regime)
    for ctrl, vals in sorted(data.items()):
        mean = statistics.mean(vals)
        std = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        print(f"{ctrl:15s} n={len(vals):3d} mean={mean:.2f} std={std:.2f}")
