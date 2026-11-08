"""Regression tests for the AgentTask ``repairs`` response shape.

Docker Compose smoke on ee6e9d13d failed because ``task_data["repairs"]`` was
built as ``[iter.coder_output.code_changes for ...]`` — a ``List[List[dict]]``.
``AgentTask.repairs`` is typed ``List[Dict[str, Any]]``, so FastAPI rejected the
whole ``GET /api/agent/tasks/{task_id}`` response with a
``ResponseValidationError`` (``loc: ('response', 'repairs', 0)``) and the smoke
run exited 1. These tests pin both the shaping helper and the model contract.
"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.app.routers.agent import AgentTask, _shape_repair_records


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
