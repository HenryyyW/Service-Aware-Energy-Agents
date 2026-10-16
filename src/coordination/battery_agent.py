"""Battery coordination agent."""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from src.coordination.base import (
    CoordinationAgent, CoordinationMessage, CoordinationPhase,
    Proposal, BatteryProposal
)
from src.schemas.scenario import BatteryConfig
from src.schemas.action import Action, ActionType


class BatteryAgent(CoordinationAgent):
    """Battery coordination agent.
    
    Responsible for:
    - Proposing battery charge/discharge based on net demand and PV
    - Managing SOC within limits
    - Responding to grid signals (voltage, frequency)
    """
    
    def __init__(self, battery_id: str, battery_config: BatteryConfig):
        super().__init__(battery_id)
        self.battery_id = battery_id
        self.config = battery_config
        
        # State
        self.current_soc = battery_config.initial_soc
        self.target_soc = battery_config.initial_soc
        self.last_action: Optional[Action] = None
    
    def propose(self, context: Dict[str, Any]) -> CoordinationMessage:
        """Propose battery operation based on net demand and PV."""
        observations = context.get("observations", {})
        timestep = context.get("timestep", 0)
        net_demand = context.get("building_net_demand", 0)
        pv_generation = context.get("pv_generation", 0)
        
        # Calculate excess PV and deficit
        excess_pv = max(0, pv_generation - net_demand)
        deficit = max(0, net_demand - pv_generation)
        
        # Determine desired action
        requested_power = 0.0
        action_type = ActionType.BATTERY_CHARGE
        
        if excess_pv > 0.1 and self.current_soc < self.config.soc_max:
            # Charge from excess PV
            max_charge = min(
                excess_pv,
                self.config.power_kw,
                (self.config.soc_max - self.current_soc) * self.config.capacity_kwh
            )
            requested_power = max_charge
            action_type = ActionType.BATTERY_CHARGE
            self.target_soc = min(
                self.current_soc + (max_charge * self.config.efficiency_charge * 0.25) / self.config.capacity_kwh,
                self.config.soc_max
            )
        elif deficit > 0.1 and self.current_soc > self.config.soc_min:
            # Discharge to meet deficit
            max_discharge = min(
                deficit,
                self.config.power_kw,
                (self.current_soc - self.config.soc_min) * self.config.capacity_kwh
            )
            requested_power = -max_discharge  # Negative = discharge (generate)
            action_type = ActionType.BATTERY_DISCHARGE
            self.target_soc = max(
                self.current_soc - (max_discharge * 0.25) / (self.config.capacity_kwh * self.config.efficiency_discharge),
                self.config.soc_min
            )
        
        proposal = BatteryProposal(
            agent_id=self.agent_id,
            asset_id=self.battery_id,
            requested_power_kw=requested_power,
            priority=1.5,  # High priority - batteries are flexible
            constraints={
                "soc_min": self.config.soc_min,
                "soc_max": self.config.soc_max,
                "power_kw": self.config.power_kw,
                "capacity_kwh": self.config.capacity_kwh,
                "efficiency_charge": self.config.efficiency_charge,
                "efficiency_discharge": self.config.efficiency_discharge
            },
            battery_id=self.battery_id,
            current_soc=self.current_soc,
            target_soc=self.target_soc,
            max_charge_kw=self.config.power_kw,
            max_discharge_kw=self.config.power_kw
        )
        
        return self.send_message(
            receiver=f"building_{self.battery_id.split('_')[1]}",
            phase=CoordinationPhase.LOCAL_PROPOSAL,
            payload={"proposal": proposal}
        )
    
    def receive(self, message: CoordinationMessage) -> Optional[CoordinationMessage]:
        """Receive final allocation from building agent."""
        if message.phase == CoordinationPhase.FINAL_ALLOCATION:
            allocation = message.payload.get("allocation")
            if allocation and allocation.battery_id == self.battery_id:
                # Update target SOC based on allocation
                self.target_soc = allocation.target_soc
                
                # Create action for simulation
                if allocation.requested_power_kw > 0:
                    self.last_action = Action(
                        asset_id=self.battery_id,
                        action_type=ActionType.BATTERY_CHARGE,
                        value_kw=allocation.requested_power_kw,
                        timestep=0  # Will be set by controller
                    )
                elif allocation.requested_power_kw < 0:
                    self.last_action = Action(
                        asset_id=self.battery_id,
                        action_type=ActionType.BATTERY_DISCHARGE,
                        value_kw=allocation.requested_power_kw,
                        timestep=0
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
        self.target_soc = self.config.initial_soc
        self.last_action = None