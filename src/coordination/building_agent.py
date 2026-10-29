"""Building agent for multi-agent coordination."""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from src.coordination.base import (
    CoordinationAgent, CoordinationMessage, CoordinationPhase,
    BuildingProposal, Proposal
)
from src.schemas.scenario import BuildingConfig, BatteryConfig, EVConfig, FlexibleLoadConfig
from src.schemas.action import Action, ActionType


class BuildingAgent(CoordinationAgent):
    """Building-level coordination agent.
    
    Responsible for:
    - Collecting proposals from battery, EV, and flexible load sub-agents
    - Aggregating into a building-level net demand
    - Submitting building proposal to community aggregator
    """
    
    def __init__(
        self, 
        building_id: str, 
        building_config: BuildingConfig,
        battery_agent: 'BatteryAgent' = None,
        ev_agents: List['EVAgent'] = None,
        flexible_load_agents: List['FlexibleLoadAgent'] = None
    ):
        super().__init__(f"building_{building_id}")
        self.building_id = building_id
        self.building_config = building_config
        self.battery_agent = battery_agent
        self.ev_agents = ev_agents or []
        self.flexible_load_agents = flexible_load_agents or []
        
        # Internal state
        self.current_observations: Dict[str, Any] = {}
        self.current_timestep = 0
        
        # Create sub-agents if not provided
        if self.battery_agent is None and building_config.battery:
            from src.coordination.battery_agent import BatteryAgent
            self.battery_agent = BatteryAgent(
                f"{building_id}_battery", building_config.battery
            )
        
        if not self.ev_agents and building_config.evs:
            from src.coordination.ev_agent import EVAgent
            self.ev_agents = [
                EVAgent(f"{building_id}_ev_{i}", ev_config)
                for i, ev_config in enumerate(building_config.evs or [])
            ]
        
        if not self.flexible_load_agents and building_config.flexible_loads:
            from src.coordination.flexible_load_agent import FlexibleLoadAgent
            self.flexible_load_agents = [
                FlexibleLoadAgent(f"{building_id}_flex_{i}", fl_config)
                for i, fl_config in enumerate(building_config.flexible_loads or [])
            ]
    
    def propose(self, context: Dict[str, Any]) -> CoordinationMessage:
        """Generate building-level proposal by collecting sub-agent proposals."""
        self.current_observations = context.get("observations", {})
        self.current_timestep = context.get("timestep", 0)
        
        # Extract building-level observations
        net_demand = self.current_observations.get(
            f"{self.building_id}_net_electricity_consumption", 0
        )
        pv_generation = self.current_observations.get(
            f"{self.building_id}_solar_generation", 0
        )
        
        # Collect battery proposal
        battery_proposal = None
        if self.battery_agent:
            battery_ctx = {
                "observations": self.current_observations,
                "timestep": self.current_timestep,
                "building_net_demand": net_demand,
                "pv_generation": pv_generation,
                "hours_per_step": context.get("hours_per_step", 0.25),
            }
            battery_msg = self.battery_agent.propose(battery_ctx)
            battery_proposal = battery_msg.payload.get("proposal")
        
        # Collect EV proposals
        ev_proposals = []
        for ev_agent in self.ev_agents:
            ev_ctx = {
                "observations": self.current_observations,
                "timestep": self.current_timestep,
                "building_net_demand": net_demand,
                "pv_generation": pv_generation,
                "hours_per_step": context.get("hours_per_step", 0.25),
            }
            ev_msg = ev_agent.propose(ev_ctx)
            ev_proposal = ev_msg.payload.get("proposal")
            if ev_proposal:
                ev_proposals.append(ev_proposal)
        
        # Collect flexible load proposals
        flex_proposals = []
        for fl_agent in self.flexible_load_agents:
            fl_ctx = {
                "observations": self.current_observations,
                "timestep": self.current_timestep,
                "pv_generation": pv_generation,
                "hours_per_step": context.get("hours_per_step", 0.25),
            }
            fl_msg = fl_agent.propose(fl_ctx)
            fl_proposal = fl_msg.payload.get("proposal")
            if fl_proposal:
                flex_proposals.append(fl_proposal)
        
        # Calculate net demand from proposals
        battery_power = battery_proposal.requested_power_kw if battery_proposal else 0
        ev_power = sum(p.requested_power_kw for p in ev_proposals)
        flex_power = sum(p.requested_power_kw for p in flex_proposals)
        
        # Net demand = load - PV + battery + EV + flexible
        # Note: battery positive = charge (consume), negative = discharge (generate)
        # EV positive = charge (consume)
        # Flexible positive = consume
        net_from_assets = battery_power + ev_power + flex_power
        
        building_proposal = BuildingProposal(
            agent_id=self.agent_id,
            asset_id=self.building_id,
            building_id=self.building_id,
            requested_power_kw=net_demand + net_from_assets,  # Total building grid import
            priority=1.0,
            constraints={},
            battery_proposal=battery_proposal,
            ev_proposals=ev_proposals,
            flexible_load_proposals=flex_proposals,
            net_demand_kw=net_demand,
            pv_generation_kw=pv_generation
        )
        
        return self.send_message(
            receiver="community_aggregator",
            phase=CoordinationPhase.LOCAL_PROPOSAL,
            payload={"proposal": building_proposal, "building_id": self.building_id}
        )
    
    def receive(self, message: CoordinationMessage) -> Optional[CoordinationMessage]:
        """Receive allocation from aggregator and distribute to sub-agents."""
        if message.phase == CoordinationPhase.FINAL_ALLOCATION:
            allocation = message.payload.get("allocation")
            if allocation and allocation.building_id == self.building_id:
                # Distribute to sub-agents
                if self.battery_agent and allocation.battery_proposal:
                    self.battery_agent.receive(CoordinationMessage(
                        sender=self.agent_id,
                        receiver=self.battery_agent.agent_id,
                        phase=CoordinationPhase.FINAL_ALLOCATION,
                        payload={"allocation": allocation.battery_proposal}
                    ))
                
                for i, ev_proposal in enumerate(allocation.ev_proposals):
                    if i < len(self.ev_agents):
                        self.ev_agents[i].receive(CoordinationMessage(
                            sender=self.agent_id,
                            receiver=self.ev_agents[i].agent_id,
                            phase=CoordinationPhase.FINAL_ALLOCATION,
                            payload={"allocation": ev_proposal}
                        ))
                
                for i, fl_proposal in enumerate(allocation.flexible_load_proposals):
                    if i < len(self.flexible_load_agents):
                        self.flexible_load_agents[i].receive(CoordinationMessage(
                            sender=self.agent_id,
                            receiver=self.flexible_load_agents[i].agent_id,
                            phase=CoordinationPhase.FINAL_ALLOCATION,
                            payload={"allocation": fl_proposal}
                        ))
        
        return None
    
    def get_actions(self) -> List[Action]:
        """Convert final allocations to actions for simulation."""
        actions = []
        
        # Get actions from sub-agents
        if self.battery_agent:
            actions.extend(self.battery_agent.get_actions())
        
        for ev_agent in self.ev_agents:
            actions.extend(ev_agent.get_actions())
        
        for fl_agent in self.flexible_load_agents:
            actions.extend(fl_agent.get_actions())
        
        return actions
    
    def reset(self):
        super().reset()
        if self.battery_agent:
            self.battery_agent.reset()
        for ev_agent in self.ev_agents:
            ev_agent.reset()
        for fl_agent in self.flexible_load_agents:
            fl_agent.reset()


