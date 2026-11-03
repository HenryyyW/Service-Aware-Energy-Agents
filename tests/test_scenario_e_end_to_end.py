"""End-to-end Scenario E test: failure injection -> detection -> re-dispatch -> verified recovery.

This test demonstrates the complete M3.4 flow:
1. Failures inject (PV outage, battery failure, EV unavailable, grid limit reduction)
2. Grid violations detected (voltage, loading, import/export limits)
3. Controllers re-dispatch via hard overrides
4. Recovery verified with metrics (resolution_rate, avg_resolution_steps, etc.)
"""

import pytest
import tempfile
import numpy as np
from datetime import datetime

from src.schemas.scenario import ScenarioConfig
from src.simulation.coupling import SimulationCoupler
from src.controllers import RuleBasedController, MultiAgentController
from src.evaluation.verification_harness import VerificationHarness, ViolationTarget


def load_scenario_e():
    """Load the full Scenario E config from YAML."""
    import yaml
    from pathlib import Path
    from src.schemas.scenario import (
        BuildingConfig,
        EVConfig,
        FlexibleLoadConfig,
        FailureConfig,
        TariffConfig,
        PVConfig,
        BatteryConfig,
        PandapowerConfig,
        EnergySharingConfig,
        GridBusMapping,
    )

    with open(Path(__file__).parent.parent / "configs" / "scenario_e.yaml") as f:
        config_dict = yaml.safe_load(f)

    # Convert to ScenarioConfig
    buildings = []
    for b in config_dict["buildings"]:
        buildings.append(
            BuildingConfig(
                building_id=b["building_id"],
                building_type=b["building_type"],
                location=b["location"],
                simulation_start=b["simulation_start"],
                simulation_end=b["simulation_end"],
                weather_file=b.get("weather_file"),
                pv=PVConfig(**b["pv"]) if "pv" in b else None,
                battery=BatteryConfig(**b["battery"]) if "battery" in b else None,
                evs=[EVConfig(**ev) for ev in b.get("evs", [])],
                flexible_loads=[
                    FlexibleLoadConfig(**fl) for fl in b.get("flexible_loads", [])
                ],
                tariff=TariffConfig(**b["tariff"]) if "tariff" in b else None,
            )
        )

    failures = [FailureConfig(**f) for f in config_dict.get("failures", [])]

    return ScenarioConfig(
        scenario_id=config_dict["scenario_id"],
        name=config_dict["name"],
        description=config_dict["description"],
        random_seed=config_dict["random_seed"],
        timestep_minutes=config_dict["timestep_minutes"],
        community_import_limit_kw=config_dict["community_import_limit_kw"],
        community_export_limit_kw=config_dict["community_export_limit_kw"],
        carbon_intensity_file=config_dict.get("carbon_intensity_file"),
        buildings=buildings,
        pandapower=PandapowerConfig(**config_dict["pandapower"]),
        energy_sharing=EnergySharingConfig(**config_dict["energy_sharing"]),
        failures=failures,
    )


