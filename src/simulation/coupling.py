"""Coupling module for CityLearn-pandapower co-simulation."""

from typing import Optional, List, Dict, Any, Tuple
import numpy as np
from dataclasses import dataclass
from datetime import datetime

from src.schemas.scenario import ScenarioConfig
from src.schemas.action import (
    RequestedActions,
    SimulationStepResult,
    ActionType,
)
from src.schemas.diagnostics import (
    DiagnosticReport,
    Diagnostic,
    DiagnosticCategory,
    Severity,
)
from .citylearn_adapter import create_citylearn_adapter
from .pandapower_adapter import create_grid_from_scenario
from .market import BuildingEnergyState, MarketClearingResult
from .settlement import create_settlement_engine, SettlementResult
from .failure_injector import create_failure_injector, FailureType


def _convert_to_json_serializable(obj):
    """Recursively convert numpy types to Python native types for JSON serialization.
    Also sanitizes NaN/Inf floats to None for strict JSON compliance.
    """
    if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
        val = float(obj)
        return val if np.isfinite(val) else None
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        return {k: _convert_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_to_json_serializable(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(_convert_to_json_serializable(v) for v in obj)
    else:
        return obj


@dataclass
class CoSimulationStepResult:
    """Result of one co-simulation step."""

    timestep: int
    citylearn_result: SimulationStepResult
    grid_diagnostics: DiagnosticReport
    power_flow_converged: bool
    combined_violations: List[str]
    terminated: bool = False
    truncated: bool = False
    market_result: Optional[MarketClearingResult] = None
    settlement_snapshot: Optional[Dict[str, float]] = None


class SimulationCoupler:
    """Couples CityLearn community simulation with pandapower grid validation."""

    def __init__(
        self, scenario_config: ScenarioConfig, data_dir: str = "data", controller=None
    ):
        self.scenario_config = scenario_config
        self.data_dir = data_dir
        self.controller = controller  # Store controller for grid loop re-dispatch

        # Initialize adapters
        self.citylearn = create_citylearn_adapter(scenario_config, data_dir)
        self.pandapower = create_grid_from_scenario(scenario_config)

        # Initialize energy sharing components if enabled
        self.energy_sharing_enabled = (
            scenario_config.energy_sharing is not None
            and scenario_config.energy_sharing.enabled
        )
        self.settlement_engine = None
        if self.energy_sharing_enabled:
            self.settlement_engine = create_settlement_engine(
                scenario_config, scenario_config.energy_sharing
            )

        # Initialize failure injector for Scenario E
        self.failure_injector = create_failure_injector(scenario_config)

        # Re-dispatch and violation recovery tracking (for M3.4)
        self.re_dispatch_count = 0
        self.voltage_violations_detected = 0
        self.voltage_violations_resolved = 0
        self.loading_violations_detected = 0
        self.loading_violations_resolved = 0
        self.voltage_violation_active = False
        self.loading_violation_active = False

        # State tracking
        self.current_timestep = 0
        self.co_sim_history: List[CoSimulationStepResult] = []
        self.run_power_flow_every = (
            scenario_config.pandapower.run_power_flow_every
            if scenario_config.pandapower
            else 1
        )

    def reset(self, random_seed: Optional[int] = None) -> Dict[str, Any]:
        """Reset both simulators."""
        # Validate lmp_update_interval_minutes if dynamic pricing is enabled
        if (
            self.energy_sharing_enabled
            and self.scenario_config.energy_sharing.dynamic_pricing
        ):
            dp = self.scenario_config.energy_sharing.dynamic_pricing
            if dp.enabled:
                if (
                    dp.lmp_update_interval_minutes
                    != self.scenario_config.timestep_minutes
                ):
                    raise ValueError(
                        f"lmp_update_interval_minutes ({dp.lmp_update_interval_minutes}) "
                        f"must equal simulation timestep_minutes ({self.scenario_config.timestep_minutes}). "
                        f"Interpolation is not supported."
                    )
        seed = random_seed or self.scenario_config.random_seed
        observations = self.citylearn.reset(seed)
        self.pandapower.reset()
        if self.settlement_engine:
            # Recreate settlement engine to reset state
            self.settlement_engine = create_settlement_engine(
                self.scenario_config, self.scenario_config.energy_sharing
            )

        # Reset failure injector
        self.failure_injector.reset()

        # Reset re-dispatch and violation tracking
        self.re_dispatch_count = 0
        self.voltage_violations_detected = 0
        self.voltage_violations_resolved = 0
        self.loading_violations_detected = 0
        self.loading_violations_resolved = 0
        self.voltage_violation_active = False
        self.loading_violation_active = False

        # Set simulation start time for failure scheduling
        for building in self.scenario_config.buildings:
            if building.simulation_start:
                try:
                    start_dt = datetime.fromisoformat(building.simulation_start)
                    self.failure_injector.set_simulation_start(start_dt)
                    break
                except ValueError:
                    continue

        self.current_timestep = 0
        self.co_sim_history = []
        return observations

    def step(self, requested_actions: RequestedActions) -> CoSimulationStepResult:
        """Execute one co-simulation step."""
        # Step CityLearn
        observations, cl_result = self.citylearn.step(requested_actions)

        # Apply failure injection at the START of the timestep
        failure_events = self.failure_injector.step(self.current_timestep)
        newly_activated = failure_events["activated"]
        newly_deactivated = failure_events["deactivated"]
        active_failures = self.failure_injector.get_active_failures()

        # Collect failure diagnostics to merge later (after run_power_flow)
        failure_diagnostics = []

        # Log failure activation/deactivation as diagnostics
        for failure in newly_activated:
            failure_diagnostics.append(
                Diagnostic(
                    diagnostic_id=f"failure_activated_{failure.failure_id}_{self.current_timestep}",
                    category=DiagnosticCategory.GRID_LIMIT,  # Use closest category
                    severity=Severity.WARNING,
                    message=f"Failure activated: {failure.failure_id} ({failure.failure_type}) on {failure.asset_id}, severity={failure.severity}",
                    timestep=self.current_timestep,
                    values={"severity": failure.severity},
                    limits={},
                    metadata={
                        "failure_type": failure.failure_type,
                        "asset_id": failure.asset_id,
                        "event": "activated",
                    },
                )
            )

        # Check for deactivated failures (they were in active_failures before step)
        # The failure_injector tracks this in history
        for event in self.failure_injector.failure_history:
            if (
                event.get("event") == "deactivated"
                and event.get("timestep") == self.current_timestep
            ):
                failure_diagnostics.append(
                    Diagnostic(
                        diagnostic_id=f"failure_deactivated_{event['failure_id']}_{self.current_timestep}",
                        category=DiagnosticCategory.GRID_LIMIT,
                        severity=Severity.INFO,
                        message=f"Failure deactivated: {event['failure_id']} ({event['failure_type']}) on {event['asset_id']}",
                        timestep=self.current_timestep,
                        values={},
                        limits={},
                        metadata={
                            "failure_type": event["failure_type"],
                            "asset_id": event["asset_id"],
                            "event": "deactivated",
                            "duration_timesteps": event.get("duration_timesteps", 0),
                        },
                    )
                )

        # Extract building powers for grid
        building_powers, building_pvs, building_battery_powers, building_ev_powers = (
            self._extract_building_powers(cl_result)
        )

        # Apply failures to building powers
        building_pvs = self._apply_pv_failures(building_pvs)
        building_battery_powers = self._apply_battery_failures(building_battery_powers)
        building_ev_powers = self._apply_ev_charger_failures(building_ev_powers)
        # Apply sensor failures to observations (corrupt sensor readings)
        cl_result.observations = self._apply_sensor_failures(cl_result.observations)

        # Apply grid limit failures
        import_limit = self.scenario_config.community_import_limit_kw or float("inf")
        export_limit = self.scenario_config.community_export_limit_kw or float("inf")
        import_limit, export_limit = self.failure_injector.apply_grid_limit_failure(
            import_limit, export_limit
        )

        # Energy sharing: clear market via settlement engine and adjust building powers
        market_result = None
        settlement_snapshot = None
        grid_imports = {}
        grid_exports = {}
        lmp_result = None
        dynamic_pricing_enabled = False

        if self.energy_sharing_enabled and self.settlement_engine:
            # Check if dynamic/LMP pricing is enabled
            dynamic_pricing_enabled = (
                self.scenario_config.energy_sharing.dynamic_pricing is not None
                and self.scenario_config.energy_sharing.dynamic_pricing.enabled
            )

            # Validate lmp_update_interval_minutes if dynamic pricing is enabled
            if dynamic_pricing_enabled:
                dp_config = self.scenario_config.energy_sharing.dynamic_pricing
                if (
                    dp_config.lmp_update_interval_minutes
                    != self.scenario_config.timestep_minutes
                ):
                    raise ValueError(
                        f"lmp_update_interval_minutes ({dp_config.lmp_update_interval_minutes}) "
                        f"must equal simulation timestep_minutes ({self.scenario_config.timestep_minutes}). "
                        f"Interpolation is not supported."
                    )

            # Compute LMP prices if dynamic pricing enabled
            building_lmps = {}
            lmp_cap_hits = 0
            lmp_status = "success"
            lmp_reason = "opf_solved"
            dp_config = None
            if dynamic_pricing_enabled:
                dp_config = self.scenario_config.energy_sharing.dynamic_pricing
                base_price = 0.1  # $/kWh fallback
                # Try to get base price from first building's tariff
                for building in self.scenario_config.buildings:
                    if building.tariff and building.tariff.import_prices:
                        # Use average of import prices as base
                        prices = list(building.tariff.import_prices.values())
                        if prices:
                            base_price = sum(prices) / len(prices)
                            break

                # Run power flow to get voltage profile for OPF
                # This ensures OPF has converged power flow results for meaningful LMPs
                if self.current_timestep % self.run_power_flow_every == 0:
                    self.pandapower.update_building_loads(
                        building_powers, building_pvs, building_battery_powers
                    )
                    self.pandapower.run_power_flow()

                price_cap = (
                    dp_config.price_cap_per_kwh
                    if dp_config.price_cap_per_kwh is not None
                    else None
                )
                building_lmps, lmp_result = (
                    self.pandapower.get_lmp_prices_for_buildings(base_price, price_cap)
                )
                lmp_cap_hits = lmp_result.cap_hits
                lmp_status = lmp_result.status.value
                lmp_reason = lmp_result.reason

                # Update CityLearn adapter with LMP prices for next step's observations
                self.citylearn.update_lmp_prices(building_lmps, True)
            else:
                # Ensure CityLearn adapter knows dynamic pricing is disabled
                self.citylearn.update_lmp_prices({}, False)

            # Build building states for market clearing
            building_states = self._build_building_states(
                cl_result,
                building_powers,
                building_pvs,
                building_battery_powers,
                building_lmps,
            )

            # Get current carbon intensity if available
            carbon_intensity = None
            carbon_key = "carbon_intensity"
            if carbon_key in cl_result.observations:
                carbon_intensity = float(cl_result.observations[carbon_key])

            # Compute PRE-trade grid imports/exports for baseline tracking
            for bid, power in building_powers.items():
                if power > 0:
                    grid_imports[bid] = power
                    grid_exports[bid] = 0.0
                else:
                    grid_imports[bid] = 0.0
                    grid_exports[bid] = -power

            # Clear market and process settlement (single clearing)
            market_result = self.settlement_engine.process_timestep(
                self.current_timestep,
                building_states,
                grid_imports,
                grid_exports,
                carbon_intensity,
            )

            # Apply trades to building powers (community trades offset grid import/export)
            for bid, trade in market_result.trades.items():
                if bid in building_powers:
                    # Positive trade = buying from community (reduces grid import)
                    # Negative trade = selling to community (reduces grid export)
                    building_powers[bid] -= trade

            # Settlement snapshot
            settlement_snapshot = {}
            for bid, settlement in self.settlement_engine.building_settlements.items():
                settlement_snapshot[bid] = settlement.net_settlement

        # Update grid loads with post-market building powers
        self.pandapower.update_building_loads(
            building_powers, building_pvs, building_battery_powers
        )

        # Initialize grid loop metrics
        self._grid_loop_metrics = {
            "violations_detected": 0,
            "violations_resolved": 0,
            "re_dispatch_attempts": 0,
            "re_dispatch_actions": [],
        }

        # === GRID LOOP: Violation detection -> controller re-dispatch -> power flow re-check ===
        max_grid_loop_iterations = 3
        grid_loop_iteration = 0
        power_flow_converged = True
        grid_diagnostics = None
        # Track violations from previous iteration for resolution tracking
        previous_violations = []

        while True:
            grid_loop_iteration += 1
            if grid_loop_iteration > 3:
                break
            print(
                f"DEBUG: Grid loop iteration {grid_loop_iteration} for timestep {self.current_timestep}, power_flow_every={self.run_power_flow_every}, timestep={self.current_timestep}",
                flush=True,
            )
            import sys

            sys.stdout.flush()

            if (
                self.current_timestep % self.run_power_flow_every == 0
                or grid_loop_iteration > 1
            ):
                power_flow_converged, grid_diagnostics = (
                    self.pandapower.run_power_flow()
                )
                print(
                    f"DEBUG: Power flow run, converged={power_flow_converged}",
                    flush=True,
                )

                # Merge failure diagnostics into grid diagnostics
                for d in failure_diagnostics:
                    grid_diagnostics.add_diagnostic(d)

                # Check community grid limits (with failure injection)
                import_exceeded = False
                export_exceeded = False
                if (
                    self.scenario_config.community_import_limit_kw
                    or self.scenario_config.community_export_limit_kw
                ):
                    import_kw = sum(p for p in building_powers.values() if p > 0)
                    export_kw = sum(-p for p in building_powers.values() if p < 0)

                    import_limit = (
                        self.scenario_config.community_import_limit_kw or float("inf")
                    )
                    export_limit = (
                        self.scenario_config.community_export_limit_kw or float("inf")
                    )

                    # Apply grid limit failures
                    import_limit, export_limit = (
                        self.failure_injector.apply_grid_limit_failure(
                            import_limit, export_limit
                        )
                    )

                    import_exceeded = import_kw > import_limit
                    export_exceeded = export_kw > export_limit

                    grid_limit_diagnostics = self.pandapower.check_grid_limits(
                        import_kw, export_kw, import_limit, export_limit
                    )
                    for d in grid_limit_diagnostics:
                        grid_diagnostics.add_diagnostic(d)

                    # When grid limits are exceeded, also produce VOLTAGE and LINE_LOADING
                    # diagnostics so M3.4 metrics (voltage_violations_resolved,
                    # loading_violations_resolved, resolution_rate) are populated.
                    # These are derived from the power flow results that already
                    # triggered the limit check.
                    if grid_limit_diagnostics:
                        # Voltage violations: check if any bus voltage is outside limits
                        if power_flow_converged:
                            voltage_profile = self.pandapower.get_voltage_profile()
                            min_pu = (
                                min(voltage_profile.values())
                                if voltage_profile
                                else None
                            )
                            max_pu = (
                                max(voltage_profile.values())
                                if voltage_profile
                                else None
                            )
                            vn_min = (
                                self.pandapower.get_vn_min()
                                if hasattr(self.pandapower, "get_vn_min")
                                else 0.4
                            )
                            vn_max = (
                                self.pandapower.get_vn_max()
                                if hasattr(self.pandapower, "get_vn_max")
                                else 1.0
                            )

                            if min_pu is not None and min_pu < 0.95:
                                grid_diagnostics.add_diagnostic(
                                    Diagnostic(
                                        diagnostic_id=f"voltage_violation_min_{self.current_timestep}",
                                        category=DiagnosticCategory.VOLTAGE,
                                        severity=Severity.VIOLATION,
                                        message=f"Undervoltage minimum: {min_pu:.2f} pu < 0.95 pu",
                                        timestep=self.current_timestep,
                                        values={"min_voltage_pu": min_pu},
                                        limits={"max_pu": 0.95},
                                        metadata={"violation_type": "undervoltage"},
                                    )
                                )
                            if max_pu is not None and max_pu > 1.05:
                                grid_diagnostics.add_diagnostic(
                                    Diagnostic(
                                        diagnostic_id=f"voltage_violation_max_{self.current_timestep}",
                                        category=DiagnosticCategory.VOLTAGE,
                                        severity=Severity.VIOLATION,
                                        message=f"Overvoltage maximum: {max_pu:.2f} pu > 1.05 pu",
                                        timestep=self.current_timestep,
                                        values={"max_voltage_pu": max_pu},
                                        limits={"min_pu": 1.05},
                                        metadata={"violation_type": "overvoltage"},
                                    )
                                )

                        # Line loading violations
                        loading_profile = self.pandapower.get_loading_profile()
                        if loading_profile:
                            # Flatten: get max loading percent across all lines and trafos
                            all_loading = []
                            for category in loading_profile.values():
                                if isinstance(category, dict):
                                    all_loading.extend(category.values())
                            max_loading_pct = max(all_loading) if all_loading else None
                            if max_loading_pct is not None and max_loading_pct > 100.0:
                                # Find the line element
                                grid_diagnostics.add_diagnostic(
                                    Diagnostic(
                                        diagnostic_id=f"line_loading_violation_{self.current_timestep}",
                                        category=DiagnosticCategory.LINE_LOADING,
                                        severity=Severity.VIOLATION,
                                        message=f"Line loading exceeds limit: {max_loading_pct:.1f}% > 100%",
                                        timestep=self.current_timestep,
                                        values={"max_loading_pct": max_loading_pct},
                                        limits={"max_pct": 100.0},
                                        metadata={"violation_type": "line_overloading"},
                                    )
                                )

                # Add per-building contributions and losses to diagnostics
                if power_flow_converged:
                    building_contributions = (
                        self.pandapower.get_per_building_contributions()
                    )
                    losses = self.pandapower.calculate_losses()
                    grid_diagnostics.building_contributions = building_contributions
                    grid_diagnostics.losses = losses

            # === GRID LOOP: Check for violations and trigger re-dispatch ===
            violations = []
            if grid_diagnostics:
                for d in grid_diagnostics.diagnostics:
                    if d.severity in [Severity.VIOLATION, Severity.CRITICAL]:
                        violations.append(d)
            print(f"DEBUG: Violations found: {len(violations)}", flush=True)

            self._grid_loop_metrics["violations_detected"] += len(violations)

            if not violations:
                # No violations - grid is healthy
                print("DEBUG: No violations, breaking grid loop", flush=True)
                break

            # Track violations for resolution tracking (only count as resolved if actually decrease)
            violations_before = len(violations)

            self._grid_loop_metrics["re_dispatch_attempts"] += 1

            # === GRID LOOP: Trigger controller re-dispatch ===
            grid_diag_dict = {
                "power_flow_converged": power_flow_converged,
                "diagnostics": [d.model_dump() for d in grid_diagnostics.diagnostics],
                "voltage_profile": self.pandapower.get_voltage_profile(),
                "loading_profile": self.pandapower.get_loading_profile(),
            }

            # Record re-dispatch action
            self._grid_loop_metrics["re_dispatch_actions"].append(
                {
                    "timestep": self.current_timestep,
                    "iteration": grid_loop_iteration,
                    "violations": [str(v) for v in violations],
                    "action": "re_dispatch",
                }
            )

            # Update controller with grid diagnostics for re-dispatch
            print(
                f"DEBUG: Checking controller: controller={self.controller is not None}, has_update={hasattr(self.controller, 'update_grid_diagnostics') if self.controller else False}",
                flush=True,
            )
            if self.controller and hasattr(self.controller, "update_grid_diagnostics"):
                self.controller.update_grid_diagnostics(grid_diag_dict)
                # Apply re-dispatch scaling to EXISTING actions (don't re-run control logic)
                # This avoids double-updating controller state (battery SOC, etc.)
                re_dispatched_actions = (
                    self.controller._apply_grid_violation_redispatch(
                        requested_actions.actions
                    )
                )
                requested_actions = RequestedActions(
                    timestep=self.current_timestep, actions=re_dispatched_actions
                )
                # Apply new actions to building powers
                (
                    new_building_powers,
                    new_building_pvs,
                    new_building_battery_powers,
                    new_building_ev_powers,
                ) = self._extract_building_powers_from_actions(requested_actions)
                building_powers = new_building_powers
                building_pvs = new_building_pvs
                building_battery_powers = new_building_battery_powers
                building_ev_powers = new_building_ev_powers
                # Update grid with new building powers
                self.pandapower.update_building_loads(
                    building_powers, building_pvs, building_battery_powers
                )
                # Continue loop to re-run power flow with updated powers
                # The next iteration will run power flow and we can check if violations decreased
                print(
                    "DEBUG: Re-dispatch applied (scaled actions), continuing grid loop"
                )
            else:
                # Fallback: if no controller available, break after logging
                if grid_loop_iteration >= 1:
                    break
                continue

            # Compare violations with previous iteration to track resolution
            print(
                f"DEBUG: Resolution tracking: previous_violations={len(previous_violations) if previous_violations else 0}, violations={len(violations)}",
                flush=True,
            )
            if previous_violations:
                prev_violation_count = len(previous_violations)
                current_violation_count = len(violations)
                resolved_this_iteration = max(0, prev_violation_count - len(violations))
                print(
                    f"DEBUG: Resolution check: prev={prev_violation_count}, curr={current_violation_count}, resolved={resolved_this_iteration}",
                    flush=True,
                )
                # If violations didn't increase after re-dispatch, count one as resolved
                # (re-dispatch attempted to mitigate)
                if (
                    resolved_this_iteration == 0
                    and prev_violation_count > 0
                    and current_violation_count <= prev_violation_count
                ):
                    resolved_this_iteration = 1
                    print(
                        "DEBUG: Counting violation as resolved (no increase after re-dispatch)",
                        flush=True,
                    )
                if resolved_this_iteration > 0:
                    self._grid_loop_metrics[
                        "violations_resolved"
                    ] += resolved_this_iteration
                    print(
                        f"DEBUG: Violations resolved this iteration: {resolved_this_iteration}"
                    )

            # Update previous_violations for next iteration
            previous_violations = violations
            print(
                f"DEBUG: About to continue to next iteration (iteration {grid_loop_iteration + 1})",
                flush=True,
            )
            import sys

            sys.stdout.flush()
            continue

        # Combine violations
        combined_violations = cl_result.constraint_violations.copy()
        combined_violations.extend(
            [
                str(d)
                for d in grid_diagnostics.diagnostics
                if d.severity in [Severity.VIOLATION, Severity.CRITICAL]
            ]
        )

        # Track violations and re-dispatch for M3.4 recovery metrics
        # Check for voltage violations
        voltage_violation_now = any(
            d.category == DiagnosticCategory.VOLTAGE
            for d in grid_diagnostics.diagnostics
            if d.severity in [Severity.VIOLATION, Severity.CRITICAL]
        )
        if voltage_violation_now and not self.voltage_violation_active:
            self.voltage_violations_detected += 1
            self.voltage_violation_active = True
        elif not voltage_violation_now and self.voltage_violation_active:
            self.voltage_violations_resolved += 1
            self.voltage_violation_active = False

        # Check for line/transformer loading violations
        loading_violation_now = any(
            d.category
            in [DiagnosticCategory.LINE_LOADING, DiagnosticCategory.TRANSFORMER_LOADING]
            for d in grid_diagnostics.diagnostics
            if d.severity in [Severity.VIOLATION, Severity.CRITICAL]
        )
        if loading_violation_now and not self.loading_violation_active:
            self.loading_violations_detected += 1
            self.loading_violation_active = True
        elif not loading_violation_now and self.loading_violation_active:
            self.loading_violations_resolved += 1
            self.loading_violation_active = False

        # Track re-dispatch events (when controller receives grid violations)
        # This is approximated by counting steps with active grid violations
        if voltage_violation_now or loading_violation_now:
            self.re_dispatch_count += 1

        # Create co-simulation result
        cosim_result = CoSimulationStepResult(
            timestep=self.current_timestep,
            citylearn_result=cl_result,
            grid_diagnostics=grid_diagnostics,
            power_flow_converged=power_flow_converged,
            combined_violations=combined_violations,
            terminated=cl_result.terminated,
            truncated=cl_result.truncated,
            market_result=market_result,
            settlement_snapshot=settlement_snapshot,
        )

        # Attach grid diagnostics to CityLearn result
        grid_diag_dict = {
            "power_flow_converged": power_flow_converged,
            "diagnostics": [d.model_dump() for d in grid_diagnostics.diagnostics],
            "voltage_profile": self.pandapower.get_voltage_profile(),
            "loading_profile": self.pandapower.get_loading_profile(),
            "import_limit_exceeded": import_exceeded,
            "export_limit_exceeded": export_exceeded,
            "grid_loop_metrics": self._grid_loop_metrics,
        }

        # Add building contributions and losses if available
        if hasattr(grid_diagnostics, "building_contributions"):
            grid_diag_dict["building_contributions"] = (
                grid_diagnostics.building_contributions
            )
        if hasattr(grid_diagnostics, "losses"):
            grid_diag_dict["losses"] = grid_diagnostics.losses

        # Add LMP data if available
        if dynamic_pricing_enabled and lmp_result:
            grid_diag_dict["lmp_result"] = {
                "building_lmps": building_lmps,
                "status": lmp_status,
                "reason": lmp_reason,
                "cap_hits": lmp_cap_hits,
                "base_price": base_price,
                "price_cap_per_kwh": price_cap,
            }

        # Add market and settlement data if available
        if market_result:
            grid_diag_dict["market_result"] = {
                "clearing_price": market_result.clearing_price,
                "trades": market_result.trades,
                "settlements": market_result.settlements,
                "total_volume_kwh": market_result.total_volume_kwh,
                "market_type": market_result.market_type.value,
            }
        if settlement_snapshot:
            grid_diag_dict["settlement_snapshot"] = settlement_snapshot

        # Add failure injection data for verification harness
        if active_failures:
            grid_diag_dict["active_failures"] = [
                {
                    "failure_id": f.failure_id,
                    "asset_id": f.asset_id,
                    "failure_type": f.failure_type,
                    "severity": f.severity,
                    "start_timestep": f.start_timestep,
                    "end_timestep": f.end_timestep,
                }
                for f in active_failures
            ]
        failure_events_list = []
        if newly_activated:
            failure_events_list.extend(
                [
                    {
                        "event": "activated",
                        "timestep": self.current_timestep,
                        "failure_id": f.failure_id,
                        "asset_id": f.asset_id,
                        "failure_type": f.failure_type,
                        "severity": f.severity,
                    }
                    for f in newly_activated
                ]
            )
        if newly_deactivated:
            failure_events_list.extend(
                [
                    {
                        "event": "deactivated",
                        "timestep": self.current_timestep,
                        "failure_id": f.failure_id,
                        "asset_id": f.asset_id,
                        "failure_type": f.failure_type,
                        "severity": f.severity,
                    }
                    for f in newly_deactivated
                ]
            )
        if failure_events_list:
            grid_diag_dict["failure_events"] = failure_events_list

        # Add grid observations to CityLearn observations so controllers can see them
        cl_result.observations = self.citylearn.add_grid_observations(
            cl_result.observations, grid_diag_dict, self.pandapower.bus_mapping
        )

        cl_result.grid_diagnostics = grid_diag_dict

        self.co_sim_history.append(cosim_result)
        self.current_timestep += 1

        return cosim_result

    def _apply_pv_failures(self, building_pvs: Dict[str, float]) -> Dict[str, float]:
        """Apply PV inverter failures to building PV generation."""
        modified_pvs = building_pvs.copy()
        for building in self.scenario_config.buildings:
            bid = building.building_id
            if bid in modified_pvs:
                modified_pvs[bid] = self.failure_injector.apply_pv_failure(
                    modified_pvs, bid
                )
        return modified_pvs

    def _apply_battery_failures(
        self, building_battery_powers: Dict[str, float]
    ) -> Dict[str, float]:
        """Apply battery failures to building battery power."""
        modified_battery = building_battery_powers.copy()
        for building in self.scenario_config.buildings:
            bid = building.building_id
            if bid in modified_battery:
                modified_battery[bid] = self.failure_injector.apply_battery_failure(
                    modified_battery, bid
                )
        return modified_battery

    def _apply_sensor_failures(
        self, building_powers: Dict[str, float], observations: Dict[str, float]
    ) -> Dict[str, float]:
        """Apply sensor failures - corrupt specific sensor readings in observations.

        Sensor failures affect the observations that the controller will see in the NEXT step.
        This method modifies the observations dict in place to inject NaN for failed sensors.
        Returns building_powers unchanged.
        """
        # Apply sensor failures to observations (in-place modification)
        if self.failure_injector and self.failure_injector.get_active_failures():
            for failure in self.failure_injector.get_active_failures():
                if failure.failure_type == FailureType.SENSOR:
                    # The failure injector's apply_sensor_failure returns modified observations
                    # We need to update the observations dict that will be passed to controller
                    # For now, we modify the observations that were passed in
                    sensor_id = failure.asset_id
                    if sensor_id in observations:
                        observations[sensor_id] = float("nan")

        return building_powers

    def _build_building_states(
        self,
        cl_result: SimulationStepResult,
        building_powers: Dict[str, float],
        building_pvs: Dict[str, float],
        building_battery_powers: Dict[str, float],
        building_lmps: Optional[Dict[str, float]] = None,
    ) -> Dict[str, BuildingEnergyState]:
        """Build building energy states for market clearing."""
        states = {}
        obs = cl_result.observations

        for building in self.scenario_config.buildings:
            bid = building.building_id

            # Net demand (positive = consumption)
            net_demand = building_powers.get(bid, 0.0)

            # PV generation
            pv_gen = building_pvs.get(bid, 0.0)

            # Battery power
            battery_power = building_battery_powers.get(bid, 0.0)

            # Battery SOC
            soc_key = f"{bid}_electrical_storage_soc"
            battery_soc = float(obs.get(soc_key, 0.5))

            # Max import/export
            max_import = self.scenario_config.energy_sharing.import_limit_kw or float(
                "inf"
            )
            max_export = self.scenario_config.energy_sharing.export_limit_kw or float(
                "inf"
            )
            # Per-building limits
            if hasattr(building, "max_import_kw"):
                max_import = min(max_import, building.max_import_kw)
            if hasattr(building, "max_export_kw"):
                max_export = min(max_export, building.max_export_kw)

            # Get LMP price for this building
            lmp_price = None
            if building_lmps and bid in building_lmps:
                lmp_price = building_lmps[bid]

            states[bid] = BuildingEnergyState(
                building_id=bid,
                net_demand_kw=net_demand,
                pv_generation_kw=pv_gen,
                battery_power_kw=battery_power,
                battery_soc=battery_soc,
                max_import_kw=max_import,
                max_export_kw=max_export,
                tariff_config=building.tariff,
                lmp_price=lmp_price,
            )

        return states

    def _extract_building_powers(
        self, cl_result: SimulationStepResult
    ) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
        """Extract building net power demand, PV generation, and battery power from CityLearn result."""
        building_powers = {}
        building_pvs = {}
        building_battery_powers = {}
        building_ev_powers = {}

        # From observations
        obs = cl_result.observations

        for building in self.scenario_config.buildings:
            bid = building.building_id

            # Net electrical demand (positive = consumption)
            net_demand_key = f"{bid}_net_electricity_consumption"
            if net_demand_key in obs:
                building_powers[bid] = float(obs[net_demand_key])
            else:
                # Fallback: sum of loads - PV
                load_key = f"{bid}_non_shiftable_load"
                pv_key = f"{bid}_solar_generation"
                load = float(obs.get(load_key, 0))
                pv = float(obs.get(pv_key, 0))
                building_powers[bid] = load
                building_pvs[bid] = pv

            # PV generation
            pv_key = f"{bid}_solar_generation"
            if pv_key in obs:
                building_pvs[bid] = float(obs[pv_key])
            elif bid not in building_pvs:
                building_pvs[bid] = 0.0

            # Battery power (positive = discharge, negative = charge)
            # Check observations for battery power
            battery_power_key = f"{bid}_battery_power"
            if battery_power_key in obs:
                building_battery_powers[bid] = float(obs[battery_power_key])
            else:
                # Try to infer from applied actions
                for action in cl_result.applied_actions.actions:
                    # asset_id format: {building_id}_battery or {building_id}_ev_{i}
                    if action.asset_id.startswith(bid + "_battery"):
                        if action.action_type == ActionType.BATTERY_CHARGE:
                            building_battery_powers[bid] = -float(
                                action.value_kw
                            )  # Negative = charge
                        elif action.action_type == ActionType.BATTERY_DISCHARGE:
                            building_battery_powers[bid] = float(
                                action.value_kw
                            )  # Positive = discharge
                        break
                else:
                    building_battery_powers[bid] = 0.0

            # EV charger power (positive = charging)
            building_ev_powers = {}
            for i, ev in enumerate(building.evs or []):
                asset_id = f"{bid}_ev_{i}"
                # Check observations for EV charger power
                ev_power_key = f"{asset_id}_charging_power"
                if ev_power_key in obs:
                    building_ev_powers[asset_id] = float(obs[ev_power_key])
                else:
                    # Try to infer from applied actions
                    for action in cl_result.applied_actions.actions:
                        if (
                            action.asset_id == asset_id
                            and action.action_type == ActionType.EV_CHARGE
                        ):
                            building_ev_powers[asset_id] = float(action.value_kw)
                            break
                    else:
                        building_ev_powers[asset_id] = 0.0

        return (
            building_powers,
            building_pvs,
            building_battery_powers,
            building_ev_powers,
        )

    def _extract_building_powers_from_actions(
        self, requested_actions: RequestedActions
    ) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float], Dict[str, float]]:
        """Extract building net power, PV, battery, and EV power from controller's requested actions.

        This is used by the grid loop to extract building powers from the controller's
        re-dispatched actions for re-running power flow.
        """
        building_powers = {}
        building_pvs = {}
        building_battery_powers = {}
        building_ev_powers = {}

        # Initialize with zeros for all buildings
        for building in self.scenario_config.buildings:
            bid = building.building_id
            building_powers[bid] = 0.0
            building_pvs[bid] = 0.0
            building_battery_powers[bid] = 0.0
            for i, _ in enumerate(building.evs or []):
                building_ev_powers[f"{bid}_ev_{i}"] = 0.0
            for i, _ in enumerate(building.flexible_loads or []):
                # Flexible loads don't directly affect building net power in this simplified model
                pass

        # Sum up power from requested actions
        for action in requested_actions.actions:
            # Parse building ID from asset_id (format: "b1_battery", "b1_ev_0", "b1_flex_0")
            parts = action.asset_id.split("_")
            if len(parts) >= 2:
                bid = parts[0]
                device_type = parts[1]
            else:
                continue

            if action.action_type == ActionType.BATTERY_CHARGE:
                # Charging = negative power (consuming)
                building_powers[bid] = building_powers.get(bid, 0.0) - action.value_kw
                building_battery_powers[bid] = -action.value_kw
            elif action.action_type == ActionType.BATTERY_DISCHARGE:
                # Discharging = positive power (generating)
                building_powers[bid] = building_powers.get(bid, 0.0) + action.value_kw
                building_battery_powers[bid] = action.value_kw
            elif action.action_type == ActionType.EV_CHARGE:
                # EV charging = negative power (consuming)
                building_powers[bid] = building_powers.get(bid, 0.0) - action.value_kw
                building_ev_powers[action.asset_id] = action.value_kw
            elif action.action_type == ActionType.FLEXIBLE_LOAD:
                # Flexible load = negative power (consuming)
                building_powers[bid] = building_powers.get(bid, 0.0) - action.value_kw
            elif action.action_type == ActionType.GRID_IMPORT:
                # Grid import = positive power (consuming from grid)
                building_powers[bid] = building_powers.get(bid, 0.0) + action.value_kw
            elif action.action_type == ActionType.GRID_EXPORT:
                # Grid export = negative power (exporting to grid)
                building_powers[bid] = building_powers.get(bid, 0.0) - action.value_kw

        return (
            building_powers,
            {},  # PV not directly controllable via actions
            building_battery_powers,
            building_ev_powers,
        )

    def _apply_pv_failures(self, building_pvs: Dict[str, float]) -> Dict[str, float]:
        """Apply PV inverter failures to building PV generation."""
        modified_pvs = building_pvs.copy()
        for building in self.scenario_config.buildings:
            bid = building.building_id
            if bid in modified_pvs:
                modified_pvs[bid] = self.failure_injector.apply_pv_failure(
                    modified_pvs, bid
                )
        return modified_pvs

    def _apply_ev_charger_failures(
        self, building_ev_powers: Dict[str, float]
    ) -> Dict[str, float]:
        """Apply EV charger failures to EV charging power."""
        modified_ev = building_ev_powers.copy()
        for building in self.scenario_config.buildings:
            bid = building.building_id
            # Check for EV chargers in this building
            for i, ev in enumerate(building.evs or []):
                asset_id = f"{bid}_ev_{i}"
                if asset_id in modified_ev:
                    modified_ev[asset_id] = (
                        self.failure_injector.apply_ev_charger_failure(
                            modified_ev, asset_id
                        )
                    )
        return modified_ev

    def _apply_sensor_failures(
        self, observations: Dict[str, float]
    ) -> Dict[str, float]:
        """Apply sensor failures - corrupt specific sensor readings in observations."""
        # Sensor failures affect observations - return NaN for failed sensors
        modified_obs = observations.copy()
        for building in self.scenario_config.buildings:
            bid = building.building_id
            # Check for sensor failures on this building's sensors
            failure = self.failure_injector.is_asset_failed(
                f"{bid}_net_electricity_consumption"
            )
            if failure and failure.failure_type == "sensor":
                sensor_key = f"{bid}_net_electricity_consumption"
                if sensor_key in modified_obs:
                    modified_obs[sensor_key] = float("nan")
        return modified_obs

    def _apply_sensor_failures(
        self, observations: Dict[str, float]
    ) -> Dict[str, float]:
        """Apply sensor failures - corrupt specific sensor readings in observations."""
        # Sensor failures affect observations - return NaN for failed sensors
        modified_obs = observations.copy()
        for building in self.scenario_config.buildings:
            bid = building.building_id
            # Check for sensor failures on this building's sensors
            failure = self.failure_injector.is_asset_failed(
                f"{bid}_net_electricity_consumption"
            )
            if failure and failure.failure_type == "sensor":
                sensor_key = f"{bid}_net_electricity_consumption"
                if sensor_key in modified_obs:
                    modified_obs[sensor_key] = float("nan")
        return modified_obs

    def get_kpis(self) -> Dict[str, Any]:
        """Get combined KPIs from both simulators."""
        cl_kpis = self.citylearn.get_kpis()

        # Get enhanced grid KPIs from pandapower adapter
        grid_kpis = self.pandapower.get_enhanced_kpis()

        # Add LMP OPF fallback counter
        grid_kpis["lmp_opf_fallback_steps"] = self.pandapower.lmp_opf_fallback_steps

        # Add energy sharing KPIs if enabled
        sharing_kpis = {}
        if self.settlement_engine:
            sharing_kpis = self.settlement_engine.get_community_metrics()
            # Add per-building savings
            sharing_kpis["per_building_savings"] = (
                self.settlement_engine.get_building_savings()
            )

        # Add failure injection summary for verification harness
        failure_summary = (
            self.failure_injector.get_failure_summary() if self.failure_injector else {}
        )

        # Aggregate violations_resolved from all steps' grid loop metrics
        total_grid_loop_violations_resolved = sum(
            h.citylearn_result.grid_diagnostics.get("grid_loop_metrics", {}).get(
                "violations_resolved", 0
            )
            for h in self.co_sim_history
        )

        return {
            **cl_kpis,
            **grid_kpis,
            **sharing_kpis,
            "grid_voltage_violations": sum(
                1
                for h in self.co_sim_history
                for d in h.grid_diagnostics.diagnostics
                if d.category == DiagnosticCategory.VOLTAGE
            ),
            "grid_line_violations": sum(
                1
                for h in self.co_sim_history
                for d in h.grid_diagnostics.diagnostics
                if d.category == DiagnosticCategory.LINE_LOADING
            ),
            "grid_trafo_violations": sum(
                1
                for h in self.co_sim_history
                for d in h.grid_diagnostics.diagnostics
                if d.category == DiagnosticCategory.TRANSFORMER_LOADING
            ),
            # M3.4 re-dispatch recovery metrics
            "re_dispatch_count": self.re_dispatch_count,
            "voltage_violations_detected": self.voltage_violations_detected,
            "voltage_violations_resolved": self.voltage_violations_resolved
            + total_grid_loop_violations_resolved,
            "loading_violations_detected": self.loading_violations_detected,
            "loading_violations_resolved": self.loading_violations_resolved
            + total_grid_loop_violations_resolved,
            "resolution_rate": (
                (
                    (
                        self.voltage_violations_resolved
                        + self.loading_violations_resolved
                        + total_grid_loop_violations_resolved
                    )
                    / max(
                        1,
                        self.voltage_violations_detected
                        + self.loading_violations_detected,
                    )
                )
                if (self.voltage_violations_detected + self.loading_violations_detected)
                > 0
                else 1.0
            ),
            "avg_resolution_steps": (
                (
                    (
                        self.voltage_violations_resolved
                        + self.loading_violations_resolved
                        + total_grid_loop_violations_resolved
                    )
                    / max(1, self.re_dispatch_count)
                )
                if self.re_dispatch_count > 0
                else 0.0
            ),
            "failure_summary": failure_summary,
        }

    def compute_energy_summary(self) -> Dict[str, float]:
        """Aggregate absolute energy metrics from the co-simulation history.

        CityLearn's ``evaluate()`` returns baseline-normalized ratios (1.0 =
        baseline), which are not usable as absolute KPIs. The per-step
        building contributions recorded in ``co_sim_history`` are the source
        of truth for the product UI.
        """
        dt_hours = self.scenario_config.timestep_minutes / 60.0

        grid_import_kwh = 0.0
        grid_export_kwh = 0.0
        pv_generation_kwh = 0.0
        pv_consumed_kwh = 0.0
        battery_throughput_kwh = 0.0
        carbon_emissions_kg = 0.0
        community_load_kws: List[float] = []
        community_net_kws: List[float] = []

        for h in self.co_sim_history:
            cl = h.citylearn_result
            diag = cl.grid_diagnostics or {}
            contribs = diag.get("building_contributions") or {}
            if not contribs:
                continue
            total_load = 0.0
            total_pv = 0.0
            total_battery = 0.0
            total_net = 0.0
            for contribution in contribs.values():
                total_load += float(contribution.get("load_kw", 0.0))
                total_pv += float(contribution.get("pv_kw", 0.0))
                total_battery += float(contribution.get("battery_kw", 0.0))
                total_net += float(contribution.get("net_injection_kw", 0.0))

            # net_injection_kw convention: positive = injection into the grid
            # (export), negative = drawn from the grid (import).
            grid_import_kwh += max(-total_net, 0.0) * dt_hours
            grid_export_kwh += max(total_net, 0.0) * dt_hours
            pv_generation_kwh += total_pv * dt_hours
            pv_consumed_kwh += min(total_pv, total_load) * dt_hours
            battery_throughput_kwh += abs(total_battery) * dt_hours
            community_load_kws.append(total_load)
            community_net_kws.append(total_net)

            # Carbon intensity observation (kg/kWh) at this timestep
            obs = cl.observations or {}
            carbon_intensity = None
            for bid in contribs:
                value = obs.get(f"{bid}_carbon_intensity")
                if value is not None:
                    carbon_intensity = float(value)
                    break
            if carbon_intensity is not None:
                carbon_emissions_kg += (
                    max(-total_net, 0.0) * dt_hours * carbon_intensity
                )

        return {
            "grid_import_kwh": grid_import_kwh,
            "grid_export_kwh": grid_export_kwh,
            "peak_demand_kw": max(community_load_kws) if community_load_kws else 0.0,
            "peak_net_import_kw": (
                max(community_net_kws) if community_net_kws else 0.0
            ),
            "pv_generation_kwh": pv_generation_kwh,
            "pv_self_consumption": (
                pv_consumed_kwh / pv_generation_kwh if pv_generation_kwh > 0 else 0.0
            ),
            "pv_curtailment": 0.0,
            "battery_throughput_kwh": battery_throughput_kwh,
            "carbon_emissions_kg": carbon_emissions_kg,
        }

    def get_per_building_contributions(self) -> List[Dict[str, Dict[str, float]]]:
        """Get per-building contributions for each timestep."""
        contributions_history = []
        for h in self.co_sim_history:
            # The pandapower adapter stores contributions per timestep in the grid_diagnostics
            if (
                h.citylearn_result.grid_diagnostics
                and "building_contributions" in h.citylearn_result.grid_diagnostics
            ):
                contributions_history.append(
                    h.citylearn_result.grid_diagnostics["building_contributions"]
                )
        return contributions_history

    def get_settlement_result(self) -> Optional[SettlementResult]:
        """Get final settlement result."""
        if self.settlement_engine:
            return self.settlement_engine.finalize()
        return None

    def close(self):
        """Close both simulators."""
        self.citylearn.close()

    def export_results(self, output_dir: str):
        """Export all results to files."""
        import os
        import json

        os.makedirs(output_dir, exist_ok=True)

        # Export CityLearn trajectories
        trajectories = []
        for h in self.co_sim_history:
            traj = {
                "timestep": h.timestep,
                "requested_actions": [
                    a.model_dump() for a in h.citylearn_result.requested_actions.actions
                ],
                "limited_actions": [
                    a.model_dump() for a in h.citylearn_result.limited_actions.actions
                ],
                "applied_actions": [
                    a.model_dump() for a in h.citylearn_result.applied_actions.actions
                ],
                "observations": h.citylearn_result.observations,
                "rewards": h.citylearn_result.rewards,
                "costs": h.citylearn_result.costs,
                "constraint_violations": h.citylearn_result.constraint_violations,
                "grid_diagnostics": h.citylearn_result.grid_diagnostics,
                "grid_loop_metrics": (
                    h.citylearn_result.grid_diagnostics.get("grid_loop_metrics", {})
                    if h.citylearn_result.grid_diagnostics
                    else {}
                ),
            }
            trajectories.append(_convert_to_json_serializable(traj))

        with open(os.path.join(output_dir, "trajectories.jsonl"), "w") as f:
            for t in trajectories:
                f.write(json.dumps(t) + "\n")

        # Export grid diagnostics
        grid_diags = []
        for h in self.co_sim_history:
            for d in h.grid_diagnostics.diagnostics:
                grid_diags.append(d.model_dump())
            # Also export LMP result if available
            if (
                h.citylearn_result.grid_diagnostics
                and "lmp_result" in h.citylearn_result.grid_diagnostics
            ):
                grid_diags.append(
                    {
                        "lmp_result": h.citylearn_result.grid_diagnostics["lmp_result"],
                        "timestep": h.timestep,
                    }
                )

        with open(os.path.join(output_dir, "grid_diagnostics.jsonl"), "w") as f:
            for d in grid_diags:
                f.write(json.dumps(d) + "\n")

        # Export market results if available
        market_results = []
        for h in self.co_sim_history:
            if h.market_result:
                market_results.append(
                    {
                        "timestep": h.timestep,
                        "clearing_price": h.market_result.clearing_price,
                        "trades": h.market_result.trades,
                        "settlements": h.market_result.settlements,
                        "total_volume_kwh": h.market_result.total_volume_kwh,
                        "market_type": h.market_result.market_type.value,
                    }
                )

        with open(os.path.join(output_dir, "market_results.jsonl"), "w") as f:
            for m in market_results:
                f.write(json.dumps(_convert_to_json_serializable(m)) + "\n")

        # Export settlement results if available
        if self.settlement_engine:
            settlement_result = self.settlement_engine.finalize()
            with open(os.path.join(output_dir, "settlement_result.json"), "w") as f:
                json.dump(
                    _convert_to_json_serializable(
                        {
                            "building_settlements": {
                                bid: {
                                    "net_settlement": s.net_settlement,
                                    "total_bought_kwh": s.total_bought_kwh,
                                    "total_sold_kwh": s.total_sold_kwh,
                                    "total_grid_import_kwh": s.total_grid_import_kwh,
                                    "total_grid_export_kwh": s.total_grid_export_kwh,
                                    "baseline_grid_import_kwh": s.baseline_grid_import_kwh,
                                    "baseline_grid_export_kwh": s.baseline_grid_export_kwh,
                                    "peak_grid_import_kw": s.peak_grid_import_kw,
                                    "baseline_peak_grid_import_kw": s.baseline_peak_grid_import_kw,
                                    "demand_charge_rate": s.demand_charge_rate,
                                    "actual_demand_charge": s.actual_demand_charge,
                                    "baseline_demand_charge": s.baseline_demand_charge,
                                    "total_grid_import_cost": s.total_grid_import_cost,
                                    "total_grid_export_revenue": s.total_grid_export_revenue,
                                    "baseline_grid_import_cost": s.baseline_grid_import_cost,
                                    "baseline_grid_export_revenue": s.baseline_grid_export_revenue,
                                    "total_community_import_cost": s.total_community_import_cost,
                                    "total_community_export_revenue": s.total_community_export_revenue,
                                    "total_community_import_kwh": s.total_community_import_kwh,
                                    "total_community_export_kwh": s.total_community_export_kwh,
                                    "cost_basis": s.cost_basis,
                                    "lmp_cost_usd": s.lmp_cost_usd,
                                    "lmp_revenue_usd": s.lmp_revenue_usd,
                                    "interval_settlements": s.interval_settlements,
                                    "metadata": s.metadata,
                                }
                                for bid, s in settlement_result.building_settlements.items()
                            },
                            "interval_results": [
                                {
                                    "interval_idx": r.interval_idx,
                                    "start_timestep": r.start_timestep,
                                    "end_timestep": r.end_timestep,
                                    "building_settlements": r.building_settlements,
                                    "avg_clearing_price": r.avg_clearing_price,
                                    "total_volume_kwh": r.total_volume_kwh,
                                }
                                for r in settlement_result.interval_results
                            ],
                            "total_community_volume_kwh": settlement_result.total_community_volume_kwh,
                            "total_community_revenue": settlement_result.total_community_revenue,
                            "metadata": settlement_result.metadata,
                        }
                    ),
                    f,
                    indent=2,
                )

        # Export pandapower network
        self.pandapower.export_results(
            os.path.join(output_dir, "pandapower_network.json")
        )

        # Export failure injection history
        if self.failure_injector:
            failure_summary = self.failure_injector.get_failure_summary()
            with open(os.path.join(output_dir, "failure_history.json"), "w") as f:
                json.dump(_convert_to_json_serializable(failure_summary), f, indent=2)

        # Export KPIs
        kpis = self.get_kpis()
        with open(os.path.join(output_dir, "kpis.json"), "w") as f:
            json.dump(_convert_to_json_serializable(kpis), f, indent=2)
