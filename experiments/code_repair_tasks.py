"""Seeded code-repair benchmark tasks (source of truth for the matrix).

Owner: Research. Execution owner: Research (after Backend A's vocabulary
sign-off). Approved scope: docs/reviewer_response/code_repair_benchmark_scope.md
(Project Partner approval with two amendments: A signs off the defect+detector
set and the vocabulary mapping before any LLM call; per-cell L1/L5 telemetry
published).

Design rules:
- every mutation is an exact, line-anchored replacement on the real controller
  source in src/controllers/__init__.py, so the defect diff is reviewable and
  the baseline behaviour is the shipped behaviour;
- every detector is deterministic (no LLM, no network) - see
  experiments/code_repair_detectors.py; a detector passes on the pristine
  controller and fails on the mutated one (verified by
  experiments/code_repair_selfcheck.py);
- every task names the coder transformations (src/agents/coder.py `_add_*`)
  expected to express the repair - THE CLAIM BACKEND A MUST VERIFY.

Matrix output: experiments/m2b_code_repair/ only (authorized envelope).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from experiments.code_repair_detectors import DETECTORS, config_for

CONTROLLER_FILE = "src/controllers/__init__.py"

# Exact substrings from the shipped source (verified against origin/main).
EV_TARGET_CHECK = "        if current_soc >= ev.target_soc:"
EV_CHARGE_CAP = "        charge_kw = min(required_power, max_charge)"
BATTERY_DISCHARGE_CAP = (
    "                deficit, max_power, (current_soc - battery.soc_min) * capacity_kwh"
)
APPLY_IMPORT_LIMIT = "        if total_import > import_limit:"
APPLY_EXPORT_LIMIT = "        if total_export > export_limit:"
REDISPATCH_OVERVOLTAGE = "            if overvoltage:"
REDISPATCH_LINE_LOADING = "            elif line_loading_violated:"
REDISPATCH_CALL = "        actions = self._apply_grid_violation_redispatch(actions)"
FLEX_PV_GATE = "        if pv_gen > fl.power_kw * 0.5:"


@dataclass
class Task:
    task_id: str
    arm: str
    title: str
    target_function: str
    mutation_from: str
    mutation_to: str
    detector: str
    expected_transformations: List[str]
    success_test: str
    negative_control: bool = False
    notes: str = ""
    # Harness-side planner bypass (per A's sign-off): the planner's
    # _prioritize_issues picks by severity only and its issue->function map has
    # no entry for _apply_grid_violation_redispatch, so the driver forces the
    # task's own issue/targets instead of inferring them.
    planner_issue: str = ""
    planner_targets: List[str] = field(default_factory=list)

    def detector_fn(self):
        return DETECTORS[self.detector]

    def config(self):
        return config_for(self.detector)


def _load_controller(source: str, module_name: str):
    """Load a controller source string as a module; return RuleBasedController."""
    import importlib.util
    import sys
    from pathlib import Path

    path = Path("/tmp/opencode/code_repair") / f"{module_name}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.RuleBasedController


TASKS: List[Task] = [
    Task(
        planner_issue="ev_deadline",
        planner_targets=["_control_ev", "get_actions"],
        task_id="task_1_ev_deadline_soc",
        arm="deterministic",
        title="EV charging stops early (deadline SOC miss)",
        target_function="_control_ev",
        mutation_from=EV_TARGET_CHECK,
        mutation_to="        if current_soc >= 0.5 * ev.target_soc:",
        detector="detect_ev_deadline_soc",
        expected_transformations=[
            "_add_precise_time_to_departure",
            "_add_ev_prioritization_by_departure",
        ],
        success_test="final EV SOC >= 0.800 at departure",
    ),
    Task(
        planner_issue="ev_deadline",
        planner_targets=["_control_ev", "get_actions"],
        task_id="task_2_ev_urgent_power",
        arm="deterministic",
        title="EV urgent-deadline charging underpowered",
        target_function="_control_ev",
        mutation_from=EV_CHARGE_CAP,
        mutation_to="        charge_kw = min(required_power, 0.3 * max_charge)",
        detector="detect_ev_urgent_power",
        expected_transformations=[
            "_add_max_power_for_urgent_deadline",
            "_add_early_charging_for_low_soc",
        ],
        success_test="charge power covers the remaining need at 1h-to-departure",
    ),
    Task(
        planner_issue="battery_soc",
        planner_targets=["_control_battery", "get_actions"],
        task_id="task_3_battery_soc_floor",
        arm="deterministic",
        title="Battery discharge ignores the SOC floor (over-discharge)",
        target_function="_control_battery",
        mutation_from=BATTERY_DISCHARGE_CAP,
        mutation_to="                deficit, max_power, current_soc * capacity_kwh",
        detector="detect_battery_soc_floor",
        expected_transformations=[
            "_add_dynamic_soc_reserve",
            "_add_emergency_reserve",
            "_add_soc_forecast",
        ],
        success_test="no discharge action draws above-floor stored energy",
    ),
    Task(
        planner_issue="grid_import",
        planner_targets=["_apply_grid_limits", "get_actions"],
        task_id="task_4_import_limit",
        arm="deterministic",
        title="Community import limit not enforced",
        target_function="_apply_grid_limits",
        mutation_from=APPLY_IMPORT_LIMIT,
        mutation_to="        if False:",
        detector="detect_import_limit",
        expected_transformations=[
            "_add_import_limit_enforcement",
            "_add_proportional_curtailment",
        ],
        success_test="requested import <= 3 kW under a 3 kW limit",
    ),
    Task(
        planner_issue="grid_export",
        planner_targets=["_apply_grid_limits", "get_actions"],
        task_id="task_5_export_limit",
        arm="deterministic",
        title="Community export limit not enforced",
        target_function="_apply_grid_limits",
        mutation_from=APPLY_EXPORT_LIMIT,
        mutation_to="        if False:",
        detector="detect_export_limit",
        expected_transformations=[
            "_add_export_limit_enforcement",
            "_add_pv_curtailment",
            "_add_battery_charge_for_excess_pv",
        ],
        success_test="requested export <= 3 kW under a 3 kW limit",
    ),
    Task(
        planner_issue="voltage",
        planner_targets=["_apply_grid_violation_redispatch", "get_actions"],
        task_id="task_6_voltage_response",
        arm="deterministic",
        title="No overvoltage response in re-dispatch",
        target_function="_apply_grid_violation_redispatch",
        mutation_from=REDISPATCH_OVERVOLTAGE,
        mutation_to="            if False:",
        detector="detect_voltage_response",
        expected_transformations=[
            "_add_voltage_monitoring_and_reduction",
            "_add_voltage_triggered_load_reduction",
        ],
        success_test="actions scale to exactly 2x baseline under a 1.08 pu diagnostic",
    ),
    Task(
        planner_issue="line_loading",
        planner_targets=["_apply_grid_violation_redispatch", "get_actions"],
        task_id="task_7_line_loading_response",
        arm="deterministic",
        title="No line-loading response in re-dispatch",
        target_function="_apply_grid_violation_redispatch",
        mutation_from=REDISPATCH_LINE_LOADING,
        mutation_to="            elif False:",
        detector="detect_line_loading_response",
        expected_transformations=[
            "_add_line_loading_monitoring",
            "_add_transformer_loading_check",
        ],
        success_test="actions scale to exactly 0.1x baseline under 110% loading",
    ),
    Task(
        planner_issue="flexible_load",
        planner_targets=["_control_flexible_load", "get_actions"],
        task_id="task_8_flex_deadline",
        arm="deterministic",
        title="Flexible load never runs (deadline miss)",
        target_function="_control_flexible_load",
        mutation_from=FLEX_PV_GATE,
        mutation_to="        if False:",
        detector="detect_flex_deadline",
        expected_transformations=[
            "_add_earliest_deadline_first",
            "_add_deadline_tracking",
        ],
        success_test="flexible load runs inside its window when PV is available",
    ),
    Task(
        planner_issue="ev_deadline",
        planner_targets=["_control_ev", "get_actions"],
        task_id="task_9_overcharge_spike",
        arm="deterministic",
        title="EV charges at charger max regardless of remaining need",
        target_function="_control_ev",
        mutation_from=EV_CHARGE_CAP,
        mutation_to="        charge_kw = max_charge",
        detector="detect_overcharge_spike",
        expected_transformations=[
            "_add_proportional_power_allocation",
            "_add_action_magnitude_reduction",
            "_add_precise_time_to_departure",
        ],
        success_test="no charge action exceeds the remaining energy need",
    ),
    Task(
        planner_issue="voltage",
        planner_targets=["_apply_grid_violation_redispatch", "get_actions"],
        task_id="task_10_NEG_redispatch_removed",
        arm="deterministic",
        title="NEGATIVE CONTROL: re-dispatch call site removed (outside vocabulary)",
        target_function="get_actions",
        mutation_from=REDISPATCH_CALL,
        mutation_to="        pass  # re-dispatch call removed (seeded defect)",
        detector="detect_redispatch_call_removed",
        expected_transformations=[],
        success_test="none - honest non-repair is the required outcome",
        negative_control=True,
        notes="Vocabulary-boundary probe: the _add_* transformations add logic "
        "inside functions; nothing restores a deleted call site. A "
        "'repair' here would mean the pipeline accepts cosmetic diffs. "
        "Amends the scope doc's tariff-lookup probe (the rule_based "
        "controller has no price-aware surface to mutate).",
    ),
]


def load_tasks(task_ids: Optional[List[str]] = None) -> List[Task]:
    if not task_ids:
        return TASKS
    by_id = {t.task_id: t for t in TASKS}
    return [by_id[t] for t in task_ids]


def apply_mutation(source: str, task: Task) -> str:
    n = source.count(task.mutation_from)
    if n != 1:
        raise ValueError(
            f"{task.task_id}: anchor occurs {n}x (expected exactly 1): "
            f"{task.mutation_from!r}"
        )
    return source.replace(task.mutation_from, task.mutation_to)
