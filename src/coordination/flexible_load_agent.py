"""Flexible load coordination agent."""
from typing import Optional, List, Dict, Any

from src.coordination.base import (
    CoordinationAgent, CoordinationMessage, CoordinationPhase,
    Proposal
)
from src.schemas.scenario import FlexibleLoadConfig
from src.schemas.action import Action, ActionType


class FlexibleLoadAgent(CoordinationAgent):
    """Flexible load coordination agent.
    
    Responsible for:
    - Proposing flexible load operation within time window
    - Tracking progress towards energy target
    - Preferring operation during high PV generation
    """
    
    def __init__(self, asset_id: str, flexible_load_config: FlexibleLoadConfig):
        super().__init__(asset_id)
        self.asset_id = asset_id
        self.config = flexible_load_config
        
        # State
        self.current_progress = 0.0  # kWh delivered so far
        self.last_action: Optional[Action] = None
    
    def _time_to_hour(self, time_str: str) -> float:
        """Convert HH:MM to hour float."""
        h, m = map(int, time_str.split(':'))
        return h + m / 60
    
    def _in_window(self, hour_of_day: float) -> bool:
        """Check if current hour is within flexible load window."""
        start_hour = self._time_to_hour(self.config.earliest_start)
        end_hour = self._time_to_hour(self.config.latest_end)
        
        if end_hour < start_hour:  # overnight
            return hour_of_day >= start_hour or hour_of_day < end_hour
        else:
            return start_hour <= hour_of_day < end_hour
    
    def propose(self, context: Dict[str, Any]) -> CoordinationMessage:
        """Propose flexible load operation."""
        observations = context.get("observations", {})
        timestep = context.get("timestep", 0)
        pv_generation = context.get("pv_generation", 0)
        
        # Calculate current hour
        hours_per_step = float(context.get("hours_per_step", 0.25))
        hour_of_day = (timestep * hours_per_step) % 24
        
        # Check if within operating window
        in_window = self._in_window(hour_of_day)
        
        # Check progress
        if self.current_progress >= self.config.energy_kwh:
            in_window = False
        
        requested_power = 0.0
        
        if in_window:
            # Prefer to run when PV is high
            if pv_generation > self.config.power_kw * 0.5:
                requested_power = self.config.power_kw
            # Also run if deadline approaching and not enough progress
            elif self.current_progress < self.config.energy_kwh * 0.5:
                requested_power = self.config.power_kw
        
        proposal = Proposal(
            agent_id=self.agent_id,
            asset_id=self.asset_id,
            requested_power_kw=requested_power,
            priority=0.5,  # Lower priority than battery/EV
            constraints={
                "max_power": self.config.power_kw,
                "energy_required": self.config.energy_kwh,
                "progress": self.current_progress,
                "remaining_energy": max(0, self.config.energy_kwh - self.current_progress)
            }
        )
        
        return self.send_message(
            receiver=f"building_{self.asset_id.split('_')[1]}",
            phase=CoordinationPhase.LOCAL_PROPOSAL,
            payload={"proposal": proposal}
        )
    
    def receive(self, message: CoordinationMessage) -> Optional[CoordinationMessage]:
        """Receive final allocation from building agent."""
        if message.phase == CoordinationPhase.FINAL_ALLOCATION:
            allocation = message.payload.get("allocation")
            if allocation and allocation.asset_id == self.asset_id:
                # Update progress
                self.current_progress = allocation.constraints.get("progress", self.current_progress)
                
                # Create action for simulation
                if allocation.requested_power_kw > 0:
                    self.last_action = Action(
                        asset_id=self.asset_id,
                        action_type=ActionType.FLEXIBLE_LOAD,
                        value_kw=allocation.requested_power_kw,
                        timestep=0  # Will be set by controller
                    )
        return None
    
    def get_actions(self) -> List[Action]:
        """Get action for simulation."""
        if self.last_action:
            return [self.last_action]
        return []
    
    def update_progress(self, energy_delivered: float):
        """Update progress from simulation."""
        self.current_progress += energy_delivered
    
    def reset(self):
        super().reset()
        self.current_progress = 0.0
        self.last_action = None