"""Tests for LMP-based market clearing."""
import pytest
import numpy as np

from src.schemas.scenario import (
    ScenarioConfig, BuildingConfig, BuildingType, EnergySharingConfig,
    TariffConfig, PVConfig, BatteryConfig, PandapowerConfig, GridBusMapping,
    DynamicPricingConfig
)
from src.simulation.market import (
    MarketType,
    MarketClearingEngine,
    LmpClearing,
    create_market_engine,
    BuildingEnergyState,
    MarketClearingResult,
)


@pytest.fixture
def lmp_scenario_config():
    """Create a scenario config with LMP market type."""
    return ScenarioConfig(
        scenario_id="test_lmp_scenario",
        name="LMP Test Scenario",
        description="Scenario for LMP market clearing tests",
        random_seed=42,
        timestep_minutes=15,
        community_import_limit_kw=200,
        community_export_limit_kw=150,
        buildings=[
            BuildingConfig(
                building_id="building_0",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                simulation_start="2023-07-01",
                simulation_end="2023-07-02",
                tariff=TariffConfig(
                    type="time_of_use",
                    import_prices={"on_peak": 0.30, "mid_peak": 0.20, "off_peak": 0.10},
                    export_prices={"default": 0.05},
                    demand_charge=0.0,
                ),
                pv=PVConfig(capacity_kw=5.0),
                battery=BatteryConfig(capacity_kwh=10.0, power_kw=5.0),
            ),
            BuildingConfig(
                building_id="building_1",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                simulation_start="2023-07-01",
                simulation_end="2023-07-02",
                tariff=TariffConfig(
                    type="time_of_use",
                    import_prices={"on_peak": 0.30, "mid_peak": 0.20, "off_peak": 0.10},
                    export_prices={"default": 0.05},
                    demand_charge=0.0,
                ),
                pv=PVConfig(capacity_kw=3.0),
                battery=BatteryConfig(capacity_kwh=5.0, power_kw=3.0),
            ),
            BuildingConfig(
                building_id="building_2",
                building_type=BuildingType.COMMERCIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                simulation_start="2023-07-01",
                simulation_end="2023-07-02",
                tariff=TariffConfig(
                    type="time_of_use",
                    import_prices={"on_peak": 0.30, "mid_peak": 0.20, "off_peak": 0.10},
                    export_prices={"default": 0.05},
                    demand_charge=0.0,
                ),
                pv=PVConfig(capacity_kw=10.0),
                battery=BatteryConfig(capacity_kwh=20.0, power_kw=10.0),
            ),
        ],
        pandapower=PandapowerConfig(
            network_type="ieee_34",
            bus_mappings=[
                GridBusMapping(building_id="building_0", bus_idx=1),
                GridBusMapping(building_id="building_1", bus_idx=2),
                GridBusMapping(building_id="building_2", bus_idx=3),
            ]
        ),
        energy_sharing=EnergySharingConfig(
            enabled=True,
            market_type="lmp",
            settlement_interval="15min",
            dynamic_pricing=DynamicPricingConfig(
                enabled=True,
                pricing_type="lmp",
            ),
        )
    )


@pytest.fixture
def lmp_energy_sharing_config():
    """Create an energy sharing configuration with LMP market type."""
    return EnergySharingConfig(
        enabled=True,
        market_type="lmp",
        settlement_interval="15min",
        export_limit_kw=100.0,
        import_limit_kw=100.0,
        dynamic_pricing=DynamicPricingConfig(
            enabled=True,
            pricing_type="lmp",
        ),
    )


