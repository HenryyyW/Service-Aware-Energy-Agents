"""Fallback backend - deterministic rule-based fallback when no LLM available."""

from typing import Optional, Dict, Any, List
from src.agents.backend.interface import AgentBackend, BackendResponse, CostBudget
from src.schemas.scenario import ScenarioConfig
from src.schemas.action import Action, ActionType
from src.controllers import RuleBasedController


class FallbackBackend(AgentBackend):
    """Deterministic rule-based fallback when no LLM available.
    
    Uses the existing RuleBasedController logic internally to provide
    deterministic, zero-cost actions when no LLM backend is available.
    """
    
    backend_id = "fallback"
    supports_streaming = False
    
    def __init__(self):
        self._controller_cache: Dict[str, RuleBasedController] = {}
    
    async def generate_actions(
        self,
        scenario: ScenarioConfig,
        observations: Dict[str, Any],
        timestep: int,
        context: Optional[Dict[str, Any]] = None,
        budget: Optional["CostBudget"] = None,
    ) -> "BackendResponse":
        """Generate actions using rule-based controller."""
        # Get or create controller for this scenario
        scenario_key = scenario.scenario_id
        if scenario_key not in self._controller_cache:
            self._controller_cache[scenario_key] = RuleBasedController(scenario)
        
        controller = self._controller_cache[scenario_key]
        
        # Pass grid diagnostics if available for re-dispatch
        if context and "grid_diagnostics" in context:
            controller.update_grid_diagnostics(context["grid_diagnostics"])
        
        requested = controller.get_actions(observations, timestep)
        
        # Convert to our action format
        actions = []
        for action in requested.actions:
            # Action is already in the right format
            actions.append(action)
        
        return BackendResponse(
            actions=actions,
            raw_output="fallback",
            prompt_hash="fallback",
            token_usage={"prompt": 0, "completion": 0, "total": 0},
            latency_ms=0.0,
            cost_usd=0.0,
            metadata={"backend": "fallback", "controller": "RuleBasedController"}
        )
    
    async def health_check(self) -> bool:
        """Fallback is always healthy."""
        return True
    
    def estimate_cost(self, prompt_tokens: int, max_completion_tokens: int) -> float:
        """Fallback has zero cost."""
        return 0.0