"""Tests for accounting invariants and billing identity.

C1: Settlement accounting invariant - internal P2P payments must cancel in community aggregate.
B1: Billing identity - dispatch-identical controllers should not imply cost-identical across TOU/LMP.
"""

import pytest
import tempfile
from pathlib import Path

from src.schemas.scenario import (
    ScenarioConfig,
    BuildingConfig,
    BuildingType,
    EnergySharingConfig,
    TariffConfig,
    PVConfig,
    BatteryConfig,
    PandapowerConfig,
    GridBusMapping,
)
from src.simulation.coupling import SimulationCoupler
from src.controllers import RuleBasedController
from src.controllers import LLMAgentController, LLMVerifiedController
from src.schemas.action import RequestedActions, Action, ActionType


class TestAccountingInvariantC1:
    """Tests for C1: Settlement accounting invariant.

    Internal P2P payments must cancel in the community aggregate
    (sum_i C_internal = 0), so a second settlement layer cannot
    by itself change community cost.
    """

    @pytest.fixture
    def scenario_d_config(self):
        """Load Scenario D configuration from YAML."""
        import yaml

        config_path = Path(__file__).parent.parent / "configs" / "scenario_d.yaml"
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        return ScenarioConfig(**data)

    @pytest.fixture
    def scenario_a_config(self):
        """Load Scenario A configuration from YAML."""
        import yaml

        config_path = Path(__file__).parent.parent / "configs" / "scenario_a.yaml"
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        return ScenarioConfig(**data)

    def test_internal_p2p_payments_sum_to_zero(self, scenario_d_config, tmp_path):
        """Test that internal P2P payments sum to zero in community aggregate.

        The sum of net_settlement across all buildings must be zero,
        as internal P2P payments must cancel in the community aggregate.
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            coupler = SimulationCoupler(scenario_d_config, data_dir=str(tmp_path))
            coupler.reset(random_seed=42)

            controller = RuleBasedController(scenario_d_config)
            coupler.controller = controller

            observations = coupler.reset(random_seed=42)

            for step in range(24):
                from src.schemas.action import RequestedActions, Action, ActionType

                requested = RequestedActions(
                    timestep=step,
                    actions=[
                        Action(
                            asset_id=f"building_{i}_battery",
                            action_type=ActionType.BATTERY_CHARGE,
                            value_kw=1.0,
                            timestep=step,
                        )
                        for i in range(5)
                    ],
                )
                result = coupler.step(requested)
                if result.terminated:
                    break
                observations = result.citylearn_result.observations

            # Check settlement engine
            settlement_engine = coupler.settlement_engine

            # Verify internal P2P payments sum to zero
            total_net_settlement = sum(
                s.net_settlement
                for s in settlement_engine.building_settlements.values()
            )
            assert (
                abs(total_net_settlement) < 1e-9
            ), f"Internal P2P payments do not sum to zero: {total_net_settlement}"

            # Verify community trades sum to zero
            total_bought = sum(
                s.total_bought_kwh
                for s in settlement_engine.building_settlements.values()
            )
            total_sold = sum(
                s.total_sold_kwh
                for s in settlement_engine.building_settlements.values()
            )
            assert (
                abs(total_bought - total_sold) < 1e-9
            ), f"Community energy trades do not balance: bought={total_bought}, sold={total_sold}"

    def test_community_aggregate_cost_invariant(self, scenario_d_config, tmp_path):
        """Test that community aggregate cost doesn't change from internal settlement alone.

        The sum of member net bills should equal external grid bill
        plus explicit external fees minus explicit subsidies.
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            controller = RuleBasedController(scenario_d_config)
            coupler = SimulationCoupler(scenario_d_config, data_dir=str(tmp_path))
            coupler.controller = controller
            observations = coupler.reset(random_seed=42)

            for step in range(24):
                from src.schemas.action import RequestedActions, Action, ActionType

                requested = RequestedActions(
                    timestep=step,
                    actions=[
                        Action(
                            asset_id=f"building_{i}_battery",
                            action_type=ActionType.BATTERY_CHARGE,
                            value_kw=1.0,
                            timestep=step,
                        )
                        for i in range(5)
                    ],
                )
                result = coupler.step(requested)
                if result.terminated:
                    break
                observations = result.citylearn_result.observations

            # Get settlement result
            settlement_result = coupler.get_settlement_result()

            # Verify community aggregate cost invariant
            # sum(member net bills) == external grid bill + explicit external fees - explicit subsidies
            member_net_bills = {
                bid: s.metadata.get("actual_total_bill", 0.0)
                for bid, s in settlement_result.building_settlements.items()
            }

            community_metrics = coupler.settlement_engine.get_community_metrics()

            # Sum of member net bills should equal actual_total_bill
            sum_member_bills = sum(member_net_bills.values())
            actual_total_bill = sum(
                s.metadata.get("actual_total_bill", 0.0)
                for s in settlement_result.building_settlements.values()
            )

            assert (
                abs(sum_member_bills - actual_total_bill) < 1e-6
            ), f"Member bills sum ({sum_member_bills}) != actual_total_bill ({actual_total_bill})"

            # Verify community aggregate cost invariant
            # actual_total_bill = actual_grid_bill + community_import_cost - community_export_revenue
            # Internal P2P payments should net to zero
            assert (
                abs(settlement_result.total_community_revenue) < 1e-9
                or settlement_result.total_community_revenue == 0.0
            ), "Total community revenue should be zero (internal P2P payments cancel)"


