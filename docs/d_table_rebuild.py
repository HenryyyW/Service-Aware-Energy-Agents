#!/usr/bin/env python3
"""Rebuild the Scenario D rows for the paper tables after the 9f62e027f fix.

Sources
-------
* New runs (post-fix): ``experiments/matrix_d_rerun`` (pool_tou),
  ``experiments/matrix_d_rerun_lmp`` (lmp), ``experiments/matrix_d_rerun_p2p``
  (p2p) -- 5 controllers x 10 seeds per regime.
* Untouched baseline rows for the other scenarios come from the B-axis
  matrices (``experiments/matrix_full``, ``experiments/matrix_p2p``,
  ``experiments/m52_benchmark``); 9f62e027f only changes the ``total_cost``
  KPI when energy sharing is enabled, i.e. scenario D alone.

Outputs (``docs/d_table_rebuild/``)
-----------------------------------
* ``d_deltas_pool_tou.md`` -- Table 2 (tab:deltas) scenario-D rows.
* ``d_kpis_pool_tou.md`` -- scenario-D KPI means + 95% CI half-widths.
* ``d_rows_lmp.md`` -- LMP table scenario-D rows + TOU->LMP shift.
* ``d_rows_p2p.md`` -- P2P regression check on scenario D.
* ``d_summary.json`` -- machine-readable form of all of the above.

Statistics protocol (identical to the paper tables): paired per-seed deltas
vs. rule_based within the scenario, Student-t 95% CI half-width, Holm
correction within the scenario over the controller comparisons.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "d_table_rebuild"

SEEDS = [42, 123, 456, 789, 999, 1234, 2024, 3456, 5555, 8888]
CONTROLLERS = ["rule_based", "multi_agent", "centralized", "mpc", "rl"]
BASELINE = "rule_based"

NEW_MATRICES = {
    "pool_tou": "experiments/matrix_d_rerun",
    "lmp": "experiments/matrix_d_rerun_lmp",
    "p2p": "experiments/matrix_d_rerun_p2p",
}
OLD_MATRICES = {
    "pool_tou": "experiments/matrix_full",
    "p2p": "experiments/matrix_p2p",
    "lmp": "experiments/m52_benchmark",
}

METRICS = {
    "total_cost": ("energy", "total_cost"),
    "peak_demand_kw": ("energy", "peak_demand_kw"),
    "ev_completion_rate": ("service", "ev_completion_rate"),
    "pv_generation_kwh": ("energy", "pv_generation_kwh"),
    "grid_import_kwh": ("energy", "grid_import_kwh"),
    "comfort_violation_degree_hours": ("service", "comfort_violation_degree_hours"),
}


def load_run(matrix: str, scenario: str, controller: str, seed: int) -> Optional[dict]:
    path = ROOT / matrix / scenario / f"{scenario}_{controller}_{seed}" / "result.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def metric(result: dict, key: str):
    section, field = METRICS[key]
    return result.get(section, {}).get(field)


def t_critical(n: int, confidence: float = 0.95) -> float:
    """Two-sided Student-t critical value (df = n-1)."""
    if n < 2:
        return 0.0
    try:
        from scipy.stats import t as student_t

        return float(student_t.ppf(0.5 + confidence / 2.0, n - 1))
    except Exception:
        table = {2: 12.706, 3: 4.303, 4: 3.227, 5: 2.776, 6: 2.571, 7: 2.447,
                 8: 2.365, 9: 2.306, 10: 2.262}
        return table.get(n, 2.262)


def describe(values: List[float]) -> Dict[str, float]:
    n = len(values)
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if n > 1 else 0.0
    half = t_critical(n) * sd / math.sqrt(n) if n > 1 else 0.0
    return {"n": n, "mean": mean, "sd": sd, "ci95": half}


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def holm(pvalues: List[float]) -> List[float]:
    """Holm-Bonferroni adjusted p-values (same order as the input)."""
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    m = len(pvalues)
    adjusted: List[Optional[float]] = [None] * m
    running = 0.0
    for rank, idx in enumerate(order):
        value = (m - rank) * pvalues[idx]
        running = max(running, min(value, 1.0))
        adjusted[idx] = running
    return [a if a is not None else 1.0 for a in adjusted]


def paired_t(sample: List[float]) -> Dict[str, float]:
    """Paired t-test vs 0 (one-sample t on the deltas)."""
    n = len(sample)
    if n < 2:
        return {"t": 0.0, "p": 1.0, "mean": sample[0] if sample else 0.0}
    mean = statistics.fmean(sample)
    sd = statistics.stdev(sample)
    if sd == 0.0:
        return {"t": math.inf if mean else 0.0, "p": 0.0 if mean else 1.0, "mean": mean}
    t = mean / (sd / math.sqrt(n))
    try:
        from scipy.stats import t as student_t

        p = float(2 * student_t.sf(abs(t), n - 1))
    except Exception:
        p = float("nan")
    return {"t": t, "p": p, "mean": mean}


def collect(matrix: str, scenario: str = "scenario_d"):
    """All controllers x seeds x metrics for one matrix."""
    out: Dict[str, Dict[int, dict]] = {}
    for controller in CONTROLLERS:
        out[controller] = {}
        for seed in SEEDS:
            result = load_run(matrix, scenario, controller, seed)
            if result is None:
                continue
            out[controller][seed] = {
                key: metric(result, key) for key in METRICS
            }
            out[controller][seed]["per_member_costs"] = result.get("service", {}).get(
                "per_member_costs"
            )
            out[controller][seed]["energy_sharing"] = result.get("energy_sharing")
    return out


def deltas_block(data, metric_key: str) -> List[dict]:
    """Paired deltas of every controller vs rule_based, with Holm p-values."""
    rows = []
    pvalues = []
    for controller in CONTROLLERS:
        if controller == BASELINE:
            continue
        pairs = []
        for seed in SEEDS:
            if seed not in data[controller] or seed not in data[BASELINE]:
                continue
            base = data[BASELINE][seed][metric_key]
            test = data[controller][seed][metric_key]
            if base is None or test is None:
                continue
            pairs.append(test - base)
        if not pairs:
            continue
        stats = paired_t(pairs)
        rows.append({
            "controller": controller,
            "n": len(pairs),
            "mean": stats["mean"],
            "ci95": describe(pairs)["ci95"],
            "t": stats["t"],
            "p_raw": stats["p"],
        })
        pvalues.append(stats["p"])
    for row, adjusted in zip(rows, holm(pvalues)):
        row["p_holm"] = adjusted
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary: Dict[str, dict] = {}

    for regime, matrix in NEW_MATRICES.items():
        if not (ROOT / matrix).is_dir():
            print(f"[skip] {matrix} not run yet")
            continue
        data = collect(matrix)
        present = {c: len(s) for c, s in data.items() if s}
        complete = all(len(data[c]) == len(SEEDS) for c in CONTROLLERS)
        print(f"[{regime}] runs per controller: {present}")
        if not complete:
            print(
                f"[skip] {matrix} incomplete "
                f"({sum(present.values())}/{len(CONTROLLERS) * len(SEEDS)} runs); "
                "re-run this script when the matrix finishes"
            )
            continue

        if regime == "pool_tou":
            # --- Table 2 (tab:deltas) scenario-D rows ---------------------
            cost_rows = deltas_block(data, "total_cost")
            peak_rows = deltas_block(data, "peak_demand_kw")
            ev_rows = deltas_block(data, "ev_completion_rate")
            lines = [
                "# Scenario D — Table `tab:deltas` rows (pool TOU, post-fix)",
                "",
                "Paired per-seed deltas vs. `rule_based`, n=10 seeds; Holm within",
                "scenario D over the controller comparisons.",
                "",
                "| Scenario | Controller | Δ cost (USD) | Δ peak (kW) | p_Holm |",
                "|---|---|---|---|---|",
            ]
            by_controller = {c: r for c, r in zip([r["controller"] for r in cost_rows], cost_rows)}
            peak_by = {r["controller"]: r for r in peak_rows}
            ev_by = {r["controller"]: r for r in ev_rows}
            for controller in CONTROLLERS:
                if controller == BASELINE:
                    continue
                cost = by_controller.get(controller)
                peak = peak_by.get(controller)
                if not cost or not peak:
                    continue
                ev = ev_by.get(controller)
                p_text = "< 0.0001" if cost["p_holm"] < 0.0001 else f"{cost['p_holm']:.4f}"
                lines.append(
                    f"| D | {controller} | {cost['mean']:+.2f} ± {cost['ci95']:.2f} "
                    f"| {peak['mean']:+.2f} ± {peak['ci95']:.2f} | {p_text} |"
                )
                if ev is not None:
                    summary.setdefault("pool_tou", {}).setdefault("deltas", []).append(
                        {**cost, "delta_peak": peak, "delta_ev": ev}
                    )
            (OUT / "d_deltas_pool_tou.md").write_text("\n".join(lines) + "\n")

            # --- scenario-D KPI means -----------------------------------
            kpi_lines = [
                "# Scenario D — KPI comparison (pool TOU, post-fix)",
                "",
                "| Controller | Total cost (USD) | Peak demand (kW) | EV completion |",
                "|---|---|---|---|",
            ]
            for controller in CONTROLLERS:
                cells = []
                for key in ("total_cost", "peak_demand_kw", "ev_completion_rate"):
                    values = [
                        data[controller][seed][key]
                        for seed in SEEDS
                        if seed in data[controller] and data[controller][seed][key] is not None
                    ]
                    stats = describe(values)
                    cells.append(f"{stats['mean']:.2f} ± {stats['ci95']:.2f}")
                    summary.setdefault("pool_tou", {}).setdefault("kpis", {})[controller] = {
                        key: describe(values)
                    }
                kpi_lines.append(f"| {controller} | {cells[0]} | {cells[1]} | {cells[2]} |")
            (OUT / "d_kpis_pool_tou.md").write_text("\n".join(kpi_lines) + "\n")

        elif regime == "lmp":
            lines = [
                "# Scenario D — LMP-regime rows (post-fix)",
                "",
                "| Controller | Cost TOU (USD) | Cost LMP (USD) | Δ | EV TOU | EV LMP |",
                "|---|---|---|---|---|---|",
            ]
            tou = collect(NEW_MATRICES["pool_tou"])
            for controller in CONTROLLERS:
                lmp_cost = [
                    data[controller][seed]["total_cost"]
                    for seed in SEEDS
                    if seed in data[controller] and data[controller][seed]["total_cost"] is not None
                ]
                tou_cost = [
                    tou[controller][seed]["total_cost"]
                    for seed in SEEDS
                    if seed in tou.get(controller, {}) and tou[controller][seed]["total_cost"] is not None
                ]
                lmp_ev = [
                    data[controller][seed]["ev_completion_rate"]
                    for seed in SEEDS
                    if seed in data[controller]
                ]
                tou_ev = [
                    tou[controller][seed]["ev_completion_rate"]
                    for seed in SEEDS
                    if seed in tou.get(controller, {})
                ]
                a, b = describe(tou_cost), describe(lmp_cost)
                ea, eb = describe(tou_ev), describe(lmp_ev)
                lines.append(
                    f"| {controller} | {a['mean']:.2f} ± {a['ci95']:.2f} "
                    f"| {b['mean']:.2f} ± {b['ci95']:.2f} | {b['mean']-a['mean']:+.2f} "
                    f"| {ea['mean']:.3f} | {eb['mean']:.3f} |"
                )
                summary.setdefault("lmp", {})[controller] = {
                    "cost_tou": a, "cost_lmp": b, "ev_tou": ea, "ev_lmp": eb
                }
            (OUT / "d_rows_lmp.md").write_text("\n".join(lines) + "\n")

        elif regime == "p2p":
            tou = collect(NEW_MATRICES["pool_tou"])
            lines = [
                "# Scenario D — P2P regression check (post-fix)",
                "",
                "Paired per-seed (scenario D, controller, seed) comparison of the new",
                "pool-TOU and P2P runs.",
                "",
                "| Controller | Δ cost P2P−TOU (USD) | Δ peak (kW) | Δ EV | community volume (kWh) |",
                "|---|---|---|---|---|",
            ]
            for controller in CONTROLLERS:
                dc, dp, de, vols = [], [], [], []
                for seed in SEEDS:
                    a = tou.get(controller, {}).get(seed)
                    b = data.get(controller, {}).get(seed)
                    if not a or not b:
                        continue
                    if a["total_cost"] is not None and b["total_cost"] is not None:
                        dc.append(b["total_cost"] - a["total_cost"])
                    if a["peak_demand_kw"] is not None and b["peak_demand_kw"] is not None:
                        dp.append(b["peak_demand_kw"] - a["peak_demand_kw"])
                    if a["ev_completion_rate"] is not None and b["ev_completion_rate"] is not None:
                        de.append(b["ev_completion_rate"] - a["ev_completion_rate"])
                    sharing = b.get("energy_sharing") or {}
                    volume = sharing.get("total_community_volume_kwh")
                    if volume is not None:
                        vols.append(volume)
                stats_c = describe(dc) if dc else None
                stats_p = describe(dp) if dp else None
                stats_e = describe(de) if de else None
                stats_v = describe(vols) if vols else None
                lines.append(
                    f"| {controller} "
                    f"| {stats_c['mean']:+.2f} ± {stats_c['ci95']:.2f} "
                    f"| {stats_p['mean']:+.2f} ± {stats_p['ci95']:.2f} "
                    f"| {stats_e['mean']:+.4f} "
                    f"| {stats_v['mean']:.1f} ± {stats_v['ci95']:.1f} |"
                    if all([stats_c, stats_p, stats_e, stats_v])
                    else f"| {controller} | — | — | — | — |"
                )
                summary.setdefault("p2p", {})[controller] = {
                    "delta_cost": stats_c, "delta_peak": stats_p,
                    "delta_ev": stats_e, "volume_kwh": stats_v,
                }
            (OUT / "d_rows_p2p.md").write_text("\n".join(lines) + "\n")

    (OUT / "d_summary.json").write_text(json.dumps(summary, indent=1, default=float))
    print(f"\nwrote {OUT}/")


if __name__ == "__main__":
    main()
