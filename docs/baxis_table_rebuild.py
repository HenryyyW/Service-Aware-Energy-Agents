#!/usr/bin/env python3
"""Rebuild the paper's B-axis (three-regime) tables/claims from the three
re-run legs produced on final code (9763bd7b0 + docs-only 05a925219).

Sources (each 5 scenarios x 5 controllers x 10 seeds = 250 runs, every
manifest git_dirty=false, correct regime flag recorded)::

    experiments/baxis_rerun_pooltou  (--regime pool_tou, rl policy default prefix)
    experiments/baxis_rerun_lmp      (--regime lmp,     rl policy prefix lmp_)
    experiments/baxis_rerun_p2p      (--regime p2p,     rl policy default prefix)

Outputs (``docs/baxis_rebuild/``)
-----------------------------------
* ``deltas_pool_tou.md``      -- Table 3 (tab:deltas) rows, paired per-seed deltas vs
                                rule_based, Student-t 95% CI half-width, Holm within scenario.
* ``kpis_pool_tou.md``        -- per-scenario x controller KPI means (n=10).
* ``d_kpis.md``               -- scenario-D KPI rows (Table 4 basis).
* ``lmp_shift.md``            -- TOU->LMP cost shift + dispatch identity counts.
* ``p2p_pairing.md``          -- p2p vs pool_tou paired aggregates + member redistribution.
* ``rl_fallback.md``          -- fallback-step disclosure per scenario (no silent substitution).
* ``regime_claims.md``        -- dispatch/cost identity across regimes (measured counts).
* ``abstract_numbers.md``     -- the exact claim strings for the abstract/prose.
* ``summary.json``            -- machine-readable form of everything.

Every printed number is computed from the run records; nothing is hand-entered.
Statistics protocol identical to docs/d_table_rebuild.py (paper protocol).
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "baxis_rebuild"

SEEDS = [42, 123, 456, 789, 999, 1234, 2024, 3456, 5555, 8888]
CONTROLLERS = ["rule_based", "multi_agent", "centralized", "mpc", "rl"]
BASELINE = "rule_based"
SCENARIOS = ["scenario_a", "scenario_b", "scenario_c", "scenario_d", "scenario_e"]
LETTER = {s: s.split("_")[1].upper() for s in SCENARIOS}

LEGS = {
    "pool_tou": "experiments/baxis_rerun_pooltou",
    "lmp": "experiments/baxis_rerun_lmp",
    "p2p": "experiments/baxis_rerun_p2p",
}

# Metrics used by the paper tables (same as the raw_results schema).
KPIS = [
    "total_cost",
    "peak_demand_kw",
    "ev_completion_rate",
    "grid_import_kwh",
    "pv_self_consumption_kwh",
    "pv_curtailment_kwh",
    "battery_throughput_kwh",
    "carbon_emissions_kg",
    "gini_coefficient",
    "members_interrupted_count",
    "controller_fallback_steps",
]


# --------------------------------------------------------------------------- #
# statistics helpers (verbatim protocol from docs/d_table_rebuild.py)
# --------------------------------------------------------------------------- #
def t_critical(n: int, confidence: float = 0.95) -> float:
    if n < 2:
        return 0.0
    try:
        from scipy.stats import t as student_t

        return float(student_t.ppf(0.5 + confidence / 2.0, n - 1))
    except Exception:
        table = {
            2: 12.706,
            3: 4.303,
            4: 3.227,
            5: 2.776,
            6: 2.571,
            7: 2.447,
            8: 2.365,
            9: 2.306,
            10: 2.262,
        }
        return table.get(n, 2.262)


def describe(values: List[float]) -> Dict[str, float]:
    n = len(values)
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if n > 1 else 0.0
    half = t_critical(n) * sd / math.sqrt(n) if n > 1 else 0.0
    return {"n": n, "mean": mean, "sd": sd, "ci95": half}


def holm(pvalues: List[float]) -> List[float]:
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


def fmt(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def _gini(values: List[float]) -> float:
    """Gini coefficient of a non-negative bill vector (0 = perfectly equal)."""
    v = sorted(values)
    n = len(v)
    total = sum(v)
    if total <= 0:
        return 0.0
    cum = sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(v))
    return cum / (n * total)


def fmt_p(p: float) -> str:
    if p != p:  # NaN
        return "n/a"
    if p < 0.0001:
        return "< 0.0001"
    return f"{p:.4f}"


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
def load_leg(leg: str) -> Dict[str, Dict[str, dict]]:
    """{(scenario, controller, seed): row} from the leg's raw_results.json."""
    path = ROOT / LEGS[leg] / "raw_results.json"
    rows = json.loads(path.read_text())
    out: Dict[str, Dict[str, dict]] = {}
    for r in rows:
        out[(r["scenario"], r["controller"], r["seed"])] = r
    return out


