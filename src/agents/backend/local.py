"""Ollama local LLM backend - for Ollama local inference (free, no API key).

This backend uses a local Ollama server running at LLM_LOCAL_ENDPOINT (default http://localhost:11434)
with the model specified by LLM_LOCAL_MODEL. Supports backend selection via AGENT_BACKEND=ollama:<model>.
"""

import asyncio
import json
import os
import time
from typing import Optional, Dict, Any, List
import aiohttp

from src.agents.backend.interface import AgentBackend, BackendResponse, CostBudget
from src.schemas.scenario import ScenarioConfig
from src.schemas.action import Action


class OllamaBackend(AgentBackend):
    """Ollama local LLM backend - free local inference with no API key required.
    
    Expects a local Ollama server running at LLM_LOCAL_ENDPOINT (default http://localhost:11434)
    with the model specified by LLM_LOCAL_MODEL (default: qwen2.5-coder:7b).
    
    Backend selection: AGENT_BACKEND=ollama:<model_name>
    - AGENT_BACKEND=ollama:qwen2.5-coder:7b (recommended default - code generation optimized)
    - AGENT_BACKEND=ollama:llama3.2:3b
    - AGENT_BACKEND=ollama:qwen:latest
    - etc.
    """
    
    backend_id = "ollama"
    supports_streaming = True
    
    # Recommended default model (available on this machine, optimized for code generation)
    DEFAULT_MODEL = "qwen2.5-coder:7b"
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        prompt_template_id: Optional[str] = None,
    ):
        self.endpoint = endpoint or os.getenv("LLM_LOCAL_ENDPOINT", "http://localhost:11434")
        # Default to recommended model if not specified
        self.model = model or os.getenv("LLM_LOCAL_MODEL", self.DEFAULT_MODEL)
        self.prompt_template_id = prompt_template_id or os.getenv("LLM_PROMPT_TEMPLATE", "llm_agent_v1")
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def generate_actions(
        self,
        scenario: "ScenarioConfig",
        observations: Dict[str, Any],
        timestep: int,
        context: Optional[Dict[str, Any]] = None,
        budget: Optional["CostBudget"] = None,
    ) -> "BackendResponse":
        """Generate actions by calling local LLM."""
        start_time = time.time()
        
        # Build prompt using template
        from src.agents.backend.prompts import PROMPT_REGISTRY
        prompt_template = PROMPT_REGISTRY.get(self.prompt_template_id)
        if not prompt_template:
            raise ValueError(f"Prompt template {self.prompt_template_id} not found")
        
        # Build context for prompt
        prompt_context = self._build_prompt_context(scenario, observations, timestep, context)
        user_prompt = prompt_template.render(**prompt_context)
        
        # Prepare request
        payload = {
            "model": self.model,
            "prompt": f"{prompt_template.system_prompt}\n\n{user_prompt}",
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 2048,
            }
        }
        
        session = await self._get_session()
        url = f"{self.endpoint}/api/generate"
        
        try:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Local LLM API error {response.status}: {error_text}")
                
                result = await response.json()
                raw_output = result.get("response", "")
                
        except Exception as e:
            raise RuntimeError(f"Local LLM request failed: {e}")
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Parse actions from response
        actions = self._parse_actions(raw_output)
        
        # Estimate tokens (rough approximation)
        prompt_tokens = len(payload["prompt"]) // 4
        completion_tokens = len(raw_output) // 4
        
        return BackendResponse(
            actions=actions,
            raw_output=raw_output,
            prompt_hash=self._get_prompt_hash(),
            token_usage={
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "total": prompt_tokens + completion_tokens
            },
            latency_ms=latency_ms,
            cost_usd=0.0,  # Local inference has no API cost
            metadata={
                "backend": "ollama",
                "model": self.model,
                "prompt_template": self.prompt_template_id
            }
        )
    
    def _build_prompt_context(
        self,
        scenario: "ScenarioConfig",
        observations: Dict[str, Any],
        timestep: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build context dictionary for prompt template."""
        # Summarize observations for prompt
        building_summaries = []
        for bid in scenario.buildings:
            bid_str = bid.building_id
            building_summaries.append({
                "building_id": bid_str,
                "net_demand_kw": observations.get(f"{bid_str}_net_electricity_consumption", 0),
                "solar_generation_kw": observations.get(f"{bid_str}_solar_generation", 0),
                "battery_soc": observations.get(f"{bid_str}_electrical_storage_soc", 0.5),
            })
        
        # Grid diagnostics if available
        grid_diag = None
        if context and "grid_diagnostics" in context:
            grid_diag = context["grid_diagnostics"]
        
        return {
            "scenario_id": scenario.scenario_id,
            "timestep": timestep,
            "buildings": building_summaries,
            "grid_diagnostics": grid_diag,
            "community_import_limit_kw": scenario.community_import_limit_kw,
            "community_export_limit_kw": scenario.community_export_limit_kw,
        }
    
    def _parse_actions(self, raw_output: str) -> List:
        """Parse LLM output into Action objects.
        
        Expected format: JSON with actions array or structured text.
        For now, return empty list - implement proper parsing based on prompt format.
        """
        # TODO: Implement proper action parsing from LLM output
        # For now, return empty list - fallback will handle
        return []
    
    def _get_prompt_hash(self) -> str:
        """Get hash of current prompt template."""
        from src.agents.backend.prompts import PROMPT_REGISTRY
        prompt_template = PROMPT_REGISTRY.get(self.prompt_template_id)
        if prompt_template:
            return prompt_template.prompt_hash
        return "unknown"
    
    async def health_check(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.endpoint}/api/tags") as response:
                return response.status == 200
        except Exception:
            return False
    
    def estimate_cost(self, prompt_tokens: int, max_completion_tokens: int) -> float:
        """Local inference has zero marginal cost."""
        return 0.0