"""AgentBackend abstract interface for pluggable LLM backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, AsyncIterator
from src.schemas.scenario import ScenarioConfig
from src.schemas.action import RequestedActions, Action


@dataclass
class CostBudget:
    """Per-run cost/latency budget for LLM calls."""
    max_usd: float = 1.0
    max_latency_ms: int = 5000
    max_tokens: int = 4000
    
    # Runtime tracking
    spent_usd: float = 0.0
    spent_latency_ms: float = 0.0
    spent_tokens: int = 0


@dataclass
class BackendResponse:
    """Response from an LLM backend."""
    actions: List[Action]
    raw_output: str
    prompt_hash: str
    token_usage: Dict[str, int] = field(default_factory=dict)  # prompt, completion, total
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentBackend(ABC):
    """Abstract interface for LLM backends.
    
    All backends must implement this interface to be used by the agent controllers.
    The interface supports both sync and async operation, cost/latency tracking,
    and prompt versioning via prompt_hash.
    """
    
    @property
    @abstractmethod
    def backend_id(self) -> str:
        """Unique identifier for this backend (e.g., 'fallback', 'local_llama', 'openai_gpt4')."""
        pass
    
    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether this backend supports streaming responses."""
        pass
    
    @abstractmethod
    async def generate_actions(
        self,
        scenario: ScenarioConfig,
        observations: Dict[str, Any],
        timestep: int,
        context: Optional[Dict[str, Any]] = None,
        budget: Optional[CostBudget] = None,
    ) -> BackendResponse:
        """Generate control actions from observations.
        
        Args:
            scenario: The scenario configuration
            observations: Current observations from the simulation
            timestep: Current simulation timestep
            context: Additional context (grid diagnostics, previous actions, etc.)
            budget: Optional cost/latency budget for this call
            
        Returns:
            BackendResponse with actions, metadata, and cost/latency info
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Verify backend is available and healthy."""
        pass
    
    @abstractmethod
    def estimate_cost(self, prompt_tokens: int, max_completion_tokens: int) -> float:
        """Estimate USD cost for a request with given token counts."""
        pass
    
    def check_budget(self, budget: Optional[CostBudget]) -> Optional[str]:
        """Check if budget allows another request.
        
        Returns:
            None if budget allows, otherwise reason string for fallback.
        """
        if budget is None:
            return None
        if budget.spent_usd >= budget.max_usd:
            return f"Budget exceeded: ${budget.spent_usd:.4f} >= ${budget.max_usd:.4f}"
        if budget.spent_latency_ms >= budget.max_latency_ms:
            return f"Latency budget exceeded: {budget.spent_latency_ms:.0f}ms >= {budget.max_latency_ms}ms"
        if budget.spent_tokens >= budget.max_tokens:
            return f"Token budget exceeded: {budget.spent_tokens} >= {budget.max_tokens}"
        return None
    
    def record_usage(self, budget: Optional[CostBudget], response: BackendResponse) -> None:
        """Record usage against budget."""
        if budget is None:
            return
        budget.spent_usd += response.cost_usd
        budget.spent_latency_ms += response.latency_ms
        budget.spent_tokens += response.token_usage.get("total", 0)