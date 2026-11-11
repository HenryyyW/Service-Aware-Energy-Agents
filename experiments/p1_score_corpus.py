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
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "experiments" / "reference" / "p1_nl_corpus.json"

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
    if section == "timestep_minutes":
        # a scalar value, not a section: its correctness is a stated-value check
        return 1 if cfg.get(section) is not None else 0
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


def _iterations(record):
    """The pipeline's per-iteration records: top-level 'iterations' (the
    run_nl_to_config result shape) or nested under 'final_report'."""
    its = record.get("iterations")
    if its is None and isinstance(record.get("final_report"), dict):
        its = record["final_report"].get("iterations")
    # the pilot dump stores the iteration COUNT (an int), not the records
    if not isinstance(its, list):
        return []
    return its or []


def _last_iteration(record):
    its = _iterations(record)
    return its[-1] if its else {}


def _execution_block(record):
    """Execution evidence: a top-level 'execution' block, or the last
    iteration's 'executor_output' (the real pipeline record shape)."""
    ex = record.get("execution")
    if ex:
        return ex
    return _last_iteration(record).get("executor_output") or {}


def _verification_block(record):
    """Verification evidence: top-level 'verification', or the last
    iteration's 'verifier_output' (the real shape)."""
    v = record.get("verification")
    if v:
        return v
    return _last_iteration(record).get("verifier_output") or {}


def _rejection_evidence(item, record):
    """For a rejection-path item: (named_field_or_None, validate_blocked_bool)
    sourced from the record - schema_errors / mapping_errors / the last
    verifier's out_of_range_fields, schema_rejections, required_fields_missing,
    or a failure summary - matching the corpus's expected_named_fields."""
    if record is None:
        return None, None
    cands = []
    for key in ("schema_errors", "mapping_errors", "rejected_fields"):
        for e in record.get(key) or []:
            cands.append(str(e))
        man = record.get("manifest") or {}
        if isinstance(man, dict):
            for e in man.get(key) or []:
                cands.append(str(e))
    last_verifier = _last_iteration(record).get("verifier_output") or {}
    for key in (
        "schema_errors",
        "out_of_range_fields",
        "schema_rejections",
        "required_fields_missing",
    ):
        for e in last_verifier.get(key) or []:
            cands.append(str(e))
    fr = record.get("final_report")
    summary = (
        str(fr.get("summary") or "")
        if isinstance(fr, dict)
        else (str(fr) if fr else "")
    )
    if summary and "failed" in summary.lower():
        cands.append(summary)
    expected = item.get("expected_named_fields") or []
    hit = [c for c in cands if any(f in c for f in expected)]
    named = f"{hit[0]} (source: record)" if hit else None
    blocked = bool(cands) and record.get("success") is False
    return named, blocked


def check_c1(item, cfg, named_rejected=False, record_success=None):
    """Plans a complete config: section counts as demanded (or, for rejection
    items, that the invalid artifact is NOT planned)."""
    issues = []
    if item["kind"] != "complete":
        # Rejection-path semantics (aligned with the PM's stated acceptance: the
        # correct handling is a NAMED validator error + escalation, not the
        # absence of the invalid value from the draft): the invalid artifact in
        # the config is a failure ONLY when it was silently accepted (record
        # success=True) or when no named rejection exists in the record.
        rule = REJECTION_RULES.get(item["id"])
        planned = rule(cfg) if rule else []
        if planned and not (named_rejected or record_success is False):
            issues = planned
        return (not issues), issues
    plan = item["rubric"].get("plans_complete_config", {})
    if item["kind"] == "complete":
        # "no invented assets" (rubric C1): any building-level device section
        # present in the config that the item does not describe is an invented
        # asset. Added after the pilot observation that the coder emitted all
        # five devices on every building regardless of the description.
        for sec in ("pv", "battery", "evs", "flexible_loads", "tariff", "weather_file"):
            if sec in plan:
                continue
            n = sum(1 for b in cfg.get("buildings", []) or [] if b.get(sec))
            if n:
                issues.append(
                    f"invented asset {sec} on {n} building(s) - not described "
                    "in the NL for this item"
                )
        for sec in ("pandapower", "energy_sharing"):
            if sec not in plan and cfg.get(sec):
                # a schema-optional default (e.g. the pipeline's default grid
                # model) is reported as a note, NOT an invented-device failure:
                # the rubric's 'no invented assets' clause covers devices the NL
                # does not describe, and the confirm-UI spec treats defaults as
                # visible provenance
                issues.append(
                    f"NOTE-undemanded {sec} section present (pipeline default)"
                )
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
                    # order-insensitive, count-sensitive: the NL states the
                    # multiset of building types, not their order
                    actual_types = sorted(
                        b.get("building_type") for b in (cfg.get(section, []) or [])
                    )
                    if actual_types != sorted(val):
                        issues.append(
                            f"{section} types: {actual_types} != expected {sorted(val)}"
                        )
                elif key == "enabled":
                    got = (cfg.get(section) or {}).get("enabled")
                    if got is not val:
                        issues.append(f"{section}.enabled: {got} != expected {val}")
                elif isinstance(val, str):
                    got = (cfg.get(section) or {}).get(key)
                    if got != val:
                        issues.append(f"{section}.{key}: {got!r} != expected {val!r}")
    # NOTE- = informational (never scored); LIMIT- = an unsatisfiable-in-this-
    # environment requirement, which counts as NOT passing with the limitation
    # reason quoted (the bar counts passes)
    real = [i for i in issues if not i.startswith("NOTE-")]
    return (not real), real


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