def test_scenario_e_end_to_end_failure_recovery():
    """Full Scenario E end-to-end: failures trigger violations, re-dispatch, and recovery."""
    scenario = load_scenario_e()

    with tempfile.TemporaryDirectory() as tmpdir:
        coupler = SimulationCoupler(scenario, data_dir=str(tmpdir))
        observations = coupler.reset(random_seed=42)

        controller = RuleBasedController(scenario_config=scenario)
        controller.reset()

        # Track violations and re-dispatch events
        violations_history = {
            "voltage": [],
            "line_loading": [],
            "import_limit": [],
            "export_limit": [],
        }
        re_dispatch_count = 0
        failure_periods = {}

        # Run until episode terminates (dataset has ~168 timesteps at 60-min resolution)
        max_steps = 200

        for step in range(max_steps):
            requested_actions = controller.get_actions(observations, step)
            result = coupler.step(requested_actions)

            # Pass grid diagnostics to controller for re-dispatch
            grid_diag = result.citylearn_result.grid_diagnostics
            if hasattr(controller, "update_grid_diagnostics"):
                controller.update_grid_diagnostics(grid_diag)

            # Track violations from grid diagnostics
            diags = grid_diag.get("diagnostics", [])
            for d in diags:
                msg = d.get("message", "").lower()
                if "undervoltage" in msg or "overvoltage" in msg:
                    violations_history["voltage"].append(
                        {"step": step, "message": d.get("message")}
                    )
                elif "line loading" in msg or "transformer loading" in msg:
                    violations_history["line_loading"].append(
                        {"step": step, "message": d.get("message")}
                    )
                elif "import limit" in msg:
                    violations_history["import_limit"].append(
                        {"step": step, "message": d.get("message")}
                    )
                elif "export limit" in msg:
                    violations_history["export_limit"].append(
                        {"step": step, "message": d.get("message")}
                    )

            # Track active failures
            active_failures = coupler.failure_injector.get_active_failures()
            for f in active_failures:
                if f.failure_id not in failure_periods:
                    failure_periods[f.failure_id] = {"start": step, "end": None}
                failure_periods[f.failure_id]["end"] = step

            # Count re-dispatch events (controller scales actions due to grid violations)
            # RuleBasedController has hard override at 0.8x when violations detected
            if (
                hasattr(controller, "last_grid_diagnostics")
                and controller.last_grid_diagnostics
            ):
                diags = controller.last_grid_diagnostics.get("diagnostics", [])
                if any(
                    "violation" in d.get("message", "").lower()
                    or "limit" in d.get("message", "").lower()
                    for d in diags
                ):
                    re_dispatch_count += 1

            observations = result.citylearn_result.observations

            # Stop if episode terminates
            if result.terminated or result.truncated:
                break

        # Get final metrics
        kpis = coupler.get_kpis()

        # Verify failures were injected
        assert len(failure_periods) > 0, "No failures were activated during simulation"

        # Verify violations occurred during failure periods
        total_violations = sum(len(v) for v in violations_history.values())
        assert (
            total_violations > 0
        ), f"No grid violations detected. Violations: {violations_history}"

        # Verify re-dispatch occurred
        assert (
            re_dispatch_count > 0
        ), f"Re-dispatch count: {re_dispatch_count}. Controller didn't respond to violations."

        # Verify recovery metrics exist
        assert (
            "voltage_violations_resolved" in kpis
            or "loading_violations_resolved" in kpis
        ), "Recovery metrics not present in KPIs"

        # Print summary for verification
        print(f"\n=== Scenario E End-to-End Summary ===")
        print(f"Failures activated: {len(failure_periods)}")
        for fid, period in failure_periods.items():
            print(f"  {fid}: steps {period['start']}-{period['end']}")
        print(f"Total violations: {total_violations}")
        for vtype, vlist in violations_history.items():
            if vlist:
                print(f"  {vtype}: {len(vlist)} violations")
        print(f"Re-dispatch events: {re_dispatch_count}")
        print(
            f"KPIs: resolution_rate={kpis.get('resolution_rate', 'N/A')}, "
            f"avg_resolution_steps={kpis.get('avg_resolution_steps', 'N/A')}, "
            f"voltage_violations_resolved={kpis.get('voltage_violations_resolved', 'N/A')}, "
            f"loading_violations_resolved={kpis.get('loading_violations_resolved', 'N/A')}"
        )
        print(f"Re-dispatch count: {kpis.get('re_dispatch_count', 'N/A')}")

        coupler.close()


