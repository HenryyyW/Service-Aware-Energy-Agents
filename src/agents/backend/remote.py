"""Remote API backend - for OpenAI, Anthropic, and other cloud LLM providers."""

import asyncio
import json
import os
import time
from typing import Optional, Dict, Any, List
import aiohttp

from src.agents.backend.interface import AgentBackend, BackendResponse, CostBudget
from src.schemas.scenario import ScenarioConfig
from src.schemas.action import Action


class RemoteAPIBackend(AgentBackend):
    """Remote API backend for cloud LLM providers (OpenAI, Anthropic, etc.)."""
    
    # Model pricing in USD per 1M tokens
    MODEL_PRICING = {
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.6},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
    }
    
    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        prompt_template_id: Optional[str] = None,
    ):
        self.provider = provider.lower()
        self.model = model or os.getenv("LLM_MODEL", "gpt-4-turbo")
        self.prompt_template_id = prompt_template_id or os.getenv("LLM_PROMPT_TEMPLATE", "llm_agent_v1")
        
        # Set API key based on provider
        if self.provider == "openai":
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.endpoint = endpoint or "https://api.openai.com/v1"
        elif self.provider == "anthropic":
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            self.endpoint = endpoint or "https://api.anthropic.com/v1"
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        
        if not self.api_key:
            raise ValueError(f"API key required for {provider} backend")
        
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def backend_id(self) -> str:
        return f"{self.provider}_{self.model.replace('.', '_').replace('-', '_')}"
    
    @property
    def supports_streaming(self) -> bool:
        return True
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            if self.provider == "anthropic":
                headers["anthropic-version"] = "2023-06-01"
            self._session = aiohttp.ClientSession(headers=headers)
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
        """Generate actions by calling remote LLM API."""
        start_time = time.time()
        
        # Check budget
        if budget:
            budget_ok = True  # Will check after getting token estimates
        
        # Build prompt
        from src.agents.backend.prompts import PROMPT_REGISTRY
        prompt_template = PROMPT_REGISTRY.get(self.prompt_template_id)
        if not prompt_template:
            raise ValueError(f"Prompt template {self.prompt_template_id} not found")
        
        prompt_context = self._build_prompt_context(scenario, observations, timestep, context)
        user_prompt = prompt_template.render(**self._build_prompt_context(scenario, observations, timestep, context))
        
        # Call appropriate provider
        if self.provider == "openai":
            response = await self._call_openai(prompt_template.system_prompt, user_prompt)
        elif self.provider == "anthropic":
            response = await self._call_anthropic(prompt_template.system_prompt, user_prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Parse response
        raw_output = self._extract_response(response)
        actions = self._parse_actions(raw_output)
        
        # Calculate cost
        prompt_tokens = response.get("usage", {}).get("prompt_tokens", 0)
        completion_tokens = response.get("usage", {}).get("completion_tokens", 0)
        cost_usd = self._calculate_cost(prompt_tokens, completion_tokens)
        
        return BackendResponse(
            actions=actions,
            raw_output=raw_output,
            prompt_hash=self._get_prompt_hash(),
            token_usage={
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "total": prompt_tokens + completion_tokens
            },
            latency_ms=(time.time() - start_time) * 1000,
            cost_usd=cost_usd,
            metadata={
                "backend": self.backend_id,
                "provider": self.provider,
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
        """Build context for prompt template (same as local backend)."""
        from src.agents.backend.local import LocalLLMBackend
        # Reuse the same context building logic
        local_backend = LocalLLMBackend()
        return local_backend._build_prompt_context(scenario, observations, timestep, context)
    
    def _parse_actions(self, raw_output: str) -> List:
        """Parse LLM output into Action objects."""
        # TODO: Implement proper action parsing
        return []
    
    def _get_prompt_hash(self) -> str:
        from src.agents.backend.prompts import PROMPT_REGISTRY
        prompt_template = PROMPT_REGISTRY.get(self.prompt_template_id)
        return prompt_template.prompt_hash if prompt_template else "unknown"
    
    async def _call_openai(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call OpenAI Chat Completions API."""
        session = await self._get_session()
        url = f"{self.endpoint}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
        }
        
        async with self._session.post(url, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"OpenAI API error {response.status}: {error_text}")
            return await response.json()
    
    async def _call_anthropic(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call Anthropic Messages API."""
        session = await self._get_session()
        url = f"{self.endpoint}/messages"
        
        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": 0.2,
            "max_tokens": 2048,
        }
        
        async with self._session.post(url, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"Anthropic API error {response.status}: {error_text}")
            return await response.json()
    
    def _extract_response(self, response: Dict[str, Any]) -> str:
        """Extract text content from provider response."""
        if self.provider == "openai":
            return response["choices"][0]["message"]["content"]
        elif self.provider == "anthropic":
            return response["content"][0]["text"]
        return ""
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost in USD based on model pricing."""
        pricing = self.MODEL_PRICING.get(self.model, {"input": 0, "output": 0})
        cost = (prompt_tokens / 1_000_000) * pricing["input"] + (completion_tokens / 1_000_000) * pricing["output"]
        return cost
    
    def _get_prompt_hash(self) -> str:
        from src.agents.backend.prompts import PROMPT_REGISTRY
        prompt_template = PROMPT_REGISTRY.get(self.prompt_template_id)
        return prompt_template.prompt_hash if prompt_template else "unknown"
    
    async def health_check(self) -> bool:
        """Check if remote API is reachable."""
        try:
            session = await self._get_session()
            if self.provider == "openai":
                async with session.get(f"{self.endpoint}/models") as response:
                    return response.status == 200
            elif self.provider == "anthropic":
                # Anthropic doesn't have a simple health endpoint
                return True
        except Exception:
            return False
        return False
    
    def estimate_cost(self, prompt_tokens: int, max_completion_tokens: int) -> float:
        """Estimate cost for a request."""
        pricing = self.MODEL_PRICING.get(self.model, {"input": 0, "output": 0})
        return (prompt_tokens / 1_000_000) * pricing["input"] + (max_completion_tokens / 1_000_000) * pricing["output"]