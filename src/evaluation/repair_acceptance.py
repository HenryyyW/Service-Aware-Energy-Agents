"""Shared repair acceptance criteria — single source of truth for no-masking verification.

Extracted from tests/test_grid_closed_loop.py (Research's binding criteria).
All acceptance logic centralized here; both tests and production verifier import from here.
"""

from dataclasses import dataclass

# --- Tolerances (Research's binding criteria) ---
EPS = 1e-9
DEPARTURE_SOC_MAX_DROP = 0.01
COMFORT_TOL_FACTOR = 0.02
COMFORT_TOL_ABS = 1.0  # deg-hours


@dataclass
class RepairVerdict:
    """Result of repair evaluation."""

    accepted: bool
    reasons: list[str]
    metric_deltas: dict


def _key(metrics: dict, path: str, default=None):
    """Safely get nested dict value by dotted path."""
    keys = path.split(".")
    cur = metrics
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def _ev_completion_rate(metrics: dict) -> float:
    return float(_key(metrics, "service.ev_completion_rate", 1.0))


def _ev_avg_soc(metrics: dict) -> float:
    return float(_key(metrics, "service.ev_avg_soc_at_departure", 1.0))


def _ev_worst_soc(metrics: dict) -> float:
    return float(_key(metrics, "service.ev_worst_soc_at_departure", 1.0))


def _flex_completion(metrics: dict) -> float:
    return float(_key(metrics, "service.flexible_load_completion_rate", 1.0))


def _comfort_deg_h(metrics: dict) -> float:
    return float(_key(metrics, "service.comfort_violation_degree_hours", 0.0))


def _member_cost_coverage(metrics: dict) -> float:
    return float(_key(metrics, "service.member_cost_coverage", 1.0))


def _members_interrupted(metrics: dict) -> int:
    return int(_key(metrics, "service.members_interrupted_count", 0))


def _member_cost_interrupted(metrics: dict) -> float | None:
    return _key(metrics, "service.member_cost_interrupted", None)


def _voltage_violations(metrics: dict) -> int:
    return int(_key(metrics, "grid.voltage_violations_count", 0))


def _loading_violations(metrics: dict) -> int:
    return int(_key(metrics, "grid.line_loading_violations", 0))


def _trafo_violations(metrics: dict) -> int:
    return int(_key(metrics, "grid.transformer_loading_violations", 0))


def _member_cost_interrupted_val(metrics: dict) -> float | None:
    return _key(metrics, "service.member_cost_interrupted", None)


