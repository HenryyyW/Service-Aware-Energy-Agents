"""Centralized controller for energy community coordination."""
from typing import Optional, List, Dict, Any

from src.controllers import BaseController
from src.schemas.action import RequestedActions, Action, ActionType
from src.schemas.scenario import ScenarioConfig, BuildingConfig, BatteryConfig, EVConfig, FlexibleLoadConfig


class CentralizedController(BaseController):
    """Centralized controller for renewable energy community.
    
    Unlike the rule-based controller which makes decentralized decisions,
    this controller considers the entire community state when making decisions.
    It still uses rule-based logic but applies it with community-level awareness.
    """
    
    def __init__(self, scenario_config: ScenarioConfig):
        super().__init__(scenario_config)
        self.battery_soc: Dict[str, float] = {}
        self.ev_soc: Dict[str, float] = {}
        self.ev_connected: Dict[str, bool] = {}
        self.flexible_load_progress: Dict[str, float] = {}
        self._initialize_state()
        
        # Community-level tracking for better coordination
        self.community_pv_total: float = 0.0
        self.community_load_total: float = 0.0
        self.community_net_demand: float = 0.0
    
    def _initialize_state(self):
        """Initialize controller state from scenario config."""
        for building in self.scenario_config.buildings:
            bid = building.building_id
            
            # Battery initial SOC
            if building.battery:
                self.battery_soc[f"{bid}_battery"] = building.battery.initial_soc
            
            # EV initial SOC and connection status
            for i, ev in enumerate(building.evs):
                ev_id = f"{bid}_ev_{i}"
                self.ev_soc[ev_id] = ev.initial_soc
                self.ev_connected[ev_id] = False
            
            # Flexible load progress
            for i, fl in enumerate(building.flexible_loads):
                fl_id = f"{bid}_flex_{i}"
                self.flexible_load_progress[fl_id] = 0.0
    
    def get_actions(self, observations: Dict[str, Any], timestep: int) -> RequestedActions:
        """Generate centralized actions considering community state."""
        self.timestep = timestep
        actions = []
        
        # Calculate community-level totals for better coordination
        self._compute_community_totals(observations)
        
        # Get current hour for time-of-use decisions
        current_hour = (timestep * self.scenario_config.timestep_minutes) / 60
        hour_of_day = current_hour % 24
        
        # Determine community PV availability (for better coordination)
        community_has_excess_pv = self.community_pv_total > self.community_load_total
        
        for building in self.scenario_config.buildings:
            bid = building.building_id
            
            # Get observations for this building
            net_demand = observations.get(f"{bid}_net_electricity_consumption", 0)
            pv_gen = observations.get(f"{bid}_solar_generation", 0)
            load = observations.get(f"{bid}_non_shiftable_load", 0)
            
            # Battery control with community awareness
            if building.battery:
                battery_action = self._control_battery_centralized(
                    bid, building.battery, net_demand, pv_gen, hour_of_day,
                    community_has_excess_pv
                )
                if battery_action:
                    actions.append(battery_action)
            
            # EV control with community awareness
            for i, ev in enumerate(building.evs):
                ev_id = f"{bid}_ev_{i}"
                ev_action = self._control_ev_centralized(
                    ev_id, ev, net_demand, pv_gen, hour_of_day, timestep,
                    community_has_excess_pv
                )
                if ev_action:
                    actions.append(ev_action)
            
            # Flexible load control with community awareness
            for i, fl in enumerate(building.flexible_loads):
                fl_id = f"{bid}_flex_{i}"
                fl_action = self._control_flexible_load_centralized(
                    fl_id, fl, pv_gen, hour_of_day, timestep,
                    community_has_excess_pv
                )
                if fl_action:
                    actions.append(fl_action)
        
        # Apply community-level grid limits
        actions = self._apply_grid_limits(actions)
        
        return self._create_requested_actions(actions)
    
    def _compute_community_totals(self, observations: Dict[str, Any]):
        """Compute community-level totals for better coordination."""
        pv_total = 0.0
        load_total = 0.0
        
        for building in self.scenario_config.buildings:
            bid = building.building_id
            pv_gen = observations.get(f"{bid}_solar_generation", 0)
            load = observations.get(f"{bid}_non_shiftable_load", 0)
            pv_total += pv_gen
            load_total += load
        
        self.community_pv_total = pv_total
        self.community_load_total = load_total
        self.community_net_demand = load_total - pv_total
    
    def _control_battery_centralized(
        self, 
        bid: str, 
        battery: BatteryConfig, 
        net_demand: float, 
        pv_gen: float,
        hour_of_day: float,
        community_has_excess_pv: bool
    ) -> Optional[Action]:
        """Control battery with community-level awareness."""
        battery_id = f"{bid}_battery"
        current_soc = self.battery_soc.get(battery_id, battery.initial_soc)
        capacity_kwh = battery.capacity_kwh
        max_power = battery.power_kw
        
        # Calculate available excess PV
        excess_pv = max(0, pv_gen - net_demand)
        deficit = max(0, net_demand - pv_gen)
        
        # Community-aware charging/discharging logic
        if community_has_excess_pv:
            # Community has excess PV - prefer charging batteries to store excess
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
        else:
            # Community has deficit - prefer discharging batteries to meet demand
            if deficit > 0.1 and current_soc > battery.soc_min:
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
    
    def _control_ev_centralized(
        self, 
        ev_id: str, 
        ev: EVConfig, 
        net_demand: float, 
        pv_gen: float,
        hour_of_day: float,
        timestep: int,
        community_has_excess_pv: bool
    ) -> Optional[Action]:
        """Control EV charging with community-level awareness."""
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
        
        # Community-aware charging: prefer PV charging when community has excess
        if community_has_excess_pv:
            excess_pv = max(0, pv_gen - net_demand)
            if excess_pv > 0:
                charge_kw = min(charge_kw, excess_pv)
        else:
            # Community has deficit - still charge EV if needed, but be more conservative
            if charge_kw > 0.5:  # Only allow significant charging if really needed
                charge_kw *= 0.7  # Reduce charging rate to help community deficit
        
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
    
    def _control_flexible_load_centralized(
        self, 
        fl_id: str, 
        fl: 'FlexibleLoadConfig', 
        pv_gen: float,
        hour_of_day: float,
        timestep: int,
        community_has_excess_pv: bool
    ) -> Optional[Action]:
        """Control flexible load with community-level awareness."""
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
        
        # Community-aware flexible load scheduling
        if community_has_excess_pv:
            # Community has excess PV - more likely to run flexible loads
            if pv_gen > fl.power_kw * 0.3:  # Lower threshold when community has excess
                power_kw = fl.power_kw
                energy_this_step = power_kw * self.scenario_config.timestep_minutes / 60
                self.flexible_load_progress[fl_id] = progress + energy_this_step
                
                return Action(
                    asset_id=fl_id,
                    action_type=ActionType.FLEXIBLE_LOAD,
                    value_kw=power_kw,
                    timestep=self.timestep
                )
        else:
            # Community has deficit - only run flexible loads if absolutely necessary
            # and if we have sufficient PV
            if pv_gen > fl.power_kw * 0.7:  # Higher threshold when community has deficit
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
    
    def _time_to_hour(self, time_str: str) -> float:
        """Convert HH:MM to hour float."""
        h, m = map(int, time_str.split(':'))
        return h + m / 60
    
    def reset(self):
        super().reset()
        self._initialize_state()
        self.community_pv_total = 0.0
        self.community_load_total = 0.0
        self.community_net_demand = 0.0