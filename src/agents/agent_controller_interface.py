"""Agent-Controller Interface for simulation interaction.

Defines how agents request simulations and receive observations from the environment.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from pydantic import BaseModel


class SimulationStatus(str, Enum):
    """Status of a simulation run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class SimulationRequest:
    """Request to run a simulation."""

    scenario_config: Dict[str, Any]
    controller_code: str
    controller_name: str
    max_steps: int = 100
    random_seed: int = 42
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationResult:
    """Result of a simulation run."""

    status: SimulationStatus
    steps_completed: int = 0
    observations: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    rewards: Dict[str, float] = field(default_factory=dict)
    costs: Dict[str, float] = field(default_factory=dict)
    grid_diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    error: Optional[str] = None
    sandbox_result: Optional[Dict[str, Any]] = None


class ControllerInterface(ABC):
    """Abstract interface for controller execution."""

    @abstractmethod
    def get_actions(
        self, observations: Dict[str, Any], timestep: int
    ) -> Dict[str, Any]:
        """Get actions from controller given observations.

        Args:
            observations: Current environment observations
            timestep: Current simulation timestep

        Returns:
            Dictionary of actions for each controllable asset
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset controller state."""
        pass

    @abstractmethod
    def update_grid_diagnostics(self, diagnostics: Dict[str, Any]) -> None:
        """Update controller with grid diagnostics.

        Args:
            diagnostics: Grid diagnostics from pandapower
        """
        pass


class AgentSimulationInterface(ABC):
    """Interface for agents to request simulations and receive observations."""

    @abstractmethod
    def request_simulation(self, request: SimulationRequest) -> SimulationResult:
        """Request a simulation run.

        Args:
            request: Simulation configuration and controller

        Returns:
            SimulationResult with observations, actions, and metrics
        """
        pass

    @abstractmethod
    def get_observation_space(self) -> Dict[str, Any]:
        """Get the observation space definition.

        Returns:
            Dictionary describing observation space
        """
        pass

    @abstractmethod
    def get_action_space(self) -> Dict[str, Any]:
        """Get the action space definition.

        Returns:
            Dictionary describing action space
        """
        pass


class SimulationProvider:
    """Provides simulation execution via sandbox."""

    def __init__(self, sandbox_timeout: int = 60, memory_limit_mb: int = 512):
        from src.agents.sandbox import Sandbox, validate_controller_in_sandbox

        self.sandbox_timeout = sandbox_timeout
        self.memory_limit_mb = memory_limit_mb
        self._sandbox = None

    def run_controller_simulation(
        self,
        controller_code: str,
        controller_file: str,
        scenario_config: Dict[str, Any],
        max_steps: int = 100,
    ) -> SimulationResult:
        """Run a controller in sandbox and return simulation result."""
        from src.agents.sandbox import Sandbox, validate_controller_in_sandbox

        # Convert scenario config to file path
        import tempfile
        import yaml

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(scenario_config, f)
            scenario_config_path = f.name

        try:
            # Create sandbox
            with Sandbox(
                timeout=60,
                memory_limit_mb=512,
                enable_network=False,
                enable_filesystem=False,
            ) as sandbox:
                # Write controller code
                controller_path = os.path.join(sandbox.temp_dir, "controller.py")
                os.makedirs(os.path.dirname(controller_path), exist_ok=True)
                with open(controller_path, "w") as f:
                    f.write(controller_code)

                # Validate imports and syntax
                import_result = sandbox._validate_imports(controller_code)
                if not import_result.success:
                    return SimulationResult(
                        status=SimulationStatus.FAILED,
                        error=f"Import validation failed: {import_result.error}",
                    )

                syntax_result = sandbox.validate_syntax("controller.py")
                if not syntax_result.success:
                    return SimulationResult(
                        status=SimulationStatus.FAILED,
                        error=f"Syntax error: {syntax_result.error}",
                    )

                # Run experiment
                exp_result = sandbox.run_experiment(
                    scenario_config=scenario_config_path,
                    controller_file="controller.py",
                    max_steps=100,
                )

                # Parse results
                if exp_result.success:
                    return SimulationResult(
                        status=SimulationStatus.COMPLETED,
                        steps_completed=100,  # Would parse from actual output
                        execution_time=exp_result.execution_time,
                        sandbox_result={
                            "stdout": exp_result.stdout,
                            "stderr": exp_result.stderr,
                            "tests_passed": exp_result.tests_passed,
                        },
                    )
                else:
                    return SimulationResult(
                        status=SimulationStatus.FAILED,
                        error=exp_result.error or "Unknown error",
                        execution_time=exp_result.execution_time,
                        sandbox_result={
                            "stdout": exp_result.stdout,
                            "stderr": exp_result.stderr,
                            "timed_out": exp_result.timed_out,
                        },
                    )

        except subprocess.TimeoutExpired:
            return SimulationResult(
                status=SimulationStatus.TIMEOUT, error="Simulation timed out"
            )
        except Exception as e:
            return SimulationResult(status=SimulationStatus.FAILED, error=str(e))
        finally:
            # Cleanup temp file
            try:
                os.unlink(scenario_config_path)
            except:
                pass