@pytest.fixture
def building_states_with_lmp():
    """Create sample building energy states with LMP prices."""
    return {
        "building_0": BuildingEnergyState(
            building_id="building_0",
            net_demand_kw=2.0,   # Needs energy
            pv_generation_kw=1.0,
            battery_power_kw=0.0,
            battery_soc=0.5,
            max_import_kw=50.0,
            max_export_kw=50.0,
            tariff_config=TariffConfig(
                type="time_of_use",
                import_prices={"on_peak": 0.30, "off_peak": 0.10},
                export_prices={"default": 0.05},
                demand_charge=0.0,
            ),
            lmp_price=0.15,  # $/kWh
        ),
        "building_1": BuildingEnergyState(
            building_id="building_1",
            net_demand_kw=-3.0,  # Has surplus
            pv_generation_kw=5.0,
            battery_power_kw=0.0,
            battery_soc=0.8,
            max_import_kw=30.0,
            max_export_kw=30.0,
            tariff_config=TariffConfig(
                type="time_of_use",
                import_prices={"on_peak": 0.30, "off_peak": 0.10},
                export_prices={"default": 0.05},
                demand_charge=0.0,
            ),
            lmp_price=0.12,  # $/kWh (lower LMP - cheaper to generate)
        ),
        "building_2": BuildingEnergyState(
            building_id="building_2",
            net_demand_kw=1.0,   # Small need
            pv_generation_kw=0.0,
            battery_power_kw=0.0,
            battery_soc=0.3,
            max_import_kw=100.0,
            max_export_kw=100.0,
            tariff_config=TariffConfig(
                type="time_of_use",
                import_prices={"on_peak": 0.30, "off_peak": 0.10},
                export_prices={"default": 0.05},
                demand_charge=0.0,
            ),
            lmp_price=0.18,  # $/kWh (higher LMP)
        ),
    }


class TestLmpClearing:
    """Tests for the LMP clearing engine."""

    def test_lmp_clearing_basic(self, lmp_scenario_config, lmp_energy_sharing_config, building_states_with_lmp):
        """Test LMP clearing produces valid results."""
        engine = LmpClearing(lmp_scenario_config, lmp_energy_sharing_config)
        result = engine.clear_market(building_states_with_lmp, timestep=0)
        
        assert isinstance(result, MarketClearingResult)
        assert result.market_type == MarketType.LMP
        assert result.clearing_price >= 0
        assert result.total_volume_kwh >= 0
        assert set(result.trades.keys()) == set(building_states_with_lmp.keys())
        assert set(result.settlements.keys()) == set(building_states_with_lmp.keys())

    def test_lmp_clearing_trades_sum_to_zero(self, lmp_scenario_config, lmp_energy_sharing_config, building_states_with_lmp):
        """Test that net trades sum to zero (energy conserved)."""
        engine = LmpClearing(lmp_scenario_config, lmp_energy_sharing_config)
        result = engine.clear_market(building_states_with_lmp, timestep=0)
        
        total_trade = sum(result.trades.values())
        assert abs(total_trade) < 1e-6, f"Trades don't balance: {total_trade}"

    def test_lmp_clearing_settlements_sum_to_zero(self, lmp_scenario_config, lmp_energy_sharing_config, building_states_with_lmp):
        """Test that settlements sum to zero (money conserved)."""
        engine = LmpClearing(lmp_scenario_config, lmp_energy_sharing_config)
        result = engine.clear_market(building_states_with_lmp, timestep=0)
        
        total_settlement = sum(result.settlements.values())
        assert abs(total_settlement) < 1e-6, f"Settlements don't balance: {total_settlement}"

    def test_lmp_clearing_no_buyers(self, lmp_scenario_config, lmp_energy_sharing_config):
        """Test LMP clearing with no buyers."""
        states = {
            "b0": BuildingEnergyState("b0", -2.0, 5.0, 0.0, 0.5, 50.0, 50.0, lmp_price=0.15),
            "b1": BuildingEnergyState("b1", -1.0, 3.0, 0.0, 0.5, 30.0, 30.0, lmp_price=0.12),
        }
        engine = LmpClearing(lmp_scenario_config, lmp_energy_sharing_config)
        result = engine.clear_market(states, timestep=0)
        
        assert result.total_volume_kwh == 0.0
        assert result.clearing_price == 0.0
        assert all(t == 0.0 for t in result.trades.values())

    def test_lmp_clearing_no_sellers(self, lmp_scenario_config, lmp_energy_sharing_config):
        """Test LMP clearing with no sellers."""
        states = {
            "b0": BuildingEnergyState("b0", 2.0, 0.0, 0.0, 0.5, 50.0, 50.0, lmp_price=0.15),
            "b1": BuildingEnergyState("b1", 1.0, 0.0, 0.0, 0.5, 30.0, 30.0, lmp_price=0.12),
        }
        engine = LmpClearing(lmp_scenario_config, lmp_energy_sharing_config)
        result = engine.clear_market(states, timestep=0)
        
        assert result.total_volume_kwh == 0.0
        assert result.clearing_price == 0.0
        assert all(t == 0.0 for t in result.trades.values())

    def test_lmp_clearing_respects_limits(self, lmp_scenario_config, lmp_energy_sharing_config, building_states_with_lmp):
        """Test that LMP trades respect import/export limits."""
        lmp_energy_sharing_config.import_limit_kw = 0.5
        lmp_energy_sharing_config.export_limit_kw = 0.5
        
        engine = LmpClearing(lmp_scenario_config, lmp_energy_sharing_config)
        result = engine.clear_market(building_states_with_lmp, timestep=0)
        
        for bid, trade in result.trades.items():
            if trade > 0:
                assert trade <= lmp_energy_sharing_config.import_limit_kw + 1e-6
            elif trade < 0:
                assert -trade <= lmp_energy_sharing_config.export_limit_kw + 1e-6

    def test_lmp_clearing_fallback_to_tariff(self, lmp_scenario_config, lmp_energy_sharing_config):
        """Test LMP clearing falls back to tariff when no LMP prices provided."""
        states = {
            "building_0": BuildingEnergyState(
                building_id="building_0",
                net_demand_kw=2.0,
                pv_generation_kw=1.0,
                battery_power_kw=0.0,
                battery_soc=0.5,
                max_import_kw=50.0,
                max_export_kw=50.0,
                tariff_config=TariffConfig(
                    type="time_of_use",
                    import_prices={"on_peak": 0.30, "mid_peak": 0.20, "off_peak": 0.10},
                    export_prices={"default": 0.05},
                    demand_charge=0.0,
                ),
                # No lmp_price - should fall back to tariff
            ),
            "building_1": BuildingEnergyState(
                building_id="building_1",
                net_demand_kw=-3.0,
                pv_generation_kw=5.0,
                battery_power_kw=0.0,
                battery_soc=0.8,
                max_import_kw=30.0,
                max_export_kw=30.0,
                tariff_config=TariffConfig(
                    type="time_of_use",
                    import_prices={"on_peak": 0.30, "mid_peak": 0.20, "off_peak": 0.10},
                    export_prices={"default": 0.05},
                    demand_charge=0.0,
                ),
                lmp_price=None,
            ),
        }
        engine = LmpClearing(lmp_scenario_config, lmp_energy_sharing_config)
        result = engine.clear_market(states, timestep=0)
        
        # Should still clear using tariff prices
        assert result.total_volume_kwh >= 0
        assert result.clearing_price >= 0

    def test_lmp_clearing_metadata_contains_lmp_prices(self, lmp_scenario_config, lmp_energy_sharing_config, building_states_with_lmp):
        """Test that LMP clearing metadata includes LMP prices used."""
        engine = LmpClearing(lmp_scenario_config, lmp_energy_sharing_config)
        result = engine.clear_market(building_states_with_lmp, timestep=0)
        
        assert "lmp_prices" in result.metadata
        assert "building_0" in result.metadata["lmp_prices"]
        assert "building_1" in result.metadata["lmp_prices"]
        assert "building_2" in result.metadata["lmp_prices"]
        assert result.metadata["lmp_prices"]["building_0"] == 0.15
        assert result.metadata["lmp_prices"]["building_1"] == 0.12
        assert result.metadata["lmp_prices"]["building_2"] == 0.18


