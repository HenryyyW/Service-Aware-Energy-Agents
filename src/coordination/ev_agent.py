"""EV coordination agent."""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from src.coordination.base import (
    CoordinationAgent, CoordinationMessage, CoordinationPhase,
    Proposal, EVProposal
)
from src.schemas.scenario import EVConfig
from src.schemas.action import Action, ActionType


class EVAgent(CoordinationAgent):
    """EV coordination agent.
    
    Responsible for:
    - Proposing EV charging based on departure deadline and SOC target
    - Managing charging schedule
    - Responding to grid signals (price, voltage)
    """
    
    def __init__(self, ev_id: str, ev_config: EVConfig):
        super().__init__(ev_id)
        self.ev_id = ev_id
        self.config = ev_config
        
        # State
        self.current_soc = ev_config.initial_soc
        self.target_soc = ev_config.target_soc
        self.connected = False
        self.last_action: Optional[Action] = None
    
    def _time_to_hour(self, time_str: str) -> float:
        """Convert HH:MM to hour float."""
        h, m = map(int, time_str.split(':'))
        return h + m / 60
    
    def _is_connected(self, hour_of_day: float) -> bool:
        """Check if EV is connected at given hour."""
        arrival_hour = self._time_to_hour(self.config.arrival_time)
        departure_hour = self._time_to_hour(self.config.departure_time)
        
        if departure_hour < arrival_hour:  # overnight
            return hour_of_day >= arrival_hour or hour_of_day < departure_hour
        else:
            return arrival_hour <= hour_of_day < departure_hour
    
    def _hours_until_departure(self, hour_of_day: float) -> float:
        """Calculate hours until departure."""
        departure_hour = self._time_to_hour(self.config.departure_time)
        
        if hour_of_day < departure_hour:
            return departure_hour - hour_of_day
        else:
            return (24 - hour_of_day) + departure_hour
    
    def propose(self, context: Dict[str, Any]) -> CoordinationMessage:
        """Propose EV charging based on deadline and SOC."""
        observations = context.get("observations", {})
        timestep = context.get("timestep", 0)
        net_demand = context.get("building_net_demand", 0)
        pv_generation = context.get("pv_generation", 0)
        
        # Calculate current hour
        hour_of_day = (timestep * 0.25) % 24  # assuming 15-min steps
        
        # Check connection
        self.connected = self._is_connected(hour_of_day)
        
        requested_power = 0.0
        
        if self.connected and self.current_soc < self.config.target_soc:
            # Calculate time remaining
            hours_remaining = self._hours_until_departure(hour_of_day)
            
            # Energy needed
            energy_needed = (self.config.target_soc - self.current_soc) * self.config.capacity_kwh
            required_power = energy_needed / max(hours_remaining, 0.25)
            
            # Determine charge power
            charge_kw = min(required_power, self.config.max_charge_kw)
            
            # Prefer PV charging
            excess_pv = max(0, pv_generation - net_demand)
            if excess_pv > 0:
                charge_kw = min(charge_kw, excess_pv)
            
            # Off-peak preference (reduce during peak 17-21)
            if 17 <= hour_of_day < 21:
                charge_kw *= 0.5
            
            # Ensure minimum charging if deadline approaching
            if hours_remaining < 2 and charge_kw < self.config.max_charge_kw * 0.5:
                charge_kw = self.config.max_charge_kw * 0.8
            
            if charge_kw > 0.1:
                requested_power = charge_kw
        
        proposal = EVProposal(
            agent_id=self.agent_id,
            asset_id=self.ev_id,
            requested_power_kw=requested_power,
            priority=1.8,  # Highest priority - deadlines are hard constraints
            constraints={
                "max_charge_kw": self.config.max_charge_kw,
                "capacity_kwh": self.config.capacity_kwh,
                "efficiency": self.config.efficiency,
                "target_soc": self.config.target_soc,
                "deadline_hours": self._hours_until_departure(hour_of_day) if self.connected else 0
            },
            ev_id=self.ev_id,
            current_soc=self.current_soc,
            target_soc=self.config.target_soc,
            departure_deadline=self._hours_until_departure(hour_of_day) if self.connected else 0,
            max_charge_kw=self.config.max_charge_kw,
            connected=self.connected
        )
        
        return self.send_message(
            receiver=f"building_{self.ev_id.split('_')[1]}",
            phase=CoordinationPhase.LOCAL_PROPOSAL,
            payload={"proposal": proposal}
        )
    
    def receive(self, message: CoordinationMessage) -> Optional[CoordinationMessage]:
        """Receive final allocation from building agent."""
        if message.phase == CoordinationPhase.FINAL_ALLOCATION:
            allocation = message.payload.get("allocation")
            if allocation and allocation.ev_id == self.ev_id:
                # Create action for simulation
                if allocation.requested_power_kw > 0:
                    self.last_action = Action(
                        asset_id=self.ev_id,
                        action_type=ActionType.EV_CHARGE,
                        value_kw=allocation.requested_power_kw,
                        timestep=0  # Will be set by controller
                    )
        return None
    
    def get_actions(self) -> List[Action]:
        """Get action for simulation."""
        if self.last_action:
            return [self.last_action]
        return []
    
    def update_soc(self, new_soc: float):
        """Update SOC from simulation."""
        self.current_soc = new_soc
    
    def reset(self):
        super().reset()
        self.current_soc = self.config.initial_soc
        self.connected = False
        self.last_action = None