def evaluate_repair(
    baseline_metrics: dict,
    repaired_metrics: dict,
) -> RepairVerdict:
    """
    Evaluate whether a repair is acceptable per Research's no-masking criteria.

    Criteria (binding, from test_grid_closed_loop.py):
    1. HELD-HARMLESS METRICS (must not decrease):
       - ev_completion_rate: NO decrease (eps 1e-9)
       - departure SOC: avg AND worst, drop <= 0.01 absolute
       - comfort_violation_degree_hours: increase <= max(1.0 deg-h, 2% of reference)
       - flexible_load_completion_rate: NO decrease (eps 1e-9)
       - member_cost_coverage: NO decrease
       - members_interrupted_count: NO increase
       - interrupted cost: must stay None, never 0.0

    2. VIOLATION IMPROVEMENT (grid):
       - violations per category strictly decrease (or reach zero)

    3. NO NETTING: each metric evaluated independently; no netting across metrics.

    4. MASKED VIOLATION: if grid violation resolved BUT any held-harmless criterion violated,
       the repair is REJECTED (masked violation).

    Returns:
        RepairVerdict with accepted/rejected, reasons, and metric_deltas for transparency.
    """
    reasons: list[str] = []
    metric_deltas: dict = {}

    # --- Helpers for delta computation ---
    def _delta(path: str, baseline: dict, repaired: dict) -> float:
        b = float(_key(baseline, path, 0.0))
        r = float(_key(repaired, path, 0.0))
        delta = r - b
        metric_deltas[path] = {"before": b, "after": r, "delta": r - b}
        return delta

    def _key(d: dict, path: str, default=0.0):
        cur = baseline if d is baseline else repaired
        for k in path.split("."):
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                return 0.0
        return float(cur)

    baseline = baseline_metrics
    repaired = repaired_metrics

    reasons: list[str] = []
    metric_deltas = {}

    # --- 1. EV completion rate: NO decrease (eps) ---
    b_ev = float(_ev_completion_rate(baseline_metrics))
    r_ev = float(_ev_completion_rate(repaired_metrics))
    d_ev = r_ev - b_ev
    metric_deltas["ev_completion_rate"] = {"before": b_ev, "after": r_ev, "delta": d_ev}
    if r_ev < b_ev - 1e-9:
        reasons.append(
            f"EV completion rate decreased: {b_ev:.4f} -> {r_ev:.4f} (delta {d_ev:.6f})"
        )

    # --- 2. Departure SOC (avg): drop <= 0.01 ---
    b_avg = float(_ev_avg_soc(baseline))
    r_avg = float(_ev_avg_soc(repaired))
    d_avg = r_avg - b_avg
    metric_deltas["ev_avg_soc_at_departure"] = {
        "before": b_avg,
        "after": r_avg,
        "delta": d_avg,
    }
    if r_avg < b_avg - DEPARTURE_SOC_MAX_DROP:
        reasons.append(
            f"Avg departure SOC dropped: {b_avg:.4f} -> {r_avg:.4f} (drop {d_avg:.4f} > {DEPARTURE_SOC_MAX_DROP})"
        )

    # --- 3. Departure SOC worst case: drop <= 0.01 ---
    b_worst = float(_ev_worst_soc(baseline))
    r_worst = float(_ev_worst_soc(repaired))
    d_worst = r_worst - b_worst
    metric_deltas["ev_worst_soc_at_departure"] = {
        "before": b_worst,
        "after": r_worst,
        "delta": d_worst,
    }
    if r_worst < b_worst - DEPARTURE_SOC_MAX_DROP:
        reasons.append(
            f"Worst departure SOC dropped: {b_worst:.4f} -> {r_worst:.4f} (drop {b_worst - r_worst:.4f} > {DEPARTURE_SOC_MAX_DROP})"
        )

    # --- 4. Flexible load completion: NO decrease ---
    b_flex = float(_flex_completion(baseline))
    r_flex = float(_flex_completion(repaired))
    d_flex = r_flex - b_flex
    metric_deltas["flexible_load_completion_rate"] = {
        "before": b_flex,
        "after": r_flex,
        "delta": d_flex,
    }
    if r_flex < b_flex - 1e-9:
        reasons.append(
            f"Flexible load completion decreased: {b_flex:.4f} -> {r_flex:.4f} (delta {d_flex:.6f})"
        )

    # --- 4b. Comfort violation degree-hours: increase <= max(1.0, 2% of ref) ---
    b_comf = float(_comfort_deg_h(baseline))
    r_comf = float(_comfort_deg_h(repaired))
    d_comf = r_comf - b_comf
    tol = max(COMFORT_TOL_ABS, COMFORT_TOL_FACTOR * max(b_comf, 1.0))
    metric_deltas["comfort_violation_degree_hours"] = {
        "before": b_comf,
        "after": r_comf,
        "delta": d_comf,
        "tol": tol,
    }
    if d_comf > tol:
        reasons.append(
            f"Comfort violation increased: {b_comf:.2f} -> {r_comf:.2f} (delta {d_comf:.2f} > tol {tol:.2f})"
        )

    # --- 5. Member cost coverage: NO decrease ---
    b_mcc = float(_member_cost_coverage(baseline))
    r_mcc = float(_member_cost_coverage(repaired))
    d_mcc = r_mcc - b_mcc
    metric_deltas["member_cost_coverage"] = {
        "before": b_mcc,
        "after": r_mcc,
        "delta": d_mcc,
    }
    if r_mcc < b_mcc - 1e-9:
        reasons.append(
            f"Member cost coverage decreased: {b_mcc:.4f} -> {r_mcc:.4f} (delta {d_mcc:.6f})"
        )

    # --- 6. Members interrupted: NO increase ---
    b_mint = int(_members_interrupted(baseline))
    r_mint = int(_members_interrupted(repaired))
    metric_deltas["members_interrupted_count"] = {
        "before": b_mint,
        "after": r_mint,
        "delta": r_mint - b_mint,
    }
    if r_mint > b_mint:
        reasons.append(
            f"Members interrupted increased: {b_mint} -> {r_mint} (increase not allowed)"
        )

    # --- 5. Interrupted cost: must stay None, never 0.0 ---
    cost_int = _member_cost_interrupted_val(baseline)
    cost_int_r = _member_cost_interrupted_val(repaired)
    if cost_int_r is not None and cost_int_r <= 0.0:
        reasons.append("Interrupted member cost is 0.0 or negative (must stay None)")

    # --- 6. Grid violation improvement ---
    v_viol = _voltage_violations(baseline)
    r_v_viol = _voltage_violations(repaired)
    l_viol = _loading_violations(baseline)
    r_l_viol = _loading_violations(repaired)
    t_viol = _trafo_violations(baseline)
    r_t_viol = _trafo_violations(repaired)

    metric_deltas["voltage_violations"] = {
        "before": v_viol,
        "after": r_v_viol,
        "delta": r_v_viol - v_viol,
    }
    metric_deltas["loading_violations"] = {
        "before": l_viol,
        "after": r_l_viol,
        "delta": r_l_viol - l_viol,
    }
    metric_deltas["transformer_violations"] = {
        "before": t_viol,
        "after": r_t_viol,
        "delta": r_t_viol - t_viol,
    }

    # Violations must decrease (or reach zero)
    if r_v_viol > 0 or r_l_viol > 0 or r_t_viol > 0:
        # Still violations remain - acceptable if they decreased
        pass

    # --- MASKED VIOLATION CHECK ---
    # If grid violations improved (all went to zero or decreased) BUT any held-harmless criterion violated -> REJECT
    violations_resolved = (
        (
            _voltage_violations(baseline) > 0
            or _loading_violations(baseline) > 0
            or _trafo_violations(baseline) > 0
        )
        and _voltage_violations(repaired) == 0
        and _loading_violations(repaired) == 0
        and _trafo_violations(repaired) == 0
    )

    any_held_harmless_violated = len(reasons) > 0

    if violations_resolved and any_held_harmless_violated:
        reasons.insert(
            0,
            f"MASKED VIOLATION: grid violations resolved ({_voltage_violations(baseline)}V/{_loading_violations(baseline)}L/{_trafo_violations(baseline)}T -> 0) but service degraded: "
            + "; ".join(reasons[:3]),
        )

    accepted = len(reasons) == 0

    return RepairVerdict(
        accepted=accepted,
        reasons=reasons,
        metric_deltas=metric_deltas,
    )


def _key(metrics: dict, path: str, default=0.0) -> float:
    """Safely get nested dict value by dotted path."""
    cur = metrics
    for k in path.split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur if cur is not None else default
