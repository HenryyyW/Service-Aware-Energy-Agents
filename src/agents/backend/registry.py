"""Backend registry for managing available LLM backends."""

from typing import Any, Dict, Type, Optional, List
from src.agents.backend.interface import AgentBackend
from src.agents.backend.fallback import FallbackBackend
from src.agents.backend.local import OllamaBackend
from src.agents.backend.remote import RemoteAPIBackend


class BackendRegistry:
    """Registry of available LLM backends."""
    
    _backends: Dict[str, type] = {
        "fallback": FallbackBackend,
        "ollama": OllamaBackend,
        "openai_gpt4": "RemoteAPIBackend",  # Will resolve at runtime
        "anthropic_claude": "RemoteAPIBackend",
    }
    
    _backend_configs: Dict[str, Dict] = {}
    
    @classmethod
    def register(cls, backend_id: str, backend_class: type, config: Dict = None) -> None:
        """Register a new backend class."""
        cls._backends[backend_id] = backend_class
        if config:
            cls._backend_configs[backend_id] = config
    
    @classmethod
    def get(cls, backend_id: str, **kwargs) -> "AgentBackend":
        """Get a backend instance by ID."""
        if backend_id not in cls._backends:
            raise ValueError(f"Unknown backend: {backend_id}. Available: {list(cls._backends.keys())}")
        
        backend_class = cls._backends[backend_id]
        
        # Resolve string references
        if isinstance(backend_class, str):
            if backend_class == "RemoteAPIBackend":
                backend_class = RemoteAPIBackend
            else:
                raise ValueError(f"Unknown backend class reference: {backend_class}")
        
        # Merge default config with provided kwargs
        config = cls._backend_configs.get(backend_id, {}).copy()
        config.update(kwargs)
        
        return backend_class(**config)
    
    @classmethod
    def list_available(cls) -> List[str]:
        """List all available backend IDs."""
        return list(cls._backends.keys())
    
    @classmethod
    def is_available(cls, backend_id: str) -> bool:
        """Check if a backend is registered."""
        return backend_id in cls._backends
    
    @classmethod
    def get_default(cls) -> "AgentBackend":
        """Get the default fallback backend."""
        return cls.get("fallback")


def create_backend_from_config(config: Dict[str, Any]) -> "AgentBackend":
    """Create a backend instance from a configuration dictionary.
    
    Expected config format:
    {
        "backend": "fallback|ollama|openai_gpt4|anthropic_claude",
        "model": "gpt-4-turbo",  # for remote
        "endpoint": "http://localhost:11434",  # for local
        "model": "llama3.2:3b",  # for local
        "prompt_template": "llm_agent_v1",
        "max_usd": 1.00,
        "max_latency_ms": 5000,
        "max_tokens": 4000
    }
    """
    backend_type = config.get("backend", "fallback")
    
    # Extract relevant config for the backend
    backend_config = {k: v for k, v in config.items() if k != "backend"}
    
    return BackendRegistry.get(backend_type, **backend_config)