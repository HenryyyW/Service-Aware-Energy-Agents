"""End-to-end integration tests for Scenario D: Local Energy Sharing and Settlement."""
import pytest
import tempfile
import os
from pathlib import Path

from src.schemas.scenario import ScenarioConfig, BuildingConfig, BuildingType
from src.simulation.coupling import SimulationCoupler
from src.schemas.action import RequestedActions, Action, ActionType


@pytest.fixture
def scenario_d_config():
    """Load Scenario D configuration from YAML."""
    import yaml
    config_path = Path(__file__).parent.parent / "configs" / "scenario_d.yaml"
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)
    return ScenarioConfig(**data)


class TestScenarioDIntegration:
    """End-to-end tests for Scenario D energy sharing."""

    def test_scenario_d_loads_with_energy_sharing(self, scenario_d_config):
        """Test Scenario D config has energy sharing enabled."""
        assert scenario_d_config.scenario_id == "scenario_d"
        assert scenario_d_config.energy_sharing is not None
        assert scenario_d_config.energy_sharing.enabled is True
        assert scenario_d_config.energy_sharing.market_type == "uniform_price"
        assert len(scenario_d_config.buildings) == 5

    def test_scenario_d_coupler_initializes(self, scenario_d_config, tmp_path):
        """Test SimulationCoupler initializes with Scenario D config."""
        coupler = SimulationCoupler(scenario_d_config, data_dir=str(tmp_path))
        
        assert coupler.energy_sharing_enabled is True
        assert coupler.settlement_engine is not None
        assert coupler.settlement_engine.market_engine is not None
        assert len(coupler.settlement_engine.building_ids) == 5

    def test_scenario_d_end_to_end_short_run(self, scenario_d_config, tmp_path):
        """Test Scenario D runs end-to-end for a few timesteps with real trades."""
        coupler = SimulationCoupler(scenario_d_config, data_dir=str(tmp_path))
        observations = coupler.reset()
        
        # Run 5 timesteps
        for timestep in range(5):
            requested = RequestedActions(
                timestep=timestep,
                actions=[
                    Action(asset_id=f"building_{i}_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=0.5, timestep=timestep)
                    for i in range(5)
                ]
            )
            result = coupler.step(requested)
            
            # Verify market data is present
            grid_diag = result.citylearn_result.grid_diagnostics
            assert "market_result" in grid_diag
            assert "settlement_snapshot" in grid_diag
            assert "clearing_price" in grid_diag["market_result"]
            assert "trades" in grid_diag["market_result"]
            assert "settlements" in grid_diag["market_result"]
            
            # Verify trades structure
            trades = grid_diag["market_result"]["trades"]
            assert set(trades.keys()) == set(b.building_id for b in scenario_d_config.buildings)
            
            # Verify settlements structure
            settlements = grid_diag["market_result"]["settlements"]
            assert set(settlements.keys()) == set(b.building_id for b in scenario_d_config.buildings)

    def test_scenario_d_trades_balance(self, scenario_d_config, tmp_path):
        """Test that community trades sum to zero (energy conserved)."""
        coupler = SimulationCoupler(scenario_d_config, data_dir=str(tmp_path))
        coupler.reset()
        
        for timestep in range(10):
            requested = RequestedActions(
                timestep=timestep,
                actions=[
                    Action(asset_id=f"building_{i}_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=timestep)
                    for i in range(5)
                ]
            )
            result = coupler.step(requested)
            
            trades = result.citylearn_result.grid_diagnostics["market_result"]["trades"]
            total_trade = sum(trades.values())
            assert abs(total_trade) < 1e-6, f"Timestep {timestep}: trades don't balance: {total_trade}"

    def test_scenario_d_settlements_balance(self, scenario_d_config, tmp_path):
        """Test that settlements sum to zero (money conserved)."""
        coupler = SimulationCoupler(scenario_d_config, data_dir=str(tmp_path))
        coupler.reset()
        
        for timestep in range(10):
            requested = RequestedActions(
                timestep=timestep,
                actions=[
                    Action(asset_id=f"building_{i}_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=timestep)
                    for i in range(5)
                ]
            )
            result = coupler.step(requested)
            
            settlements = result.citylearn_result.grid_diagnostics["market_result"]["settlements"]
            total_settlement = sum(settlements.values())
            assert abs(total_settlement) < 1e-6, f"Timestep {timestep}: settlements don't balance: {total_settlement}"

    def test_scenario_d_final_settlement_report(self, scenario_d_config, tmp_path):
        """Test final settlement report has per-member accounting."""
        coupler = SimulationCoupler(scenario_d_config, data_dir=str(tmp_path))
        coupler.reset()
        
        # Run enough timesteps to trigger at least one settlement interval
        # settlement_interval = 15min, timestep = 15min, so 1 timestep per interval
        # But we need to run enough to get meaningful results
        for timestep in range(20):
            requested = RequestedActions(
                timestep=timestep,
                actions=[
                    Action(asset_id=f"building_{i}_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=timestep)
                    for i in range(5)
                ]
            )
            result = coupler.step(requested)
        
        # Get final settlement result
        settlement_result = coupler.get_settlement_result()
        assert settlement_result is not None
        
        # Verify per-building settlements
        assert len(settlement_result.building_settlements) == 5
        for bid in [f"building_{i}" for i in range(5)]:
            assert bid in settlement_result.building_settlements
            settlement = settlement_result.building_settlements[bid]
            
            # Verify key accounting fields
            assert hasattr(settlement, 'net_settlement')
            assert hasattr(settlement, 'total_bought_kwh')
            assert hasattr(settlement, 'total_sold_kwh')
            assert hasattr(settlement, 'total_grid_import_kwh')
            assert hasattr(settlement, 'total_grid_export_kwh')
            assert hasattr(settlement, 'baseline_grid_import_kwh')
            assert hasattr(settlement, 'baseline_grid_export_kwh')
            assert hasattr(settlement, 'total_community_import_kwh')
            assert hasattr(settlement, 'total_community_export_kwh')
            assert hasattr(settlement, 'peak_grid_import_kw')
            assert hasattr(settlement, 'baseline_peak_grid_import_kw')
            assert hasattr(settlement, 'demand_charge_rate')
            assert hasattr(settlement, 'actual_demand_charge')
            assert hasattr(settlement, 'baseline_demand_charge')
            
            # Verify metadata includes savings
            assert 'savings_vs_baseline' in settlement.metadata
            assert 'self_sufficiency' in settlement.metadata

    def test_scenario_d_community_metrics(self, scenario_d_config, tmp_path):
        """Test community-level metrics are computed."""
        coupler = SimulationCoupler(scenario_d_config, data_dir=str(tmp_path))
        coupler.reset()
        
        for timestep in range(20):
            requested = RequestedActions(
                timestep=timestep,
                actions=[
                    Action(asset_id=f"building_{i}_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=timestep)
                    for i in range(5)
                ]
            )
            result = coupler.step(requested)
        
        metrics = coupler.settlement_engine.get_community_metrics()
        
        # Verify key community metrics
        assert "total_grid_import_kwh" in metrics
        assert "total_grid_export_kwh" in metrics
        assert "total_community_volume_kwh" in metrics
        assert "community_self_sufficiency" in metrics
        assert "total_savings_vs_baseline" in metrics
        assert "avg_clearing_price" in metrics
        
        # Community self-sufficiency should be between 0 and 1
        assert 0 <= metrics["community_self_sufficiency"] <= 1

    def test_scenario_d_interval_settlements(self, scenario_d_config, tmp_path):
        """Test interval-based settlement aggregation works."""
        coupler = SimulationCoupler(scenario_d_config, data_dir=str(tmp_path))
        coupler.reset()
        
        # Run multiple intervals (15min interval = 1 timestep at 15min)
        for timestep in range(8):
            requested = RequestedActions(
                timestep=timestep,
                actions=[
                    Action(asset_id=f"building_{i}_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=timestep)
                    for i in range(5)
                ]
            )
            result = coupler.step(requested)
        
        settlement_result = coupler.get_settlement_result()
        
        # Should have interval results
        assert len(settlement_result.interval_results) >= 1
        
        for interval in settlement_result.interval_results:
            assert interval.interval_idx >= 0
            assert interval.start_timestep <= interval.end_timestep
            assert interval.total_volume_kwh >= 0
            assert set(interval.building_settlements.keys()) == set(b.building_id for b in scenario_d_config.buildings)

    def test_scenario_d_different_market_types(self, scenario_d_config, tmp_path):
        """Test Scenario D works with different market types."""
        from src.schemas.scenario import EnergySharingConfig
        import yaml
        import copy
        config_path = Path(__file__).parent.parent / "configs" / "scenario_d.yaml"
        with open(config_path, 'r') as f:
            base_data = yaml.safe_load(f)
        
        for market_type in ["uniform_price", "weighted", "carbon_aware", "fairness_aware"]:
            # Create fresh config for each market type (deep copy to avoid shared dicts)
            data = copy.deepcopy(base_data)
            data['energy_sharing']['market_type'] = market_type
            test_config = ScenarioConfig(**data)
            
            coupler = SimulationCoupler(test_config, data_dir=str(tmp_path))
            observations = coupler.reset()
            
            requested = RequestedActions(
                timestep=0,
                actions=[
                    Action(asset_id=f"building_{i}_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=0)
                    for i in range(5)
                ]
            )
            result = coupler.step(requested)
            
            market_result = result.citylearn_result.grid_diagnostics["market_result"]
            assert market_result["market_type"] == market_type
            assert "clearing_price" in market_result
            assert "trades" in market_result

    def test_scenario_d_exports_results(self, scenario_d_config, tmp_path):
        """Test exporting Scenario D results including market and settlement data."""
        coupler = SimulationCoupler(scenario_d_config, data_dir=str(tmp_path))
        coupler.reset()
        
        for timestep in range(10):
            requested = RequestedActions(
                timestep=timestep,
                actions=[
                    Action(asset_id=f"building_{i}_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=timestep)
                    for i in range(5)
                ]
            )
            result = coupler.step(requested)
        
        output_dir = tmp_path / "output"
        coupler.export_results(str(output_dir))
        
        # Verify output files exist
        assert (output_dir / "trajectories.jsonl").exists()
        assert (output_dir / "grid_diagnostics.jsonl").exists()
        assert (output_dir / "market_results.jsonl").exists()
        assert (output_dir / "settlement_result.json").exists()
        assert (output_dir / "kpis.json").exists()
        
        # Verify settlement_result.json has expected structure
        import json
        with open(output_dir / "settlement_result.json", 'r') as f:
            settlement_data = json.load(f)
        
        assert "building_settlements" in settlement_data
        assert len(settlement_data["building_settlements"]) == 5
        assert "interval_results" in settlement_data
        assert "total_community_volume_kwh" in settlement_data

    def test_scenario_d_no_sharing_baseline_comparison(self, scenario_d_config, tmp_path):
        """Test that savings are computed correctly vs no-sharing baseline."""
        coupler = SimulationCoupler(scenario_d_config, data_dir=str(tmp_path))
        coupler.reset()
        
        for timestep in range(20):
            requested = RequestedActions(
                timestep=timestep,
                actions=[
                    Action(asset_id=f"building_{i}_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=timestep)
                    for i in range(5)
                ]
            )
            result = coupler.step(requested)
        
        savings = coupler.settlement_engine.get_building_savings()
        
        # All buildings should have savings calculated
        assert len(savings) == 5
        for bid in [f"building_{i}" for i in range(5)]:
            assert bid in savings
            # Savings can be positive, negative, or zero depending on market conditions
            assert isinstance(savings[bid], float)
        
        community_metrics = coupler.settlement_engine.get_community_metrics()
        assert "total_savings_vs_baseline" in community_metrics
        assert isinstance(community_metrics["total_savings_vs_baseline"], float)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])