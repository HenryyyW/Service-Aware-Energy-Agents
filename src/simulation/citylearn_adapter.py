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
        self.device_metadata: Dict[str, Dict[str, Any]] = {}
        self.episode_step = 0
        self.observation_history: List[Dict[str, Any]] = []
        self.action_history: List[SimulationStepResult] = []
        
        self._setup_environment()
    
    def _setup_environment(self):
        """Initialize CityLearn environment from built-in dataset."""
        # Get dataset schema
        dataset = DataSet()
        schema = dataset.get_schema(self.dataset_name)
        
        # Capture dataset's native time resolution (seconds per step)
        self.dataset_seconds_per_step = int(schema.get('seconds_per_time_step', 3600))
        dataset_timestep_minutes = self.dataset_seconds_per_step // 60
        if self.scenario_config.timestep_minutes != dataset_timestep_minutes:
            print(f"[WARNING] Scenario timestep ({self.scenario_config.timestep_minutes} min) differs from dataset native resolution ({dataset_timestep_minutes} min). "
                  f"Using dataset resolution ({dataset_timestep_minutes} min) for CityLearn simulation.")
            # Override scenario timestep for this adapter to avoid resampling issues
            self.scenario_config.timestep_minutes = dataset_timestep_minutes
        
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
        
        # Capture original building IDs from dataset schema BEFORE customizing
        self.building_ids = [b for b in schema['buildings'].keys() if schema['buildings'][b].get('include', True)]
        
        # Update schema with our scenario parameters
        schema = self._customize_schema(schema)
        
        # Build per-building action lists
        self._build_per_building_actions(schema)
        
        # Save schema to a per-run directory for CityLearn. Concurrent benchmark
        # runs pass a unique SAEA_RUN_ID; otherwise all runs of one scenario
        # would write the same schema.json and race (corrupting each other).
        run_suffix = os.environ.get("SAEA_RUN_ID", "").strip()
        dir_name = run_suffix or self.scenario_config.scenario_id
        schema_dir = Path(self.data_dir) / "schemas" / dir_name
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
        
        # Get observation names from schema - ONLY ACTIVE observations
        all_observations = schema.get('observations', {})
        self.observation_names = [
            name for name, info in all_observations.items()
            if info.get('active', True)  # Default to True if 'active' not specified
        ]
        print(f"Active observations: {self.observation_names} ({len(self.observation_names)} out of {len(all_observations)})")
        
        print(f"Loaded CityLearn dataset: {self.dataset_name}")
        print(f"Buildings: {self.building_ids}")
        print(f"Observations: {len(self.observation_names)}")

        self.device_metadata = self.get_device_metadata()
    
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
        # Ensure seconds_per_time_step is stored as integer in schema
        schema['seconds_per_time_step'] = int(self.dataset_seconds_per_step)
        schema['central_agent'] = False
        
        # Ensure critical observations are active for metrics
        critical_observations = [
            'indoor_dry_bulb_temperature',
            'average_unmet_cooling_setpoint_difference',
            'indoor_relative_humidity',
            'cooling_storage_soc',
            'heating_storage_soc',
            'dhw_storage_soc',
        ]
        for obs_name in critical_observations:
            if obs_name in schema.get('observations', {}):
                schema['observations'][obs_name]['active'] = True
        
        # Set simulation time steps based on dataset resolution - ensure all values are integers
        dataset_timestep_minutes = int(self.dataset_seconds_per_step // 60)
        timesteps_per_day = int(24 * 60 // dataset_timestep_minutes)
        schema['simulation_start_time_step'] = 0
        episode_time_steps = int(7 * timesteps_per_day)
        # CityLearn terminates at time_step >= time_steps - 1.
        # Add one extra step for safety
        episode_time_steps += 1
        schema['episode_time_steps'] = int(episode_time_steps)
        schema['simulation_end_time_step'] = int(episode_time_steps - 1)
        
        # Update root directory to our data dir - use absolute path to avoid double resolution
        schema['root_directory'] = str(Path(self.data_dir).resolve() / "schemas" / self.scenario_config.scenario_id)
        
        # Keep ONLY the buildings from our scenario - no fallback to dataset buildings
        # This ensures dummy data is created for all scenario buildings
        buildings_to_keep = {}
        for i, building_config in enumerate(self.scenario_config.buildings[:5]):
            # Map scenario building to dataset building by index if available
            if i < len(self.building_ids):
                old_name = self.building_ids[i]
                new_name = building_config.building_id
                if old_name in schema['buildings']:
                    # Use dataset building config as template
                    buildings_to_keep[new_name] = schema['buildings'][old_name].copy()
                else:
                    # Dataset doesn't have enough buildings, create minimal config
                    buildings_to_keep[new_name] = {}
                # Always use our building name for energy simulation file
                buildings_to_keep[new_name]['energy_simulation'] = f"{new_name}.csv"
                # Ensure building is included
                buildings_to_keep[new_name]['include'] = True
        
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
        # Use episode_time_steps from schema to match CityLearn's expectation
        # episode_time_steps = 7 * timesteps_per_day + 1 (for safety)
        dataset_timestep_minutes = int(self.dataset_seconds_per_step // 60)
        timesteps_per_day = int(24 * 60 // dataset_timestep_minutes)
        timesteps = int(7 * timesteps_per_day + 1)  # +1 for safety to match episode_time_steps
        timestamps = pd.date_range(
            start="2023-07-01",  # Summer month to avoid heating
            periods=timesteps,
            freq=f"{self.scenario_config.timestep_minutes}min"
        )
        # Seeded generator: otherwise the synthetic load/PV trace changes on every
        # process, so two runs with the same scenario seed are not reproducible.
        rng = np.random.default_rng(self.scenario_config.random_seed)
        # Generate realistic dummy data matching EnergySimulation expected columns
        # Set all thermal demands to 0 to avoid CityLearn assertions for buildings without those devices
        data = pd.DataFrame({
            "month": timestamps.month,
            "hour": timestamps.hour,
            "day_type": (timestamps.dayofweek < 5).astype(int),
            "daylight_savings_status": 0,
            "indoor_dry_bulb_temperature": 22 + 2 * np.sin(2 * np.pi * timestamps.hour / 24) + rng.normal(0, 1, timesteps),
            "average_unmet_cooling_setpoint_difference": np.zeros(timesteps),
            "indoor_relative_humidity": 50 + 15 * np.sin(2 * np.pi * timestamps.hour / 24) + rng.normal(0, 3, timesteps),
            "non_shiftable_load": rng.uniform(1, 5, timesteps),
            "dhw_demand": np.zeros(timesteps),  # No DHW demand - buildings may not have DHW devices
            "cooling_demand": np.zeros(timesteps),  # No cooling demand - buildings may not have cooling devices
            "heating_demand": np.zeros(timesteps),  # No heating demand
            "solar_generation": np.maximum(0, 5 * np.sin(2 * np.pi * (timestamps.hour - 6) / 12) + rng.normal(0, 1, timesteps)),
        })
        data.to_csv(filepath, index=False)
    
    def _convert_observations_to_dict(self, observations) -> Dict[str, Any]:
        """Convert observations to flat dict keyed by '{building_id}_{observation_name}'."""
        if isinstance(observations, list):
            # Assume it's a list of lists, one per building, in the order of self.building_ids
            flat_obs = {}
            for bid_idx, bid in enumerate(self.building_ids):
                if bid_idx < len(observations):
                    obs_list = observations[bid_idx]
                    for i, obs_name in enumerate(self.observation_names):
                        if i < len(obs_list):
                            flat_obs[f"{bid}_{obs_name}"] = obs_list[i]
            return flat_obs
        elif isinstance(observations, dict):
            # Check if it's a dict of building_id -> list
            is_building_dict = all(
                bid in observations and isinstance(observations[bid], list)
                for bid in self.building_ids
            ) if self.building_ids else False
            if is_building_dict:
                flat_obs = {}
                for bid in self.building_ids:
                    obs_list = observations[bid]
                    for i, obs_name in enumerate(self.observation_names):
                        if i < len(obs_list):
                            flat_obs[f"{bid}_{obs_name}"] = obs_list[i]
                return flat_obs
            else:
                # Assume it's already flat
                return observations
        else:
            # Try to convert to dict if possible
            try:
                return dict(observations)
            except Exception:
                return observations
    
    def reset(self, random_seed: Optional[int] = None) -> Dict[str, Any]:
        """Reset environment and return initial observations."""
        seed = random_seed or self.scenario_config.random_seed
        result = self.env.reset(seed=seed)
        # CityLearn v3 reset returns (observations, info)
        observations = result[0] if isinstance(result, tuple) else result
        # Convert list to dict if needed
        observations = self._convert_observations_to_dict(observations)
        observations = self._enrich_electric_vehicle_observations(observations)
        observations = self._apply_tariff_pricing(observations)
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
        observations = self._enrich_electric_vehicle_observations(observations)
        observations = self._apply_tariff_pricing(observations)

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

        Controllers speak the project's action schema: ``value_kw`` is a power
        in kW and ``asset_id`` names a configured asset (``{building}_battery``,
        ``{building}_ev_{i}``, ``{building}_flex_{i}``). CityLearn instead wants
        one normalized value per *active* device, in [-1, 1], for each building.
        This method owns that translation:

        * ``{building}_battery`` -> ``electrical_storage`` (kW / nominal_power)
        * ``{building}_ev_{i}`` -> ``electric_vehicle_storage``
          (kW / max charging or discharging power)
        * ``{building}_flex_{i}`` -> ``deferrable_appliance`` (fraction of the
          appliance's cycle energy, so any positive kW clamps to 1.0)

        Controllers that emit CityLearn-shaped ids
        (``{building}_electrical_storage`` etc.) are accepted too. Without device
        metadata the raw value is passed through, which keeps the low-level
        adapter tests usable.
        """
        metadata = getattr(self, "device_metadata", None) or {}
        actions = []
        for bid in self.building_ids:
            building_actions = []
            for action_name in self.building_actions.get(bid, []):
                action = self._find_action(requested, bid, action_name)
                if action is None:
                    building_actions.append(0.0)
                else:
                    building_actions.append(
                        self._to_normalized_action(bid, action_name, action.value_kw, metadata)
                    )
            actions.append(building_actions)
        return actions

    @staticmethod
    def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
        return max(low, min(high, float(value)))

    def _find_action(self, requested: RequestedActions, bid: str, action_name: str) -> Optional[Action]:
        """Find the controller action for a CityLearn action name.

        Matches both the CityLearn-shaped asset id and the ids used by the
        configured-asset controllers (battery / ev / flex). Asset ids are unique
        per building and device, so no action_type filter is applied;
        ``ActionSet.get_action`` would filter on the type and silently drop
        actions.
        """
        aliases = [f"{bid}_{action_name}"]
        if action_name == "electrical_storage":
            aliases.append(f"{bid}_battery")
        elif action_name == "electric_vehicle_storage":
            aliases.extend([f"{bid}_ev_0", f"{bid}_ev"])
        elif action_name == "deferrable_appliance":
            aliases.extend([f"{bid}_flex_0", f"{bid}_flex"])

        for alias in aliases:
            for action in requested.actions:
                if action.asset_id == alias:
                    return action
        return None

    def _to_normalized_action(
        self,
        bid: str,
        action_name: str,
        value_kw: float,
        metadata: Dict[str, Dict[str, Any]],
    ) -> float:
        """Map a requested power (kW) to CityLearn's normalized device action."""
        building_meta = metadata.get(bid) or {}
        if action_name == "electrical_storage":
            battery = building_meta.get("battery") or {}
            power = float(battery.get("power_kw") or 0.0)
            return self._clamp(value_kw / power) if power > 0.0 else self._clamp(value_kw)

        if action_name == "electric_vehicle_storage":
            chargers = building_meta.get("chargers") or []
            max_charge = max((float(c.get("max_charge_kw") or 0.0) for c in chargers), default=0.0)
            max_discharge = max((float(c.get("max_discharge_kw") or 0.0) for c in chargers), default=0.0)
            if value_kw >= 0.0 and max_charge > 0.0:
                return self._clamp(value_kw / max_charge)
            if value_kw < 0.0 and max_discharge > 0.0:
                return -self._clamp(-value_kw / max_discharge)
            return self._clamp(value_kw)

        if action_name == "deferrable_appliance":
            return self._clamp(value_kw, 0.0, 1.0)

        return self._clamp(value_kw)

    def get_device_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Live device ratings for every configured building.

        Controllers must not size actions from the scenario YAML: the adapter
        builds the CityLearn schema from a dataset template, so the simulated
        battery/charger ratings are what the simulator will actually accept.
        """
        metadata: Dict[str, Dict[str, Any]] = {}
        if self.env is None:
            return metadata
        hours_per_step = float(getattr(self, "dataset_seconds_per_step", 3600)) / 3600.0
        for bid, building in zip(self.building_ids, self.env.buildings):
            battery = getattr(building, "electrical_storage", None)
            battery_meta = None
            if battery is not None:
                battery_meta = {
                    "capacity_kwh": float(getattr(battery, "capacity", 0.0) or 0.0),
                    "power_kw": float(getattr(battery, "nominal_power", 0.0) or 0.0),
                    "efficiency": float(getattr(battery, "efficiency", 1.0) or 1.0),
                }
            chargers = []
            for charger in getattr(building, "electric_vehicle_chargers", None) or []:
                chargers.append({
                    "charger_id": str(getattr(charger, "charger_id", "")),
                    "max_charge_kw": float(getattr(charger, "max_charging_power", 0.0) or 0.0),
                    "min_charge_kw": float(getattr(charger, "min_charging_power", 0.0) or 0.0),
                    "max_discharge_kw": float(getattr(charger, "max_discharging_power", 0.0) or 0.0),
                    "efficiency": float(getattr(charger, "efficiency", 1.0) or 1.0),
                })
            deferrable = [
                {"power_kw": float(getattr(appliance, "nominal_power", 0.0) or 0.0)}
                for appliance in getattr(building, "deferrable_appliances", None) or []
            ]
            pv = getattr(building, "pv", None)
            metadata[bid] = {
                "battery": battery_meta,
                "chargers": chargers,
                "deferrable": deferrable,
                "pv_kw": float(getattr(pv, "nominal_power", 0.0) or 0.0) if pv else 0.0,
                "hours_per_step": hours_per_step,
            }
        return metadata

    def _enrich_electric_vehicle_observations(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Add unambiguous EV state keys.

        The stock dataset observation names for chargers do not line up with the
        underlying arrays (``*_at_charger_soc`` can carry battery capacity,
        ``*_battery_capacity`` can carry hours-to-departure), so these keys are
        derived from the live charger devices instead.
        """
        if self.env is None:
            return observations
        for bid, building in zip(self.building_ids, self.env.buildings):
            chargers = getattr(building, "electric_vehicle_chargers", None) or []
            for index, charger in enumerate(chargers):
                prefix = f"{bid}_ev_{index}"
                simulation = getattr(charger, "charger_simulation", None)
                vehicle = getattr(charger, "connected_electric_vehicle", None)
                connected = vehicle is not None
                observations[f"{prefix}_connected"] = 1.0 if connected else 0.0
                if vehicle is not None:
                    battery = vehicle.battery
                    step = int(getattr(building, "time_step", 0) or 0)
                    soc_series = getattr(battery, "soc", None)
                    if soc_series is not None and len(soc_series) > step:
                        soc = float(soc_series[step] or 0.0)
                    else:
                        soc = 0.0
                    capacity = float(getattr(battery, "capacity", 0.0) or 0.0)
                    observations[f"{prefix}_soc"] = soc
                    observations[f"{prefix}_capacity_kwh"] = capacity
                    observations[f"{prefix}_energy_kwh"] = soc * capacity
                if simulation is not None:
                    step = int(getattr(building, "time_step", 0) or 0)
                    departure = getattr(simulation, "electric_vehicle_departure_time", None)
                    required = getattr(simulation, "electric_vehicle_required_soc_departure", None)
                    if departure is not None and len(departure) > step:
                        observations[f"{prefix}_hours_to_departure"] = float(departure[step])
                    if required is not None and len(required) > step:
                        observations[f"{prefix}_required_soc"] = float(required[step])
                observations[f"{prefix}_max_charge_kw"] = float(
                    getattr(charger, "max_charging_power", 0.0) or 0.0
                )
                observations[f"{prefix}_min_charge_kw"] = float(
                    getattr(charger, "min_charging_power", 0.0) or 0.0
                )
        return observations

    @staticmethod
    def _tariff_period(hour: int) -> str:
        """TOU period used by the scenario tariff and the metric code."""
        if hour < 7 or hour >= 23:
            return "off_peak"
        if hour < 12 or (18 <= hour < 21):
            return "mid_peak"
        return "on_peak"

    def _tariff_price(self, building, hour: int, is_import: bool) -> Optional[float]:
        tariff = getattr(building, "tariff", None)
        if tariff is None:
            return None
        prices = getattr(tariff, "import_prices" if is_import else "export_prices", None) or {}
        if not prices:
            return None
        return float(prices.get(self._tariff_period(hour), 0.0))

    def _apply_tariff_pricing(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Publish the scenario tariff as the price observation.

        CityLearn datasets ship their own ``pricing.csv``; the scenario YAML
        tariff is what the cost metrics and settlement use. Without this
        override, controllers optimise a price that the evaluation does not
        charge (the two differ by roughly 2x on scenario A).
        """
        for building in self.scenario_config.buildings:
            hour = int(observations.get(f"{building.building_id}_hour", 0)) % 24
            price = self._tariff_price(building, hour, is_import=True)
            if price is not None:
                observations[f"{building.building_id}_electricity_pricing"] = price
        return observations

    def _extract_limited_actions(self, info: Dict, requested: RequestedActions) -> LimitedActions:
        """Extract limited actions from CityLearn info."""
        limited = LimitedActions(timestep=self.episode_step)
        if 'limited_actions' in info and info['limited_actions'] is not None:
            # info['limited_actions'] is a list of lists, one per building, in the order of self.building_ids
            for bid_idx, bid in enumerate(self.building_ids):
                if bid_idx < len(info['limited_actions']):
                    limited_action_values = info['limited_actions'][bid_idx]
                    # For each action in the building's active actions
                    for act_idx, action_name in enumerate(self.building_actions.get(bid, [])):
                        if act_idx < len(limited_action_values):
                            asset_id = f"{bid}_{action_name}"
                            # Try to get the action_type from the requested actions for this asset_id
                            action_obj = requested.get_action(asset_id, None)
                            action_type = action_obj.action_type if action_obj is not None else ActionType.BATTERY_CHARGE
                            limited.actions.append(Action(
                                asset_id=asset_id,
                                action_type=action_type,
                                value_kw=float(limited_action_values[act_idx]),
                                timestep=self.episode_step
                            ))
        else:
            # Fallback to requested actions
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
        if 'applied_actions' in info and info['applied_actions'] is not None:
            # info['applied_actions'] is a list of lists, one per building, in the order of self.building_ids
            for bid_idx, bid in enumerate(self.building_ids):
                if bid_idx < len(info['applied_actions']):
                    applied_action_values = info['applied_actions'][bid_idx]
                    # For each action in the building's active actions
                    for act_idx, action_name in enumerate(self.building_actions.get(bid, [])):
                        if act_idx < len(applied_action_values):
                            asset_id = f"{bid}_{action_name}"
                            # Try to get the action_type from the requested actions for this asset_id
                            action_obj = requested.get_action(asset_id, None)
                            action_type = action_obj.action_type if action_obj is not None else ActionType.BATTERY_CHARGE
                            applied.actions.append(Action(
                                asset_id=asset_id,
                                action_type=action_type,
                                value_kw=float(applied_action_values[act_idx]),
                                timestep=self.episode_step
                            ))
        else:
            # Fallback to requested actions
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
        else:
            # Debug: print info keys if cost not found
            print("!!! COST NOT FOUND IN INFO !!!")
            print("Info keys:", list(info.keys()))
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