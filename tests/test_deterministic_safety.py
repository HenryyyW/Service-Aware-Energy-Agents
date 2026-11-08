"""Tests for DeterministicSafetyController."""

import pytest
from unittest.mock import MagicMock, patch

from src.controllers.deterministic_safety import DeterministicSafetyController
from src.controllers import RuleBasedController
from src.schemas.scenario import (
    ScenarioConfig,
    BuildingConfig,
    BatteryConfig,
    EVConfig,
    EnergySharingConfig,
)
from src.schemas.action import (
    Action,
    ActionType,
    RequestedActions,
    LimitedActions,
    AppliedActions,
)


@pytest.fixture
def scenario_config():
    """Minimal scenario config for testing."""
    return ScenarioConfig(
        name="test_safety",
        description="test",
        scenario_id="test_safety",
        random_seed=42,
        timestep_minutes=60,
        energy_sharing=EnergySharingConfig(),
        buildings=[
            BuildingConfig(
                building_id="Building_1",
                simulation_start="2023-07-01T00:00:00",
                simulation_end="2023-07-02T00:00:00",
                battery=BatteryConfig(
                    capacity_kwh=100,
                    power_kw=50,
                    efficiency_charge=0.95,
                    efficiency_discharge=0.95,
                    initial_soc=0.5,
                    soc_min=0.1,
                    soc_max=0.9,
                ),
                evs=[
                    EVConfig(
                        capacity_kwh=40,
                        max_charge_kw=7.2,
                        efficiency=0.95,
                        arrival_time="18:00",
                        departure_time="07:00",
                        initial_soc=0.2,
                        target_soc=0.8,
                        connected_days=[0, 1, 2, 3, 4, 5, 6],
                    )
                ],
                flexible_loads=[],
            )
        ],
    )


@pytest.fixture
def device_metadata():
    """Live device metadata matching the scenario."""
    return {
        "Building_1": {
            "battery": {"capacity_kwh": 100.0, "power_kw": 50.0, "efficiency": 0.95},
            "chargers": [
                {
                    "charger_id": "charger_0",
                    "max_charge_kw": 7.2,
                    "min_charge_kw": 0.0,
                    "max_discharge_kw": 0.0,
                    "efficiency": 0.95,
                }
            ],
            "deferrable": [],
            "pv_kw": 12.0,
            "hours_per_step": 1.0,
        }
    }


