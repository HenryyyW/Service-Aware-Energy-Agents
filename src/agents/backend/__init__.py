"""AgentBackend package - pluggable LLM backend interface for agent controllers.

This package provides a pluggable interface for LLM backends used by agent controllers.
It supports:
- FallbackBackend: Deterministic rule-based fallback (always available, zero cost)
- OllamaBackend: Local inference via Ollama (free, no API key, default model: llama3.2:3b)
- RemoteAPIBackend: Cloud APIs (OpenAI, Anthropic) with cost/latency tracking

Usage:
    from src.agents.backend import create_backend_from_config, LLMConfig
    
    # Load from environment
    config = LLMConfig()
    backend = config.create_backend()
    
    # Or create directly
    from src.agents.backend.registry import BackendRegistry
    backend = BackendRegistry.get("fallback")
    
    # Use in controller
    response = await backend.generate_actions(scenario, observations, timestep, context, budget)
"""

from src.agents.backend.interface import (
    AgentBackend,
    BackendResponse,
    CostBudget,
)
from src.agents.backend.fallback import FallbackBackend
from src.agents.backend.local import OllamaBackend
from src.agents.backend.remote import RemoteAPIBackend
from src.agents.backend.registry import (
    BackendRegistry,
    create_backend_from_config,
)
from src.agents.backend.config import (
    LLMConfig,
    load_llm_config,
    get_llm_config_for_scenario,
)
from src.agents.backend.prompts import (
    PromptTemplate,
    PROMPT_REGISTRY,
    register_prompt,
    get_prompt,
    get_prompt_hash,
    load_prompts_from_dir,
)

__all__ = [
    # Interface
    "AgentBackend",
    "BackendResponse",
    "CostBudget",
    # Backends
    "FallbackBackend",
    "OllamaBackend",
    "RemoteAPIBackend",
    # Registry & Config
    "BackendRegistry",
    "create_backend_from_config",
    "LLMConfig",
    "load_llm_config",
    "get_llm_config_for_scenario",
    # Prompts
    "PromptTemplate",
    "PROMPT_REGISTRY",
    "register_prompt",
    "get_prompt",
    "get_prompt_hash",
    "load_prompts_from_dir",
]