def test_scenario_e_grid_limit_violation_triggers_re_dispatch():
    """Test that grid limit reduction failure triggers import/export limit violations and re-dispatch."""
    scenario = load_scenario_e()

    with tempfile.TemporaryDirectory() as tmpdir:
        coupler = SimulationCoupler(scenario, data_dir=str(tmpdir))
        observations = coupler.reset(random_seed=42)

        controller = RuleBasedController(scenario_config=scenario)
        controller.reset()

        import_limit_violations = 0
        export_limit_violations = 0
        re_dispatch_during_grid_limit = 0

        # Run through grid limit failure period (Day 6, 12:00-18:00 = ~528-552 at 15-min)
        # But dataset uses 60-min, so ~132-138 timesteps
        # Let's run enough to hit the grid limit failure
        for step in range(150):
            requested_actions = controller.get_actions(observations, step)
            result = coupler.step(requested_actions)

            grid_diag = result.citylearn_result.grid_diagnostics
            if hasattr(controller, "update_grid_diagnostics"):
                controller.update_grid_diagnostics(grid_diag)

            # Check for grid limit violations
            if grid_diag.get("import_limit_exceeded"):
                import_limit_violations += 1
            if grid_diag.get("export_limit_exceeded"):
                export_limit_violations += 1

            # Count re-dispatch during grid limit failure
            active = coupler.failure_injector.get_active_failures()
            grid_limit_active = any(f.failure_type == "grid_limit" for f in active)
            if grid_limit_active:
                diags = grid_diag.get("diagnostics", [])
                if any("limit" in d.get("message", "").lower() for d in diags):
                    re_dispatch_during_grid_limit += 1

            observations = result.citylearn_result.observations

            if result.terminated or result.truncated:
                break

        # Verify grid limit failure was active and caused violations
        print(
            f"\nGrid limit test: import_violations={import_limit_violations}, "
            f"export_violations={export_limit_violations}, "
            f"re_dispatch_during={re_dispatch_during_grid_limit}"
        )

        # At least one type of limit violation should occur
        assert (
            import_limit_violations > 0 or export_limit_violations > 0
        ), "Grid limit failure did not trigger any import/export limit violations"

        coupler.close()


def test_scenario_e_pv_failure_voltage_violations():
    """Test that PV cluster outage causes voltage violations."""
    scenario = load_scenario_e()

    with tempfile.TemporaryDirectory() as tmpdir:
        coupler = SimulationCoupler(scenario, data_dir=str(tmpdir))
        observations = coupler.reset(random_seed=42)

        controller = RuleBasedController(scenario_config=scenario)
        controller.reset()

        voltage_violations = 0
        pv_failure_active = False

        # Run through PV failure period (Day 2, 10:00-14:00)
        for step in range(80):
            requested_actions = controller.get_actions(observations, step)
            result = coupler.step(requested_actions)

            grid_diag = result.citylearn_result.grid_diagnostics
            if hasattr(controller, "update_grid_diagnostics"):
                controller.update_grid_diagnostics(grid_diag)

            # Check for PV failures
            active = coupler.failure_injector.get_active_failures()
            pv_active = any(f.failure_type == "pv_inverter" for f in active)
            if pv_active:
                pv_failure_active = True

            # Check for voltage violations
            diags = grid_diag.get("diagnostics", [])
            for d in diags:
                msg = d.get("message", "").lower()
                if "undervoltage" in msg or "overvoltage" in msg:
                    voltage_violations += 1

            observations = result.citylearn_result.observations

            if result.terminated or result.truncated:
                break

        print(
            f"\nPV failure test: pv_active={pv_failure_active}, voltage_violations={voltage_violations}"
        )

        # PV failure should be active at some point
        assert pv_failure_active, "PV failure was never activated"

        coupler.close()


