"""Config Coder agent - applies plan to create/modify scenario configuration."""

from typing import Dict, Any, Optional, List
import copy
import json
import difflib
from src.agents.config_roles import ConfigAgentState, ConfigCoderOutput


class ConfigCoderAgent:
    """Config Coder agent - applies plan to create/modify ScenarioConfig."""

    def __init__(self, model: str = "poolside/laguna-xs-2.1", temperature: float = 0.1):
        self.model = model
        self.temperature = temperature

    def _get_backend(self):
        """Get the LLM backend for coding."""
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

    def code(
        self,
        state: "ConfigAgentState",
        plan: Dict[str, Any],
        baseline_config: Optional[Dict[str, Any]] = None,
    ) -> "ConfigCoderOutput":
        """
        Apply plan to create/modify scenario configuration.

        Args:
            state: Current agent state
            plan: Plan from ConfigPlannerOutput
            baseline_config: Optional baseline config to modify

        Returns:
            ConfigCoderOutput with patched configuration
        """
        # Get baseline config
        baseline = baseline_config or state.baseline_config
        if baseline is None:
            # Create minimal baseline
            baseline = self._create_minimal_baseline()

        # Apply plan to create patched config
        patched = self._apply_plan(baseline, plan)

        # Generate diff
        diff = self._generate_diff(baseline, patched)

        # Extract changes
        changes = self._extract_changes(baseline, patched)

        # Build output
        output = ConfigCoderOutput(
            config_changes=changes,
            patched_config=patched,
            config_diff=self._format_diff(diff),
            implementation_notes=f"Applied plan with {len(changes)} changes",
            applied_count=len(changes),
            failed_count=0,
        )

        return output

    def _create_minimal_baseline(self) -> Dict[str, Any]:
        """Create a minimal baseline scenario config."""
        return {
            "scenario_id": "scenario_base",
            "name": "Base Scenario",
            "description": "Minimal baseline scenario",
            "buildings": [],
            "pandapower": {
                "network_type": "ieee_34",
                "voltage_limits": {"min": 0.95, "max": 1.05},
                "line_loading_limit": 1.0,
                "transformer_loading_limit": 1.0,
                "run_power_flow_every": 1,
            },
            "energy_sharing": None,
            "failures": [],
            "community_import_limit_kw": None,
            "community_export_limit_kw": None,
            "random_seed": 42,
            "timestep_minutes": 15,
        }

    def _apply_plan(
        self, baseline: Dict[str, Any], plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply plan to baseline config."""
        patched = copy.deepcopy(baseline)

        # Apply building configs
        if plan.get("target_assets"):
            buildings = self._build_buildings(plan)
            patched["buildings"] = buildings

        # Apply community settings
        if plan.get("community_import_limit_kw") is not None:
            patched["community_import_limit_kw"] = plan["community_import_limit_kw"]
        if plan.get("community_export_limit_kw") is not None:
            patched["community_export_limit_kw"] = plan["community_export_limit_kw"]

        # Energy sharing
        if plan.get("energy_sharing_enabled"):
            patched["energy_sharing"] = self._build_energy_sharing(plan)

        # Dynamic pricing
        if plan.get("dynamic_pricing_enabled"):
            patched["energy_sharing"] = patched.get("energy_sharing") or {}
            patched["energy_sharing"]["dynamic_pricing"] = self._build_dynamic_pricing(
                plan
            )

        # Grid config
        if plan.get("grid_configs"):
            patched["pandapower"] = self._build_pandapower(plan)

        # Failures
        if plan.get("failure_injections"):
            patched["failures"] = plan["failure_injections"]

        # Simulation settings
        if plan.get("timestep_minutes"):
            patched["timestep_minutes"] = plan["timestep_minutes"]
        if plan.get("random_seed"):
            patched["random_seed"] = plan["random_seed"]

        return patched

    def _build_buildings(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build building configurations from plan."""
        buildings = []
        count = plan.get("building_count", 1)

        for i in range(count):
            building = {
                "building_id": f"building_{i+1}",
                "building_type": plan.get("building_types", ["residential"])[
                    i % len(plan.get("building_types", ["residential"]))
                ],
                "location": {},
            }

            # PV
            if "pv" in plan.get("target_assets", []) and plan.get("pv_configs"):
                pv = plan["pv_configs"][i % len(plan["pv_configs"])]
                building["pv"] = pv

            # Battery
            if "battery" in plan.get("target_assets", []) and plan.get(
                "battery_configs"
            ):
                battery = plan["battery_configs"][i % len(plan["battery_configs"])]
                building["battery"] = battery

            # EV
            if "ev" in plan.get("target_assets", []) and plan.get("ev_configs"):
                building["evs"] = plan["ev_configs"]

            # Flexible loads
            if "flexible_load" in plan.get("target_assets", []) and plan.get(
                "flexible_load_configs"
            ):
                building["flexible_loads"] = plan["flexible_load_configs"]

            # Tariff
            if "tariff" in plan.get("target_assets", []) and plan.get("tariff_configs"):
                building["tariff"] = plan["tariff_configs"][0]

            # Location/simulation
            if plan.get("location"):
                building["location"] = plan["location"]

            return buildings

    def _build_energy_sharing(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Build energy sharing config."""
        return {
            "enabled": True,
            "market_type": "uniform_price",
            "settlement_interval": "15min",
            "export_limit_kw": plan.get("community_export_limit_kw"),
            "import_limit_kw": plan.get("community_import_limit_kw"),
        }

    def _build_dynamic_pricing(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Build dynamic pricing config."""
        return {
            "enabled": True,
            "pricing_type": "lmp",
            "lmp_update_interval_minutes": 15,
            "congestion_cost_method": "dc_approx",
            "price_cap_per_kwh": 1.0,
            "fallback_to_tariff": True,
        }

    def _build_pandapower(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Build pandapower config."""
        grid = plan.get("grid_configs", [{}])[0]
        return {
            "network_type": grid.get("network_type", "ieee_34"),
            "voltage_limits": grid.get("voltage_limits", {"min": 0.95, "max": 1.05}),
            "line_loading_limit": grid.get("line_loading_limit", 1.0),
            "transformer_loading_limit": grid.get("transformer_loading_limit", 1.0),
            "run_power_flow_every": grid.get("run_power_flow_every", 1),
        }

    def _generate_diff(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        """Generate unified diff between two configs."""
        old_str = json.dumps(old, indent=2, sort_keys=True)
        new_str = json.dumps(new, indent=2, sort_keys=True)
        diff = difflib.unified_diff(
            old_str.splitlines(keepends=True),
            new_str.splitlines(keepends=True),
            fromfile="baseline",
            tofile="patched",
        )
        return list(diff)

    def _format_diff(self, diff: List[str]) -> str:
        """Format diff for output."""
        return "".join(diff)

    def _extract_changes(
        self, old: Dict[str, Any], new: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract semantic changes between configs."""
        changes = []

        # Compare buildings
        old_buildings = old.get("buildings", [])
        new_buildings = new.get("buildings", [])

        for i, (old_b, new_b) in enumerate(zip(old_buildings, new_buildings)):
            for key in ["pv", "battery", "evs", "flexible_loads", "tariff"]:
                if old_b.get(key) != new_b.get(key):
                    changes.append(
                        {
                            "file": f"buildings[{i}]",
                            "field": key,
                            "change": f"Modified {key}",
                            "type": "modification",
                        }
                    )

        # Compare community settings
        for field in ["community_import_limit_kw", "community_export_limit_kw"]:
            if old.get(field) != new.get(field):
                changes.append(
                    {
                        "file": "scenario",
                        "field": field,
                        "change": f"Set {field} to {new.get(field)}",
                        "type": "modification",
                    }
                )

        # Energy sharing
        if old.get("energy_sharing") != new.get("energy_sharing"):
            changes.append(
                {
                    "file": "scenario",
                    "field": "energy_sharing",
                    "change": "Modified energy sharing config",
                    "type": "modification",
                }
            )

        return changes


def create_config_coder(config: Dict[str, Any]):
    """Factory function to create config coder from config."""
    return ConfigCoderAgent(
        model=config.get("model", "poolside/laguna-xs-2.1"),
        temperature=config.get("temperature", 0.1),
    )
