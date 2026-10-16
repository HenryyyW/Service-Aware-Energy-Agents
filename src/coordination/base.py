"""Base classes for multi-agent coordination."""
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from pydantic import BaseModel


class CoordinationPhase(str, Enum):
    """Phases of the coordination protocol."""
    LOCAL_PROPOSAL = "local_proposal"
    AGGREGATOR_RECONCILIATION = "aggregator_reconciliation"
    GRID_VALIDATION = "grid_validation"
    FINAL_ALLOCATION = "final_allocation"
    COMPLETE = "complete"


class CoordinationMessage(BaseModel):
    """Message passed between coordination agents."""
    sender: str
    receiver: str
    phase: CoordinationPhase
    payload: Dict[str, Any]
    timestamp: float = 0.0
    message_id: str = ""


class CoordinationAgent(ABC):
    """Base class for all coordination agents."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.message_history: List[CoordinationMessage] = []
    
    @abstractmethod
    def propose(self, context: Dict[str, Any]) -> CoordinationMessage:
        """Generate a local proposal."""
        pass
    
    @abstractmethod
    def receive(self, message: CoordinationMessage) -> Optional[CoordinationMessage]:
        """Receive and process a message."""
        pass
    
    def send_message(self, receiver: str, phase: CoordinationPhase, payload: Dict[str, Any]) -> CoordinationMessage:
        """Create a coordination message."""
        import time
        import uuid
        msg = CoordinationMessage(
            sender=self.agent_id,
            receiver=receiver,
            phase=phase,
            payload=payload,
            timestamp=time.time(),
            message_id=str(uuid.uuid4())[:8]
        )
        self.message_history.append(msg)
        return msg
    
    def reset(self):
        """Reset agent state."""
        self.message_history = []


@dataclass
class Proposal:
    """Base proposal from an agent."""
    agent_id: str
    asset_id: str
    requested_power_kw: float  # positive = consume, negative = generate
    priority: float = 1.0  # higher = more important
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BuildingProposal(Proposal):
    """Proposal from a building agent."""
    building_id: str = ""  # Default to allow dataclass inheritance
    battery_proposal: Optional[Proposal] = None
    ev_proposals: List[Proposal] = field(default_factory=list)
    flexible_load_proposals: List[Proposal] = field(default_factory=list)
    net_demand_kw: float = 0.0
    pv_generation_kw: float = 0.0


@dataclass
class BatteryProposal(Proposal):
    """Proposal from a battery agent."""
    battery_id: str = ""
    current_soc: float = 0.0
    target_soc: float = 0.0
    max_charge_kw: float = 0.0
    max_discharge_kw: float = 0.0


@dataclass
class EVProposal(Proposal):
    """Proposal from an EV agent."""
    ev_id: str = ""
    current_soc: float = 0.0
    target_soc: float = 0.0
    departure_deadline: float = 0.0
    max_charge_kw: float = 0.0
    connected: bool = False


@dataclass
class AggregationResult:
    """Result of aggregator reconciliation."""
    building_allocations: Dict[str, BuildingProposal]
    total_import_kw: float
    total_export_kw: float
    grid_constraints_satisfied: bool
    adjustments_made: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CoordinationResult:
    """Final result of multi-agent coordination."""
    building_proposals: Dict[str, BuildingProposal]
    final_allocations: Dict[str, BuildingProposal]
    grid_validation_passed: bool
    grid_violations: List[Dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    converged: bool = False