class TestDeterministicSafetyController:
    """Test the deterministic safety baseline controller."""

    def test_clamping_to_device_bounds_on_known_violations(
        self, scenario_config, device_metadata
    ):
        """Test clamping with exact expected values per asset."""
        # Create proposer that emits known out-of-bounds values
        mock_proposer = MagicMock()
        mock_proposer.get_actions.return_value = RequestedActions(
            timestep=0,
            actions=[
                Action(
                    asset_id="Building_1_battery",
                    action_type=ActionType.BATTERY_CHARGE,
                    value_kw=100.0,  # Exceeds 50kW limit
                    timestep=0,
                ),
                Action(
                    asset_id="Building_1_ev_0",
                    action_type=ActionType.EV_CHARGE,
                    value_kw=15.0,  # Exceeds 7.2kW limit
                    timestep=0,
                ),
                Action(
                    asset_id="Building_1_battery",
                    action_type=ActionType.BATTERY_DISCHARGE,
                    value_kw=-80.0,  # Exceeds -50kW limit (discharge)
                    timestep=0,
                ),
            ],
        )

        controller = DeterministicSafetyController(
            scenario_config, proposer=mock_proposer, device_metadata=device_metadata
        )

        requested = controller.get_actions({}, 0)

        # Verify clamping to exact device bounds
        battery_charge = next(
            a
            for a in requested.actions
            if a.asset_id == "Building_1_battery" and a.value_kw > 0
        )
        ev_charge = next(
            a for a in requested.actions if a.asset_id == "Building_1_ev_0"
        )
        battery_discharge = next(
            a
            for a in requested.actions
            if a.asset_id == "Building_1_battery" and a.value_kw < 0
        )

        assert battery_charge.value_kw == 50.0, "Battery charge clamped to 50kW limit"
        assert ev_charge.value_kw == 7.2, "EV charge clamped to 7.2kW limit"
        assert (
            battery_discharge.value_kw == -50.0
        ), "Battery discharge clamped to -50kW limit"

        # Verify Level 1 counter: 3 raw violations (one per action)
        summary = controller.get_stratification_summary()
        assert summary["level1_raw_proposal_violations"]["total"] == 3

        # Verify Level 2 counter: 3 accepted (after clamping)
        assert summary["level2_accepted_by_agent"]["total"] == 3

    def test_five_level_counters_increment_on_scripted_episode(
        self, scenario_config, device_metadata
    ):
        """Test all 5 stratification levels on a simulated episode."""
        # Create proposer that emits alternating in-bounds and out-of-bounds
        call_count = 0

        def proposer_get_actions(obs, timestep):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 1:
                # Odd steps: out-of-bounds
                actions = [
                    Action(
                        asset_id="Building_1_battery",
                        action_type=ActionType.BATTERY_CHARGE,
                        value_kw=75.0,  # Exceeds 50kW
                        timestep=timestep,
                    )
                ]
            else:
                # Even steps: in-bounds
                actions = [
                    Action(
                        asset_id="Building_1_battery",
                        action_type=ActionType.BATTERY_CHARGE,
                        value_kw=25.0,  # Within 50kW
                        timestep=timestep,
                    )
                ]
            return RequestedActions(timestep=timestep, actions=actions)

        mock_proposer = MagicMock()
        mock_proposer.get_actions.side_effect = proposer_get_actions

        controller = DeterministicSafetyController(
            scenario_config, proposer=mock_proposer, device_metadata=device_metadata
        )

        # Simulate 4 steps
        for step in range(4):
            requested = controller.get_actions({}, step)

            # Simulate adapter clamping (in this case, no additional clamping needed since we already clamped)
            limited = LimitedActions(
                timestep=step,
                actions=[
                    Action(
                        asset_id=a.asset_id,
                        action_type=a.action_type,
                        value_kw=a.value_kw,
                        timestep=step,
                    )
                    for a in requested.actions
                ],
            )
            applied = AppliedActions(
                timestep=step,
                actions=[
                    Action(
                        asset_id=a.asset_id,
                        action_type=a.action_type,
                        value_kw=a.value_kw,
                        timestep=step,
                    )
                    for a in requested.actions
                ],
            )

            controller.record_adapter_interventions(requested, limited, applied)
            controller.record_post_execution_violations(
                {"diagnostics": []}, {}  # No grid violations  # No observations
            )

        summary = controller.get_stratification_summary()

        # Level 1: 2 out-of-bounds steps * 1 violation each = 2
        assert summary["level1_raw_proposal_violations"]["total"] == 2

        # Level 2: 4 steps * 1 action each = 4 accepted
        assert summary["level2_accepted_by_agent"]["total"] == 4

        # Level 3: 0 adapter interventions (we already clamped)
        assert summary["level3_adapter_interventions"]["total"] == 0

        # Level 4: 0 final violations (all within bounds)
        assert summary["level4_final_applied_violations"]["total"] == 0

        # Level 5: 0 post-execution violations
        assert summary["level5_post_execution_violations"]["total"] == 0

        # Verify history has 4 entries
        history = controller.get_stratification_history()
        assert len(history) == 4

    def test_proposer_passthrough_when_in_bounds_identity(
        self, scenario_config, device_metadata
    ):
        """Test identity passthrough when proposer is already in bounds."""
        mock_proposer = MagicMock()
        mock_proposer.get_actions.return_value = RequestedActions(
            timestep=0,
            actions=[
                Action(
                    asset_id="Building_1_battery",
                    action_type=ActionType.BATTERY_CHARGE,
                    value_kw=25.0,  # Well within 50kW limit
                    timestep=0,
                ),
                Action(
                    asset_id="Building_1_ev_0",
                    action_type=ActionType.EV_CHARGE,
                    value_kw=3.6,  # Well within 7.2kW limit
                    timestep=0,
                ),
            ],
        )

        controller = DeterministicSafetyController(
            scenario_config, proposer=mock_proposer, device_metadata=device_metadata
        )

        requested = controller.get_actions({}, 0)

        # Values should be unchanged (identity)
        battery_action = next(
            a for a in requested.actions if a.asset_id == "Building_1_battery"
        )
        ev_action = next(
            a for a in requested.actions if a.asset_id == "Building_1_ev_0"
        )

        assert battery_action.value_kw == 25.0
        assert ev_action.value_kw == 3.6

        # Level 1: 0 violations
        summary = controller.get_stratification_summary()
        assert summary["level1_raw_proposal_violations"]["total"] == 0

        # Level 2: 2 accepted (no clamping needed)
        assert summary["level2_accepted_by_agent"]["total"] == 2

    def test_no_llm_network_client_construction(self, scenario_config, device_metadata):
        """Assert no LLM network/client construction in the safety path."""
        # The controller should work without any LLM backend
        controller = DeterministicSafetyController(
            scenario_config, proposer=None, device_metadata=device_metadata
        )

        # No proposer means empty actions - no network calls
        requested = controller.get_actions({}, 0)
        assert len(requested.actions) == 0

        # Verify no LLM-related attributes exist
        assert not hasattr(controller, "_backend")
        assert not hasattr(controller, "llm_config")
        assert not hasattr(controller, "llm_calls")

        # Proposer can be set later
        mock_proposer = MagicMock()
        mock_proposer.get_actions.return_value = RequestedActions(
            timestep=1, actions=[]
        )
        controller.set_proposer(mock_proposer)
        requested = controller.get_actions({}, 1)
        mock_proposer.get_actions.assert_called_once_with({}, 1)

    def test_adapter_intervention_recording(self, scenario_config, device_metadata):
        """Test Level 3 adapter intervention recording when adapter clamps further."""
        mock_proposer = MagicMock()
        mock_proposer.get_actions.return_value = RequestedActions(
            timestep=0,
            actions=[
                Action(
                    asset_id="Building_1_battery",
                    action_type=ActionType.BATTERY_CHARGE,
                    value_kw=100.0,  # Exceeds 50kW
                    timestep=0,
                ),
            ],
        )

        controller = DeterministicSafetyController(
            scenario_config, proposer=mock_proposer, device_metadata=device_metadata
        )

        requested = controller.get_actions({}, 0)

        # Simulate adapter doing ADDITIONAL clamping (e.g., different limits)
        limited = LimitedActions(
            timestep=0,
            actions=[
                Action(
                    asset_id="Building_1_battery",
                    action_type=ActionType.BATTERY_CHARGE,
                    value_kw=40.0,  # Adapter clamped to 40kW (more restrictive)
                    timestep=0,
                ),
            ],
            limit_reasons={"Building_1_battery": "adapter_softer_limit"},
        )
        applied = AppliedActions(
            timestep=0,
            actions=[
                Action(
                    asset_id="Building_1_battery",
                    action_type=ActionType.BATTERY_CHARGE,
                    value_kw=40.0,
                    timestep=0,
                ),
            ],
        )

        controller.record_adapter_interventions(requested, limited, applied)

        summary = controller.get_stratification_summary()
        # Level 3 should record 1 intervention
        assert summary["level3_adapter_interventions"]["total"] == 1
        assert (
            summary["level3_adapter_interventions"]["by_asset"]["Building_1_battery"]
            == 1
        )

    def test_final_applied_violations_detection(self, scenario_config, device_metadata):
        """Test Level 4 detection of final applied violations."""
        mock_proposer = MagicMock()
        mock_proposer.get_actions.return_value = RequestedActions(
            timestep=0,
            actions=[
                Action(
                    asset_id="Building_1_battery",
                    action_type=ActionType.BATTERY_CHARGE,
                    value_kw=25.0,  # In bounds
                    timestep=0,
                ),
            ],
        )

        controller = DeterministicSafetyController(
            scenario_config, proposer=mock_proposer, device_metadata=device_metadata
        )

        requested = controller.get_actions({}, 0)

        # Simulate applied actions that VIOLATE bounds (buggy adapter)
        limited = LimitedActions(
            timestep=0,
            actions=[
                Action(
                    asset_id="Building_1_battery",
                    action_type=ActionType.BATTERY_CHARGE,
                    value_kw=25.0,
                    timestep=0,
                ),
            ],
        )
        applied = AppliedActions(
            timestep=0,
            actions=[
                Action(
                    asset_id="Building_1_battery",
                    action_type=ActionType.BATTERY_CHARGE,
                    value_kw=75.0,  # VIOLATION: exceeds 50kW limit!
                    timestep=0,
                ),
            ],
        )

        controller.record_adapter_interventions(requested, limited, applied)

        summary = controller.get_stratification_summary()
        # Level 4 should detect 1 final violation
        assert summary["level4_final_applied_violations"]["total"] == 1
        assert (
            summary["level4_final_applied_violations"]["by_asset"]["Building_1_battery"]
            == 1
        )

    def test_post_execution_grid_violations(self, scenario_config, device_metadata):
        """Test Level 5 post-execution grid violation recording."""
        mock_proposer = MagicMock()
        mock_proposer.get_actions.return_value = RequestedActions(
            timestep=0, actions=[]
        )

        controller = DeterministicSafetyController(
            scenario_config, proposer=mock_proposer, device_metadata=device_metadata
        )

        requested = controller.get_actions({}, 0)

        # Grid diagnostics with violations
        grid_diagnostics = {
            "diagnostics": [
                {
                    "category": "voltage",
                    "severity": "violation",
                    "location": "Bus_1",
                    "values": {"voltage_pu": 1.08},
                },
                {
                    "category": "line_loading",
                    "severity": "critical",
                    "location": "Line_1-2",
                    "values": {"line_loading_pct": 110},
                },
            ]
        }

        controller.record_post_execution_violations(grid_diagnostics, {})

        summary = controller.get_stratification_summary()
        # Level 5 should record 2 grid violations
        assert summary["level5_post_execution_violations"]["total"] == 2
        assert "Bus_1" in summary["level5_post_execution_violations"]["by_asset"]
        assert "Line_1-2" in summary["level5_post_execution_violations"]["by_asset"]

    def test_post_execution_ev_deadline_violations(
        self, scenario_config, device_metadata
    ):
        """Test Level 5 EV deadline violation recording from observations."""
        mock_proposer = MagicMock()
        mock_proposer.get_actions.return_value = RequestedActions(
            timestep=0, actions=[]
        )

        controller = DeterministicSafetyController(
            scenario_config, proposer=mock_proposer, device_metadata=device_metadata
        )

        requested = controller.get_actions({}, 0)

        # Observations with EV about to depart but below target SOC
        observations = {
            "Building_1_ev_0_connected": 1.0,
            "Building_1_ev_0_hours_to_departure": 0.5,  # 30 min left
            "Building_1_ev_0_required_soc": 0.8,  # Target 80%
            "Building_1_ev_0_soc": 0.5,  # Only at 50% - below target
        }

        controller.record_post_execution_violations({}, observations)

        summary = controller.get_stratification_summary()
        # Level 5 should record 1 service violation (EV deadline)
        assert summary["level5_post_execution_violations"]["total"] == 1
        assert (
            "Building_1_ev_0_deadline"
            in summary["level5_post_execution_violations"]["by_asset"]
        )
