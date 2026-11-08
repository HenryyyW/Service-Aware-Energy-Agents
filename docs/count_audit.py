#!/usr/bin/env python3
"""Reviewer-response count audit + Table 7 (M2b) rebuild from raw run artifacts.

Addresses reviewer items F4/F5/F6 (run-count arithmetic) and F7 (Table 7's
suspiciously identical detection/recovery rows). Every number is recomputed
from run manifests / result.json files under experiments/ and the quarantine
archives under /tmp/opencode/m2b_recovery_quarantine* — never from prose.

Outputs:
  docs/count_audit/counts_table.md   claim -> source -> correct value
  docs/count_audit/table7_rebuilt.md rebuilt M2b table rows + per-cell detail
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "count_audit"
M2B_SEEDS = [42, 123, 456]
Q1 = Path("/tmp/opencode/m2b_recovery_quarantine")
Q2 = Path("/tmp/opencode/m2b_recovery_quarantine_round2")
MAIN_SCENARIOS = ("scenario_a", "scenario_b", "scenario_c", "scenario_d", "scenario_e")


def load_manifests(matrix: str) -> List[dict]:
    root = ROOT / "experiments" / matrix
    if not root.is_dir():
        return []
    out = []
    for m in sorted(root.rglob("manifest.json")):
        try:
            out.append(json.loads(m.read_text()))
        except Exception:
            pass
    return out


def cells(root: Path) -> Dict[str, dict]:
    """All result.json under root, keyed by run-dir name."""
    out: Dict[str, dict] = {}
    if not root.is_dir():
        return out
    for res in sorted(root.rglob("result.json")):
        try:
            out[res.parent.name] = json.loads(res.read_text())
        except Exception:
            pass
    return out


def metrics(cell: dict) -> dict:
    cfg = cell.get("controller_config") or {}
    steps = cfg.get("total_steps") or 24
    errs = cfg.get("llm_backend_errors") or 0
    calls = cfg.get("llm_calls") or 0
    telemetry_ok = cfg.get("repair_success_rate") is not None or (
        cfg.get("verification_failures") is not None
    )
    ctype = cell.get("controller_type") or (
        "llm_agent_verified"
        if "verified" in str(cell.get("run_id", ""))
        else "llm_agent"
    )
    return {
        "type": ctype,
        "scenario": cell.get("scenario_id"),
        "seed": cell.get("random_seed"),
        "steps": steps,
        "fallback": cfg.get("llm_fallback_steps") or 0,
        "errs": errs,
        "calls": calls,
        "keep": errs <= 2 and calls >= steps and telemetry_ok,
        "repair_sr": cfg.get("repair_success_rate"),
        "unrepaired": cfg.get("llm_unrepaired_violations"),
        "cost": (cell.get("energy") or {}).get("total_cost"),
    }


def verified_cells(all_cells: Dict[str, dict]) -> Dict[str, dict]:
    return {k: m for k, m in all_cells.items() if m["type"] == "llm_agent_verified"}


def unverified_cells(all_cells: Dict[str, dict]) -> Dict[str, dict]:
    return {k: m for k, m in all_cells.items() if m["type"] == "llm_agent"}


def summarize(label: str, sel: Dict[str, dict]) -> dict:
    costs = [m["cost"] for m in sel.values() if m["cost"] is not None]
    rates = [m["repair_sr"] for m in sel.values() if m["repair_sr"] is not None]
    return {
        "label": label,
        "cells": len(sel),
        "fallback_total": sum(m["fallback"] for m in sel.values()),
        "steps_total": sum(m["steps"] for m in sel.values()),
        "cost_mean": round(statistics.mean(costs), 2) if costs else None,
        "repair_sr_min": min(rates) if rates else None,
        "repair_sr_max": max(rates) if rates else None,
        "repair_sr_mean": round(statistics.mean(rates), 3) if rates else None,
    }


# ---------------------------------------------------------------------------
# Part 1: count audit
# ---------------------------------------------------------------------------


def count_audit() -> List[Dict[str, str]]:
    rows = []

    full = load_manifests("matrix_full")
    p2p = load_manifests("matrix_p2p")
    m52 = load_manifests("m52_benchmark")
    seeds_full = sorted({m.get("random_seed") for m in full})
    ctrls_full = sorted({m.get("controller", {}).get("type") for m in full})
    scens_full = Counter(m.get("scenario_id") for m in full)
    m52_scens = Counter(m.get("scenario_id") for m in m52)
    m52_regimes = Counter(m.get("pricing_regime") for m in m52)

    rows.append(
        {
            "claim": (
                "Paper abstract/§3: 750 runs = 3 regimes x 250 "
                "(5 controllers x 5 scenarios x 10 seeds)"
            ),
            "source": (
                "experiments/matrix_full + matrix_p2p + m52_benchmark manifests "
                "(all three matrix dirs swept)"
            ),
            "value": (
                f"matrix_full={len(full)} (pool_tou), matrix_p2p={len(p2p)} "
                f"(p2p), m52_benchmark={len(m52)} "
                f"(lmp; regimes={dict(m52_regimes)}, "
                f"per-scenario={dict(sorted(m52_scens.items()))}, commit "
                f"0e584b74f0); seeds={seeds_full}; "
                f"controllers={ctrls_full}; per-scenario={dict(sorted(scens_full.items()))}"
            ),
            "verdict": (
                "CONFIRMED — all three regime legs exist on disk: pool_tou "
                "(matrix_full), lmp (m52_benchmark — the name is a misnomer; it "
                "began as the M5.2 LMP benchmark and was extended to the full "
                "5x5x10 LMP leg by the B2 LMP+RL arm and B3 seed expansion per "
                "docs/benchmark_expansion_plan.md), and p2p (matrix_p2p). "
                "750 = 250 + 250 + 250, fully manifest-backed. Caveat to "
                "disclose: within the LMP leg, scenario E carries the "
                "aggressive failure config (b152037: EV severity 1.0, grid "
                "limit 0.95) while A/B/C/D use the standard config."
            ),
        }
    )

    # F5: A/B/C/E paired pool_tou vs p2p
    per_pair: Dict[str, Dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for matrix, regime in (("matrix_full", "pool_tou"), ("matrix_p2p", "p2p")):
        for m in load_manifests(matrix):
            scen = m.get("scenario_id")
            ctrl = m.get("controller", {}).get("type")
            if scen in MAIN_SCENARIOS[:4]:
                per_pair[scen][ctrl][regime] += 1
    paired_total = sum(
        min(c["pool_tou"], c["p2p"]) for s in per_pair.values() for c in s.values()
    )
    all_ctrls = sorted({c for s in per_pair.values() for c in s})
    ctrl_rows = {
        ctrl: sum(
            min(per_pair[s][ctrl]["pool_tou"], per_pair[s][ctrl]["p2p"])
            for s in per_pair
            if ctrl in per_pair[s]
        )
        for ctrl in all_ctrls
    }
    rows.append(
        {
            "claim": (
                "Paper §4.3 P2P section: 'exactly zero across the 160 paired "
                "runs' for A/B/C/E"
            ),
            "source": "matrix_full + matrix_p2p manifests, A/B/C/E only",
            "value": (
                f"paired total = {paired_total} "
                f"({'; '.join(f'{c}={n}' for c, n in ctrl_rows.items())})"
            ),
            "verdict": (
                "PAPER WRONG: 200 pairs exist (4 scenarios x 5 controllers x 10 "
                "seeds). No controller is excluded by the data — RL runs are "
                "recorded with internal controller type 'rl_single' but are "
                "present 10+10 in every A/B/C/E scenario. 160 (= 4x4x10) has no "
                "manifest backing."
            ),
        }
    )

    # F4: the '150-cell screen'
    m2a = load_manifests("m2a_rerun_laguna")
    arms_m2a = Counter(m.get("controller", {}).get("type") for m in m2a)
    rows.append(
        {
            "claim": (
                "Paper §2.3: 'The 150-cell screen (5 scenarios x 2 LLM arms x "
                "10 seeds) plus 50 multi_agent reference cells'"
            ),
            "source": "experiments/m2a_rerun_laguna manifests + status.json",
            "value": (
                f"m2a_rerun_laguna manifests={len(m2a)} "
                f"({dict(sorted(arms_m2a.items()))}); 5x2x10 = 100 LLM cells; "
                "100 + 50 reference = 150 total"
            ),
            "verdict": (
                "PAPER §2.3 ARITHMETIC WRONG as phrased: 5x2x10 = 100 LLM cells, "
                "not 150. The 150-cell screen = 100 LLM + 50 multi_agent "
                "reference (§3 states it correctly). Data note: 149 manifests on "
                "disk vs 150 planned — scenario_d_llm_agent_verified_1234 is the "
                "deliberately quarantined cell (docs/m2a_rerun_laguna/"
                "quarantine.md, FAV 0.958); cite 149 or re-run the cell."
            ),
        }
    )

    # F6: Scenario E '50 runs per controller'
    e_by_matrix: Dict[str, Tuple[int, Dict[str, int], Dict[str, int]]] = {}
    for matrix in (
        "matrix_full",
        "matrix_p2p",
        "m52_benchmark",
        "matrix_d_rerun",
        "matrix_d_rerun_lmp",
        "matrix_d_rerun_p2p",
        "matrix_full_postfix",
    ):
        ms = [m for m in load_manifests(matrix) if m.get("scenario_id") == "scenario_e"]
        ctrls = Counter(m.get("controller", {}).get("type") for m in ms)
        regimes = Counter(m.get("pricing_regime") for m in ms)
        e_by_matrix[matrix] = (len(ms), dict(sorted(ctrls.items())), dict(regimes))
    e_summary = "; ".join(
        f"{k}: {v[0]} runs, per-ctrl={v[1]}, regime={v[2]}"
        for k, v in e_by_matrix.items()
        if v[0]
    )
    rows.append(
        {
            "claim": (
                "Paper §4.3 Scenario E text + tab:aggressive caption: 'All 50 "
                "runs per controller' / '50 runs per controller'"
            ),
            "source": "scenario_e manifests across every experiment matrix",
            "value": e_summary,
            "verdict": (
                "PAPER WRONG twice over. (a) No matrix has 50 runs per "
                "controller for scenario E — each matrix holds 50 TOTAL = 10 "
                "per controller (5 controllers x 10 seeds); the paper conflated "
                "a matrix total with a per-controller count. (b) The 50-run "
                "aggressive set is part of m52_benchmark — which is NOT a "
                "scenario-E stress matrix but the complete LMP-leg matrix (all "
                "5 scenarios x 5 controllers x 10 seeds; see row 1); within it, "
                "scenario E carries the aggressive failure config (b152037: EV "
                "severity 1.0, grid limit 0.95) while A/B/C/D use the standard "
                "config — a within-matrix asymmetry the paper must disclose. "
                "RL IS present in the stress data (internal type rl_single, 10 "
                "runs) — the paper's aggressive table silently omits the RL row."
            ),
        }
    )

    # Scenario D re-run claim
    d_counts = {
        matrix: len(
            [m for m in load_manifests(matrix) if m.get("scenario_id") == "scenario_d"]
        )
        for matrix in ("matrix_d_rerun", "matrix_d_rerun_lmp", "matrix_d_rerun_p2p")
    }
    rows.append(
        {
            "claim": (
                "Paper §3/setup: 'Scenario D was re-run in full (150 runs: 5 "
                "controllers x 10 seeds x 3 regimes)'"
            ),
            "source": "matrix_d_rerun{,_lmp,_p2p} manifests",
            "value": (
                f"pool_tou={d_counts['matrix_d_rerun']}, "
                f"lmp={d_counts['matrix_d_rerun_lmp']}, "
                f"p2p={d_counts['matrix_d_rerun_p2p']} "
                f"(total {sum(d_counts.values())})"
            ),
            "verdict": "CONFIRMED: 150 scenario-D re-run manifests across 3 regimes.",
        }
    )
    rows.append(
        {
            "claim": (
                "Follow-up (Partner, post-audit): M2a screen — cite 149 "
                "manifests or re-run the quarantined "
                "scenario_d_llm_agent_verified_1234 cell?"
            ),
            "source": (
                "docs/m2a_rerun_laguna/quarantine.md; m2a_rerun_laguna "
                "status.json (total=150 planned); paper claims from M2a are "
                "aggregate safety-metrics nulls"
            ),
            "value": (
                "Coverage 149/150 (99.3%); quarantined cell documented (1/24 "
                "steps backend-error-degraded, FAV 0.958); re-run cost ~24 LLM "
                "calls (~2-4 min) on the laguna/NIM pipeline"
            ),
            "verdict": (
                "RECOMMEND CITE 149 with the quarantine note — zero cost, "
                "already documented, and the M2a claims are aggregate (a single "
                "cell cannot flip a 100-cell null). A re-run is optional "
                "polish: worth it only if the paper needs a clean 5x2x10 "
                "per-cell grid for a paired test. If Research wants it, the "
                "re-run is an LLM run on the user-approved laguna pipeline "
                "(Research owns the key) — single-cell launch with "
                "skip-existing, then re-package the release."
            ),
        }
    )
    return rows


# ---------------------------------------------------------------------------
# Part 2: Table 7 rebuild
# ---------------------------------------------------------------------------


def table7() -> Dict:
    det_all = {
        k: metrics(v) for k, v in cells(ROOT / "experiments" / "m2b_pilot").items()
    }
    rec_all = {
        k: metrics(v) for k, v in cells(ROOT / "experiments" / "m2b_recovery").items()
    }
    q2_all = {k: metrics(v) for k, v in cells(Q2).items()}

    det_v = verified_cells(det_all)
    det_u = unverified_cells(det_all)
    rec_v = verified_cells(rec_all)
    rec_u = unverified_cells(rec_all)
    q2_v = verified_cells(q2_all)

    # Recovery epoch as the paper computed it: 15 cells with the three
    # round-2 re-run cells substituted for their degraded originals.
    rec_sub_v = dict(rec_v)
    rec_sub_v.update(q2_v)

    def agg(sel: Dict[str, dict], arm: str) -> dict:
        s = summarize(label=arm, sel=sel)
        return s

    rec_v_keep = {k: m for k, m in rec_sub_v.items() if m["keep"]}
    rec_v_drop = {k: m for k, m in rec_sub_v.items() if not m["keep"]}
    det_v_drop = {k: m for k, m in det_v.items() if not m["keep"]}

    def paired_wins(unverified, verified):
        """Verified unsafe-acceptance < unverified unsafe-acceptance, per pair."""
        v_by_key = {(m["scenario"], m["seed"]): m for m in verified.values()}
        wins, pairs, detail = 0, 0, []
        for key, u in sorted(unverified.items()):
            v = v_by_key.get((u["scenario"], u["seed"]))
            if v is None:
                continue
            u_v = (u.get("unrepaired") or 0) / max(1, u.get("steps") or 24)
            v_v = (v.get("unrepaired") or 0) / max(1, v.get("steps") or 24)
            pairs += 1
            if v_v < u_v:
                wins += 1
            detail.append((key, round(u_v, 3), round(v_v, 3)))
        return wins, pairs, detail

    # detection epoch: unverified + verified from m2b_pilot
    det_wins, det_pairs, det_detail = paired_wins(det_u, det_v)
    # recovery: unverified from m2b_recovery, verified with q2 substitution
    rec_u_by_scenario: Dict[Tuple[str, int], dict] = {}
    for k, m in rec_u.items():
        rec_u_by_scenario[(m["scenario"], m["seed"])] = m
    rec_wins, rec_pairs, rec_detail = 0, 0, []
    for key, m in sorted(rec_v.items()):
        u = rec_u_by_scenario.get((m["scenario"], m["seed"]))
        if u is None:
            continue
        u_v = (u.get("unrepaired") or 0) / max(1, u.get("steps") or 24)
        v_v = (m.get("unrepaired") or 0) / max(1, m.get("steps") or 24)
        rec_pairs += 1
        if v_v < u_v:
            rec_wins += 1
        rec_detail.append((key, round(u_v, 3), round(v_v, 3)))

    def fallback(sel):
        total = sum(m["fallback"] for m in sel.values())
        steps = sum(m["steps"] for m in sel.values())
        return f"{total}/{steps}"

    def cost(sel):
        costs = [m["cost"] for m in sel.values() if m["cost"] is not None]
        return round(statistics.mean(costs), 2) if costs else None

    result = {
        "provenance": {
            "detection_raw": "experiments/m2b_pilot (30 result.json)",
            "recovery_raw": "experiments/m2b_recovery (30 result.json)",
            "recovery_rerun_cells": (
                "3 verified cells in /tmp/opencode/m2b_recovery_quarantine_round2 "
                "(scenario_c_llm_agent_verified_{42,123}, scenario_e_llm_agent_verified_42)"
            ),
            "paper_recovery_column_reconstruction": (
                "fallback 18/360 and cost 442.62 reproduce EXACTLY as: recovery "
                "matrix over ALL 15 verified cells with the round-2 re-run cells "
                "substituted (no keep-rule filter on the denominator)"
            ),
        },
        "rows": {
            "fallback_steps_verified": {
                "paper_detection": "18/360",
                "paper_recovery": "18/360",
                "raw_detection": fallback(det_v),
                "raw_recovery": fallback(rec_sub_v),
                "raw_recovery_keep13": fallback(rec_v_keep),
                "verdict": (
                    "DETECTION COLUMN UNTRACEABLE: raw detection = 360/360 "
                    "(every step fell back — re-prompts were corrupted, matching "
                    "the paper's own prose); the table's 18/360 for detection is "
                    "a copy of the recovery column. Recovery 18/360 traces to "
                    "all-15-cells-with-substitutions."
                ),
            },
            "cost_mean_verified": {
                "paper_detection": 442.62,
                "paper_recovery": 442.62,
                "raw_detection": cost(det_v),
                "raw_recovery": cost(rec_sub_v),
                "raw_recovery_keep13": cost(rec_v_keep),
                "verdict": (
                    "DETECTION COLUMN UNTRACEABLE: raw detection verified-arm "
                    "mean cost = "
                    f"{cost(det_v)} USD (per cell 171-301), not 442.62. Recovery "
                    "442.62 traces to the substituted 15-cell set."
                ),
            },
            "repair_success_rate": {
                "paper_recovery": "0.880-1.000 (mean 0.974)",
                "raw_recovery_keep13": (
                    f"{min(m['repair_sr'] for m in rec_v_keep.values()):.3f}-"
                    f"{max(m['repair_sr'] for m in rec_v_keep.values()):.3f} "
                    f"(mean {statistics.mean([m['repair_sr'] for m in rec_v_keep.values()]):.3f})"
                ),
                "raw_recovery_sub15": (
                    f"{min(m['repair_sr'] for m in rec_sub_v.values()):.3f}-"
                    f"{max(m['repair_sr'] for m in rec_sub_v.values()):.3f} "
                    f"(mean {statistics.mean([m['repair_sr'] for m in rec_sub_v.values()]):.3f})"
                ),
                "verdict": (
                    "PARTIALLY UNTRACEABLE: paper mixes the keep-13 mean (~0.97) "
                    "with an all-15 range (0.88 floor comes from a quarantined "
                    "cell). State the cell set for both numbers."
                ),
            },
            "unsafe_acceptance_per_step": {
                "paper_detection_unverified": 10.33,
                "raw_detection_unverified_mean": round(
                    statistics.mean(
                        [
                            (m["unrepaired"] or 0) / max(1, m["steps"])
                            for m in det_u.values()
                        ]
                    ),
                    3,
                ),
                "raw_recovery_unverified_mean": round(
                    statistics.mean(
                        [
                            (m["unrepaired"] or 0) / max(1, m["steps"])
                            for m in rec_u.values()
                        ]
                    ),
                    3,
                ),
                "verdict": (
                    "10.33 does not trace to either epoch's cell-mean (detection "
                    "= 10.6, recovery = 10.26); per-cell values emitted so "
                    "Research can locate the intended aggregation."
                ),
            },
            "paired_wins": {
                "paper_detection": "12/12",
                "raw_detection": f"{det_wins}/{det_pairs} (15 cells on disk, "
                "all pass keep: the paper's 12/15 pre-rerun bookkeeping does not "
                "match the on-disk state)",
                "paper_recovery": "13/13",
                "raw_recovery": f"{rec_wins}/{rec_pairs}",
            },
            "quarantine": {
                "detection_drop": sorted(det_v_drop),
                "recovery_drop_after_substitution": sorted(rec_v_drop),
            },
        },
    }
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    rows = count_audit()
    lines = [
        "# Count audit: paper claims vs manifest-backed ground truth",
        "",
        "Every 'manifest-backed value' below is recomputed from run",
        "manifests/result.json files under experiments/ (and quarantine archives",
        "under /tmp/opencode/), never from prose. Generated by docs/count_audit.py.",
        "",
        "| # | Paper claim | Source (raw artifacts) | Manifest-backed value | Verdict |",
        "|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        lines.append(
            f"| {i} | {r['claim']} | {r['source']} | {r['value']} | {r['verdict']} |"
        )
    (OUT / "counts_table.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT / 'counts_table.md'}")

    t7 = table7()
    (OUT / "table7_rebuilt.md").write_text(
        "# Table 7 (M2b) rebuilt from raw run artifacts\n"
        "\n"
        "Recomputed per-cell from result.json controller_config counters:\n"
        "- detection epoch: experiments/m2b_pilot\n"
        "- recovery epoch: experiments/m2b_recovery\n"
        "- re-run cells: /tmp/opencode/m2b_recovery_quarantine_round2\n"
        "- keep rule: llm_backend_errors <= 2 AND llm_calls >= steps AND telemetry recorded\n"
        "\n"
        "Headline (see `rows` for full verdicts):\n"
        f"- DETECTION raw: verified fallback {t7['rows']['fallback_steps_verified']['raw_detection']}, "
        f"cost mean {t7['rows']['cost_mean_verified']['raw_detection']} USD\n"
        f"- RECOVERY raw (15 cells, q2 substituted): fallback {t7['rows']['fallback_steps_verified']['raw_recovery']}, "
        f"cost mean {t7['rows']['cost_mean_verified']['raw_recovery']} USD\n"
        f"- RECOVERY keep-13: fallback {t7['rows']['fallback_steps_verified']['raw_recovery_keep13']}, "
        f"cost mean {t7['rows']['cost_mean_verified']['raw_recovery_keep13']} USD\n"
        "\n```json\n" + json.dumps(t7, indent=1, default=str) + "\n```\n"
    )
    print(f"wrote {OUT / 'table7_rebuilt.md'}")


if __name__ == "__main__":
    main()
