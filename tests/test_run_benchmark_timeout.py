"""Per-run timeout enforcement in the benchmark runner.

Regression for the first full matrix's three scenario_e multi_agent runs that
hung ~33,000 s despite run_benchmark's 900 s per-run timeout: capturing output
through pipes makes subprocess.run block after the kill until every inherited
handle closes. The runner must use per-run log files and kill the process tree.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from experiments.run_benchmark import _run_with_timeout


def _python(cmd: str) -> list:
    return [sys.executable, "-c", cmd]


def test_hanging_child_times_out_and_is_killed(tmp_path):
    result_file = tmp_path / "scenario" / "run" / "result.json"
    start = time.time()
    with pytest.raises(subprocess.TimeoutExpired):
        _run_with_timeout(
            _python('print("started", flush=True); import time; time.sleep(600)'),
            os.environ.copy(),
            2,
            result_file,
        )
    elapsed = time.time() - start
    assert elapsed < 20, f"timeout enforcement took {elapsed:.1f}s"


def test_fast_child_completes_and_logs_are_kept(tmp_path):
    result_file = tmp_path / "scenario" / "run" / "result.json"
    completed, tail = _run_with_timeout(
        _python('print("hello from run"); print("second line")'),
        os.environ.copy(),
        60,
        result_file,
    )
    assert completed.returncode == 0
    assert "hello from run" in tail
    log_file = result_file.parent / "run_output.log"
    assert log_file.exists()
