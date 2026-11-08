"""Regression tests for the AgentTask response shape (Docker Compose smoke).

Two smoke regressions came from ``task_data`` fields not matching the
``AgentTask`` response model, each 500-ing ``GET /api/agent/tasks/{id}``:

1. run ee6e9d13d: ``repairs`` was ``List[List[dict]]``
   (``iter.coder_output.code_changes``) vs the model's ``List[Dict]``.
2. run 01ce700c3: ``report`` got the raw ``final_report`` dict vs the
   model's ``Optional[str]``.
"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.app.routers.agent import (
    AgentTask,
    _render_repair_report_markdown,
    _shape_repair_records,
)


def _fake_iteration(index: int, n_changes: int):
    return SimpleNamespace(
        iteration=index,
        planner_output=SimpleNamespace(repair_strategy=f"strategy-{index}"),
        coder_output=SimpleNamespace(
            diff=f"--- diff {index}",
            code_changes=[{"file": "src/controllers/__init__.py", "change": index}]
            * n_changes,
        ),
        success=index == 1,
    )


def _fake_result(n_iterations: int):
    return SimpleNamespace(
        iterations=[_fake_iteration(i, 2) for i in range(n_iterations)]
    )


def test_shape_one_dict_per_iteration():
    records = _shape_repair_records(_fake_result(3))

    assert len(records) == 3
    for index, record in enumerate(records):
        assert isinstance(record, dict)
        assert record["iteration"] == index
        assert record["file"] == "src/controllers/__init__.py"
        assert record["description"] == f"strategy-{index}"
        assert record["diff"] == f"--- diff {index}"
        # code_changes stays a list INSIDE the dict, never a bare list entry
        assert isinstance(record["code_changes"], list)
        assert len(record["code_changes"]) == 2
        assert record["success"] is (index == 1)


def test_shape_empty_and_none_results():
    assert _shape_repair_records(None) == []
    assert _shape_repair_records(SimpleNamespace(iterations=[])) == []


def _minimal_task_kwargs(repairs):
    return {
        "task_id": "task_test",
        "description": "repair grid violations",
        "created_at": "2026-11-08T00:00:00+00:00",
        "updated_at": "2026-11-08T00:00:00+00:00",
        "repairs": repairs,
    }


def test_agent_task_accepts_shaped_repairs():
    task = AgentTask(**_minimal_task_kwargs(_shape_repair_records(_fake_result(2))))
    assert len(task.repairs) == 2


def test_agent_task_rejects_list_of_lists_repairs():
    """The exact smoke failure: repairs[0] was a list of change dicts."""
    bad_repairs = [[{"file": "src/controllers/__init__.py", "change": "x"}]]
    with pytest.raises(ValidationError):
        AgentTask(**_minimal_task_kwargs(bad_repairs))


def _final_report_fixture():
    return {
        "repair_session": {
            "run_id": "run_smoke",
            "scenario_id": "smoke_violation",
            "total_iterations": 2,
            "final_status": "FAILED",
            "completed_at": "2026-11-08T11:40:44+00:00",
        },
        "iteration_history": [
            {
                "iteration": 0,
                "planner": {
                    "primary_issue": "voltage",
                    "repair_strategy": "voltage-aware control",
                },
                "verifier": {
                    "violations_resolved": False,
                    "confidence": 0.0,
                    "recommendation": "retry",
                },
                "success": False,
                "duration": 1.5,
            },
            {
                "iteration": 1,
                "planner": {
                    "primary_issue": "voltage",
                    "repair_strategy": "reactive power support",
                },
                "verifier": {
                    "violations_resolved": True,
                    "confidence": 0.9,
                    "recommendation": "accept",
                },
                "success": True,
                "duration": 2.25,
            },
        ],
        "final_recommendations": ["Consider more iterations"],
        "lessons_learned": ["Iteration 2 succeeded"],
    }


def test_render_final_report_markdown():
    text = _render_repair_report_markdown(_final_report_fixture())

    assert isinstance(text, str)
    assert "# Multi-Agent Repair Report" in text
    assert "run_smoke" in text and "smoke_violation" in text
    assert "**FAILED**" in text
    # 0-based iteration numbers render 1-based for humans
    assert "### Iteration 1 (FAILED)" in text
    assert "### Iteration 2 (SUCCESS)" in text
    assert "Strategy: voltage-aware control" in text
    assert "recommendation=retry" in text
    assert "Consider more iterations" in text
    assert "Iteration 2 succeeded" in text


def test_render_final_report_non_dict_returns_empty():
    assert _render_repair_report_markdown(None) == ""
    assert _render_repair_report_markdown("already a string") == ""
    assert _render_repair_report_markdown({}) == ""


def test_agent_task_report_must_be_string():
    """The smoke failure on 01ce700c3: report got the raw dict."""
    with pytest.raises(ValidationError):
        AgentTask(**_minimal_task_kwargs([]) | {"report": _final_report_fixture()})

    task = AgentTask(
        **_minimal_task_kwargs([])
        | {"report": _render_repair_report_markdown(_final_report_fixture())}
    )
    assert task.report.startswith("# Multi-Agent Repair Report")
