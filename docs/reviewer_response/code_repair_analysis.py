#!/usr/bin/env python3
"""Code-repair benchmark analysis (read-only; no LLM calls).

Consumes experiments/m2b_code_repair/ once Backend A's execution lands. Until
then it exits cleanly with "matrix not found - nothing to analyse".

Conventions (deliberately identical to the M2b audits):
- cells are enumerated by RUN-ID DIRECTORY NAME, never result.json's
  controller_type (the standing counting trap: centralized is recorded as
  rule_based, multi_agent as llm_agent, rl as rl_single);
- the keep rule for LLM cells is llm_backend_errors <= 2 AND llm_calls >=
  iterations AND telemetry recorded; quarantined cells are published per cell
  and excluded from headline stats; epochs are never pooled;
- any functional criterion (a)-(f) that is NOT recorded is reported as not
  recorded, never assumed.

The task list / pre-registered criteria live on origin/main at
experiments/m2b_code_repair_tasks.md; the fields this script expects per cell
are documented in docs/reviewer_response/code_repair_contract.md.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(os.environ.get("SAEA_REPO_ROOT", Path(__file__).resolve().parents[2]))
MATRIX = ROOT / "experiments" / "m2b_code_repair"
CELL_RE = re.compile(r"^(task_[0-9a-z]+)_(.+)_(\d+)$")

# Functional criteria (a)-(f) from experiments/m2b_code_repair_tasks.md,
# mapped to the field names the harness should record. add the actual names
# here once the first cells exist; missing criteria are reported, not assumed.
CRITERIA_FIELDS = {
    "a_parses": ("parses", "code_repair.parses"),
    "b_ran_clean": ("ran_clean_under_three_diagnostics",
                    "code_repair.ran_clean_under_three_diagnostics"),
    "c_output_differs": ("baseline_patch_differs",
                        "code_repair.baseline_patch_differs"),
    "d_not_cosmetic": ("diff_classifier_cosmetic", "code_repair.diff_classifier_cosmetic"),
    "e_harness_accepts": ("verification_harness_accepts",
                        "code_repair.verification_harness_accepts"),
    "f_service_preserved": ("service_preserved", "code_repair.service_preserved"),
}


def dig(d: dict, dotted: str):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def load_audit(cell_dir: Path) -> dict:
    """Merge manifest + result + repair_audit (where present) into one view."""
    out: dict = {}
    for name, key in (("manifest.json", "manifest"), ("result.json", "result")):
        p = cell_dir / name
        if p.is_file():
            out[key] = json.loads(p.read_text())
    audit = cell_dir / "repair_audit.json"
    if audit.is_file():
        out["audit"] = json.loads(audit.read_text())
    return out


def criterion(audit: dict, dotted: str):
    for src in ("audit", "manifest"):
        v = dig(audit.get(src, {}), dotted)
        if v is not None:
            return v
    return None


def main() -> int:
    if not MATRIX.is_dir():
        print("matrix not found - nothing to analyse "
              f"({MATRIX.relative_to(ROOT)} does not exist)")
        return 0
    cells: List[dict] = []
    for task_dir in sorted(p for p in MATRIX.iterdir() if p.is_dir()):
        for cell_dir in sorted(p for p in task_dir.iterdir() if p.is_dir()):
            m = CELL_RE.match(cell_dir.name)
            if not m:
                continue
            audit = load_audit(cell_dir)
            if "manifest" not in audit:
                continue
            agent = audit["manifest"].get("agent") or {}
            manifest = audit["manifest"]
            criteria = {k: criterion(audit, v) for k, v in CRITERIA_FIELDS.items()}
            steps = agent.get("total_steps") or 0
            keep = (
                agent.get("llm_backend_errors") is not None
                and agent["llm_backend_errors"] <= 2
                and (agent.get("llm_calls") or 0) >= steps
                and agent.get("first_attempt_validity") is not None
            )
            cells.append({
                "task": m.group(1),
                "cell": cell_dir.name,
                "keep": keep,
                "llm_calls": agent.get("llm_calls"),
                "llm_backend_errors": agent.get("llm_backend_errors"),
                "repair_iterations": agent.get("repair_iterations"),
                "repair_success_rate": agent.get("repair_success_rate"),
                "criteria": criteria,
                "criteria_unrecorded": [k for k, v in criteria.items() if v is None],
                "stratification": dig(audit.get("audit", {}), "stratification"),
            })
    if not cells:
        print("matrix present but contains no cells with manifest.json "
              "- nothing to analyse")
        return 0
    print(f"cells: {len(cells)} (keep {sum(1 for c in cells if c['keep'])})")
    unrecorded = sorted({k for c in cells for k in c["criteria_unrecorded"]})
    print(f"criteria not recorded anywhere: {unrecorded or 'none'}")
    for c in cells:
        crit = " ".join(
            f"{k}={'Y' if v is True else ('N' if v is False else '?')}"
            for k, v in c["criteria"].items()
        )
        print(f"  {c['task']:>10} {c['cell']:<44} keep={c['keep']} "
              f"calls={c['llm_calls']} errs={c['llm_backend_errors']} {crit}")
    # aggregation skeleton: per-task pass counts vs the pre-registered
    # threshold (>= 7/9 measured tasks) fill in once cells exist.
    return 0


if __name__ == "__main__":
    sys.exit(main())
