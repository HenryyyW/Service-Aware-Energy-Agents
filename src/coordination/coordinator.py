"""Main multi-agent coordinator for hierarchical coordination."""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import time

from src.coordination.base import (
    CoordinationAgent, CoordinationMessage, CoordinationPhase,
    BuildingProposal, AggregationResult, CoordinationResult
)
from src.coordination.building_agent import BuildingAgent, create_building_agents
from src.coordination.aggregator_agent import CommunityAggregator
from src.schemas.scenario import ScenarioConfig


class MultiAgentCoordinator:
    """Main coordinator for multi-agent hierarchical coordination.
    
    Orchestrates the coordination protocol:
    1. LOCAL_PROPOSAL - Building agents collect sub-agent proposals
    2. AGGREGATOR_RECONCILIATION - Community aggregator reconciles proposals
    3. GRID_VALIDATION - Validate against pandapower grid constraints
    4. FINAL_ALLOCATION - Distribute final allocations to building agents
    """
    
    def __init__(
        self, 
        scenario_config: ScenarioConfig, 
        pandapower_network=None,
        max_iterations: int = 3
    ):
        self.scenario_config = scenario_config
        self.max_iterations = max_iterations

        # Create agents
        self.building_agents = create_building_agents(scenario_config)
        self.aggregator = CommunityAggregator(scenario_config, pandapower_network)

        # Coordination state
        self.current_timestep = 0
        self.current_observations: Dict[str, Any] = {}
        self.coordination_history: List[CoordinationResult] = []
    
    def coordinate(self, observations: Dict[str, Any], timestep: int) -> CoordinationResult:
        """Run full coordination protocol for one timestep."""
        self.current_observations = observations
        self.current_timestep = timestep
        
        start_time = time.time()
        converged = False
        iterations = 0
        grid_violations = []
        
        for iteration in range(self.max_iterations):
            iterations = iteration + 1
            
            # Phase 1: Local Proposals
            building_proposals = self._collect_local_proposals()
            
            # Phase 2: Aggregator Reconciliation
            aggregation_result = self._run_aggregator_reconciliation(building_proposals)
            
            # Phase 3: Grid Validation
            grid_valid, violations = self._validate_grid(aggregation_result)
            grid_violations = violations
            
            if grid_valid:
                converged = True
                break
            
            # If not converged, iterate with adjusted constraints
            # In a full implementation, this would feed back to agents
            
        # Phase 4: Final Allocation - Send allocations to building agents and collect responses
        allocation_messages = []
        for building_id, allocation in self.aggregator.final_allocations.items():
            msg = self.aggregator.send_message(
                receiver=f"building_{building_id}",
                phase=CoordinationPhase.FINAL_ALLOCATION,
                payload={"allocation": allocation}
            )
            allocation_messages.append(msg)
        
        # Deliver allocation messages to building agents
        for msg in allocation_messages:
            building_id = msg.receiver.replace("building_", "")
            if building_id in self.building_agents:
                self.building_agents[building_id].receive(msg)
        
        # Final allocations are already stored in aggregator
        final_allocations = self.aggregator.final_allocations
        
        result = CoordinationResult(
            building_proposals=building_proposals,
            final_allocations=final_allocations,
            grid_validation_passed=grid_valid,
            grid_violations=grid_violations,
            iterations=iterations,
            converged=converged
        )
        
        self.coordination_history.append(result)
        return result
    
    def _collect_local_proposals(self) -> Dict[str, BuildingProposal]:
        """Phase 1: Collect proposals from all building agents."""
        context = {
            "observations": self.current_observations,
            "timestep": self.current_timestep,
            # Real simulation resolution: agents must not assume 15-min steps
            # (the dataset adapter overrides the scenario to hourly, and any
            # scenario may differ; the hardcoded 0.25 h/step drifted every
            # agent clock 4x off the simulator's actual departures).
            "hours_per_step": self.scenario_config.timestep_minutes / 60.0,
        }
        
        proposals = {}
        for building_id, agent in self.building_agents.items():
            message = agent.propose(context)
            proposal = message.payload.get("proposal")
            if proposal:
                proposals[building_id] = proposal
        
        return proposals
    
    def _run_aggregator_reconciliation(
        self, 
        building_proposals: Dict[str, BuildingProposal]
    ) -> AggregationResult:
        """Phase 2: Run aggregator reconciliation."""
        # Send proposals to aggregator
        for building_id, proposal in building_proposals.items():
            msg = CoordinationMessage(
                sender=f"building_{building_id}",
                receiver="community_aggregator",
                phase=CoordinationPhase.LOCAL_PROPOSAL,
                payload={"proposal": proposal, "building_id": building_id}
            )
            self.aggregator.receive(msg)
        
        # Trigger reconciliation
        self.aggregator._reconcile_proposals()
        
        return AggregationResult(
            building_allocations=self.aggregator.final_allocations,
            total_import_kw=sum(max(0, a.requested_power_kw) for a in self.aggregator.final_allocations.values()),
            total_export_kw=sum(-min(0, a.requested_power_kw) for a in self.aggregator.final_allocations.values()),
            grid_constraints_satisfied=True,  # Will be updated by validation
            adjustments_made=[]
        )
    
    def _validate_grid(self, aggregation_result: AggregationResult) -> tuple:
        """Phase 3: Validate against grid constraints."""
        if self.aggregator.pandapower_network is None:
            return True, []
        
        return self.aggregator._validate_grid()
    
    def get_actions(self) -> List:
        """Get all actions from building agents for simulation."""
        actions = []
        for agent in self.building_agents.values():
            actions.extend(agent.get_actions())
        return actions
    
    def update_state(self, observations: Dict[str, Any]):
        """Update agent states from simulation observations."""
        # Update SOCs from observations
        for building_id, agent in self.building_agents.items():
            # Battery SOC
            if agent.battery_agent:
                battery_id = agent.battery_agent.battery_id
                soc_key = f"{battery_id}_soc"
                if soc_key in observations:
                    agent.battery_agent.update_soc(observations[soc_key])
            
            # EV SOCs
            for ev_agent in agent.ev_agents:
                ev_id = ev_agent.ev_id
                soc_key = f"{ev_id}_soc"
                if soc_key in observations:
                    ev_agent.update_soc(observations[soc_key])
            
            # Flexible load progress
            for fl_agent in agent.flexible_load_agents:
                fl_id = fl_agent.asset_id
                progress_key = f"{fl_id}_progress"
                if progress_key in observations:
                    fl_agent.update_progress(observations[progress_key])
    
    def reset(self):
        """Reset all agents."""
        for agent in self.building_agents.values():
            agent.reset()
        self.aggregator.reset()
        self.coordination_history = []
        self.current_timestep = 0
        self.current_observations = {}


def create_coordinator(
    scenario_config: ScenarioConfig, 
    pandapower_network=None,
    max_iterations: int = 3
) -> MultiAgentCoordinator:
    """Factory to create multi-agent coordinator."""
    return MultiAgentCoordinator(
        scenario_config=scenario_config,
        pandapower_network=pandapower_network,
        max_iterations=max_iterations
    )