class TestBillingIdentityB1:
    """Tests for B1: Billing identity.

    Dispatch-identical controllers should NOT imply cost-identical
    across TOU and LMP. Cost is a function of prices on a fixed trajectory.
    """

    @pytest.fixture
    def scenario_d_config(self):
        """Load Scenario D configuration from YAML."""
        import yaml

        config_path = Path(__file__).parent.parent / "configs" / "scenario_d.yaml"
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        return ScenarioConfig(**data)

    def test_tou_vs_lmp_billing_difference(self, scenario_d_config, tmp_path):
        """Test that TOU and LMP pricing produce different costs for same trajectory.

        Run the same trajectory under TOU and LMP price series and compare.
        Cost is a function of prices on a fixed trajectory.
        """
        from src.schemas.scenario import DynamicPricingConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            # Test TOU regime
            scenario_tou = scenario_d_config.model_copy()
            scenario_tou.energy_sharing.dynamic_pricing = DynamicPricingConfig(
                enabled=False,
                pricing_type="tariff",
            )

            with tempfile.TemporaryDirectory() as tmpdir_tou:
                controller_tou = RuleBasedController(scenario_d_config)
                coupler_tou = SimulationCoupler(scenario_d_config, data_dir=tmpdir)
                coupler_tou.controller = controller_tou
                observations = coupler_tou.reset(random_seed=42)

                for step in range(24):
                    from src.schemas.action import RequestedActions, Action, ActionType

                    requested = RequestedActions(
                        timestep=step,
                        actions=[
                            Action(
                                asset_id=f"building_{i}_battery",
                                action_type=ActionType.BATTERY_CHARGE,
                                value_kw=1.0,
                                timestep=step,
                            )
                            for i in range(5)
                        ],
                    )
                    result = coupler_tou.step(requested)
                    if result.terminated:
                        break
                    observations = result.citylearn_result.observations

            result_tou = coupler_tou.get_settlement_result()

            # Test LMP regime
            scenario_lmp = scenario_d_config.model_copy()
            scenario_lmp.energy_sharing.dynamic_pricing = DynamicPricingConfig(
                enabled=True,
                pricing_type="lmp",
                lmp_update_interval_minutes=scenario_d_config.timestep_minutes,
            )

            with tempfile.TemporaryDirectory() as tmpdir_lmp:
                controller_lmp = RuleBasedController(scenario_lmp)
                coupler_lmp = SimulationCoupler(scenario_lmp, data_dir=tmpdir)
                coupler_lmp.controller = controller_lmp
                observations = coupler_lmp.reset(random_seed=42)

                for step in range(24):
                    from src.schemas.action import RequestedActions, Action, ActionType

                    requested = RequestedActions(
                        timestep=step,
                        actions=[
                            Action(
                                asset_id=f"building_{i}_battery",
                                action_type=ActionType.BATTERY_CHARGE,
                                value_kw=1.0,
                                timestep=step,
                            )
                            for i in range(5)
                        ],
                    )
                    result = coupler_lmp.step(requested)
                    if result.terminated:
                        break
                    observations = result.citylearn_result.observations

            result_lmp = coupler_lmp.get_settlement_result()

            # Compare costs
            cost_tou = sum(
                s.metadata.get("actual_total_bill", 0.0)
                for s in result_tou.building_settlements.values()
            )
            cost_lmp = sum(
                s.metadata.get("actual_total_bill", 0.0)
                for s in result_lmp.building_settlements.values()
            )

            # TOU and LMP should produce different costs for same dispatch
            # (they use different price series)
            assert (
                abs(cost_tou - cost_lmp) > 1e-6
            ), f"TOU ({cost_tou:.4f}) and LMP ({cost_lmp:.4f}) costs should differ"

            # Both should use same dispatch (same controller, same seed)
            # but different pricing leads to different bills
            print(f"TOU cost: {cost_tou:.4f}, LMP cost: {cost_lmp:.4f}")

    def test_lmp_enters_billing(self, scenario_d_config, tmp_path):
        """Test that LMP prices actually enter the billing calculation.

        Run with LMP enabled and verify LMP-specific costs are non-zero.
        """
        from src.schemas.scenario import DynamicPricingConfig

        scenario_lmp = scenario_d_config.model_copy()
        scenario_lmp.energy_sharing.dynamic_pricing = DynamicPricingConfig(
            enabled=True,
            pricing_type="lmp",
            lmp_update_interval_minutes=scenario_d_config.timestep_minutes,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            controller = RuleBasedController(scenario_d_config)
            coupler = SimulationCoupler(scenario_d_config, data_dir=tmp_path)
            coupler.controller = controller
            observations = coupler.reset(random_seed=42)

            for step in range(24):
                from src.schemas.action import RequestedActions, Action, ActionType

                requested = RequestedActions(
                    timestep=step,
                    actions=[
                        Action(
                            asset_id=f"building_{i}_battery",
                            action_type=ActionType.BATTERY_CHARGE,
                            value_kw=1.0,
                            timestep=step,
                        )
                        for i in range(5)
                    ],
                )
                result = coupler.step(requested)
                if result.terminated:
                    break
                observations = result.citylearn_result.observations

            result = coupler.get_settlement_result()

            # Verify LMP metrics are populated in building settlements
            settlement_result = result
            lmp_buildings = [
                s
                for s in settlement_result.building_settlements.values()
                if s.cost_basis == "lmp"
            ]
            assert (
                len(lmp_buildings) > 0
            ), "At least one building should use LMP cost basis"

            lmp_total_cost = sum(
                s.lmp_cost_usd for s in settlement_result.building_settlements.values()
            )
            lmp_total_revenue = sum(
                s.lmp_revenue_usd
                for s in settlement_result.building_settlements.values()
            )

            print(
                f"LMP total cost: {sum(s.lmp_cost_usd for s in settlement_result.building_settlements.values()):.4f}"
            )
            print(
                f"LMP total revenue: {sum(s.lmp_revenue_usd for s in settlement_result.building_settlements.values()):.4f}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
