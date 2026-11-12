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


def test_r01_invented_capacity_for_a_quantityless_nl_is_named():
    # r01's live shape: the LLM invents 5.0 kW for an NL that states no
    # quantities at all - the invented value must be named, not accepted.
    data = {
        "target_assets": ["pv"],
        "pv_configs": [{"capacity_kw": 5.0, "azimuth": 180}],
    }
    assert "pv.capacity_kw" in name_rejections(
        data, "Add rooftop PV to building 2 of the community."
    )


def test_setup_description_without_quantities_is_not_named():
    # c12's shape: a CREATE description leaving asset values to defaults must
    # NOT trip the quantityless rule.
    data = {
        "target_assets": ["pv", "battery"],
        "pv_configs": [{"capacity_kw": 6.0}],
        "battery_configs": [{"capacity_kwh": 10, "power_kw": 4}],
    }
    assert (
        name_rejections(
            data,
            "Create a mixed-use community: one commercial building with PV, one industrial with a battery.",
        )
        == []
    )


def test_setup_pv_without_capacity_is_not_named():
    # c07's shape: 'Create one residential building with PV' - the block is
    # demanded; the capacity is a sensible default, not an invention.
    data = {"target_assets": ["pv"], "pv_configs": [{"capacity_kw": 5.0}]}
    assert (
        name_rejections(
            data,
            "Create one residential building with PV and run it under the Singapore weather file.",
        )
        == []
    )


def test_building_index_is_not_a_stated_quantity():
    # 'building 2' must not count as a stated quantity - the quantityless rule
    # has to fire for r01's NL.
    data = {
        "target_assets": ["pv"],
        "pv_configs": [{"capacity_kw": 5.0, "azimuth": 180}],
    }
    named = name_rejections(data, "Add rooftop PV to building 2 of the community.")
    assert "pv.capacity_kw" in named


def test_r01_stated_capacity_is_not_named():
    # The same plan shape with an NL that states the capacity: grounded.
    data = {
        "target_assets": ["pv"],
        "pv_configs": [{"capacity_kw": 5.0, "azimuth": 180}],
    }
    named = name_rejections(data, "Add a 5 kW rooftop PV to building 2.")
    assert "pv.capacity_kw" not in named


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
    assert (
        name_rejections(
            data,
            "a two-building community: 6 kW PV, a 10 kWh battery, a 40 kWh EV, a 2 kW flexible load and a TOU tariff",
        )
        == []
    )


def test_battery_schema_names_out_of_range_soc():
    with pytest.raises(Exception, match="out of"):
        BatteryConfig(capacity_kwh=10, power_kw=5, soc_min=1.4, soc_max=0.6)


def test_battery_schema_names_inverted_soc():
    with pytest.raises(Exception, match="inverted"):
        BatteryConfig(capacity_kwh=10, power_kw=5, soc_min=0.8, soc_max=0.2)


def test_battery_schema_accepts_valid_bounds():
    batt = BatteryConfig(capacity_kwh=10, power_kw=5, soc_min=0.1, soc_max=0.9)
    assert batt.capacity_kwh == 10