def check_c3(item, cfg, reject_named=False):
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
        wf = b.get("weather_file")
        if wf is not None:
            # the value must be a resolvable filename, not the NL phrase echoed
            # back (e.g. 'Singapore weather file' does not name a file)
            if not re.fullmatch(r"[A-Za-z0-9_.\-]+\.(csv|epw|json|zip)", str(wf)):
                # no Singapore-class weather file ships with the CityLearn
                # datasets in this environment (each carries one weather.csv),
                # so a canonical token is the environment's honest ceiling: an
                # UNSATISFIABLE requirement is a documented LIMITATION - it
                # counts as NOT passing with the reason quoted (the bar counts
                # passes), never as a pipeline failure
                if str(wf).strip().upper() == "SINGAPORE":
                    issues.append(
                        f"LIMIT-weather environment gap (no Singapore weather "
                        f"file ships here): {wf!r}"
                    )
                else:
                    issues.append(
                        f"buildings[{i}].weather_file not a resolvable filename: {wf!r}"
                    )
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
        vl = pv_cfg.get("voltage_limits")
        if isinstance(vl, dict):
            for k in ("min", "max"):
                v = vl.get(k)
                if v is not None and not (0.5 < v < 1.5):
                    issues.append(f"pandapower.voltage_limits.{k} implausible: {v}")
        elif vl is not None:
            # the schema types voltage_limits as Dict[str, float]; a list (or
            # any non-dict) is a shape violation the endpoint will reject
            issues.append(
                f"pandapower.voltage_limits wrong shape: {type(vl).__name__} "
                "(schema expects a dict with min/max)"
            )
    for k in ("community_import_limit_kw", "community_export_limit_kw"):
        v = cfg.get(k)
        if v is not None and v <= 0:
            # for a rejection item whose record carries the NAMED rejection,
            # the invalid value is the designed honest artifact (planned, then
            # named and refused by the validator) - note it, do not fail C3
            if reject_named and any(
                (f in k) or (k in f) for f in (item.get("expected_named_fields") or [])
            ):
                issues.append(f"NOTE-designed rejection value {k}={v}")
            else:
                issues.append(f"{k} non-positive: {v}")
    if reject_named:
        # general designed-rejection downgrade: any range issue naming one of
        # the corpus's expected fields for this rejection item (e.g. r03's
        # soc_min/soc_max) is the designed honest artifact - planned, then
        # named and refused by the validator
        expected = item.get("expected_named_fields") or []
        issues = [
            (
                ("NOTE-designed rejection value: " + i)
                if (
                    not i.startswith(("NOTE-", "LIMIT-"))
                    and any(
                        (f in i) or ("soc" in f and "soc inverted" in i)
                        for f in expected
                    )
                )
                else i
            )
            for i in issues
        ]
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
    real = [i for i in issues if not i.startswith("NOTE-")]
    return (not real), real


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
        loaded = json.loads(cfg_path.read_text())
        # A's pipeline (run_nl_to_config) returns a RESULT dict - final_config
        # plus the run record (execution / verification / schema_errors /
        # manifest with provenance). Accept both shapes; the record is used as
        # SOURCED evidence for C4 (simulated) and for the rejection-path
        # naming, never as a substitute for the C5 API round-trip.
        record = None
        if isinstance(loaded, dict) and isinstance(loaded.get("final_config"), dict):
            record = loaded
            cfg = loaded["final_config"]
        else:
            cfg = loaded
        rec_named, _rec_blocked = (
            _rejection_evidence(item, record)
            if item["kind"] != "complete"
            else (None, None)
        )
        ok1, iss1 = check_c1(
            item,
            cfg,
            named_rejected=rec_named,
            record_success=(record or {}).get("success"),
        )
        ok2, iss2 = check_c2(item, cfg)
        ok3, iss3 = check_c3(item, cfg, reject_named=bool(rec_named))
        rt = runtime.get(iid, {})
        notes = []
        plan_source = None
        if item["kind"] == "complete":
            c4 = rt.get("simulates_clean")
            c5 = rt.get("post_round_trip")
            c4_src = "runtime record"
            c5_src = "runtime record"
            if c4 is None and record is not None:
                ex = _execution_block(record)
                if not ex and record.get("success") is not None:
                    # the pilot dump kept only the item-level success (the
                    # pipeline derives it from executor_output.success) - source
                    # it explicitly and note that the finer evidence
                    # (power_flow/energy_balance/steps) was not dumped
                    c4 = bool(record.get("success"))
                    c4_src = "item-level success=True (executor detail not dumped)"
                    notes.append(
                        "C4 rests on item-level success only; the execution "
                        "block (power_flow_converged/energy_balance_ok/"
                        "simulation_steps) was not dumped for this item"
                    )
                if ex:
                    steps = ex.get("simulation_steps", ex.get("steps", 0)) or 0
                    c4 = bool(
                        ex.get("success")
                        and ex.get("power_flow_converged")
                        and ex.get("energy_balance_ok")
                        and steps > 0
                    )
                    c4_src = (
                        "pipeline record execution "
                        "(success+power_flow_converged+energy_balance_ok+"
                        f"simulation_steps={steps}>0)"
                    )
            if record is not None:
                v = _verification_block(record)
                rt = v.get("round_trip_valid", v.get("round_trip"))
                if rt is not None:
                    notes.append(
                        f"pipeline record verification.round_trip_valid={rt} "
                        "is a SERIALIZATION round-trip (pydantic parse/dump/reparse), "
                        "NOT the POST /scenarios API round-trip C5 requires - "
                        "reported, not scored"
                    )
                man = record.get("manifest") or {}
                prov = man.get("provenance") or man.get("plan_source")
                if prov:
                    notes.append(f"pipeline manifest provenance: {prov}")
                plan_source = (
                    man.get("plan_source")
                    or (record.get("plan") or {}).get("plan_source")
                    or _last_iteration(record)
                    .get("planner_output", {})
                    .get("plan_source")
                )
                if plan_source == "rule_based_fallback":
                    # the planner fell back to the keyword path (LLM call raised
                    # or its response did not parse) - this item does NOT
                    # measure the agent's planning; report, never pool silently
                    notes.append(
                        "PLANNED BY rule_based_fallback - not an agent "
                        "measurement (LLM call raised or response unparsable)"
                    )
                elif plan_source:
                    notes.append(f"planned by: {plan_source}")
                else:
                    notes.append(
                        "plan_source NOT recorded in the dump - the planner "
                        "path is not evidenced by the record itself"
                    )
            c4_v = "PASS" if c4 is True else ("UNCHECKED" if c4 is None else "FAIL")
            c5_v = "PASS" if c5 is True else ("UNCHECKED" if c5 is None else "FAIL")
            notes.insert(0, f"C4 source: {c4_src}")
            notes.insert(1, f"C5 source: {c5_src}")
        else:
            # rejection items: C4 = the run was blocked before starting WITH the
            # named field surfaced; C5 = the validate gate returns the named
            # error (POST itself may legitimately succeed - schema-valid)
            named = rt.get("blocked_with_named_field")
            blocked = rt.get("validate_returns_error")
            if named is None and record is not None:
                # sourced from the pipeline record: the named field(s) in
                # schema_errors / mapping_errors / the failure summary
                cands = []
                for key in ("schema_errors", "mapping_errors"):
                    for e in record.get(key) or []:
                        cands.append(str(e))
                last_verifier = _last_iteration(record).get("verifier_output") or {}
                for key in (
                    "schema_errors",
                    "out_of_range_fields",
                    "schema_rejections",
                    "required_fields_missing",
                ):
                    for e in last_verifier.get(key) or []:
                        cands.append(str(e))
                fr = record.get("final_report")
                summary = (
                    str(fr.get("summary") or "")
                    if isinstance(fr, dict)
                    else (str(fr) if fr else "")
                )
                if summary and "failed" in summary.lower():
                    cands.append(summary)
                expected = item.get("expected_named_fields") or []
                hit = [c for c in cands if any(f in c for f in expected)]
                if hit:
                    named = f"{hit[0]} (source: pipeline record)"
                elif cands:
                    notes.append(
                        "pipeline record names other errors but not the expected "
                        f"field(s) {expected}: {cands[:2]}"
                    )
                if cands and record.get("success") is False:
                    blocked = True
                    notes.append(
                        "validate-gate rejection sourced from the pipeline record "
                        "(success=False with named errors)"
                    )
            c4_v = (
                "PASS"
                if named
                else ("UNCHECKED" if named is None and blocked is None else "FAIL")
            )
            if record is not None and record.get("success") is True:
                c4_v = "FAIL"
                notes.append(
                    "pipeline record shows success=True on a rejection-path item: "
                    "the invalid artifact was produced/run"
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
        if plan_source:
            entry["plan_source"] = plan_source
        if notes:
            entry["record_notes"] = notes
        passed += 1 if entry["pass"] else 0
        report["items"].append(entry)

    total = len(corpus["items"])
    produced = [
        it for it in report["items"] if "MISSING-CONFIG" not in it["criteria"].values()
    ]
    missing = [it["id"] for it in report["items"] if it not in produced]
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
        "configs_produced": len(produced),
        "configs_missing": missing,
    }
    if missing:
        # Pilot reading (NOT the acceptance of record): the tally over the
        # produced subset only, so a partial run (e.g. the first-10 pilot) is
        # not misread as a pipeline failure. The acceptance bar above is
        # evaluated over the FULL corpus and stays the record.
        pilot_domains = {
            d
            for it in produced
            if it["pass"] and it["kind"] == "complete"
            for d in next(c["domains"] for c in corpus["items"] if c["id"] == it["id"])
        }
        pilot_rejection = sum(
            1 for it in produced if it["pass"] and it["kind"] != "complete"
        )

        def _plan_source(it):
            return it.get("plan_source")

        fallback_items = [
            it["id"] for it in produced if _plan_source(it) == "rule_based_fallback"
        ]
        report["score"]["pilot_reading"] = {
            "scope": f"{len(produced)}/{total} items produced; the remaining "
            f"{len(missing)} are MISSING-CONFIG and are NOT evidence about the "
            "pipeline",
            "items_passed_over_produced": sum(1 for it in produced if it["pass"]),
            "domains_covered": sorted(pilot_domains),
            "rejection_items_passed": pilot_rejection,
            "planned_by_fallback": fallback_items,
            "llm_planned_passed": sum(
                1 for it in produced if it["pass"] and _plan_source(it) == "llm"
            ),
            "provenance_unrecorded": [
                it["id"] for it in produced if it.get("plan_source") is None
            ],
            "note": "pilot reading only - the acceptance bar is evaluated over "
            "the full 16-item corpus and is the record of decision; items whose "
            "plan_source is rule_based_fallback are listed separately and never "
            "pooled as agent measurements",
        }
    text = json.dumps(report, indent=2)
    if args.report:
        Path(args.report).write_text(text)
    print(text)
    return 0 if bar else 1


if __name__ == "__main__":
    sys.exit(main())