# Convenience function for agents
def run_controller_in_sandbox(
    controller_code: str,
    scenario_config: Dict[str, Any],
    controller_file: str = "controller.py",
    max_steps: int = 100,
    timeout: int = 60,
    memory_limit_mb: int = 512,
) -> SimulationResult:
    """Convenience function to run a controller in sandbox.

    Args:
        controller_code: Python code for the controller
        scenario_config: Scenario configuration dictionary
        controller_file: Name of controller file
        max_steps: Maximum simulation steps
        timeout: Execution timeout in seconds
        memory_limit_mb: Memory limit in MB

    Returns:
        SimulationResult with status and observations
    """
    from src.agents.sandbox import Sandbox, validate_controller_in_sandbox
    import tempfile
    import yaml
    import os

    # Write scenario config
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        import yaml

        yaml.dump(scenario_config, f)
        scenario_config_path = f.name

    try:
        with Sandbox(
            timeout=60,
            memory_limit_mb=512,
            enable_network=False,
            enable_filesystem=False,
        ) as sandbox:
            # Write controller
            controller_path = os.path.join(sandbox.temp_dir, controller_file)
            os.makedirs(os.path.dirname(controller_path), exist_ok=True)
            with open(controller_path, "w") as f:
                f.write(controller_code)

            # Validate
            import_result = sandbox._validate_imports(controller_code)
            if not import_result.success:
                return SimulationResult(
                    status=SimulationStatus.FAILED,
                    error=f"Import validation failed: {import_result.error}",
                )

            syntax_result = sandbox.validate_syntax(controller_file)
            if not syntax_result.success:
                return SimulationResult(
                    status=SimulationStatus.FAILED,
                    error=f"Syntax error: {syntax_result.error}",
                )

            # Run experiment
            exp_result = sandbox.run_experiment(
                scenario_config=scenario_config_path,
                controller_file=controller_file,
                max_steps=max_steps,
            )

            if exp_result.success:
                return SimulationResult(
                    status=SimulationStatus.COMPLETED,
                    execution_time=exp_result.execution_time,
                    sandbox_result={
                        "stdout": exp_result.stdout,
                        "stderr": exp_result.stderr,
                        "tests_passed": exp_result.tests_passed,
                    },
                )
            else:
                return SimulationResult(
                    status=SimulationStatus.FAILED,
                    error=exp_result.error or "Experiment failed",
                    execution_time=exp_result.execution_time,
                    sandbox_result={
                        "stdout": exp_result.stdout,
                        "stderr": exp_result.stderr,
                        "timed_out": exp_result.timed_out,
                    },
                )

    except subprocess.TimeoutExpired:
        return SimulationResult(
            status=SimulationStatus.TIMEOUT, error="Simulation timed out"
        )
    except Exception as e:
        return SimulationResult(status=SimulationStatus.FAILED, error=str(e))
    finally:
        try:
            os.unlink(scenario_config_path)
        except:
            pass


# Standard observation/action space definitions
STANDARD_OBSERVATION_SPACE = {
    "building_0_net_electricity_consumption": {"type": "float", "unit": "kW"},
    "building_0_solar_generation": {"type": "float", "unit": "kW"},
    "building_0_non_shiftable_load": {"type": "float", "unit": "kW"},
    "building_0_electrical_storage_soc": {
        "type": "float",
        "unit": "pu",
        "min": 0.0,
        "max": 1.0,
    },
    "building_0_hour": {"type": "int", "min": 0, "max": 23},
    "building_0_electricity_pricing": {"type": "float", "unit": "$/kWh"},
    # ... repeated for each building
    "community_import_limit_kw": {"type": "float", "unit": "kW"},
    "community_export_limit_kw": {"type": "float", "unit": "kW"},
    "grid_diagnostics": {
        "type": "dict",
        "description": "Grid diagnostics from pandapower",
    },
}

STANDARD_ACTION_SPACE = {
    "building_0_battery": {"type": "float", "unit": "kW", "min": -5.0, "max": 5.0},
    "building_0_ev_0": {"type": "float", "unit": "kW", "min": 0.0, "max": 11.0},
    "building_0_flex_0": {"type": "float", "unit": "kW", "min": 0.0, "max": 3.0},
    # ... repeated for each controllable asset
}


def get_observation_space(scenario_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate observation space from scenario config."""
    space = {}
    for building in scenario_config.get("buildings", []):
        bid = building.get("building_id", "unknown")
        space[f"{bid}_net_electricity_consumption"] = {"type": "float", "unit": "kW"}
        space[f"{bid}_solar_generation"] = {"type": "float", "unit": "kW"}
        space[f"{bid}_non_shiftable_load"] = {"type": "float", "unit": "kW"}
        if building.get("battery"):
            space[f"{bid}_electrical_storage_soc"] = {
                "type": "float",
                "unit": "pu",
                "min": 0.0,
                "max": 1.0,
            }
        space[f"{bid}_hour"] = {"type": "int", "min": 0, "max": 23}
        if building.get("tariff"):
            space[f"{bid}_electricity_pricing"] = {"type": "float", "unit": "$/kWh"}

    space["community_import_limit_kw"] = {"type": "float", "unit": "kW"}
    space["community_export_limit_kw"] = {"type": "float", "unit": "kW"}
    space["grid_diagnostics"] = {
        "type": "dict",
        "description": "Grid diagnostics from pandapower",
    }

    return space


def get_action_space(scenario_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate action space from scenario config."""
    space = {}
    for building in scenario_config.get("buildings", []):
        bid = building.get("building_id", "unknown")
        if building.get("battery"):
            power = building["battery"].get("power_kw", 5.0)
            space[f"{bid}_battery"] = {
                "type": "float",
                "unit": "kW",
                "min": -power,
                "max": power,
            }
        for i, ev in enumerate(building.get("evs", [])):
            space[f"{bid}_ev_{i}"] = {
                "type": "float",
                "unit": "kW",
                "min": 0.0,
                "max": ev.get("max_charge_kw", 11.0),
            }
        for i, fl in enumerate(building.get("flexible_loads", [])):
            space[f"{bid}_flex_{i}"] = {
                "type": "float",
                "unit": "kW",
                "min": 0.0,
                "max": fl.get("power_kw", 3.0),
            }

    return space
