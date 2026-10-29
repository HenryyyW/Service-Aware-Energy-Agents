"""Base controller classes and rule-based baseline controller."""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import numpy as np

from src.schemas.action import (
    RequestedActions, Action, ActionType, ControllerOutput
)
from src.schemas.scenario import ScenarioConfig, BuildingConfig, EVConfig, BatteryConfig


class BaseController(ABC):
    """Abstract base class for all controllers."""
    
    def __init__(self, scenario_config: ScenarioConfig):
        self.scenario_config = scenario_config
        self.building_ids = [b.building_id for b in scenario_config.buildings]
        self.timestep = 0
        self.last_grid_diagnostics: Optional[Dict[str, Any]] = None
    
    @abstractmethod
    def get_actions(self, observations: Dict[str, Any], timestep: int) -> RequestedActions:
        """Get requested actions for the current timestep."""
        pass
    
    def update_grid_diagnostics(self, grid_diagnostics: Optional[Dict[str, Any]]):
        """Update controller with grid diagnostics from previous step.
        
        Args:
            grid_diagnostics: Dictionary containing grid diagnostics from pandapower,
                            including voltage violations, line loading, etc.
        """
        self.last_grid_diagnostics = grid_diagnostics
    
    def reset(self):
        """Reset controller state."""
        self.timestep = 0
        self.last_grid_diagnostics = None
    
    def _create_requested_actions(self, actions: List[Action]) -> RequestedActions:
        """Helper to create RequestedActions from action list."""
        return RequestedActions(timestep=self.timestep, actions=actions)


