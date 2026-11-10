"""P1 corpus probe driver: run NL descriptions through the LLM-planner config pipeline.

The authorized LLM path (poolside/laguna-xs-2.1 on NVIDIA NIM) is wired from the
shared key store exactly as experiments/run_code_repair.py does it, so no
per-environment credentials are needed on this machine.

Usage:
    python experiments/run_p1_probe.py --list            # list corpus items
    python experiments/run_p1_probe.py --dry-run         # wiring check, no LLM calls
    python experiments/run_p1_probe.py --items 10        # first 10 items
    python experiments/run_p1_probe.py --items 16        # the full corpus

Envelope (authorization of record): <= 10 descriptions x <= 3 iterations for the
first probe, then a report before the full corpus. Each item costs at most
max_iterations planner calls (1 pre-flight is not used by the planner path).
Outputs land under experiments/p1_probe/ (gitignored) as <item_id>.json result
dicts plus a summary.json, ready for the deterministic scorer.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CORPUS_PATH = ROOT / "experiments" / "reference" / "p1_nl_corpus.json"
NIM_ENDPOINT = "https://integrate.api.nvidia.com/v1"
NIM_MODEL = "poolside/laguna-xs-2.1"

# Key-store location is environment-driven (never a hardcoded absolute path):
# SAEA_NIM_KEY_FILE points at the key file directly, or SAEA_NIM_KEY_DIR points
# at the directory holding NVIDIA_API_KEY.
KEY_STORE = os.environ.get("SAEA_NIM_KEY_FILE", "") or str(
    Path(
        os.environ.get(
            "SAEA_NIM_KEY_DIR",
            str(Path.home() / ".config" / "OpenBot" / "agent-api-keys"),
        )
    )
    / os.environ.get("OPENBOT_AGENT_ID", "agent-66d119d6-4915-479e-a539-1ab4a6b3b57b")
    / "NVIDIA_API_KEY"
)


def configure_llm_path() -> dict:
    """Set the authorized LLM-planner environment before any config read."""
    os.environ["AGENT_BACKEND"] = f"api:{NIM_MODEL}"
    os.environ["LLM_BASE_URL"] = NIM_ENDPOINT
    os.environ["LLM_API_KEY"] = Path(KEY_STORE).read_text().strip()
    os.environ.pop("DASHSCOPE_API_KEY", None)  # never pick up the DashScope key
    return {
        "agent_backend": f"api:{NIM_MODEL}",
        "endpoint": NIM_ENDPOINT,
        "model": NIM_MODEL,
        "dashscope_unset": "DASHSCOPE_API_KEY" not in os.environ,
        "key_file_env_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--items", type=int, default=10, help="number of corpus items to run"
    )
    parser.add_argument(
        "--offset", type=int, default=0, help="skip this many items first"
    )
    parser.add_argument(
        "--iterations", type=int, default=3, help="max pipeline iterations per item"
    )
    parser.add_argument(
        "--only",
        default="",
        help="comma-separated corpus item ids (e.g. c03_battery_arbitrage,c07_weather); overrides --items/--offset",
    )
    parser.add_argument("--out", default=str(ROOT / "experiments" / "p1_probe"))
    parser.add_argument("--list", action="store_true")
    parser.add_argument(
        "--dry-run", action="store_true", help="verify wiring, make no LLM calls"
    )
    args = parser.parse_args()

    corpus = json.load(open(CORPUS_PATH))
    items = corpus["items"]
    if args.list:
        for i, it in enumerate(items):
            print(
                f"{i + 1:2d}. {it['id']:32s} {it.get('kind', ''):18s} {(it.get('nl') or it.get('description', ''))[:60]}"
            )
        return 0

    settings = configure_llm_path()
    print(f"[probe] path: {settings}", flush=True)
    if args.dry_run:
        from src.agents.config_planner import ConfigPlannerAgent  # noqa: F401

        print(
            "[probe] dry-run OK (planner imports, env wired, no calls made)", flush=True
        )
        return 0

    from src.agents.nl_config_pipeline import run_nl_to_config

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    selected = items[args.offset : args.offset + args.items]
    if args.only:
        wanted = [s.strip() for s in args.only.split(",") if s.strip()]
        by_id = {it["id"]: it for it in items}
        missing = [w for w in wanted if w not in by_id]
        if missing:
            print(f"[probe] unknown item ids: {missing}", flush=True)
            return 2
        selected = [by_id[w] for w in wanted]
    records = []
    for it in selected:
        item_id = it["id"]
        nl = it.get("nl") or it.get("description") or it.get("text")
        t0 = time.time()
        try:
            out = run_nl_to_config(
                nl,
                scenario_id=item_id,
                max_iterations=args.iterations,
                project_root=str(ROOT),
            )
            its = out.get("iterations") or []
            last_it = its[-1] if its else {}
            rec = {
                "item_id": item_id,
                "kind": it.get("kind"),
                "nl": nl,
                "success": bool(out.get("success")),
                "final_config": out.get("final_config"),
                "iterations": its,
                "iteration_count": len(its),
                "manifest": out.get("manifest"),
                # Rejection items are scored on the NAMED failure, so the last
                # iteration's report summary and verdict must survive in the
                # record (not only in the console log).
                "final_report": (last_it.get("reporter_output") or {}).get("summary"),
                "final_verdict": (last_it.get("verifier_output") or {}).get(
                    "recommendation"
                ),
                "error": None,
            }
        except Exception as e:  # noqa: BLE001 - recorded, never swallowed silently
            rec = {
                "item_id": item_id,
                "kind": it.get("kind"),
                "nl": nl,
                "success": False,
                "final_config": None,
                "iterations": [],
                "iteration_count": 0,
                "manifest": None,
                "final_report": None,
                "final_verdict": None,
                "error": f"{type(e).__name__}: {e}",
            }
        rec["elapsed_s"] = round(time.time() - t0, 1)
        records.append(rec)
        (out_dir / f"{item_id}.json").write_text(json.dumps(rec, indent=1, default=str))
        print(
            f"[{item_id}] success={rec.get('success')} iterations={rec.get('iteration_count')} "
            f"err={str(rec.get('error'))[:60]}",
            flush=True,
        )
    summary = {
        "corpus": "p1_nl_corpus",
        "envelope": {
            "items": len(selected),
            "max_iterations": args.iterations,
            "model": NIM_MODEL,
        },
        "settings": settings,
        "records": records,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    ok = sum(1 for r in records if r.get("success"))
    print(f"[probe] {ok}/{len(records)} items success -> {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