class TestLmpMarketEngineFactory:
    """Tests for the market engine factory with LMP."""

    def test_lmp_engine_factory(self, lmp_scenario_config):
        """Test factory creates LMP engine."""
        engine = create_market_engine(lmp_scenario_config, lmp_scenario_config.energy_sharing)
        assert isinstance(engine, LmpClearing)

    def test_lmp_market_type_enum(self):
        """Test LMP market type enum exists."""
        assert MarketType.LMP == "lmp"
        assert MarketType.LMP.value == "lmp"

    def test_all_market_types_include_lmp(self, lmp_scenario_config, building_states_with_lmp):
        """Test all market types including LMP produce valid results."""
        from src.simulation.market import MarketType
        
        for market_type in [MarketType.UNIFORM_PRICE, MarketType.WEIGHTED, MarketType.CARBON_AWARE, MarketType.FAIRNESS_AWARE, MarketType.LMP]:
            energy_sharing_config = EnergySharingConfig(
                enabled=True,
                market_type=market_type.value,
                settlement_interval="15min",
            )
            engine = create_market_engine(lmp_scenario_config, energy_sharing_config)
            result = engine.clear_market(building_states_with_lmp, timestep=0)
            
            assert isinstance(result, MarketClearingResult)
            assert result.market_type == market_type
            assert set(result.trades.keys()) == set(building_states_with_lmp.keys())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])