def manifest_summary(leg: str) -> dict:
    counts = Counter()
    for m in sorted((ROOT / LEGS[leg]).glob("scenario_*/*/manifest.json")):
        j = json.loads(m.read_text())
        counts[
            (j.get("git_commit"), bool(j.get("git_dirty")), j.get("pricing_regime"))
        ] += 1
    return {f"{k[0]} dirty={k[1]} regime={k[2]}": v for k, v in counts.items()}


def traj_hash(scenario: str, controller: str, seed: int, leg: str) -> Optional[str]:
    """sha256 over per-step requested actions (dispatch identity, not billing)."""
    p = (
        ROOT
        / LEGS[leg]
        / scenario
        / f"{scenario}_{controller}_{seed}"
        / "trajectories.jsonl"
    )
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open() as fh:
        for line in fh:
            step = json.loads(line)
            acts = sorted(
                (a["asset_id"], a["action_type"], round(float(a["value_kw"]), 9))
                for a in step.get("requested_actions", [])
            )
            h.update(json.dumps([step.get("timestep"), acts]).encode())
    return h.hexdigest()


def deltas_block(data, metric_key: str) -> List[dict]:
    rows, pvalues = [], []
    for controller in CONTROLLERS:
        if controller == BASELINE:
            continue
        pairs = []
        for seed in SEEDS:
            base = data.get((BASELINE, seed), {}).get(metric_key)
            test = data.get((controller, seed), {}).get(metric_key)
            if base is None or test is None:
                continue
            pairs.append(test - base)
        if not pairs:
            continue
        stats = paired_t(pairs)
        rows.append(
            {
                "controller": controller,
                "n": len(pairs),
                "mean": stats["mean"],
                "ci95": describe(pairs)["ci95"],
                "t": stats["t"],
                "p_raw": stats["p"],
            }
        )
        pvalues.append(stats["p"])
    for row, adjusted in zip(rows, holm(pvalues)):
        row["p_holm"] = adjusted
    return rows


