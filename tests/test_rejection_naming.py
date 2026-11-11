"""Named-rejection tests: the P1 rejection-path contract.

The planner names required-but-unstated fields (r01), out-of-range SOC bounds
(r03), and a missing building scope (r02); the schema names SOC bounds too;
complete items never trip the naming.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.config_planner import name_rejections  # noqa: E402
from src.schemas.scenario import BatteryConfig  # noqa: E402


def test_r01_pv_without_capacity_is_named():
    data = {"target_assets": ["pv"], "pv_configs": [{"azimuth": 180}]}
    assert "pv.capacity_kw" in name_rejections(data, "Add rooftop PV to building 2.")


def test_r01_pv_with_no_configs_at_all_is_named():
    data = {"target_assets": ["pv"], "pv_configs": []}
    assert "pv.capacity_kw" in name_rejections(data, "Add rooftop PV to building 2.")


def test_r01_complete_pv_plan_is_not_named():
    data = {
        "target_assets": ["pv"],
        "pv_configs": [{"capacity_kw": 5.0, "azimuth": 180}],
    }
    assert name_rejections(data, "Add a 5 kW PV to building 2.") == []


def test_r03_out_of_range_and_inverted_soc_named():
    data = {
        "target_assets": ["battery"],
        "battery_configs": [
            {"capacity_kwh": 10, "power_kw": 5, "soc_min": 1.4, "soc_max": 0.6}
        ],
    }
    named = name_rejections(data, "Add a 10 kWh battery with soc 1.4/0.6.")
    assert "battery.soc_min" in named
    assert "battery.soc_max" in named


def test_r03_inverted_only_named():
    data = {
        "target_assets": ["battery"],
        "battery_configs": [
            {"capacity_kwh": 10, "power_kw": 5, "soc_min": 0.8, "soc_max": 0.2}
        ],
    }
    named = name_rejections(data, "battery")
    assert "battery.soc_min" in named


def test_r02_community_edit_without_buildings_named():
    data = {"target_assets": ["tariff"], "tariff_configs": [{"type": "time_of_use"}]}
    named = name_rejections(
        data, "Just set the tariff to 0.15 USD/kWh for the community."
    )
    assert "buildings" in named


def test_r02_not_named_when_nl_describes_buildings():
    data = {"target_assets": ["tariff"], "tariff_configs": [{"type": "time_of_use"}]}
    assert (
        name_rejections(data, "Put a time-of-use tariff on one residential building.")
        == []
    )


def test_r02_not_named_when_plan_carries_the_buildings_token():
    data = {
        "target_assets": ["buildings", "tariff"],
        "tariff_configs": [{"type": "time_of_use"}],
    }
    named = name_rejections(data, "Set the tariff for the community.")
    assert "buildings" not in named


def test_complete_multi_asset_plan_is_not_named():
    data = {
        "target_assets": ["pv", "battery", "ev", "flexible_load", "tariff"],
        "pv_configs": [{"capacity_kw": 6.0}],
        "battery_configs": [{"capacity_kwh": 10, "power_kw": 4}],
        "ev_configs": [
            {
                "capacity_kwh": 40,
                "max_charge_kw": 7,
                "arrival_time": "19:00",
                "departure_time": "06:00",
            }
        ],
        "flexible_load_configs": [
            {
                "power_kw": 2,
                "energy_kwh": 6,
                "earliest_start": "10:00",
                "latest_end": "16:00",
                "duration_hours": 3,
            }
        ],
        "tariff_configs": [{"type": "time_of_use", "import_prices": {"peak": 0.3}}],
    }
    assert name_rejections(data, "a two-building community with all these assets") == []


def test_battery_schema_names_out_of_range_soc():
    with pytest.raises(Exception, match="out of"):
        BatteryConfig(capacity_kwh=10, power_kw=5, soc_min=1.4, soc_max=0.6)


def test_battery_schema_names_inverted_soc():
    with pytest.raises(Exception, match="inverted"):
        BatteryConfig(capacity_kwh=10, power_kw=5, soc_min=0.8, soc_max=0.2)


def test_battery_schema_accepts_valid_bounds():
    batt = BatteryConfig(capacity_kwh=10, power_kw=5, soc_min=0.1, soc_max=0.9)
    assert batt.capacity_kwh == 10
