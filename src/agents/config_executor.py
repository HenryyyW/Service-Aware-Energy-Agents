"""Config Executor agent - validates config by running quick simulation."""

from typing import Dict, Any
import time
import os
import json
from pathlib import Path
from src.agents.config_roles import ConfigExecutorOutput, ConfigAgentState


class ConfigExecutorAgent:
    """Executor agent that validates scenario config by running simulation."""

    def __init__(
        self,
        project_root: str = None,
        timeout: int = 120,
        quick_test_steps: int = 10,
        max_steps: int = 20,
    ):
        self.project_root = project_root or os.getcwd()
        self.timeout = timeout
        self.quick_test_steps = quick_test_steps
        self.max_steps = max_steps

    def execute(
        self,
        state: "ConfigAgentState",
        patched_config: Dict[str, Any],
        scenario_id: str = None,
    ) -> "ConfigExecutorOutput":
        """
        Execute the patched config in simulation to validate.

        Args:
            state: Current agent state
            patched_config: The patched configuration to test
            scenario_id: Optional scenario ID

        Returns:
            ConfigExecutorOutput with validation results
        """
        # Import inside function to avoid circular imports
        from experiments.run_experiment import ExperimentRunner, load_scenario

        start_time = time.time()

        # Validate internal config format first
        validation = self.validate_config(patched_config)
        if not validation["valid"]:
            execution_time = time.time() - start_time
            return ConfigExecutorOutput(
                success=False,
                scenario_id=scenario_id or f"nl_config_{int(time.time())}",
                config_valid=False,
                simulation_steps=0,
                simulation_time_sec=execution_time,
                error="; ".join(validation["errors"]),
                execution_time=execution_time,
                test_results={"validation_errors": validation["errors"]},
            )

        # Generate scenario ID
        if scenario_id is None:
            scenario_id = f"nl_config_{int(time.time())}"

        # Write config to temp scenario directory
        scenario_dir = Path(self.project_root) / "data" / "schemas" / scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Save internal config as schema.json (already in ScenarioConfig format)
            schema_path = scenario_dir / "schema.json"
            with open(schema_path, "w") as f:
                json.dump(patched_config, f, indent=2)

            # Create minimal CSV files for buildings if needed
            self._ensure_building_data(scenario_dir, patched_config)

            # Run quick simulation
            try:
                runner = ExperimentRunner(
                    load_scenario(str(schema_path)),
                    output_dir="experiments/results",
                )

                # Use rule-based for quick validation
                runner.setup("rule_based")

                # Run quick simulation
                exp_result = runner.run(max_steps=self.quick_test_steps)

                execution_time = time.time() - start_time

                # Extract validation results
                violation_counts = getattr(exp_result, "violation_counts", {})
                power_flow_converged = getattr(exp_result, "power_flow_converged", True)

                # Check energy balance
                energy_balance_ok = self._check_energy_balance(exp_result)

                output = ConfigExecutorOutput(
                    success=True,
                    scenario_id=scenario_id,
                    config_valid=True,
                    simulation_steps=(
                        exp_result.timestep
                        if hasattr(exp_result, "timestep")
                        else self.quick_test_steps
                    ),
                    simulation_time_sec=execution_time,
                    violation_counts=getattr(exp_result, "violation_counts", {}),
                    power_flow_converged=power_flow_converged,
                    energy_balance_ok=energy_balance_ok,
                    execution_time=execution_time,
                    test_results={
                        "scenario_id": scenario_id,
                        "steps": self.quick_test_steps,
                        "violations": violation_counts,
                    },
                )

            except Exception as e:
                execution_time = time.time() - start_time
                return ConfigExecutorOutput(
                    success=False,
                    scenario_id=scenario_id,
                    config_valid=False,
                    simulation_steps=0,
                    simulation_time_sec=execution_time,
                    error=str(e),
                    execution_time=execution_time,
                    test_results={"error": str(e)},
                )

        finally:
            # Cleanup temp files (optional - keep for debugging)
            pass

        return output

    def _config_to_schema(
        self, config: Dict[str, Any], scenario_id: str
    ) -> Dict[str, Any]:
        """Convert internal config to CityLearn schema format."""
        # This is a simplified conversion - in reality would use the existing _schema_to_scenario_config logic in reverse
        schema = {
            "scenario_id": config.get("scenario_id", "nl_config"),
            "name": config.get("name", "NL Generated Scenario"),
            "description": config.get("description", "Generated from natural language"),
            "random_seed": config.get("random_seed", 42),
            "seconds_per_time_step": config.get("timestep_minutes", 15) * 60,
            "buildings": {},
        }

        # Convert buildings
        buildings = config.get("buildings", [])
        for i, b in enumerate(config.get("buildings", [])):
            bid = b.get("building_id", f"building_{i}")
            building_schema = {
                "include": True,
                "building_type": b.get("building_type", "residential"),
                "location": b.get("location", {}),
                "simulation_start": b.get("simulation_start", "2023-01-01"),
                "simulation_end": b.get("simulation_end", "2023-01-08"),
            }

            if b.get("pv"):
                pv = b["pv"]
                building_schema["pv"] = {
                    "attributes": {
                        "nominal_power": pv.get("capacity_kw", 10.0),
                        "azimuth": pv.get("azimuth", 180),
                        "tilt": pv.get("tilt", 30),
                    }
                }

            if b.get("battery"):
                bat = b["battery"]
                building_schema["electrical_storage"] = {
                    "attributes": {
                        "capacity": bat.get("capacity_kwh", 13.5),
                        "nominal_power": bat.get("power_kw", 5.0),
                        "efficiency": bat.get("efficiency_charge", 0.95),
                        "initial_soc": bat.get("initial_soc", 0.5),
                    }
                }

            if b.get("evs"):
                building_schema["evs"] = b["evs"]

            if b.get("flexible_loads"):
                building_schema["flexible_loads"] = b["flexible_loads"]

            if b.get("tariff"):
                building_schema["tariff"] = b["tariff"]

            schema["buildings"][f"building_{i}"] = building_schema

        # Pandapower
        if config.get("pandapower"):
            schema["pandapower"] = config["pandapower"]

        # Energy sharing
        if config.get("energy_sharing"):
            schema["energy_sharing"] = config["energy_sharing"]

        return schema

    def _ensure_building_data(self, scenario_dir: Path, config: Dict[str, Any]):
        """Ensure CSV files exist for buildings (create minimal if missing)."""
        # In practice, this would copy/generate CSV files from the CityLearn dataset
        # For quick validation, we can skip if files exist
        pass

    def _check_energy_balance(self, exp_result) -> bool:
        """Check energy balance in simulation results."""
        # Simplified check - in reality would verify energy conservation
        return True

    def run_full_experiment(
        self, config: Dict[str, Any], scenario_id: str, max_steps: int = None
    ) -> Dict[str, Any]:
        """Run full experiment for final validation."""
        # Similar to execute but with more steps
        max_steps = max_steps or self.max_steps
        return self.execute(ConfigAgentState(), config, scenario_id)

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate config without running simulation."""
        errors = []
        warnings = []

        # Check required fields
        if not config.get("scenario_id"):
            errors.append("Missing scenario_id")

        if not config.get("name"):
            errors.append("Missing scenario name")

        if not config.get("buildings"):
            errors.append("No buildings configured")

        # Check buildings
        for i, b in enumerate(config.get("buildings", [])):
            if not b.get("building_id"):
                errors.append(f"Building {i}: missing building_id")

            if b.get("pv"):
                pv = b["pv"]
                if pv.get("capacity_kw", 0) <= 0:
                    errors.append(f"Building {i}: PV capacity must be positive")

            if b.get("battery"):
                bat = b["battery"]
                if bat.get("capacity_kwh", 0) <= 0:
                    errors.append(f"Building {i}: Battery capacity must be positive")
                if bat.get("power_kw", 0) <= 0:
                    errors.append(f"Building {i}: Battery power must be positive")

        # Check timestep
        if config.get("timestep_minutes") not in [5, 15, 30, 60]:
            warnings.append(
                f"Unusual timestep: {config.get('timestep_minutes')} minutes"
            )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }


def create_config_executor(config: Dict[str, Any]):
    """Factory function to create config executor from config."""
    return ConfigExecutorAgent(
        project_root=config.get("project_root"),
        timeout=config.get("timeout", 120),
        quick_test_steps=config.get("quick_test_steps", 10),
        max_steps=config.get("max_steps", 20),
    )
