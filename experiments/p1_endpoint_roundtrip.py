"""C5 evidence driver: round-trip each corpus item's config through the REAL
scenario API (POST /api/scenarios -> GET -> GET /validate) in-process via
TestClient - no server, no LLM calls - and emit the runtime record the scorer
consumes (--runtime). Hermetic: PROJECT_ROOT points at a temp dir so no scenario
data is written into the shared repo.

    python3 experiments/p1_endpoint_roundtrip.py \\
        --configs /home/box/OpenBot/Shared/probe_out_full16 \\
        --out /tmp/opencode/c5_runtime.json

Equivalence (the rubric's C5): POST accepted (201), GET returns a config whose
buildings are deep-equal and whose top-level fields the endpoint reads
(scenario_id/name/description/pandapower/community limits/random_seed/
timestep) are equal. Fields the endpoint does NOT read (energy_sharing,
failures, carbon_intensity_file) are recorded as dropped - a dropped field is
reported and fails the round-trip because the GET is then not equivalent.
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# the endpoint now READS these (main 268bbfb1b), so they are preserved, not
# dropped - a config field the endpoint genuinely ignores still fails C5
PRESERVED_TOP = [
    "scenario_id",
    "name",
    "description",
    "pandapower",
    "energy_sharing",
    "community_import_limit_kw",
    "community_export_limit_kw",
    "random_seed",
    "timestep_minutes",
]
DROPPED_TOP = ["failures", "carbon_intensity_file"]


def load_configs(cfg_dir: Path):
    """Accept bare ScenarioConfig JSONs or pipeline result dicts."""
    out = {}
    for f in sorted(cfg_dir.glob("*.json")):
        if f.name in ("summary.json",):
            continue
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        cfg = data.get("final_config") if isinstance(data, dict) else None
        if isinstance(cfg, dict):
            out[f.stem] = cfg
        elif isinstance(data, dict) and "buildings" in data:
            out[f.stem] = data
    return out


def buildings_signature(cfg):
    """Deep-compare the buildings (the part the endpoint preserves)."""
    sig = []
    for b in cfg.get("buildings", []) or []:
        row = {
            k: b.get(k)
            for k in (
                "building_id",
                "building_type",
                "location",
                "pv",
                "battery",
                "evs",
                "flexible_loads",
                "tariff",
                "weather_file",
                "simulation_start",
                "simulation_end",
            )
        }
        sig.append(row)
    return sig


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", required=True, help="dir with <item_id>.json")
    ap.add_argument("--out", required=True, help="where to write the runtime record")
    args = ap.parse_args()

    # hermetic scenario-data dir
    tmp = tempfile.mkdtemp(prefix="p1rt_")
    os.environ["PROJECT_ROOT"] = tmp

    from fastapi.testclient import TestClient

    import backend.app.main as main_module
    from backend.app.routers.scenarios import _scenario_to_dict
    from src.schemas.scenario import (
        BuildingConfig,
        EnergySharingConfig,
        PandapowerConfig,
        ScenarioConfig,
    )

    client = TestClient(main_module.app)
    configs = load_configs(Path(args.configs))
    corpus_items = {
        it["id"]: it
        for it in json.loads(
            (ROOT / "experiments" / "reference" / "p1_nl_corpus.json").read_text()
        )["items"]
    }
    record = {}
    print(f"round-tripping {len(configs)} configs through the scenario API")
    for item_id, cfg in configs.items():
        sid = f"p1rt_{item_id}"
        payload = dict(cfg)
        payload["scenario_id"] = sid
        item = corpus_items.get(item_id, {})
        rejection_item = item.get("kind") != "complete"
        r = None
        try:
            r = client.post("/api/scenarios", json=payload)
        except Exception as exc:  # pydantic ValidationError -> 500 surface
            msg = f"{type(exc).__name__}: {str(exc)[:300]}"
            expected = item.get("expected_named_fields") or []
            if rejection_item and any(f in msg for f in expected):
                # the DESIGNED rejection: the endpoint refuses the invalid
                # config and names the offending field (the validate-gate
                # criterion for a rejection item)
                record[item_id] = {
                    "post_round_trip": True,
                    "rejection_at_post": msg,
                }
                print(f"  {item_id:<28} designed rejection at POST (named) - PASS")
                continue
            record[item_id] = {
                "post_round_trip": False,
                "post_status": 500,
                "post_error": msg,
            }
            print(f"  {item_id:<28} POST raised {type(exc).__name__} - FAIL")
            continue
        entry = {"post_round_trip": False}
        if r.status_code != 201:
            entry["post_status"] = r.status_code
            entry["post_error"] = str(r.text)[:200]
            record[item_id] = entry
            print(f"  {item_id:<28} POST {r.status_code} - FAIL")
            continue
        g = client.get(f"/api/scenarios/{sid}")
        if g.status_code != 200:
            entry["get_status"] = g.status_code
            record[item_id] = entry
            print(f"  {item_id:<28} GET {g.status_code} - FAIL")
            continue
        got = g.json()
        # fair equivalence: compare the GET response against the endpoint's OWN
        # normalized view of the payload (the endpoint fills pydantic defaults,
        # so raw dicts always differ - normalization removes that noise while
        # still catching anything the endpoint actually loses or mangles)
        try:
            expected_model = ScenarioConfig(
                scenario_id=sid,
                name=payload.get("name", sid),
                description=payload.get("description", ""),
                buildings=[BuildingConfig(**b) for b in payload.get("buildings", [])],
                pandapower=(
                    PandapowerConfig(**payload["pandapower"])
                    if payload.get("pandapower")
                    else None
                ),
                energy_sharing=(
                    EnergySharingConfig(**payload["energy_sharing"])
                    if payload.get("energy_sharing")
                    else None
                ),
                community_import_limit_kw=payload.get("community_import_limit_kw"),
                community_export_limit_kw=payload.get("community_export_limit_kw"),
                random_seed=payload.get("random_seed", 42),
                timestep_minutes=payload.get("timestep_minutes", 15),
            )
            expected = _scenario_to_dict(expected_model)
        except Exception as exc:
            entry["post_round_trip"] = False
            entry["normalize_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            record[item_id] = entry
            print(f"  {item_id:<28} payload does not normalize - FAIL")
            continue
        diffs = []
        if got != expected:
            for k in set(list(got.keys()) + list(expected.keys())):
                if got.get(k) != expected.get(k):
                    diffs.append(f"{k} differs after round-trip")
        dropped = [k for k in DROPPED_TOP if cfg.get(k)]
        if dropped:
            diffs.append(f"endpoint dropped (not read on POST): {dropped}")
        v = client.get(f"/api/scenarios/{sid}/validate")
        entry["validate"] = (
            v.json() if v.status_code == 200 else {"status": v.status_code}
        )
        if diffs:
            entry["post_round_trip"] = False
            entry["diffs"] = diffs
            print(f"  {item_id:<28} round-trip DIFFERS: {diffs[:2]}")
        else:
            entry["post_round_trip"] = True
            print(f"  {item_id:<28} round-trip OK (201 + GET equivalent)")
        record[item_id] = entry

    Path(args.out).write_text(json.dumps(record, indent=2))
    ok = sum(1 for e in record.values() if e.get("post_round_trip"))
    print(f"\nC5 evidence: {ok}/{len(record)} round-trip clean -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