class RuleBasedController(BaseController):
    """Rule-based baseline controller for renewable energy community.
    
    Rules:
    - Charge batteries when PV exceeds load, discharge when load exceeds PV
    - Charge EVs when connected and below target SOC, prioritize off-peak
    - Shift flexible loads to PV generation hours
    - Respect grid import/export limits
    """
    
    def __init__(self, scenario_config: ScenarioConfig):
        super().__init__(scenario_config)
        self.battery_soc: Dict[str, float] = {}
        self.ev_soc: Dict[str, float] = {}
        self.ev_connected: Dict[str, bool] = {}
        self.flexible_load_progress: Dict[str, float] = {}
        self._initialize_state()
    
    def _initialize_state(self):
        """Initialize controller state from scenario config."""
        for building in self.scenario_config.buildings:
            bid = building.building_id
            
            # Battery initial SOC
            if building.battery:
                self.battery_soc[f"{bid}_battery"] = building.battery.initial_soc
            
            # EV initial SOC and connection status
            for i, ev in enumerate(building.evs or []):
                ev_id = f"{bid}_ev_{i}"
                self.ev_soc[ev_id] = ev.initial_soc
                self.ev_connected[ev_id] = False
            
            # Flexible load progress
            for i, fl in enumerate(building.flexible_loads or []):
                fl_id = f"{bid}_flex_{i}"
                self.flexible_load_progress[fl_id] = 0.0
    
    def get_actions(self, observations: Dict[str, Any], timestep: int) -> RequestedActions:
        """Generate rule-based actions."""
        self.timestep = timestep
        actions = []
        
        # Get current hour for time-of-use decisions
        current_hour = (timestep * self.scenario_config.timestep_minutes) / 60
        hour_of_day = current_hour % 24
        
        for building in self.scenario_config.buildings:
            bid = building.building_id
            
            # Get observations for this building
            net_demand = observations.get(f"{bid}_net_electricity_consumption", 0)
            pv_gen = observations.get(f"{bid}_solar_generation", 0)
            load = observations.get(f"{bid}_non_shiftable_load", 0)
            
            # Battery control
            if building.battery:
                battery_action = self._control_battery(
                    bid, building.battery, net_demand, pv_gen, hour_of_day
                )
                if battery_action:
                    actions.append(battery_action)
            
            # EV control
            for i, ev in enumerate(building.evs or []):
                ev_id = f"{bid}_ev_{i}"
                ev_action = self._control_ev(ev_id, ev, net_demand, pv_gen, hour_of_day, timestep)
                if ev_action:
                    actions.append(ev_action)
            
            # Flexible load control
            for i, fl in enumerate(building.flexible_loads or []):
                fl_id = f"{bid}_flex_{i}"
                fl_action = self._control_flexible_load(fl_id, fl, pv_gen, hour_of_day, timestep)
                if fl_action:
                    actions.append(fl_action)
        
        # Apply community-level grid limits
        actions = self._apply_grid_limits(actions)
        
        return self._create_requested_actions(actions)
    
    def _control_battery(
        self, 
        bid: str, 
        battery: BatteryConfig, 
        net_demand: float, 
        pv_gen: float,
        hour_of_day: float
    ) -> Optional[Action]:
        """Control battery: charge from excess PV, discharge to meet demand."""
        battery_id = f"{bid}_battery"
        current_soc = self.battery_soc.get(battery_id, battery.initial_soc)
        capacity_kwh = battery.capacity_kwh
        max_power = battery.power_kw
        
        # Calculate available excess PV
        excess_pv = max(0, pv_gen - net_demand)
        deficit = max(0, net_demand - pv_gen)
        
        # Simple rule: charge from excess PV, discharge for deficit
        if excess_pv > 0.1 and current_soc < battery.soc_max:
            # Charge from excess PV
            charge_kw = min(excess_pv, max_power, 
                           (battery.soc_max - current_soc) * capacity_kwh)
            new_soc = current_soc + (charge_kw * battery.efficiency_charge * 
                                     self.scenario_config.timestep_minutes / 60) / capacity_kwh
            self.battery_soc[battery_id] = min(new_soc, battery.soc_max)
            return Action(
                asset_id=battery_id,
                action_type=ActionType.BATTERY_CHARGE,
                value_kw=charge_kw,
                timestep=self.timestep
            )
        
        elif deficit > 0.1 and current_soc > battery.soc_min:
            # Discharge to meet deficit
            discharge_kw = min(deficit, max_power,
                              (current_soc - battery.soc_min) * capacity_kwh)
            new_soc = current_soc - (discharge_kw * self.scenario_config.timestep_minutes / 60) / (
                capacity_kwh * battery.efficiency_discharge)
            self.battery_soc[battery_id] = max(new_soc, battery.soc_min)
            return Action(
                asset_id=battery_id,
                action_type=ActionType.BATTERY_DISCHARGE,
                value_kw=-discharge_kw,
                timestep=self.timestep
            )
        
        return None
    
    def _control_ev(
        self, 
        ev_id: str, 
        ev: EVConfig, 
        net_demand: float, 
        pv_gen: float,
        hour_of_day: float,
        timestep: int
    ) -> Optional[Action]:
        """Control EV charging: charge when connected, prioritize off-peak and PV."""
        current_soc = self.ev_soc.get(ev_id, ev.initial_soc)
        capacity_kwh = ev.capacity_kwh
        max_charge = ev.max_charge_kw
        
        # Check if EV is connected
        arrival_hour = self._time_to_hour(ev.arrival_time)
        departure_hour = self._time_to_hour(ev.departure_time)
        
        # Handle overnight case (e.g., 22:00 to 07:00)
        if departure_hour < arrival_hour:
            connected = hour_of_day >= arrival_hour or hour_of_day < departure_hour
        else:
            connected = arrival_hour <= hour_of_day < departure_hour
        
        self.ev_connected[ev_id] = connected
        
        if not connected:
            return None
        
        # Check if already at target
        if current_soc >= ev.target_soc:
            return None
        
        # Calculate time remaining until departure
        if hour_of_day < departure_hour:
            hours_remaining = departure_hour - hour_of_day
        else:
            hours_remaining = (24 - hour_of_day) + departure_hour
        
        # Energy needed
        energy_needed = (ev.target_soc - current_soc) * capacity_kwh
        required_power = energy_needed / max(hours_remaining, 0.25)
        
        # Determine charge power
        charge_kw = min(required_power, max_charge)
        
        # Prefer PV charging
        excess_pv = max(0, pv_gen - net_demand)
        if excess_pv > 0:
            charge_kw = min(charge_kw, excess_pv)
        
        # Off-peak bonus (reduce charging during peak 17-21)
        if 17 <= hour_of_day < 21:
            charge_kw *= 0.5
        
        if charge_kw > 0.1:
            new_soc = current_soc + (charge_kw * ev.efficiency * 
                                     self.scenario_config.timestep_minutes / 60) / capacity_kwh
            self.ev_soc[ev_id] = min(new_soc, 1.0)
            return Action(
                asset_id=ev_id,
                action_type=ActionType.EV_CHARGE,
                value_kw=charge_kw,
                timestep=self.timestep
            )
        
        return None
    
    def _control_flexible_load(
        self, 
        fl_id: str, 
        fl: 'FlexibleLoadConfig', 
        pv_gen: float,
        hour_of_day: float,
        timestep: int
    ) -> Optional[Action]:
        """Control flexible load: run during high PV generation."""
        progress = self.flexible_load_progress.get(fl_id, 0.0)
        
        if progress >= fl.energy_kwh:
            return None
        
        start_hour = self._time_to_hour(fl.earliest_start)
        end_hour = self._time_to_hour(fl.latest_end)
        
        # Check if within window
        if end_hour < start_hour:  # overnight
            in_window = hour_of_day >= start_hour or hour_of_day < end_hour
        else:
            in_window = start_hour <= hour_of_day < end_hour
        
        if not in_window:
            return None
        
        # Run when PV is high
        if pv_gen > fl.power_kw * 0.5:
            power_kw = fl.power_kw
            energy_this_step = power_kw * self.scenario_config.timestep_minutes / 60
            self.flexible_load_progress[fl_id] = progress + energy_this_step
            
            return Action(
                asset_id=fl_id,
                action_type=ActionType.FLEXIBLE_LOAD,
                value_kw=power_kw,
                timestep=self.timestep
            )
        
        return None
    
    def _apply_grid_limits(self, actions: List[Action]) -> List[Action]:
        """Apply community-level grid import/export limits."""
        if not self.scenario_config.community_import_limit_kw and \
           not self.scenario_config.community_export_limit_kw:
            return actions
        
        # Calculate total grid import/export from actions
        total_import = sum(a.value_kw for a in actions if a.value_kw > 0)
        total_export = sum(-a.value_kw for a in actions if a.value_kw < 0)
        
        import_limit = self.scenario_config.community_import_limit_kw or float('inf')
        export_limit = self.scenario_config.community_export_limit_kw or float('inf')
        
        # Scale down if limits exceeded
        if total_import > import_limit:
            scale = import_limit / total_import
            for a in actions:
                if a.value_kw > 0:
                    a.value_kw *= scale
        
        if total_export > export_limit:
            scale = export_limit / total_export
            for a in actions:
                if a.value_kw < 0:
                    a.value_kw *= scale
        
        return actions

    def _apply_grid_violation_redispatch(self, actions: List[Action]) -> List[Action]:
        """Re-dispatch actions based on grid violations from previous step.
        
        If voltage or line loading violations were detected, adjust battery/EV/flexible load
        actions to mitigate the violations.
        """
        if not self.last_grid_diagnostics:
            return actions
        
        diagnostics = self.last_grid_diagnostics.get("diagnostics", [])
        voltage_violated = False
        line_loading_violated = False
        transformer_loading_violated = False
        
        for d in diagnostics:
            category = d.get("category", "")
            severity = d.get("severity", "")
            if severity in ["violation", "critical"]:
                if category == "voltage":
                    voltage_violated = True
                elif category == "line_loading":
                    line_loading_violated = True
                elif category == "transformer_loading":
                    transformer_loading_violated = True
        
        # If violations detected, apply re-dispatch scaling
        if voltage_violated or line_loading_violated or transformer_loading_violated:
            # Determine scaling factor based on violation type
            if voltage_violated:
                scale = 0.85  # Reduce export/charging to raise voltage
            elif line_loading_violated:
                scale = 0.8   # Reduce power to fix line loading
            else:  # transformer_loading
                scale = 0.9
            
            # Apply scaling to controllable actions (battery, EV, flexible load)
            for a in actions:
                if a.action_type in [ActionType.BATTERY_CHARGE, ActionType.BATTERY_DISCHARGE,
                                     ActionType.EV_CHARGE, ActionType.FLEXIBLE_LOAD]:
                    a.value_kw *= scale
        
        return actions
    
    def get_actions(self, observations: Dict[str, Any], timestep: int) -> RequestedActions:
        """Generate rule-based actions with grid-aware re-dispatch."""
        self.timestep = timestep
        actions = []
        
        # Get current hour for time-of-use decisions
        current_hour = (timestep * self.scenario_config.timestep_minutes) / 60
        hour_of_day = current_hour % 24
        
        for building in self.scenario_config.buildings:
            bid = building.building_id
            
            # Get observations for this building
            net_demand = observations.get(f"{bid}_net_electricity_consumption", 0)
            pv_gen = observations.get(f"{bid}_solar_generation", 0)
            load = observations.get(f"{bid}_non_shiftable_load", 0)
            
            # Battery control
            if building.battery:
                battery_action = self._control_battery(
                    bid, building.battery, net_demand, pv_gen, hour_of_day
                )
                if battery_action:
                    actions.append(battery_action)
            
            # EV control
            for i, ev in enumerate(building.evs or []):
                ev_id = f"{bid}_ev_{i}"
                ev_action = self._control_ev(ev_id, ev, net_demand, pv_gen, hour_of_day, timestep)
                if ev_action:
                    actions.append(ev_action)
            
            # Flexible load control
            for i, fl in enumerate(building.flexible_loads or []):
                fl_id = f"{bid}_flex_{i}"
                fl_action = self._control_flexible_load(fl_id, fl, pv_gen, hour_of_day, timestep)
                if fl_action:
                    actions.append(fl_action)
        
        # Apply community-level grid limits
        actions = self._apply_grid_limits(actions)
        
        # Apply grid violation re-dispatch based on previous step diagnostics
        actions = self._apply_grid_violation_redispatch(actions)
        
        return self._create_requested_actions(actions)
    
    def _time_to_hour(self, time_str: str) -> float:
        """Convert HH:MM to hour float."""
        h, m = map(int, time_str.split(':'))
        return h + m / 60
    
    def reset(self):
        super().reset()
        self._initialize_state()


class RuleBasedControllerWithGrid(RuleBasedController):
    """Rule-based controller with explicit grid constraint awareness."""
    
    def get_actions(self, observations: Dict[str, Any], timestep: int) -> RequestedActions:
        # Get base actions
        requested = super().get_actions(observations, timestep)
        
        # Check grid diagnostics from previous step if available
        # This would be passed via observations in a real implementation
        
        return requested
# Import multi-agent controller
from src.controllers.multi_agent import MultiAgentController
from src.controllers.centralized import CentralizedController

# Import optimization / learning baselines. Kept at the bottom so the base
# classes above are defined before these modules import them.
from src.controllers.mpc import MPCController
from src.controllers.rl import QLearningController

__all__ = [
    "BaseController",
    "RuleBasedController",
    "RuleBasedControllerWithGrid",
    "MultiAgentController",
    "CentralizedController",
    "MPCController",
    "QLearningController",
]
