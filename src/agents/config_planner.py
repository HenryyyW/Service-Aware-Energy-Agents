"""Config Planner agent - converts natural language to scenario configuration plan."""

from typing import Dict, Any
import json
from src.agents.config_roles import (
    ConfigAgentState,
    ConfigPlannerOutput,
)


class ConfigPlannerAgent:
    """Planner agent that converts natural language to scenario configuration plan."""

    def __init__(self, model: str = "poolside/laguna-xs-2.1", temperature: float = 0.1):
        self.model = model
        self.temperature = temperature

    def _get_backend(self):
        """Get the LLM backend for planning."""
        import os
        from src.agents.backend.api import api_prompt_callable

        return api_prompt_callable(
            model=self.model,
            base_url=os.getenv("LLM_BASE_URL"),
            temperature=self.temperature,
            seed=42,
            timeout_s=60.0,
            max_tokens=4096,
        )

    def plan(self, state: ConfigAgentState) -> ConfigPlannerOutput:
        """
        Convert natural language description to a structured configuration plan.

        Args:
            state: Current agent state with NL description

        Returns:
            ConfigPlannerOutput with detailed configuration plan
        """
        nl = state.nl_description

        # Build the planning prompt
        prompt = self._build_planning_prompt(nl)

        # Get backend
        backend = self._get_backend()
        if backend is None:
            # Fallback to rule-based planning
            return self._fallback_plan(nl)

        try:
            response = backend(prompt)
            return self._parse_llm_response(response, nl)
        except Exception as e:
            # Fallback on error
            return self._fallback_plan(nl)

    def _build_planning_prompt(self, nl: str) -> str:
        """Build the prompt for NL -> Scenario Config planning."""
        return f"""You are an expert energy system designer converting natural language to scenario configurations.

TASK: Parse the following natural language description and create a detailed scenario configuration plan.

NATURAL LANGUAGE DESCRIPTION:
{nl}

REQUIRED OUTPUT FORMAT (JSON):
{{
    "target_assets": ["pv", "battery", "ev", "flexible_load", "tariff", "grid"],
    "building_count": 1,
    "building_types": ["residential"],
    "pv_configs": [
        {{"capacity_kw": 10.0, "azimuth": 180, "tilt": 30, "efficiency": 0.20}}
    ],
    "battery_configs": [
        {{"capacity_kwh": 13.5, "power_kw": 5.0, "efficiency_charge": 0.95, "efficiency_discharge": 0.95, "soc_min": 0.1, "soc_max": 0.9, "initial_soc": 0.5}}
    ],
    "ev_configs": [
        {{"capacity_kwh": 60, "max_charge_kw": 11, "efficiency": 0.9, "arrival_time": "18:00", "departure_time": "07:00", "target_soc": 0.8, "initial_soc": 0.3, "connected_days": [0,1,2,3,4,5,6]}}
    ],
    "flexible_load_configs": [
        {{"power_kw": 3.0, "energy_kwh": 10, "earliest_start": "22:00", "latest_end": "06:00", "duration_hours": 2}}
    ],
    "tariff_configs": [
        {{"type": "time_of_use", "import_prices": {{"peak": 0.30, "off_peak": 0.10}}, "export_prices": {{"peak": 0.05, "off_peak": 0.02}}, "demand_charge": 10.0}}
    ],
    "grid_configs": [
        {{"network_type": "ieee_34", "voltage_limits": {{"min": 0.95, "max": 1.05}}, "line_loading_limit": 1.0}}
    ],
    "community_import_limit_kw": 500,
    "community_export_limit_kw": 300,
    "energy_sharing_enabled": false,
    "dynamic_pricing_enabled": false,
    "timestep_minutes": 15,
    "simulation_duration_days": 7,
    "random_seed": 42,
    "location": {{"lat": 34.05, "lon": -118.24, "timezone": "America/Los_Angeles"}},
    "climate_zone": "tmy3_722950",
    "confidence": 0.85,
    "assumptions": ["Single residential building", "California climate zone", "Standard TOU tariff"],
    "required_fields": ["scenario_id", "name", "description", "buildings", "random_seed", "timestep_minutes"],
    "out_of_scope": ["detailed grid topology", "custom market mechanisms"]
}}

MAPPING RULES:
1. Weather descriptions ("sunny California", "Mediterranean climate") -> CityLearn climate zones (use tmy3 zones)
2. Grid descriptions -> pandapower network types (ieee_13, ieee_34, simbench)
3. Building types: residential, commercial, industrial, mixed
3. Asset mentions -> corresponding config sections
4. Community limits -> import/export limits
5. Energy sharing -> enabled flag + market type
6. Dynamic pricing -> enabled flag + pricing type
6. Failure mentions -> failure_injections list

FOR MISSING INFO: Use sensible defaults, document assumptions, note out_of_scope items.

OUTPUT ONLY THE JSON. NO EXPLANATIONS.
"""
        prompt = f"""You are an expert energy system designer converting natural language to scenario configurations.

TASK: Parse the following natural language description and create a detailed scenario configuration plan.

NATURAL LANGUAGE DESCRIPTION:
{nl}

REQUIRED OUTPUT FORMAT (JSON):
{{
    "target_assets": ["pv", "battery", "ev", "flexible_load", "tariff", "grid"],
    "building_count": 1,
    "building_types": ["residential"],
    "pv_configs": [
        {{"capacity_kw": 10.0, "azimuth": 180, "tilt": 30, "efficiency": 0.20}}
    ],
    "battery_configs": [
        {{"capacity_kwh": 13.5, "power_kw": 5.0, "efficiency_charge": 0.95, "efficiency_discharge": 0.95, "soc_min": 0.1, "soc_max": 0.9, "initial_soc": 0.5}}
    ],
    "ev_configs": [
        {{"capacity_kwh": 60, "max_charge_kw": 11, "efficiency": 0.9, "arrival_time": "18:00", "departure_time": "07:00", "target_soc": 0.8, "initial_soc": 0.3, "connected_days": [0,1,2,3,4,5,6]}}
    ],
    "flexible_load_configs": [
        {{"power_kw": 3.0, "energy_kwh": 10, "earliest_start": "22:00", "latest_end": "06:00", "duration_hours": 2}}
    ],
    "tariff_configs": [
        {{"type": "time_of_use", "import_prices": {{"peak": 0.30, "off_peak": 0.10}}, "export_prices": {{"peak": 0.05, "off_peak": 0.02}}, "demand_charge": 10.0}}
    ],
    "grid_configs": [
        {{"network_type": "ieee_34", "voltage_limits": {{"min": 0.95, "max": 1.05}}, "line_loading_limit": 1.0}}
    ],
    "community_import_limit_kw": 500,
    "community_export_limit_kw": 300,
    "energy_sharing_enabled": false,
    "dynamic_pricing_enabled": false,
    "timestep_minutes": 15,
    "simulation_duration_days": 7,
    "random_seed": 42,
    "location": {{"lat": 34.05, "lon": -118.24, "timezone": "America/Los_Angeles"}},
    "climate_zone": "tmy3_722950",
    "confidence": 0.85,
    "assumptions": ["Single residential building", "California climate zone", "Standard TOU tariff"],
    "required_fields": ["scenario_id", "name", "description", "buildings", "random_seed", "timestep_minutes"],
    "out_of_scope": ["detailed grid topology", "custom market mechanisms"]
}}

MAPPING RULES:
1. Weather descriptions ("sunny California", "Mediterranean climate") -> CityLearn climate zones (use tmy3 zones)
2. Grid descriptions -> pandapower network types (ieee_13, ieee_34, simbench)
3. Building types: residential, commercial, industrial, mixed
3. Asset mentions -> corresponding config sections
4. Community limits -> import/export limits
5. Energy sharing -> enabled flag + market type
6. Dynamic pricing -> enabled flag + pricing type
6. Failure mentions -> failure_injections list

FOR MISSING INFO: Use sensible defaults, document assumptions, note out_of_scope items.

OUTPUT ONLY THE JSON. NO EXPLANATIONS.
"""
        return prompt

    def _fallback_plan(self, nl: str) -> ConfigPlannerOutput:
        """Fallback rule-based planning when LLM is unavailable."""
        # Simple keyword-based extraction
        nl_lower = nl.lower()

        plan = ConfigPlannerOutput(plan_source="rule_based_fallback")

        # Detect assets
        if any(kw in nl_lower for kw in ["pv", "solar", "photovoltaic"]):
            plan.target_assets.append("pv")
            plan.pv_configs.append({"capacity_kw": 10.0})

        if any(kw in nl_lower for kw in ["battery", "storage"]):
            plan.target_assets.append("battery")
            plan.battery_configs.append({"capacity_kwh": 13.5, "power_kw": 5.0})

        if any(kw in nl_lower for kw in ["ev", "electric vehicle", "car"]):
            plan.target_assets.append("ev")
            plan.ev_configs.append({"capacity_kwh": 60, "max_charge_kw": 11})

        if any(kw in nl_lower for kw in ["flexible", "load", "hvac", "thermostat"]):
            plan.target_assets.append("flexible_load")
            plan.flexible_load_configs.append({"power_kw": 3.0, "energy_kwh": 10})

        if any(kw in nl_lower for kw in ["tariff", "price", "rate", "tou"]):
            plan.target_assets.append("tariff")
            plan.tariff_configs.append({"type": "time_of_use"})

        if any(kw in nl_lower for kw in ["grid", "network", "ieee"]):
            plan.target_assets.append("grid")
            plan.grid_configs.append({"network_type": "ieee_34"})

        # Default building
        plan.building_count = 1
        plan.building_types = ["residential"]

        # Community limits
        if "import limit" in nl_lower:
            plan.community_import_limit_kw = 500
        if "export limit" in nl_lower:
            plan.community_export_limit_kw = 300

        if "energy sharing" in nl_lower or "sharing" in nl_lower:
            plan.energy_sharing_enabled = True

        if (
            "dynamic pricing" in nl_lower
            or "lmp" in nl_lower
            or "real time" in nl_lower
        ):
            plan.dynamic_pricing_enabled = True

        return plan

    def _parse_llm_response(self, response: str, nl: str) -> ConfigPlannerOutput:
        """Parse LLM response into ConfigPlannerOutput."""
        try:
            # Extract JSON from response
            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return ConfigPlannerOutput(**data)
        except Exception:
            pass

        return self._fallback_plan(nl)


def create_config_planner(config: Dict[str, Any]) -> ConfigPlannerAgent:
    """Factory function to create config planner from config."""
    return ConfigPlannerAgent(
        model=config.get("model", "poolside/laguna-xs-2.1"),
        temperature=config.get("temperature", 0.1),
    )