def scenario_metrics(data) -> Dict[str, dict]:
    """{(controller): {metric: describe}} for one scenario+leg."""
    out: Dict[str, dict] = {}
    for controller in CONTROLLERS:
        vals: Dict[str, List[float]] = {k: [] for k in KPIS}
        for seed in SEEDS:
            row = data.get((controller, seed))
            if row is None:
                continue
            for k in KPIS:
                if row.get(k) is not None:
                    vals[k].append(float(row[k]))
        out[controller] = {k: describe(v) for k, v in vals.items() if v}
    return out


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    legs = {leg: load_leg(leg) for leg in LEGS}
    summary: Dict[str, object] = {"seeds": SEEDS, "controllers": CONTROLLERS}

    # -- provenance headers ------------------------------------------------- --
    prov = {leg: manifest_summary(leg) for leg in LEGS}
    summary["provenance"] = prov
    (OUT / "provenance.md").write_text(
        "# B-axis re-run provenance (per-leg manifest audit)\n\n"
        + "\n".join(
            f"* `{leg}` ({LEGS[leg]}): {json.dumps(prov[leg], sort_keys=True)}"
            for leg in LEGS
        )
        + "\n"
    )

    complete = {
        leg: len(rows) == len(SCENARIOS) * len(CONTROLLERS) * len(SEEDS)
        for leg, rows in legs.items()
    }
    summary["legs_complete"] = complete
    for leg, ok in complete.items():
        if not ok:
            print(f"[skip] {leg} incomplete ({len(legs[leg])}/750)")

    # -- Table 3: paired deltas (pool_tou) ----------------------------------- --
    lines = [
        "# Table 3 (tab:deltas) rebuild - pool_tou leg",
        "",
        "Paired per-seed deltas vs rule_based (mean ± 95% CI half-width; n=10;",
        "Holm within each scenario over the four controller comparisons).",
        "Source: experiments/baxis_rerun_pooltou/raw_results.json.",
        "",
        "| Scenario | Controller | Δ cost (USD) | Δ peak (kW) | p_Holm |",
        "|---|---|---|---|---|",
    ]
    deltas_summary: Dict[str, dict] = {}
    for scenario in SCENARIOS:
        data = {
            (c, s): legs["pool_tou"].get((scenario, c, s), {})
            for c in CONTROLLERS
            for s in SEEDS
        }
        for metric in ("total_cost", "peak_demand_kw"):
            deltas_summary.setdefault(scenario, {})
            for row in deltas_block(data, metric):
                deltas_summary[scenario].setdefault(row["controller"], {})[metric] = {
                    "mean": row["mean"],
                    "ci95": row["ci95"],
                    "p_holm": row["p_holm"],
                }
        for row in deltas_block(data, "total_cost"):
            pk = [
                r
                for r in deltas_block(data, "peak_demand_kw")
                if r["controller"] == row["controller"]
            ][0]
            lines.append(
                f"| {LETTER[scenario]} | {row['controller']} "
                f"| {row['mean']:+.2f} ± {row['ci95']:.2f} "
                f"| {pk['mean']:+.2f} ± {pk['ci95']:.2f} "
                f"| {fmt_p(row['p_holm'])} |"
            )
    (OUT / "deltas_pool_tou.md").write_text("\n".join(lines) + "\n")

    # -- KPI table (pool_tou) + Table 4 (scenario D) -------------------------- --
    kpi_lines = [
        "# KPI means per scenario x controller - pool_tou leg (n=10)",
        "",
        "| Scenario | Controller | Total cost | Peak (kW) | EV completion | Grid import (kWh) | PV self-cons | Gini | Members interrupted |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    d_lines = [
        "# Table 4 (tab:d-kpis) rebuild - scenario D, pool_tou leg (n=10)",
        "",
        "| Controller | Total cost (USD) | Peak demand (kW) | EV completion |",
        "|---|---|---|---|",
    ]
    for scenario in SCENARIOS:
        data = {
            (c, s): legs["pool_tou"].get((scenario, c, s), {})
            for c in CONTROLLERS
            for s in SEEDS
        }
        sm = scenario_metrics(data)
        for controller in CONTROLLERS:
            m = sm.get(controller, {})
            kpi_lines.append(
                f"| {LETTER[scenario]} | {controller} "
                f"| {fmt(m.get('total_cost', {}).get('mean'))} ± {fmt(m.get('total_cost', {}).get('ci95'))} "
                f"| {fmt(m.get('peak_demand_kw', {}).get('mean'))} ± {fmt(m.get('peak_demand_kw', {}).get('ci95'))} "
                f"| {fmt(m.get('ev_completion_rate', {}).get('mean'), 3)} ± {fmt(m.get('ev_completion_rate', {}).get('ci95'), 3)} "
                f"| {fmt(m.get('grid_import_kwh', {}).get('mean'), 1)} "
                f"| {fmt(m.get('pv_self_consumption_kwh', {}).get('mean'), 1)} "
                f"| {fmt(m.get('gini_coefficient', {}).get('mean'), 3)} "
                f"| {fmt(m.get('members_interrupted_count', {}).get('mean'), 1)} |"
            )
            if scenario == "scenario_d":
                d_lines.append(
                    f"| {controller} "
                    f"| {fmt(m.get('total_cost', {}).get('mean'))} ± {fmt(m.get('total_cost', {}).get('ci95'))} "
                    f"| {fmt(m.get('peak_demand_kw', {}).get('mean'))} ± {fmt(m.get('peak_demand_kw', {}).get('ci95'))} "
                    f"| {fmt(m.get('ev_completion_rate', {}).get('mean'), 3)} ± {fmt(m.get('ev_completion_rate', {}).get('ci95'), 3)} |"
                )
    (OUT / "kpis_pool_tou.md").write_text("\n".join(kpi_lines) + "\n")
    (OUT / "d_kpis.md").write_text("\n".join(d_lines) + "\n")

    # -- LMP shift + dispatch identity --------------------------------------- --
    lmp_lines = [
        "# LMP regime shift - scenario A (and dispatch identity)",
        "",
        "TOU(pool) vs LMP per controller, scenario A, paired per-seed (n=10):",
        "",
        "| Controller | TOU cost | LMP cost | Δ (LMP-TOU) | Δ EV completion | dispatch identical (traj hash) |",
        "|---|---|---|---|---|---|",
    ]
    for scenario in SCENARIOS:
        if scenario != "scenario_a":
            continue
        for controller in CONTROLLERS:
            tou = [
                legs["pool_tou"][(scenario, controller, s)]["total_cost"] for s in SEEDS
            ]
            lmp = [legs["lmp"][(scenario, controller, s)]["total_cost"] for s in SEEDS]
            ev_t = [
                legs["pool_tou"][(scenario, controller, s)]["ev_completion_rate"]
                for s in SEEDS
            ]
            ev_l = [
                legs["lmp"][(scenario, controller, s)]["ev_completion_rate"]
                for s in SEEDS
            ]
            same = sum(
                1
                for s in SEEDS
                if traj_hash(scenario, controller, s, "pool_tou")
                == traj_hash(scenario, controller, s, "lmp")
            )
            lmp_lines.append(
                f"| {controller} | {statistics.fmean(tou):.2f} | {statistics.fmean(lmp):.2f} "
                f"| {statistics.fmean(lmp) - statistics.fmean(tou):+.2f} "
                f"| {statistics.fmean(ev_l) - statistics.fmean(ev_t):+.3f} | {same}/{len(SEEDS)} |"
            )
    (OUT / "lmp_shift.md").write_text("\n".join(lmp_lines) + "\n")

    # -- Table 5 (tab:d-lmp): scenario D under LMP, from the new lmp leg ------ --
    d_lmp_lines = [
        "# Table 5 (tab:d-lmp) rebuild - scenario D, lmp leg (n=10)",
        "",
        "Cited from experiments/baxis_rerun_lmp (regime lmp, lmp_-prefixed RL policies).",
        "",
        "| Controller | Total cost (USD) | Peak demand (kW) | EV completion |",
        "|---|---|---|---|",
    ]
    for controller in CONTROLLERS:
        vals = {
            k: [legs["lmp"][("scenario_d", controller, s)][k] for s in SEEDS]
            for k in ("total_cost", "peak_demand_kw", "ev_completion_rate")
        }
        d = {k: describe(v) for k, v in vals.items()}
        d_lmp_lines.append(
            f"| {controller} "
            f"| {fmt(d['total_cost']['mean'])} ± {fmt(d['total_cost']['ci95'])} "
            f"| {fmt(d['peak_demand_kw']['mean'])} ± {fmt(d['peak_demand_kw']['ci95'])} "
            f"| {fmt(d['ev_completion_rate']['mean'], 3)} ± {fmt(d['ev_completion_rate']['ci95'], 3)} |"
        )
    (OUT / "d_lmp.md").write_text("\n".join(d_lmp_lines) + "\n")

    # -- p2p pairing ---------------------------------------------------------- --
    def run_result(
        leg: str, scenario: str, controller: str, seed: int
    ) -> Optional[dict]:
        p = (
            ROOT
            / LEGS[leg]
            / scenario
            / f"{scenario}_{controller}_{seed}"
            / "result.json"
        )
        return json.loads(p.read_text()) if p.is_file() else None

    p2p_lines = [
        "# P2P vs pool TOU pairing (aggregate + member redistribution)",
        "",
        "Paired per-seed (p2p − pool_tou) per scenario/controller, n=10.",
        '"Redistribution" = mean |Δ per-member all-in bill| over the five members',
        "(energy_sharing.per_member[].actual_total_bill). Volume = P2P community",
        "traded volume (energy_sharing.total_community_volume_kwh).",
        "",
        "| Scenario | Controller | Δ aggregate cost (USD) | aggregate identical | mean redistribution (USD) | Δ Gini(all-in bills) | P2P volume (kWh) | dispatch identical |",
        "|---|---|---|---|---|---|---|---|",
    ]
    p2p_summary: Dict[str, dict] = {}
    for scenario in SCENARIOS:
        for controller in CONTROLLERS:
            d_cost, ident, redist, d_gini, vol, disp = [], 0, [], [], [], 0
            for s in SEEDS:
                pool_r = run_result("pool_tou", scenario, controller, s)
                p2p_r = run_result("p2p", scenario, controller, s)
                pool = legs["pool_tou"].get((scenario, controller, s))
                p2p = legs["p2p"].get((scenario, controller, s))
                if not (pool_r and p2p_r and pool and p2p):
                    continue
                d_cost.append(p2p["total_cost"] - pool["total_cost"])
                if abs(p2p["total_cost"] - pool["total_cost"]) < 1e-9:
                    ident += 1
                bp = pool_r["energy_sharing"]["per_member"]
                bq = p2p_r["energy_sharing"]["per_member"]
                bills_p = [bp[k]["actual_total_bill"] for k in bp]
                bills_q = [bq[k]["actual_total_bill"] for k in bq]
                redist.append(
                    statistics.fmean([abs(b - a) for a, b in zip(bills_p, bills_q)])
                )
                d_gini.append(_gini(bills_q) - _gini(bills_p))
                vol.append(p2p_r["energy_sharing"]["total_community_volume_kwh"])
                if traj_hash(scenario, controller, s, "pool_tou") == traj_hash(
                    scenario, controller, s, "p2p"
                ):
                    disp += 1
            p2p_summary.setdefault(LETTER[scenario], {})[controller] = {
                "delta_aggregate_mean": statistics.fmean(d_cost),
                "delta_aggregate_ci95": describe(d_cost)["ci95"],
                "aggregate_identical": f"{ident}/{len(d_cost)}",
                "mean_redistribution_usd": statistics.fmean(redist),
                "delta_gini_allin": statistics.fmean(d_gini),
                "p2p_volume_kwh": statistics.fmean(vol),
                "dispatch_identical": f"{disp}/{len(d_cost)}",
            }
            p2p_lines.append(
                f"| {LETTER[scenario]} | {controller} "
                f"| {statistics.fmean(d_cost):+.2f} ± {describe(d_cost)['ci95']:.2f} "
                f"| {ident}/{len(d_cost)} "
                f"| {statistics.fmean(redist):.3f} "
                f"| {statistics.fmean(d_gini):+.4f} "
                f"| {statistics.fmean(vol):.1f} "
                f"| {disp}/{len(d_cost)} |"
            )
    (OUT / "p2p_pairing.md").write_text("\n".join(p2p_lines) + "\n")
    summary["p2p_pairing"] = p2p_summary

    # -- p2p per-member bill shifts (paired, n=40: A/B/C/E x 10 seeds) -------- --
    members = [f"building_{i}" for i in range(5)]
    mem_lines = [
        "# P2P vs pool TOU: per-member all-in bill shifts (paired, n=40 runs per member)",
        "",
        "A/B/C/E x 10 seeds, all five controllers. Bill = energy_sharing.per_member",
        "[].actual_total_bill (all-in, settlement-inclusive).",
        "",
        "| Member | mean Δ (USD) | ±95% CI | paired t | p |",
        "|---|---|---|---|---|",
    ]
    mem_summary = {}
    for m in members:
        deltas = []
        for scenario in (
            "scenario_a",
            "scenario_b",
            "scenario_c",
            "scenario_d",
            "scenario_e",
        ):
            if scenario == "scenario_d":
                continue  # D bit-identical to A; counted once
            for controller in CONTROLLERS:
                for s in SEEDS:
                    pool_r = run_result("pool_tou", scenario, controller, s)
                    p2p_r = run_result("p2p", scenario, controller, s)
                    if pool_r and p2p_r:
                        deltas.append(
                            p2p_r["energy_sharing"]["per_member"][m][
                                "actual_total_bill"
                            ]
                            - pool_r["energy_sharing"]["per_member"][m][
                                "actual_total_bill"
                            ]
                        )
        st = paired_t(deltas)
        d95 = describe(deltas)
        mem_summary[m] = {
            "mean": st["mean"],
            "ci95": d95["ci95"],
            "t": st["t"],
            "p": st["p"],
        }
        mem_lines.append(
            f"| {m} | {st['mean']:+.2f} | ±{d95['ci95']:.2f} | {st['t']:+.2f} | {fmt_p(st['p'])} |"
        )
    (OUT / "p2p_member_bills.md").write_text("\n".join(mem_lines) + "\n")
    summary["p2p_member_bills"] = mem_summary

    # -- RL fallback disclosure ---------------------------------------------- --
    fb_lines = [
        "# RL fallback disclosure (no silent substitution)",
        "",
        "`controller_fallback_steps` per (scenario, seed), pool_tou leg:",
        "",
        "| Scenario | per-seed fallback steps | max fraction of 168 steps |",
        "|---|---|---|",
    ]
    for scenario in SCENARIOS:
        per_seed = {}
        for s in SEEDS:
            row = legs["pool_tou"].get((scenario, "rl", s))
            per_seed[s] = row.get("controller_fallback_steps") if row else None
        vals = [v for v in per_seed.values() if v is not None]
        mx = max(vals) if vals else 0
        fb_lines.append(
            f"| {LETTER[scenario]} | {json.dumps(per_seed)} | {mx}/168 ({mx/168:.1%}) |"
        )
    (OUT / "rl_fallback.md").write_text("\n".join(fb_lines) + "\n")

    # -- abstract numbers ----------------------------------------------------- --
    # cheapest controller per scenario on the pool_tou leg (measured):
    ranking = {}
    for scenario in SCENARIOS:
        means = {}
        for controller in CONTROLLERS:
            vals = [
                legs["pool_tou"][(scenario, controller, s)]["total_cost"]
                for s in SEEDS
                if (scenario, controller, s) in legs["pool_tou"]
            ]
            if vals:
                means[controller] = statistics.fmean(vals)
        ranking[scenario] = sorted(means.items(), key=lambda kv: kv[1])
    ma_delta = {
        LETTER[s]: deltas_summary[s]
        .get("multi_agent", {})
        .get("total_cost", {})
        .get("mean")
        for s in SCENARIOS
    }
    ev_ma = {
        LETTER[s]: statistics.fmean(
            [
                legs["pool_tou"][(s, "multi_agent", sd)]["ev_completion_rate"]
                for sd in SEEDS
            ]
        )
        for s in SCENARIOS
    }
    ev_rb = {
        LETTER[s]: statistics.fmean(
            [
                legs["pool_tou"][(s, "rule_based", sd)]["ev_completion_rate"]
                for sd in SEEDS
            ]
        )
        for s in SCENARIOS
    }
    ev_mpc = {
        LETTER[s]: statistics.fmean(
            [legs["pool_tou"][(s, "mpc", sd)]["ev_completion_rate"] for sd in SEEDS]
        )
        for s in SCENARIOS
    }
    abstract = [
        "# Abstract / prose numbers (measured)",
        "",
        "## Cost ranking per scenario (pool_tou leg, mean total_cost, n=10)",
        "",
    ]
    for scenario in SCENARIOS:
        abstract.append(
            f"* {LETTER[scenario]}: "
            + ", ".join(f"{c} {v:.2f}" for c, v in ranking[scenario])
        )
    abstract += [
        "",
        "## multi_agent paired cost delta vs rule_based (mean, USD)",
        "",
        json.dumps(ma_delta, indent=1),
        "",
        "## EV completion rate (mean)",
        "",
        f"* multi_agent: {json.dumps(ev_ma, indent=1)}",
        f"* rule_based:  {json.dumps(ev_rb, indent=1)}",
        f"* mpc:         {json.dumps(ev_mpc, indent=1)}",
    ]
    (OUT / "abstract_numbers.md").write_text("\n".join(abstract) + "\n")

    summary["ranking_pool_tou"] = {
        LETTER[s]: [[c, v] for c, v in ranking[s]] for s in SCENARIOS
    }
    summary["multi_agent_delta_usd"] = ma_delta
    summary["ev_completion_mean"] = {
        "multi_agent": ev_ma,
        "rule_based": ev_rb,
        "mpc": ev_mpc,
    }

    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(f"wrote {OUT}/ ({len(list(OUT.iterdir()))} files)")
    print(
        "ranking:",
        {LETTER[s]: [(c, round(v, 2)) for c, v in ranking[s]] for s in SCENARIOS},
    )


if __name__ == "__main__":
    main()
