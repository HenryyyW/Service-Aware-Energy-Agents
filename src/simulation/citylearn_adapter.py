"""CityLearn v3 adapter using built-in datasets for renewable energy community simulation."""
import os
import json
import shutil
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import numpy as np
import pandas as pd
from citylearn.data import DataSet
from citylearn.citylearn import CityLearnEnv

from src.schemas.scenario import ScenarioConfig
from src.schemas.action import (
    Action, ActionType, RequestedActions, LimitedActions, AppliedActions,
    ControllerOutput, SimulationStepResult
)
from src.schemas.diagnostics import Diagnostic, DiagnosticCategory, Severity, DiagnosticReport


class CityLearnAdapter:
    """Adapter for CityLearn v3 environment using built-in datasets."""
    
    # Map scenario types to CityLearn dataset names
    DATASET_MAP = {
        "basic": "citylearn_challenge_2020_climate_zone_1",
        "with_evs": "citylearn_challenge_2022_phase_all_plus_evs",
        "demand_response": "citylearn_challenge_2022_phase_all_demand_response",
    }
    
    def __init__(self, scenario_config: ScenarioConfig, dataset_type: str = "with_evs", data_dir: Optional[str] = None):
        self.scenario_config = scenario_config
        self.dataset_type = dataset_type
        self.dataset_name = self.DATASET_MAP.get(dataset_type, "citylearn_challenge_2022_phase_all_plus_evs")
        self.data_dir = data_dir or "data"
        self.env: Optional[CityLearnEnv] = None
        self.building_ids: List[str] = []
        self.observation_names: List[str] = []
        self.action_names: List[str] = []  # All action names from schema
        self.active_action_names: List[str] = []  # Only active actions globally
        self.building_actions: Dict[str, List[str]] = {}  # Active actions per building
        self.episode_step = 0
        self.observation_history: List[Dict[str, Any]] = []
        self.action_history: List[SimulationStepResult] = []
        
        self._setup_environment()
    
    def _setup_environment(self):
        """Initialize CityLearn environment from built-in dataset."""
        # Get dataset schema
        dataset = DataSet()
        schema = dataset.get_schema(self.dataset_name)
        
        # Save original root_directory BEFORE customizing schema
        original_root_dir = Path(schema['root_directory'])
        
        # Extract active action names from schema
        self.action_names = list(schema.get('actions', {}).keys())
        self.active_action_names = [
            name for name, info in schema.get('actions', {}).items() 
            if info.get('active', False)
        ]
        print(f"All actions: {self.action_names}")
        print(f"Active actions (global): {self.active_action_names}")
        
        # Update schema with our scenario parameters
        schema = self._customize_schema(schema)
        
        # Build per-building action lists
        self._build_per_building_actions(schema)
        
        # Save schema to temp directory for CityLearn
        schema_dir = Path(self.data_dir) / "schemas" / self.scenario_config.scenario_id
        schema_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy dataset files to our schema directory (using original root dir)
        self._copy_dataset_files(schema, schema_dir, original_root_dir)
        
        # Save modified schema
        schema_path = schema_dir / "schema.json"
        with open(schema_path, "w") as f:
            json.dump(schema, f, indent=2)
        
        # DEBUG: Print schema before creating env
        print(f"DEBUG: schema root_directory = {schema.get('root_directory')}")
        for bid in schema['buildings']:
            print(f"DEBUG: {bid} energy_simulation = {schema['buildings'][bid].get('energy_simulation')}")
        
        # Initialize environment
        self.env = CityLearnEnv(schema=str(schema_path))
        
        # Get building IDs from schema (only included buildings)
        self.building_ids = [b for b in schema['buildings'].keys() if schema['buildings'][b].get('include', True)]
        
        # Get observation names from schema
        self.observation_names = list(schema.get('observations', {}).keys())
        
        print(f"Loaded CityLearn dataset: {self.dataset_name}")
        print(f"Buildings: {self.building_ids}")
        print(f"Observations: {len(self.observation_names)}")
    
    def _build_per_building_actions(self, schema: Dict[str, Any]):
        """Build action list for each building based on its devices."""
        self.building_actions = {}
        
        # Map device names to action names
        device_to_action = {
            'electrical_storage': 'electrical_storage',
            'chargers': 'electric_vehicle_storage',
            'deferrable_appliances': 'deferrable_appliance',
            'cooling_storage': 'cooling_storage',
            'heating_storage': 'heating_storage',
            'dhw_storage': 'dhw_storage',
        }
        
        # Global active actions in order
        global_active = [name for name, info in schema.get('actions', {}).items() 
                        if info.get('active', False)]
        
        for bid in self.building_ids:
            if bid in schema['buildings']:
                building_schema = schema['buildings'][bid]
                building_actions = []
                
                # Check which devices this building has
                for device, action_name in device_to_action.items():
                    if device in building_schema and action_name in global_active:
                        building_actions.append(action_name)
                
                self.building_actions[bid] = building_actions
                print(f"Building {bid} active actions: {building_actions}")
            else:
                self.building_actions[bid] = []
    
    def _customize_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Customize schema for our scenario."""
        # Update simulation parameters
        schema['random_seed'] = self.scenario_config.random_seed
        schema['seconds_per_time_step'] = self.scenario_config.timestep_minutes * 60
        schema['central_agent'] = False
        
        # Set simulation time steps (1 week default)
        timesteps_per_day = 24 * 60 // self.scenario_config.timestep_minutes
        schema['simulation_start_time_step'] = 0
        schema['simulation_end_time_step'] = 7 * timesteps_per_day - 1
        schema['episode_time_steps'] = 7 * timesteps_per_day
        
        # Update root directory to our data dir - use absolute path to avoid double resolution
        schema['root_directory'] = str(Path(self.data_dir).resolve() / "schemas" / self.scenario_config.scenario_id)
        
        # Keep only the number of buildings we need (up to 5 for scenario A)
        buildings_to_keep = {}
        for i, building_config in enumerate(self.scenario_config.buildings[:5]):
            if i < len(self.building_ids):
                old_name = self.building_ids[i]
                new_name = building_config.building_id
                if old_name in schema['buildings']:
                    buildings_to_keep[new_name] = schema['buildings'][old_name]
                    buildings_to_keep[new_name]['energy_simulation'] = f"{new_name}.csv"
        
        # If we don't have enough buildings in dataset, use what we have
        if not buildings_to_keep:
            buildings_to_keep = {k: v for k, v in list(schema['buildings'].items())[:5]}
            # Rename to match our building IDs
            renamed = {}
            for i, (old_name, building_schema) in enumerate(buildings_to_keep.items()):
                new_name = self.scenario_config.buildings[i].building_id if i < len(self.scenario_config.buildings) else f"building_{i}"
                building_schema['energy_simulation'] = f"{new_name}.csv"
                renamed[new_name] = building_schema
            buildings_to_keep = renamed
        
        schema['buildings'] = buildings_to_keep
        self.building_ids = list(buildings_to_keep.keys())
        
        return schema
    
    def _copy_dataset_files(self, schema: Dict[str, Any], schema_dir: Path, source_dir: Path):
        """Copy dataset files to our schema directory."""
        source_dir = Path(source_dir)
        
        # Copy weather file
        weather_src = source_dir / "weather.csv"
        if weather_src.exists():
            shutil.copy2(weather_src, schema_dir / "weather.csv")
        
        # Copy carbon intensity file
        ci_src = source_dir / "carbon_intensity.csv"
        if ci_src.exists():
            shutil.copy2(ci_src, schema_dir / "carbon_intensity.csv")
        
        # Copy pricing file if exists
        pricing_src = source_dir / "pricing.csv"
        if pricing_src.exists():
            shutil.copy2(pricing_src, schema_dir / "pricing.csv")
        
        # Copy building energy simulation files
        for building_name in self.building_ids:
            if building_name in schema['buildings']:
                energy_file = schema['buildings'][building_name].get('energy_simulation', f"{building_name}.csv")
                src = source_dir / energy_file
                if src.exists():
                    shutil.copy2(src, schema_dir / energy_file)
                else:
                    # Create dummy file if not found
                    self._create_dummy_energy_file(schema_dir / energy_file)
        
        # Copy charger simulation files if they exist
        for building_name in self.building_ids:
            if building_name in schema['buildings']:
                building_schema = schema['buildings'][building_name]
                if 'chargers' in building_schema:
                    for charger_name, charger_schema in building_schema['chargers'].items():
                        charger_file = charger_schema.get('charger_simulation', '')
                        if charger_file:
                            src = source_dir / charger_file
                            if src.exists():
                                shutil.copy2(src, schema_dir / charger_file)
        
        # Copy deferrable appliance files if they exist
        for building_name in self.building_ids:
            if building_name in schema['buildings']:
                building_schema = schema['buildings'][building_name]
                if 'deferrable_appliances' in building_schema:
                    for app_name, app_schema in building_schema['deferrable_appliances'].items():
                        for key in ['cycle_profiles_file', 'flexibility_schedule_file']:
                            if key in app_schema:
                                src = source_dir / app_schema[key]
                                if src.exists():
                                    shutil.copy2(src, schema_dir / app_schema[key])
    
    def _create_dummy_energy_file(self, filepath: Path):
        """Create a dummy energy simulation file with correct columns for EnergySimulation."""
        timesteps = 7 * 24 * 60 // self.scenario_config.timestep_minutes
        timestamps = pd.date_range(
            start="2023-07-01",  # Summer month to avoid heating
            periods=timesteps,
            freq=f"{self.scenario_config.timestep_minutes}min"
        )
        # Generate realistic dummy data matching EnergySimulation expected columns
        # Set all thermal demands to 0 to avoid CityLearn assertions for buildings without those devices
        data = pd.DataFrame({
            "month": timestamps.month,
            "hour": timestamps.hour,
            "day_type": (timestamps.dayofweek < 5).astype(int),
            "daylight_savings_status": 0,
            "indoor_dry_bulb_temperature": 22 + 2 * np.sin(2 * np.pi * timestamps.hour / 24) + np.random.normal(0, 1, timesteps),
            "average_unmet_cooling_setpoint_difference": np.zeros(timesteps),
            "indoor_relative_humidity": 50 + 15 * np.sin(2 * np.pi * timestamps.hour / 24) + np.random.normal(0, 3, timesteps),
            "non_shiftable_load": np.random.uniform(1, 5, timesteps),
            "dhw_demand": np.zeros(timesteps),  # No DHW demand - buildings may not have DHW devices
            "cooling_demand": np.zeros(timesteps),  # No cooling demand - buildings may not have cooling devices
            "heating_demand": np.zeros(timesteps),  # No heating demand
            "solar_generation": np.maximum(0, 5 * np.sin(2 * np.pi * (timestamps.hour - 6) / 12) + np.random.normal(0, 1, timesteps)),
        })
        data.to_csv(filepath, index=False)
    
    def _convert_observations_to_dict(self, observations) -> Dict[str, Any]:
        """Convert observations from list format to dict keyed by building_id."""
        if isinstance(observations, list):
            return {bid: obs for bid, obs in zip(self.building_ids, observations)}
        return observations
    
    def reset(self, random_seed: Optional[int] = None) -> Dict[str, Any]:
        """Reset environment and return initial observations."""
        seed = random_seed or self.scenario_config.random_seed
        result = self.env.reset(seed=seed)
        # CityLearn v3 reset returns (observations, info)
        observations = result[0] if isinstance(result, tuple) else result
        # Convert list to dict if needed
        observations = self._convert_observations_to_dict(observations)
        self.episode_step = 0
        self.observation_history = [observations]
        self.action_history = []
        return observations
    
    def step(self, requested_actions: RequestedActions) -> Tuple[Dict[str, Any], SimulationStepResult]:
        """Execute one simulation step with requested actions."""
        # Convert requested actions to CityLearn action format
        cl_actions = self._actions_to_citylearn(requested_actions)
        
        # Step environment
        result = self.env.step(cl_actions)
        # CityLearn v3 step returns (observations, rewards, terminated, truncated, info)
        if isinstance(result, tuple) and len(result) == 5:
            observations, rewards, terminated, truncated, info = result
        else:
            observations, rewards, terminated, truncated, info = result, {}, {}, {}, {}
        
        # Convert observations to dict if it's a list (one per building)
        observations = self._convert_observations_to_dict(observations)
        
        # Get limited and applied actions from info
        limited_actions = self._extract_limited_actions(info, requested_actions)
        applied_actions = self._extract_applied_actions(info, requested_actions)
        
        # Convert rewards to dict if it's a list
        if isinstance(rewards, list):
            rewards = {bid: rew for bid, rew in zip(self.building_ids, rewards)}
        elif not isinstance(rewards, dict):
            rewards = {b: rewards for b in self.building_ids}
        
        # Check if episode is done (all buildings terminated/truncated)
        done = False
        if isinstance(terminated, dict):
            done = all(terminated.values()) or all(truncated.values())
        elif isinstance(terminated, (bool, np.bool_)):
            done = terminated or truncated
        
        # Build step result
        step_result = SimulationStepResult(
            timestep=self.episode_step,
            requested_actions=requested_actions,
            limited_actions=limited_actions,
            applied_actions=applied_actions,
            observations=observations,
            rewards=rewards,
            costs=self._extract_costs(info),
            constraint_violations=self._check_constraints(requested_actions, limited_actions, applied_actions),
            terminated=done,
            truncated=False
        )
        
        self.observation_history.append(observations)
        self.action_history.append(step_result)
        self.episode_step += 1
        
        return observations, step_result
    
    def _actions_to_citylearn(self, requested: RequestedActions) -> List[List[float]]:
        """Convert RequestedActions to CityLearn action format.
        
        CityLearn expects a list of actions per building, where each building's
        action list contains only the actions for devices that building has,
        in the same order as the global active actions list.
        """
        actions = []
        for bid in self.building_ids:
            building_actions = []
            
            # Only include actions for devices this building has
            for action_name in self.building_actions.get(bid, []):
                asset_id = f"{bid}_{action_name}"
                action = requested.get_action(asset_id, ActionType.BATTERY_CHARGE)
                if action:
                    building_actions.append(action.value_kw)
                else:
                    building_actions.append(0.0)
            
            actions.append(building_actions)
        
        return actions
    
    def _extract_limited_actions(self, info: Dict, requested: RequestedActions) -> LimitedActions:
        """Extract limited actions from CityLearn info."""
        limited = LimitedActions(timestep=self.episode_step)
        for req_action in requested.actions:
            limited.actions.append(Action(
                asset_id=req_action.asset_id,
                action_type=req_action.action_type,
                value_kw=req_action.value_kw,
                timestep=req_action.timestep
            ))
        return limited
    
    def _extract_applied_actions(self, info: Dict, requested: RequestedActions) -> AppliedActions:
        """Extract actually applied actions from CityLearn info."""
        applied = AppliedActions(timestep=self.episode_step)
        for req_action in requested.actions:
            applied.actions.append(Action(
                asset_id=req_action.asset_id,
                action_type=req_action.action_type,
                value_kw=req_action.value_kw,
                timestep=req_action.timestep
            ))
        return applied
    
    def _extract_costs(self, info: Dict) -> Dict[str, float]:
        """Extract cost information from CityLearn info."""
        costs = {}
        if "cost" in info:
            if isinstance(info["cost"], dict):
                costs = info["cost"]
            else:
                costs = {b: info["cost"] for b in self.building_ids}
        return costs
    
    def _check_constraints(
        self, 
        requested: RequestedActions, 
        limited: LimitedActions, 
        applied: AppliedActions
    ) -> List[str]:
        """Check for constraint violations between requested/limited/applied."""
        violations = []
        for req in requested.actions:
            lim = limited.get_action(req.asset_id, req.action_type)
            app = applied.get_action(req.asset_id, req.action_type)
            
            if lim and abs(lim.value_kw - req.value_kw) > 0.01:
                violations.append(f"{req.asset_id}: limited from {req.value_kw:.2f} to {lim.value_kw:.2f} kW")
            
            if app and abs(app.value_kw - req.value_kw) > 0.01:
                violations.append(f"{req.asset_id}: applied {app.value_kw:.2f} vs requested {req.value_kw:.2f} kW")
        
        return violations
    
    def get_observations(self) -> Dict[str, Any]:
        """Get current observations."""
        return self.observation_history[-1] if self.observation_history else {}
    
    def get_kpis(self) -> Dict[str, float]:
        """Get KPIs from completed episode."""
        if self.env and hasattr(self.env, "kpis"):
            return self.env.kpis
        return {}
    
    def close(self):
        """Close environment."""
        if self.env:
            self.env.close()
    
    def generate_dummy_data(self, output_dir: str):
        """Generate dummy time series data for testing (already done in _copy_dataset_files)."""
        pass


def create_citylearn_adapter(scenario_config: ScenarioConfig, data_dir: str = "data") -> CityLearnAdapter:
    """Factory function to create CityLearnAdapter with appropriate dataset."""
    # Determine dataset type based on scenario features
    has_evs = any(len(b.evs) > 0 for b in scenario_config.buildings)
    has_dr = False  # Could check for DR in scenario
    
    if has_evs:
        dataset_type = "with_evs"
    elif has_dr:
        dataset_type = "demand_response"
    else:
        dataset_type = "basic"
    
    return CityLearnAdapter(scenario_config, dataset_type=dataset_type, data_dir=data_dir)