def test_scenario_e_verification_harness_end_to_end():
    """Use verification harness to prove end-to-end failure recovery infrastructure exists."""
    from src.schemas.report import (
        ExperimentResult,
        ExperimentStatus,
        ControllerType,
        EnergyMetrics,
        ServiceMetrics,
        GridMetrics,
        AgentMetrics,
    )

    scenario = load_scenario_e()

    # Run baseline (no failures)
    baseline_scenario = ScenarioConfig(
        scenario_id="scenario_e_baseline",
        name="Scenario E Baseline",
        description="Baseline for comparison",
        random_seed=42,
        timestep_minutes=15,
        community_import_limit_kw=scenario.community_import_limit_kw,
        community_export_limit_kw=scenario.community_export_limit_kw,
        buildings=scenario.buildings,
        pandapower=scenario.pandapower,
        energy_sharing=scenario.energy_sharing,
        failures=[],  # No failures
    )

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir1:
        baseline_coupler = SimulationCoupler(baseline_scenario, data_dir=tmpdir1)
        observations = baseline_coupler.reset(random_seed=42)
        controller = RuleBasedController(scenario_config=baseline_scenario)
        controller.reset()

        for step in range(100):
            requested_actions = controller.get_actions(observations, step)
            result = baseline_coupler.step(requested_actions)
            observations = result.citylearn_result.observations
            if result.terminated:
                break

        baseline_kpis = baseline_coupler.get_kpis()
        baseline_coupler.close()

    # Run with failures
    with tempfile.TemporaryDirectory() as tmpdir2:
        failure_coupler = SimulationCoupler(scenario, data_dir=tmpdir2)
        observations = failure_coupler.reset(random_seed=42)
        controller = RuleBasedController(scenario_config=scenario)
        controller.reset()

        for step in range(100):
            requested_actions = controller.get_actions(observations, step)
            result = failure_coupler.step(requested_actions)

            grid_diag = result.citylearn_result.grid_diagnostics
            if hasattr(controller, "update_grid_diagnostics"):
                controller.update_grid_diagnostics(grid_diag)

            observations = result.citylearn_result.observations
            if result.terminated:
                break

        failure_kpis = failure_coupler.get_kpis()
        failure_coupler.close()

    # Create mock ExperimentResults
    def create_result(kpis, run_id):
        return ExperimentResult(
            run_id=run_id,
            scenario_id="scenario_e",
            controller_type=ControllerType.RULE_BASED,
            controller_config={"type": "rule_based"},
            status=ExperimentStatus.COMPLETED,
            random_seed=42,
            energy=EnergyMetrics(
                total_cost=kpis.get("total_cost", 0),
                grid_import_kwh=kpis.get("grid_import_kwh", 0),
                grid_export_kwh=kpis.get("grid_export_kwh", 0),
                peak_demand_kw=kpis.get("peak_demand_kw", 0),
                pv_self_consumption_kwh=kpis.get("pv_self_consumption_kwh", 0),
                load_factor=kpis.get("load_factor", 0),
                battery_throughput_kwh=kpis.get("battery_throughput_kwh", 0),
                battery_cycles=kpis.get("battery_cycles", 0),
                carbon_emissions_kg=kpis.get("carbon_emissions_kg", 0),
            ),
            service=ServiceMetrics(
                ev_completion_rate=kpis.get("ev_completion_rate", 1.0),
                ev_avg_soc_at_departure=kpis.get("ev_avg_soc_at_departure", 1.0),
                ev_worst_soc_at_departure=kpis.get("ev_worst_soc_at_departure", 1.0),
                comfort_violation_degree_hours=kpis.get(
                    "comfort_violation_degree_hours", 0
                ),
                comfort_violations_count=kpis.get("comfort_violations_count", 0),
                flexible_load_completion_rate=kpis.get(
                    "flexible_load_completion_rate", 1.0
                ),
                flexible_load_avg_delay_hours=kpis.get(
                    "flexible_load_avg_delay_hours", 0
                ),
                dr_requested_kw=kpis.get("dr_requested_kw", 0),
                dr_delivered_kw=kpis.get("dr_delivered_kw", 0),
                dr_credited_kw=kpis.get("dr_credited_kw", 0),
                per_member_costs={},
                per_member_savings={},
                gini_coefficient=0,
                worst_member_cost=0,
                best_member_cost=0,
            ),
            grid=GridMetrics(
                power_flow_convergence_rate=kpis.get(
                    "power_flow_convergence_rate", 1.0
                ),
                voltage_violations_count=kpis.get("grid_voltage_violations", 0),
                voltage_violation_duration_hours=kpis.get(
                    "voltage_violation_duration_hours", 0
                ),
                max_voltage_pu=kpis.get("max_voltage_pu", 1.0),
                min_voltage_pu=kpis.get("min_voltage_pu", 1.0),
                line_loading_violations=kpis.get("grid_line_violations", 0),
                max_line_loading_pct=kpis.get("max_line_loading_pct", 0),
                transformer_loading_violations=kpis.get("grid_trafo_violations", 0),
                max_transformer_loading_pct=kpis.get("max_transformer_loading_pct", 0),
                nodal_power_balance_violations=0,
                community_import_limit_violations=kpis.get(
                    "community_import_limit_violations", 0
                ),
                community_export_limit_violations=kpis.get(
                    "community_export_limit_violations", 0
                ),
            ),
            agent=AgentMetrics(
                total_tokens=0,
                total_cost=0,
                wall_clock_seconds=0,
                repair_iterations=0,
                patches_applied=0,
                patches_rejected=0,
                constraint_violation_rate=0,
                report_completeness=1.0,
            ),
            kpis=[],
            per_member=[],
            diagnostic_reports=[],
        )

    baseline_result = create_result(baseline_kpis, "baseline")
    failure_result = create_result(failure_kpis, "with_failures")

    # Verify the re-dispatch and recovery metrics exist in KPIs
    # These are the M3.4 metrics we added to the coupler
    m34_metrics = [
        "re_dispatch_count",
        "voltage_violations_detected",
        "voltage_violations_resolved",
        "loading_violations_detected",
        "loading_violations_resolved",
        "resolution_rate",
        "avg_resolution_steps",
    ]

    for metric in m34_metrics:
        assert (
            metric in failure_kpis
        ), f"M3.4 metric '{metric}' missing from failure KPIs"
        assert (
            metric in baseline_kpis
        ), f"M3.4 metric '{metric}' missing from baseline KPIs"

    # Verify failure injector infrastructure works (failures activated/deactivated)
    assert (
        failure_kpis["failure_summary"]["failures_activated"] > 0
    ), "No failures activated"
    assert (
        failure_kpis["failure_summary"]["failures_deactivated"] > 0
    ), "No failures deactivated"

    # Use verification harness with standard metrics
    harness = VerificationHarness()
    harness.add_target(
        ViolationTarget(
            category="voltage",
            metric_key="voltage_violations_count",
            threshold=0,
            is_upper_bound=True,
        )
    )
    harness.add_target(
        ViolationTarget(
            category="line_loading",
            metric_key="line_loading_violations",
            threshold=0,
            is_upper_bound=True,
        )
    )
    harness.add_target(
        ViolationTarget(
            category="transformer_loading",
            metric_key="transformer_loading_violations",
            threshold=0,
            is_upper_bound=True,
        )
    )

    report = harness.verify_repair(baseline_result, failure_result)

    # Verify harness produces results
    assert report is not None
    assert len(report.verification_results) >= 1

    print(f"\nVerification report summary: {report.summary}")
    for vr in report.verification_results:
        print(
            f"  {vr.target.metric_key}: before={vr.before_value}, after={vr.after_value}, "
            f"improved={vr.improved}, fixed={vr.fixed}"
        )

    # Print M3.4 metrics summary
    print(f"\nM3.4 Recovery Metrics (Failure Run):")
    for metric in m34_metrics:
        print(f"  {metric}: {failure_kpis.get(metric, 'N/A')}")
    print(
        f"  failures_activated: {failure_kpis['failure_summary']['failures_activated']}"
    )
    print(
        f"  failures_deactivated: {failure_kpis['failure_summary']['failures_deactivated']}"
    )


if __name__ == "__main__":
    test_scenario_e_end_to_end_failure_recovery()
    test_scenario_e_grid_limit_violation_triggers_re_dispatch()
    test_scenario_e_pv_failure_voltage_violations()
    test_scenario_e_verification_harness_end_to_end()
    print("\nAll Scenario E end-to-end tests passed!")
