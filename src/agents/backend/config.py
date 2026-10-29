"""Configuration loading for LLM backends from environment variables."""

import os
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class LLMConfig:
    """Configuration for LLM backend from environment variables."""
    
    # Backend selection - supports AGENT_BACKEND=ollama:<model>
    _backend_raw: str = field(default_factory=lambda: os.getenv("AGENT_BACKEND", os.getenv("LLM_BACKEND", "fallback")))
    
    @property
    def backend(self) -> str:
        """Parse backend from AGENT_BACKEND env var (supports ollama:<model>)."""
        raw = self._backend_raw
        if raw.startswith("ollama:"):
            return "ollama"
        return raw
    
    @backend.setter
    def backend(self, value: str):
        self._backend_raw = value
    
    @property
    def ollama_model(self) -> Optional[str]:
        """Extract model from AGENT_BACKEND=ollama:<model> format."""
        raw = self._backend_raw
        if raw.startswith("ollama:"):
            return raw.split(":", 1)[1]
        return None
    
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4-turbo"))
    prompt_template_id: str = field(default_factory=lambda: os.getenv("LLM_PROMPT_TEMPLATE", "llm_agent_v1"))
    
    # API Keys (NEVER have defaults - must be provided at runtime)
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    anthropic_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    
    # Local LLM settings
    local_endpoint: str = field(default_factory=lambda: os.getenv("LLM_LOCAL_ENDPOINT", "http://localhost:11434"))
    local_model: str = field(default_factory=lambda: os.getenv("LLM_LOCAL_MODEL", "llama3.2:3b"))
    
    # Budget limits
    max_usd: float = field(default_factory=lambda: float(os.getenv("LLM_MAX_USD", "1.00")))
    max_latency_ms: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_LATENCY_MS", "5000")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "4000")))
    
    # Provider-specific settings
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))
    endpoint: Optional[str] = field(default_factory=lambda: os.getenv("LLM_ENDPOINT"))
    
    # Fallback behavior
    fallback_on_error: bool = field(default_factory=lambda: os.getenv("LLM_FALLBACK_ON_ERROR", "true").lower() == "true")
    fallback_on_budget_exceeded: bool = field(default_factory=lambda: os.getenv("LLM_FALLBACK_ON_BUDGET", "true").lower() == "true")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding API keys for logging)."""
        return {
            "backend": self.backend,
            "model": self.model,
            "prompt_template_id": self.prompt_template_id,
            "local_endpoint": self.local_endpoint,
            "local_model": self.local_model,
            "max_usd": self.max_usd,
            "max_latency_ms": self.max_latency_ms,
            "max_tokens": self.max_tokens,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "fallback_on_error": self.fallback_on_error,
            "fallback_on_budget_exceeded": self.fallback_on_budget_exceeded,
        }
    
    def validate(self) -> List[str]:
        """Return list of validation errors."""
        errors = []
        
        valid_backends = ["fallback", "ollama", "openai_gpt4", "anthropic_claude"]
        if self.backend not in valid_backends:
            errors.append(f"Invalid backend: {self.backend}. Must be one of {valid_backends}")
        
        if self.backend in ("openai_gpt4", "openai_gpt4_turbo", "openai_gpt4o", "openai_gpt4o_mini") and not self.openai_api_key:
            errors.append("OPENAI_API_KEY required for OpenAI backend")
        
        if self.backend in ("anthropic_claude", "anthropic_claude_sonnet", "anthropic_claude_opus", "anthropic_claude_haiku") and not self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY required for Anthropic backend")
        
        if self.backend == "ollama":
            # Ollama backend doesn't require API key
            pass
        
        if self.max_usd <= 0:
            errors.append("LLM_MAX_USD must be positive")
        
        if self.max_latency_ms <= 0:
            errors.append("LLM_MAX_LATENCY_MS must be positive")
        
        if self.max_tokens <= 0:
            errors.append("LLM_MAX_TOKENS must be positive")
        
        return errors
    
    def create_cost_budget(self) -> "CostBudget":
        """Create a CostBudget from this config."""
        from src.agents.backend.interface import CostBudget
        return CostBudget(
            max_usd=self.max_usd,
            max_latency_ms=self.max_latency_ms,
            max_tokens=self.max_tokens,
        )
    
    def create_backend(self):
        """Create a backend instance from this config."""
        from src.agents.backend.registry import create_backend_from_config
        
        config = {
            "backend": self.backend,
            "model": self.model,
            "prompt_template": self.prompt_template_id,
            "endpoint": self.endpoint,
            "local_endpoint": self.local_endpoint,
            "local_model": self.local_model,
            "openai_api_key": self.openai_api_key,
            "anthropic_api_key": self.anthropic_api_key,
            "max_usd": self.max_usd,
            "max_latency_ms": self.max_latency_ms,
            "max_tokens": self.max_tokens,
            "provider": self.provider,
        }
        
        return create_backend_from_config(config)


def load_llm_config() -> LLMConfig:
    """Load LLM configuration from environment variables."""
    return LLMConfig()


def get_llm_config_for_scenario(scenario_id: str) -> "LLMConfig":
    """Get LLM config, potentially with scenario-specific overrides.
    
    Looks for environment variables prefixed with SCENARIO_{SCENARIO_ID}_LLM_
    """
    config = LLMConfig()
    
    # Check for scenario-specific overrides
    prefix = f"SCENARIO_{scenario_id.upper()}_LLM_"
    
    # Override backend if specified
    if os.getenv(f"{prefix}BACKEND"):
        config._backend_raw = os.getenv(f"{prefix}BACKEND")
    
    # Override model
    if os.getenv(f"{prefix}MODEL"):
        config.model = os.getenv(f"{prefix}MODEL")
    
    # Override budget
    if os.getenv(f"{prefix}MAX_USD"):
        config.max_usd = float(os.getenv(f"{prefix}MAX_USD"))
    if os.getenv(f"{prefix}MAX_LATENCY_MS"):
        config.max_latency_ms = int(os.getenv(f"{prefix}MAX_LATENCY_MS"))
    if os.getenv(f"{prefix}MAX_TOKENS"):
        config.max_tokens = int(os.getenv(f"{prefix}MAX_TOKENS"))
    
    return config