class FlexibleLoadAgent(CoordinationAgent):
    """Flexible load coordination agent."""
    
    def __init__(self, asset_id: str, flexible_load_config: FlexibleLoadConfig):
        super().__init__(asset_id)
        self.asset_id = asset_id
        self.config = flexible_load_config
        self.current_progress = 0.0
        self.current_soc = 0.0
    
    def propose(self, context: Dict[str, Any]) -> CoordinationMessage:
        """Propose flexible load operation."""
        observations = context.get("observations", {})
        timestep = context.get("timestep", 0)
        pv_generation = context.get("pv_generation", 0)
        
        # Check if within operating window
        from src.controllers import RuleBasedController
        controller = RuleBasedController.__new__(RuleBasedController)
        hours_per_step = float(context.get("hours_per_step", 0.25))
        hour_of_day = (timestep * hours_per_step) % 24
        
        start_hour = controller._time_to_hour(self.config.earliest_start)
        end_hour = controller._time_to_hour(self.config.latest_end)
        
        if end_hour < start_hour:  # overnight
            in_window = hour_of_day >= start_hour or hour_of_day < end_hour
        else:
            in_window = start_hour <= hour_of_day < end_hour
        
        # Check progress
        if self.current_progress >= self.config.energy_kwh:
            in_window = False
        
        requested_power = 0.0
        if in_window and pv_generation > self.config.power_kw * 0.5:
            requested_power = self.config.power_kw
        
        proposal = Proposal(
            agent_id=self.agent_id,
            asset_id=self.asset_id,
            requested_power_kw=requested_power,
            priority=0.5,  # Lower priority than battery/EV
            constraints={
                "max_power": self.config.power_kw,
                "energy_required": self.config.energy_kwh,
                "progress": self.current_progress
            }
        )
        
        return self.send_message(
            receiver=f"building_{self.asset_id.split('_')[1]}",
            phase=CoordinationPhase.LOCAL_PROPOSAL,
            payload={"proposal": proposal}
        )
    
    def receive(self, message: CoordinationMessage) -> Optional[CoordinationMessage]:
        if message.phase == CoordinationPhase.FINAL_ALLOCATION:
            allocation = message.payload.get("allocation")
            if allocation:
                self.current_progress = allocation.constraints.get("progress", 0)
        return None
    
    def get_actions(self) -> List[Action]:
        # Convert allocation to action
        if self.current_progress > 0:
            return [Action(
                asset_id=self.asset_id,
                action_type=ActionType.FLEXIBLE_LOAD,
                value_kw=self.config.power_kw,
                timestep=0
            )]
        return []


def create_building_agents(scenario_config) -> Dict[str, BuildingAgent]:
    """Factory to create building agents from scenario config."""
    agents = {}
    for building in scenario_config.buildings:
        agents[building.building_id] = BuildingAgent(
            building.building_id, building
        )
    return agents