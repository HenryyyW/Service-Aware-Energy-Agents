"""Deterministic P1 corpus scorer - the C1/C3 checks plus the merge of the
runtime (C4/C5) results, with zero mocks and zero LLM spend.

    python3 experiments/p1_score_corpus.py \
        --configs experiments/p1_pipeline_output \
        [--runtime experiments/p1_runtime_results.json] \
        [--report experiments/p1_score_report.json]

- `--configs DIR`: one ScenarioConfig JSON per corpus item (`<item_id>.json`),
  as produced by A's NL -> ScenarioConfig pipeline.
- `--runtime FILE`: optional; `{"<item_id>": {"simulates_clean": bool,
  "post_round_trip": bool, "validate": {"valid": bool, "errors": [...],
  "warnings": [...]}}}` as recorded by the verifier running the simulator and
  the live /api/scenarios endpoints. Missing entries are reported UNCHECKED and
  fail the item (a verdict is never invented).
- Criterion semantics per docs/p1_acceptance_rubric.md; rejection-path items
  invert C1-C3 (must NOT plan the invalid artifact, MUST name the field).
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "experiments" / "p1_nl_corpus.json"

DOMAIN_TARIF_TYPES = {"time_of_use", "real_time", "flat"}
MARKET_TYPES = {
    "uniform_price",
    "weighted",
    "carbon_aware",
    "fairness_aware",
    "lmp",
    "p2p",
}
BUILDING_TYPES = {"residential", "commercial", "industrial", "mixed"}


def get_path(cfg, path):
    """Walk a dotted path with [i] indices; returns (found, value)."""
    tokens = []
    for chunk in path.split("."):
        while "[" in chunk:
            head, rest = chunk.split("[", 1)
            if head:
                tokens.append(head)
            idx, chunk = rest.split("]", 1)
            tokens.append(("idx", int(idx)))
        if chunk:
            tokens.append(chunk)
    cur = cfg
    for tok in tokens:
        if isinstance(tok, tuple):
            if not isinstance(cur, list) or tok[1] >= len(cur):
                return False, None
            cur = cur[tok[1]]
        else:
            if not isinstance(cur, dict) or tok not in cur:
                return False, None
            cur = cur[tok]
    return True, cur


def count_section(cfg, section):
    """Count a section: top-level lists as-is; device sections as the total
    across buildings; pandapower/energy_sharing as presence (0/1)."""
    if section in ("buildings", "failures"):
        return len(cfg.get(section, []) or [])
    if section in ("pv", "battery", "evs", "flexible_loads", "tariff"):
        return sum(
            1 for b in cfg.get("buildings", []) or [] if b.get(section) is not None
        )
    if section in ("pandapower", "energy_sharing"):
        return 1 if cfg.get(section) else 0
    if section == "weather_file":
        return sum(1 for b in cfg.get("buildings", []) or [] if b.get("weather_file"))
    return 1 if cfg.get(section) is not None else 0


REJECTION_RULES = {
    # rejection items: the invalid artifact must NOT be silently planned.
    # Each rule returns a list of issues ([] = correctly not planned).
    "r01_missing_capacity": lambda cfg: [
        f"buildings[{i}]: planned an invented pv.capacity_kw "
        f"({(b.get('pv') or {}).get('capacity_kw')}) for an NL that gave none"
        for i, b in enumerate(cfg.get("buildings", []) or [])
        if (b.get("pv") or {}).get("capacity_kw") is not None
    ],
    "r02_no_buildings": lambda cfg: (
        [f"planned {len(cfg['buildings'])} buildings for an NL that gave none"]
        if cfg.get("buildings")
        else []
    ),
    "r03_out_of_range_soc": lambda cfg: [
        f"buildings[{i}].battery: planned out-of-range/inverted SOC "
        f"(min={bat.get('soc_min')}, max={bat.get('soc_max')})"
        for i, b in enumerate(cfg.get("buildings", []) or [])
        for bat in [b.get("battery") or {}]
        if bat
        and (
            not (0.0 <= (bat.get("soc_min") or 0.0) <= 1.0)
            or not (0.0 <= (bat.get("soc_max") or 1.0) <= 1.0)
            or (
                bat.get("soc_min") is not None
                and bat.get("soc_max") is not None
                and bat["soc_min"] >= bat["soc_max"]
            )
        )
    ],
    "r04_out_of_range_limit": lambda cfg: [
        f"{k}: planned a non-positive limit ({cfg.get(k)})"
        for k in ("community_import_limit_kw", "community_export_limit_kw")
        if cfg.get(k) is not None and cfg[k] <= 0
    ]
    + [
        f"energy_sharing.{k}: planned a non-positive limit ({(cfg.get('energy_sharing') or {}).get(k)})"
        for k in ("import_limit_kw", "export_limit_kw")
        if (cfg.get("energy_sharing") or {}).get(k) is not None
        and cfg["energy_sharing"][k] <= 0
    ],
}


def check_c1(item, cfg):
    """Plans a complete config: section counts as demanded (or, for rejection
    items, that the invalid artifact is NOT planned)."""
    issues = []
    if item["kind"] != "complete":
        rule = REJECTION_RULES.get(item["id"])
        issues = rule(cfg) if rule else []
        return (not issues), issues
    plan = item["rubric"].get("plans_complete_config", {})
    for section, demand in plan.items():
        if isinstance(demand, int):
            actual = count_section(cfg, section)
            if actual != demand:
                issues.append(f"{section}: planned {actual}, expected {demand}")
        elif isinstance(demand, dict):
            for key, val in demand.items():
                if key == "count":
                    actual = count_section(cfg, section)
                    if actual != val:
                        issues.append(f"{section}: planned {actual}, expected {val}")
                elif key == "types":
                    actual_types = [
                        b.get("building_type") for b in (cfg.get(section, []) or [])
                    ]
                    if actual_types != val:
                        issues.append(
                            f"{section} types: {actual_types} != expected {val}"
                        )
                elif key == "enabled":
                    got = (cfg.get(section) or {}).get("enabled")
                    if got is not val:
                        issues.append(f"{section}.enabled: {got} != expected {val}")
                elif isinstance(val, str):
                    got = (cfg.get(section) or {}).get(key)
                    if got != val:
                        issues.append(f"{section}.{key}: {got!r} != expected {val!r}")
    return (not issues), issues


def check_c2(item, cfg):
    """Required fields present (complete items only)."""
    missing = []
    for path in item["rubric"].get("required_fields", []):
        if path == "buildings[*].pv.capacity_kw":
            for i, b in enumerate(cfg.get("buildings", [])):
                if not (b.get("pv") or {}).get("capacity_kw"):
                    missing.append(f"buildings[{i}].pv.capacity_kw")
        elif "[*]" in path:
            base, rest = path.split("[*]", 1)
            arr = cfg.get(base, []) or []
            for i in range(len(arr)):
                ok, _ = get_path(cfg, f"{base}[{i}]{rest}")
                if not ok:
                    missing.append(f"{base}[{i}]{rest}")
        else:
            ok, _ = get_path(cfg, path)
            if not ok:
                missing.append(path)
    return (not missing), missing


def check_c3(item, cfg):
    """Values in range: the stated values match the NL text; the unstated
    values satisfy the domain-wide semantic rules."""
    issues = []
    for path, want in item.get("stated_values", {}).items():
        ok, got = get_path(cfg, path)
        if not ok:
            issues.append(f"{path}: missing (stated {want!r})")
            continue
        if path == "buildings":
            continue
        if isinstance(want, dict):
            got_map = got if isinstance(got, dict) else {}
            for k, v in want.items():
                if k not in got_map:
                    issues.append(f"{path}[{k}]: missing (stated {v!r})")
                elif isinstance(v, float) and isinstance(got_map[k], (int, float)):
                    if abs(float(got_map[k]) - v) > 1e-6:
                        issues.append(f"{path}[{k}]: {got_map[k]} != stated {v}")
                elif got_map[k] != v:
                    issues.append(f"{path}[{k}]: {got_map[k]!r} != stated {v!r}")
        elif isinstance(want, bool):
            if got is not want:
                issues.append(f"{path}: {got!r} != stated {want!r}")
        elif isinstance(want, (int, float)) and isinstance(got, (int, float)):
            if abs(float(got) - float(want)) > 1e-6:
                issues.append(f"{path}: {got} != stated {want}")
        elif str(got) != str(want):
            issues.append(f"{path}: {got!r} != stated {want!r}")
    # domain-wide rules
    for i, b in enumerate(cfg.get("buildings", []) or []):
        if b.get("building_type") not in BUILDING_TYPES:
            issues.append(
                f"buildings[{i}].building_type invalid: {b.get('building_type')!r}"
            )
        bat = b.get("battery")
        if bat:
            lo, hi, init = (
                bat.get("soc_min"),
                bat.get("soc_max"),
                bat.get("initial_soc"),
            )
            if lo is not None and not (0.0 <= lo <= 1.0):
                issues.append(f"buildings[{i}].battery.soc_min out of [0,1]: {lo}")
            if hi is not None and not (0.0 <= hi <= 1.0):
                issues.append(f"buildings[{i}].battery.soc_max out of [0,1]: {hi}")
            if lo is not None and hi is not None and not lo < hi:
                issues.append(f"buildings[{i}].battery soc inverted: {lo} >= {hi}")
            if init is not None and not (0.0 <= init <= 1.0):
                issues.append(
                    f"buildings[{i}].battery.initial_soc out of [0,1]: {init}"
                )
            if (bat.get("capacity_kwh") or 0) <= 0 or (bat.get("power_kw") or 0) <= 0:
                issues.append(f"buildings[{i}].battery non-positive capacity/power")
        for j, ev in enumerate(b.get("evs") or []):
            if (ev.get("capacity_kwh") or 0) <= 0 or (
                ev.get("max_charge_kw") or 0
            ) <= 0:
                issues.append(f"buildings[{i}].evs[{j}] non-positive capacity/power")
            arr, dep = ev.get("arrival_time"), ev.get("departure_time")
            if arr and dep and arr == dep:
                issues.append(f"buildings[{i}].evs[{j}] zero-length window {arr}")
            for t in (arr, dep):
                if t and not (
                    len(t) == 5 and t[2] == ":" and t[:2].isdigit() and t[3:].isdigit()
                ):
                    issues.append(f"buildings[{i}].evs[{j}] bad HH:MM time {t!r}")
        for j, fl in enumerate(b.get("flexible_loads") or []):
            pk, ek, dur = (
                fl.get("power_kw"),
                fl.get("energy_kwh"),
                fl.get("duration_hours"),
            )
            if pk and ek and dur and abs(pk * dur - ek) > 1e-6:
                issues.append(
                    f"buildings[{i}].flexible_loads[{j}] inconsistent: "
                    f"{pk} kW x {dur} h != {ek} kWh"
                )
        tar = b.get("tariff")
        if tar and tar.get("type") not in DOMAIN_TARIF_TYPES:
            issues.append(f"buildings[{i}].tariff.type invalid: {tar.get('type')!r}")
    pv_cfg = cfg.get("pandapower")
    if pv_cfg:
        for k in ("line_loading_limit", "transformer_loading_limit"):
            if k in pv_cfg and pv_cfg[k] <= 0:
                issues.append(f"pandapower.{k} non-positive: {pv_cfg[k]}")
        for k in ("min", "max"):
            v = (pv_cfg.get("voltage_limits") or {}).get(k)
            if v is not None and not (0.5 < v < 1.5):
                issues.append(f"pandapower.voltage_limits.{k} implausible: {v}")
    for k in ("community_import_limit_kw", "community_export_limit_kw"):
        v = cfg.get(k)
        if v is not None and v <= 0:
            issues.append(f"{k} non-positive: {v}")
    es = cfg.get("energy_sharing")
    if es:
        if es.get("market_type") not in MARKET_TYPES:
            issues.append(
                f"energy_sharing.market_type invalid: {es.get('market_type')!r}"
            )
        for k in ("import_limit_kw", "export_limit_kw"):
            v = es.get(k)
            if v is not None and v <= 0:
                issues.append(f"energy_sharing.{k} non-positive: {v}")
    if cfg.get("timestep_minutes") not in (5, 15, 30, 60):
        issues.append(f"timestep_minutes unusual: {cfg.get('timestep_minutes')}")
    return (not issues), issues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", required=True, help="dir with <item_id>.json configs")
    ap.add_argument(
        "--runtime", default=None, help="optional runtime (C4/C5) results JSON"
    )
    ap.add_argument("--report", default=None, help="write the full report here")
    args = ap.parse_args()

    corpus = json.loads(CORPUS.read_text())
    runtime = json.loads(Path(args.runtime).read_text()) if args.runtime else {}
    cfg_dir = Path(args.configs)

    report = {"corpus": corpus["corpus"], "items": [], "score": None}
    passed = 0
    for item in corpus["items"]:
        iid = item["id"]
        cfg_path = cfg_dir / f"{iid}.json"
        entry = {"id": iid, "kind": item["kind"], "criteria": {}}
        if not cfg_path.is_file():
            entry["criteria"] = {
                c: "MISSING-CONFIG" for c in ("C1", "C2", "C3", "C4", "C5")
            }
            entry["pass"] = False
            report["items"].append(entry)
            continue
        cfg = json.loads(cfg_path.read_text())
        ok1, iss1 = check_c1(item, cfg)
        ok2, iss2 = check_c2(item, cfg)
        ok3, iss3 = check_c3(item, cfg)
        rt = runtime.get(iid, {})
        if item["kind"] == "complete":
            c4 = rt.get("simulates_clean")
            c5 = rt.get("post_round_trip")
            c4_v = "PASS" if c4 is True else ("UNCHECKED" if c4 is None else "FAIL")
            c5_v = "PASS" if c5 is True else ("UNCHECKED" if c5 is None else "FAIL")
        else:
            # rejection items: C4 = the run was blocked before starting WITH the
            # named field surfaced; C5 = the validate gate returns the named
            # error (POST itself may legitimately succeed - schema-valid)
            named = rt.get("blocked_with_named_field")
            blocked = rt.get("validate_returns_error")
            c4_v = (
                "PASS"
                if named
                else ("UNCHECKED" if named is None and blocked is None else "FAIL")
            )
            c5_v = (
                "PASS"
                if blocked is True
                else ("UNCHECKED" if blocked is None else "FAIL")
            )
        entry["criteria"] = {
            "C1_plans_complete": "PASS" if ok1 else f"FAIL {iss1}",
            "C2_required_fields": "PASS" if ok2 else f"FAIL {iss2}",
            "C3_values_in_range": "PASS" if ok3 else f"FAIL {iss3}",
            "C4_simulates_clean": c4_v,
            "C5_round_trips": c5_v,
        }
        entry["pass"] = all(v == "PASS" for v in entry["criteria"].values())
        passed += 1 if entry["pass"] else 0
        report["items"].append(entry)

    total = len(corpus["items"])
    domains_covered = {
        d
        for it in report["items"]
        if it["pass"] and it["kind"] == "complete"
        for d in next(c["domains"] for c in corpus["items"] if c["id"] == it["id"])
    }
    rejection_pass = sum(
        1 for it in report["items"] if it["pass"] and it["kind"] != "complete"
    )
    bar = passed >= 14 and len(domains_covered) >= 8 and rejection_pass == 4
    report["score"] = {
        "items_passed": passed,
        "items_total": total,
        "domains_covered": sorted(domains_covered),
        "rejection_items_passed": rejection_pass,
        "acceptance_bar": "PASS" if bar else "FAIL",
        "bar_rule": ">=14/16 items AND all 8 domains covered AND all 4 rejection items pass",
    }
    text = json.dumps(report, indent=2)
    if args.report:
        Path(args.report).write_text(text)
    print(text)
    return 0 if bar else 1


if __name__ == "__main__":
    sys.exit(main())
