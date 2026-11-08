"""Regression test for the simulation background failure path.

Docker Compose smoke on run 402cdf4b8 failed with
``UnboundLocalError: cannot access local variable 'coupler'`` raised from the
``except`` branch of ``_run_simulation_background``
(``backend/app/routers/simulations.py``). ``coupler`` was only assigned inside
the ``try`` (``SimulationCoupler(...)``), so any earlier failure - data dir
resolution, scenario validation, dataset load - crashed the error handler
instead of recording the original exception on the run.
"""

import asyncio

from backend.app.routers import simulations
from backend.app.routers.simulations import _run_simulation_background


def _run_entry(run_id: str):
    return {
        "status": "pending",
        "stage": None,
        "progress": 0.0,
        "error": None,
        "outcome_sentence": None,
        "end_time": None,
    }


def test_early_failure_records_original_error(monkeypatch):
    """Constructor failure must surface as the real error, not UnboundLocalError."""

    def _boom(*args, **kwargs):
        raise RuntimeError("dataset unavailable")

    monkeypatch.setattr(simulations, "SimulationCoupler", _boom)

    run_id = "run_regression_coupler"
    simulations._runs[run_id] = _run_entry(run_id)
    try:
        asyncio.run(
            _run_simulation_background(
                run_id=run_id,
                scenario=object(),  # never touched: the coupler constructor raises
                controller_type="rule_based",
                max_steps=1,
                random_seed=42,
            )
        )

        run = simulations._runs[run_id]
        assert run["status"] == "failed"
        assert run["stage"] == "error"
        assert "dataset unavailable" in run["error"]
        assert "dataset unavailable" in run["outcome_sentence"]
    finally:
        simulations._runs.pop(run_id, None)


def test_coupler_bound_before_try():
    """The except-branch trajectory persistence must survive an early failure."""
    import inspect
    import re

    source = inspect.getsource(_run_simulation_background)
    coupler_line = re.search(r"^\s+coupler = None$", source, re.MULTILINE)
    try_line = re.search(r"^\s+try:$", source, re.MULTILINE)
    assert coupler_line is not None and try_line is not None
    assert coupler_line.start() < try_line.start()
