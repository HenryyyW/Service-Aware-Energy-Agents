#!/usr/bin/env python3
"""Self-check for the seeded code-repair benchmark (zero LLM calls).

For every task: apply the mutation to the shipped controller source, then run
the detector against PRISTINE and MUTATED controllers. Expected pattern:

- measured tasks: detector PASSES on pristine, FAILS on mutated (the defect's
  signature - if it fails on pristine the detector is wrong, if it passes on
  mutated the mutation does not reach the asserted behaviour);
- negative control: the detector PASSES only while the defect is present.

Exit code 0 iff every task behaves as expected. Run before any repair run.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.code_repair_tasks import (  # noqa: E402
    CONTROLLER_FILE,
    TASKS,
    _load_controller,
    apply_mutation,
)


def main() -> int:
    source = (ROOT / CONTROLLER_FILE).read_text()
    failures = 0
    print(f"{'task':<34} {'pristine':>9} {'mutated':>9}  verdict  detail(mutated)")
    for task in TASKS:
        mutated = apply_mutation(source, task)
        detector = task.detector_fn()
        p_ok, p_detail = detector(
            _load_controller(source, f"pristine_{task.task_id}"), task.config()
        )
        m_ok, m_detail = detector(
            _load_controller(mutated, f"mutated_{task.task_id}"), task.config()
        )
        if task.negative_control:
            ok = (p_ok is False) and (m_ok is True)
            expected = "pristine inert=no, mutated inert=yes"
        else:
            ok = (p_ok is True) and (m_ok is False)
            expected = "pristine pass, mutated fail"
        failures += 0 if ok else 1
        print(f"{task.task_id:<34} {str(p_ok):>9} {str(m_ok):>9}  "
              f"{'OK' if ok else 'REVIEW':>7}  {m_detail[:60]}")
        if not ok:
            print(f"    expected: {expected}; pristine detail: {p_detail}")
    print(f"tasks: {len(TASKS)}, needing review: {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
