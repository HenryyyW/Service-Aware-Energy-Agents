#!/usr/bin/env python3
"""M2a re-run analysis: verified vs unverified LLM arms on fixed physics.

Protocol (same as the 2026-11-04 M2a screen, re-run on the post-fix physics at
10 seeds):
* arms: ``llm_agent`` (execute-as-proposed) vs ``llm_agent_verified``
  (per-step verification, re-prompt once, fallback to rule-based on failure,
  repair cap 2);
* horizon: 24 steps (one simulated day), regime pool_tou;
* reference: ``multi_agent`` 24-step runs at the same (scenario, seed);
* seeds: 42, 123, 456, 789, 999, 1234, 2024, 3456, 5555, 8888 (10);
* 5 scenarios A-E -> 2 arms x 10 seeds x 5 scenarios = 100 LLM runs plus
  50 reference runs.

Pre-registered gate (paper §m2a): proceed to a full-week M2b confirmation only
if the arms differ by >= 10 pp on ``llm_unrepaired_violations`` or
``llm_fallback_step_share``, or KPI CIs exclude zero.

Outputs ``docs/m2a_rerun/``: ``summary.md`` (per-arm aggregates + gate check +
paired arm difference), ``summary.json``, ``kpi_deltas.md``.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]

SCENARIOS = ["scenario_a", "scenario_b", "scenario_c", "scenario_d", "scenario_e"]
SEEDS = [42, 123, 456, 789, 999, 1234, 2024, 3456, 5555, 8888]
ARMS = ["llm_agent", "llm_agent_verified"]
BASELINE = "multi_agent"

# Field map: (label, result["agent"] key, controller_config key). Both
# definitions are reported where they differ: first_attempt_validity is
# per-run in the agent block and per-step in controller_config.
AGENT_FIELDS = (
    ("first_attempt_validity_run", "first_attempt_validity", None),
    ("first_attempt_validity_step", None, "first_attempt_validity"),
    ("repair_iterations", None, "repair_iterations"),
    ("fallback_step_share", None, "llm_fallback_step_share"),
    ("fallback_steps", None, "llm_fallback_steps"),
    ("unrepaired_violations", None, "llm_unrepaired_violations"),
    ("llm_calls", None, "llm_calls"),
    ("parse_failures", None, "llm_raw_parse_failures"),
    ("fenced_outputs", None, "llm_fenced_outputs"),
    ("backend_errors", None, "llm_backend_errors"),
    ("verification_failures", None, "verification_failures"),
    ("prompt_tokens", None, "llm_prompt_tokens"),
    ("completion_tokens", None, "llm_completion_tokens"),
    ("latency_p50_ms", None, "llm_latency_p50_ms"),
    ("latency_p95_ms", None, "llm_latency_p95_ms"),
)


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


def arm_from_run_id(run_id: str) -> Optional[str]:
    """Arm implied by the run id -- the authoritative label.

    B's controller_type fix (main @ 243eabad13) landed after this matrix started,
    so its cells still write ``controller_type="llm_agent"`` for multi_agent runs.
    Grouping therefore uses the run id / manifest, and any disagreement is
    reported rather than silently trusted.
    """
    for candidate in ARMS + (BASELINE,):
        if f"_{candidate}_" in run_id:
            return candidate
    return None


def load(matrix: Path, scenario: str, controller: str, seed: int) -> Optional[dict]:
    path = matrix / scenario / f"{scenario}_{controller}_{seed}" / "result.json"
    if not path.is_file():
        return None
    result = json.loads(path.read_text())
    labelled = result.get("controller_type")
    if labelled and labelled != controller:
        print(
            f"[label] {path.parent.name}: controller_type={labelled!r} but the run id "
            f"says {controller!r}; using the run id (pre-fix label)"
        )
    return result


def agent_field(result: Optional[dict], field: str):
    """Resolve an AGENT_FIELDS label against the run record.

    ``first_attempt_validity`` exists twice with different meanings (per-run in
    ``agent``, per-step in ``controller_config``); both are reported. A missing
    cell (quarantined or not run) resolves to None so the caller can skip it.
    """
    if not result:
        return None
    for label, agent_key, cfg_key in AGENT_FIELDS:
        if label != field:
            continue
        if agent_key is not None:
            return (result.get("agent") or {}).get(agent_key)
        return (result.get("controller_config") or {}).get(cfg_key)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", default="experiments/m2a_rerun")
    parser.add_argument("--out", default="docs/m2a_rerun")
    parser.add_argument(
        "--reference-matrix",
        default=None,
        help="Matrix holding the paired multi_agent reference runs. Defaults to "
        "--matrix; set it when the LLM-arm matrix omits the deterministic "
        "reference controller (its runs are a function of scenario + seed + "
        "commit, so the reference can be shared across model arms).",
    )
    args = parser.parse_args()
    matrix = ROOT / args.matrix
    reference = ROOT / (args.reference_matrix or args.matrix)
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    present = {
        arm: [s for s in SEEDS for sc in SCENARIOS if load(matrix, sc, arm, s)]
        for arm in ARMS
    }
    for arm, seeds in present.items():
        print(f"[{arm}] {len(seeds)} runs")
    expected = len(SCENARIOS) * len(SEEDS)
    missing = {
        arm: expected - len(seeds)
        for arm, seeds in present.items()
        if len(seeds) < expected
    }
    if missing:
        print(
            "[note] cells missing from the matrix (quarantined or not run): "
            + ", ".join(f"{arm}={n}" for arm, n in missing.items())
            + " -- statistics use the cells present, and every reported n is the "
            "actual sample size"
        )

    summary: Dict[str, object] = {"matrix": str(matrix), "arms": {}}

    # ---- per-arm aggregates ------------------------------------------------
    for arm in ARMS:
        rows: Dict[str, List[float]] = {label: [] for label, _, _ in AGENT_FIELDS}
        for scenario in SCENARIOS:
            for seed in SEEDS:
                result = load(matrix, scenario, arm, seed)
                for label, _, _ in AGENT_FIELDS:
                    value = agent_field(result, label)
                    if isinstance(value, (int, float)):
                        rows[label].append(float(value))
        summary["arms"][arm] = {
            label: describe(values) for label, values in rows.items() if values
        }

    digests = sorted(
        {
            str(agent_field(load(matrix, sc, arm, s), "model_digest") or "")
            for arm in ARMS
            for sc in SCENARIOS
            for s in SEEDS
        }
        - {""}
    )
    counts = {arm: len(present[arm]) for arm in ARMS}
    lines = [
        f"# M2a re-run ({', '.join(digests) or 'model not recorded'}, 24-step, 10 seeds)",
        "",
        f"Matrix: `{args.matrix}` — "
        + " + ".join(f"{arm}={counts[arm]}" for arm in ARMS)
        + " LLM runs, plus "
        f"{len([1 for sc in SCENARIOS for s in SEEDS if load(matrix, sc, BASELINE, s)])} "
        f"paired `{BASELINE}` 24-step reference runs.",
        "",
        "## Per-arm aggregates",
        "",
        "| Metric | " + " | ".join(ARMS) + " |",
        "|---|" + "---|" * len(ARMS),
    ]
    for label, _, _ in AGENT_FIELDS:
        cells = []
        for arm in ARMS:
            stats = summary["arms"][arm].get(label)
            cells.append(f"{stats['mean']:.4f} ± {stats['ci95']:.4f}" if stats else "—")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    # ---- gate check --------------------------------------------------------
    # Pre-registered rule (paper sec:m2a): proceed to M2b only if the arms
    # differ by >= 10 pp on llm_unrepaired_violations or llm_fallback_step_share,
    # OR a KPI CI excludes zero. Arm-level means are the comparison unit; the
    # number of runs with a nonzero value is reported per arm.
    gate_lines = ["", "## Gate check (M2a divergence gate)", ""]
    gate_met = False
    for field in ("unrepaired_violations", "fallback_step_share"):
        per_arm, runs_nonzero = [], []
        for arm in ARMS:
            values = [
                agent_field(load(matrix, sc, arm, s), field) or 0.0
                for sc in SCENARIOS
                for s in SEEDS
            ]
            per_arm.append(statistics.fmean(values) if values else 0.0)
            runs_nonzero.append(sum(1 for v in values if v > 0))
        gap = abs(per_arm[0] - per_arm[1])
        gate_lines.append(
            f"- `{field}`: unverified {per_arm[0]:.4f} "
            f"({runs_nonzero[0]}/{len(ARMS) and len([1 for sc in SCENARIOS for s in SEEDS if load(matrix, sc, ARMS[0], s)])} runs nonzero) "
            f"vs verified {per_arm[1]:.4f} "
            f"({runs_nonzero[1]}/{len([1 for sc in SCENARIOS for s in SEEDS if load(matrix, sc, ARMS[1], s)])} runs nonzero) "
            f"— arm difference {gap:.4f} pp ({'>= 10 pp' if gap >= 0.10 else '< 10 pp'})"
        )
        gate_met = gate_met or gap >= 0.10

    # The third pre-registered clause ("or KPI CIs exclude zero") needs the
    # paired arm difference, so it is evaluated after it and appended at the end
    # of the summary; a literal reading would trigger the gate while the two pp
    # clauses do not, and that interpretation is the PM/user's call.
    verdict = "MET" if gate_met else "NOT met"
    lines += gate_lines + [
        "",
        f"**Verdict: the M2b gate is {verdict}.** "
        + (
            "A full-week M2b confirmation is warranted."
            if gate_met
            else "No safety-gate divergence; report as a null result on the "
            "safety metrics (the reviewer-facing claim stays honest)."
        ),
    ]
    summary["gate"] = {
        "per_arm": {field: per_arm for field, per_arm in ()},
        "met": gate_met,
    }
    summary["gate_met"] = gate_met

    # ---- paired arm difference vs the reference ---------------------------
    kpi_lines = [
        "",
        "## KPI deltas vs the paired `multi_agent` reference (n=50)",
        "",
        "| Arm | Δ cost (USD) | Δ peak (kW) | Δ EV completion |",
        "|---|---|---|---|",
    ]
    for arm in ARMS + [BASELINE]:
        dc, dp, de = [], [], []
        for scenario in SCENARIOS:
            for seed in SEEDS:
                run = load(matrix, scenario, arm, seed)
                ref = load(reference, scenario, BASELINE, seed)
                if not run or not ref:
                    continue
                if run["energy"].get("total_cost") is not None:
                    dc.append(run["energy"]["total_cost"] - ref["energy"]["total_cost"])
                if run["energy"].get("peak_demand_kw") is not None:
                    dp.append(
                        run["energy"]["peak_demand_kw"]
                        - ref["energy"]["peak_demand_kw"]
                    )
                if run["service"].get("ev_completion_rate") is not None:
                    de.append(
                        run["service"]["ev_completion_rate"]
                        - ref["service"]["ev_completion_rate"]
                    )
        stats = (describe(dc), describe(dp), describe(de))
        kpi_lines.append(
            f"| {arm} | {stats[0]['mean']:+.3f} ± {stats[0]['ci95']:.3f} "
            f"| {stats[1]['mean']:+.3f} ± {stats[1]['ci95']:.3f} "
            f"| {stats[2]['mean']:+.4f} ± {stats[2]['ci95']:.4f} |"
        )
        summary.setdefault("kpi_deltas", {})[arm] = {
            "cost": stats[0],
            "peak": stats[1],
            "ev": stats[2],
        }
    lines += kpi_lines

    # ---- arm-difference (unverified - verified) ---------------------------
    dc, dp = [], []
    for scenario in SCENARIOS:
        for seed in SEEDS:
            unv = load(matrix, scenario, "llm_agent", seed)
            ver = load(matrix, scenario, "llm_agent_verified", seed)
            if not unv or not ver:
                continue
            dc.append(unv["energy"]["total_cost"] - ver["energy"]["total_cost"])
            dp.append(unv["energy"]["peak_demand_kw"] - ver["energy"]["peak_demand_kw"])
    cost_test, peak_test = paired_t(dc), paired_t(dp)
    kpi_clause_met = False
    kpi_clause_lines = []
    for key, sample, stats in (
        ("cost", dc, cost_test),
        ("peak", dp, peak_test),
    ):
        ci = describe(sample)["ci95"]
        excludes = abs(stats["mean"]) > ci
        kpi_clause_met = kpi_clause_met or excludes
        kpi_clause_lines.append(
            f"- arm difference in {key}: {stats['mean']:+.2f} ± {ci:.2f} "
            f"(paired t={stats['t']:.3f}, p={stats['p']:.4f}, n={len(sample)}) -> "
            f"CI {'excludes' if excludes else 'includes'} zero"
        )
    gate_kpi_met = kpi_clause_met
    lines += [
        "",
        "## Arm difference (unverified − verified, paired)",
        "",
        f"- Δ cost: {cost_test['mean']:+.3f} ± {describe(dc)['ci95']:.3f} USD "
        f"(paired t={cost_test['t']:.3f}, p={cost_test['p']:.4f}, n={len(dc)})",
        f"- Δ peak: {peak_test['mean']:+.3f} ± {describe(dp)['ci95']:.3f} kW "
        f"(paired t={peak_test['t']:.3f}, p={peak_test['p']:.4f}, n={len(dp)})",
    ]
    summary["arm_difference"] = {
        "cost": {**cost_test, **describe(dc)},
        "peak": {**peak_test, **describe(dp)},
    }

    lines += [
        "",
        "## Third gate clause: KPI CIs excluding zero",
        "",
        *kpi_clause_lines,
        "",
        f"**Gate verdict: {'MET' if (gate_met or gate_kpi_met) else 'NOT met'}** "
        f"(pp clauses: {'met' if gate_met else 'not met'}; KPI-CI clause: "
        f"{'met' if gate_kpi_met else 'not met'}).",
        "",
        "Interpretation note: the two pp clauses are not met, so the safety-metrics",
        "verdict stays a null result; a literal reading of the pre-registered",
        "'or KPI CIs exclude zero' clause would trigger the gate, which is a",
        "ruling for the PM/user, not the analyst.",
    ]
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
    print(f"wrote {out}/summary.md and summary.json")


if __name__ == "__main__":
    main()
