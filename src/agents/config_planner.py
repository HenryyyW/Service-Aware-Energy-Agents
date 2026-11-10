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
            plan = self._fallback_plan(nl)
            plan.plan_source = "rule_based_fallback"
            return plan

        try:
            response = backend(prompt)
            plan = self._parse_llm_response(response, nl)
            plan.plan_source = "llm"
            return plan
        except Exception as e:
            # Fallback on error
            plan = self._fallback_plan(nl)
            plan.plan_source = "rule_based_fallback"
            return plan

    def _build_planning_prompt(self, nl: str) -> str:
        """Build the prompt for NL -> Scenario Config planning."""
        return f"""You are an expert energy system designer converting natural language to scenario configurations.

TASK: Parse the following natural language description and create a detailed scenario configuration plan.

NATURAL LANGUAGE DESCRIPTION:
{nl}

REQUIRED OUTPUT FORMAT (JSON):
{{
    "target_assets": [],  // ONLY include assets explicitly mentioned in the description (subset of: pv, battery, ev, flexible_load, tariff, grid)
    "building_count": 1,
    "building_types": ["residential"],
    "pv_configs": [],  // Only include if "pv" in target_assets
    "battery_configs": [],  // Only include if "battery" in target_assets
    "ev_configs": [],  // Only include if "ev" in target_assets
    "flexible_load_configs": [],  // Only include if "flexible_load" in target_assets
    "tariff_configs": [],  // Only include if "tariff" in target_assets
    "grid_configs": [],  // Only include if "grid" in target_assets
    "community_import_limit_kw": null,  // Only include if mentioned
    "community_export_limit_kw": null,  // Only include if mentioned
    "energy_sharing_enabled": false,
    "dynamic_pricing_enabled": false,
    "timestep_minutes": 15,
    "simulation_duration_days": 7,
    "random_seed": 42,
    "location": {{"lat": 34.05, "lon": -118.24, "timezone": "America/Los_Angeles"}},
    "climate_zone": "tmy3_722950",
    "weather_file": null,  // Only include if weather file mentioned (e.g., "Singapore weather file")
    "confidence": 0.85,
    "assumptions": [],
    "required_fields": ["scenario_id", "name", "description", "buildings", "random_seed", "timestep_minutes"],
    "out_of_scope": ["detailed grid topology", "custom market mechanisms"]
}}

MAPPING RULES:
1. ONLY include assets explicitly mentioned in the description. Do NOT add default assets.
2. target_assets should ONLY contain assets explicitly mentioned in the description.
3. For each asset in target_assets, include its corresponding config section with values from the description (or sensible defaults if specific values not given).
4. Weather descriptions ("sunny California", "Mediterranean climate", "Singapore weather") -> CityLearn climate zones (use tmy3 zones). If specific weather file mentioned (e.g., "Singapore weather file"), include in weather_file field.
5. Grid descriptions -> pandapower network types (ieee_13, ieee_34, simbench)
6. Building types: residential, commercial, industrial, mixed
7. Asset mentions -> corresponding config sections
8. Community limits -> import/export limits
9. Energy sharing -> enabled flag + market type
10. Dynamic pricing -> enabled flag + pricing type
11. Failure mentions -> failure_injections list

CRITICAL RULES:
- ONLY include assets explicitly mentioned in the description
- Do NOT add default assets that are not mentioned
- If an asset is not mentioned, do NOT include it in target_assets or its config section
- If specific values are not given for an asset, use sensible defaults but still include the asset (since it was mentioned)
- For missing info: Use sensible defaults, document assumptions, note out_of_scope items
- If weather file is explicitly mentioned (e.g., "Singapore weather file"), include in weather_file field

OUTPUT ONLY THE JSON. NO EXPLANATIONS.
"""

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
