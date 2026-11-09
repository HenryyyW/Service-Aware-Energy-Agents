"""Backend registry for managing available LLM backends."""

from typing import Any, Dict, List
from src.agents.backend.interface import AgentBackend
from src.agents.backend.fallback import FallbackBackend
from src.agents.backend.local import OllamaBackend
from src.agents.backend.remote import RemoteAPIBackend
from src.agents.backend.api import ApiPromptCallable


class BackendRegistry:
    """Registry of available LLM backends."""

    _backends: Dict[str, Any] = {
        "fallback": FallbackBackend,
        "ollama": OllamaBackend,
        "api": ApiPromptCallable,
        "openai_gpt4": RemoteAPIBackend,  # type: ignore[name-defined]
        "anthropic_claude": RemoteAPIBackend,  # type: ignore[name-defined]
    }

    _backend_configs: Dict[str, Dict] = {}

    @classmethod
    def register(
        cls, backend_id: str, backend_class: type, config: Dict = None
    ) -> None:
        """Register a new backend class."""
        cls._backends[backend_id] = backend_class
        if config:
            cls._backend_configs[backend_id] = config

    @classmethod
    def get(cls, backend_id: str, **kwargs) -> AgentBackend:
        """Get a backend instance by ID."""
        if backend_id not in cls._backends:
            raise ValueError(
                f"Unknown backend: {backend_id}. Available: {list(cls._backends.keys())}"
            )

        backend_class = cls._backends[backend_id]

        # Merge default config with provided kwargs
        config = cls._backend_configs.get(backend_id, {}).copy()
        config.update(kwargs)

        return backend_class(**config)  # type: ignore[return-value, no-any-return]

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
        "backend": "fallback|ollama|api|openai_gpt4|anthropic_claude",
        "model": "kimi-k2.7-code",  # for api
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

    # Map config keys to backend constructor parameters
    if "prompt_template" in backend_config:
        backend_config["prompt_template_id"] = backend_config.pop("prompt_template")
    # Only map local_endpoint to endpoint for ollama backend
    if "local_endpoint" in backend_config and backend_type == "ollama":
        backend_config["endpoint"] = backend_config.pop("local_endpoint")
    # Only map local_model to model for ollama/local backends
    if "local_model" in backend_config and backend_type == "ollama":
        backend_config["model"] = backend_config.pop("local_model")

    # Filter out irrelevant keys based on backend type
    if backend_type == "ollama":
        # OllamaBackend only accepts: endpoint, model, prompt_template_id
        allowed_keys = {"endpoint", "model", "prompt_template_id"}
        backend_config = {k: v for k, v in backend_config.items() if k in allowed_keys}
    elif backend_type == "api":
        # ApiPromptCallable accepts: model, base_url, api_key, temperature, seed, timeout_s, max_tokens, max_retries, retry_backoff_s
        allowed_keys = {
            "model",
            "base_url",
            "api_key",
            "temperature",
            "seed",
            "timeout_s",
            "max_tokens",
            "max_retries",
            "retry_backoff_s",
            "dashscope_api_key",
            "nvidia_api_key",
            "openai_api_key",  # fallback if no dashscope/nvidia key
            "endpoint",  # alias for base_url
        }
        backend_config = {k: v for k, v in backend_config.items() if k in allowed_keys}
        # Map dashscope_api_key to api_key for ApiPromptCallable
        if backend_config.get("dashscope_api_key"):
            backend_config["api_key"] = backend_config.pop("dashscope_api_key")
        elif backend_config.get("nvidia_api_key"):
            backend_config["api_key"] = backend_config.pop("nvidia_api_key")
        elif backend_config.get("openai_api_key"):
            backend_config["api_key"] = backend_config.pop("openai_api_key")
        # Remove all api key aliases that were used for mapping
        backend_config.pop("dashscope_api_key", None)
        backend_config.pop("nvidia_api_key", None)
        backend_config.pop("openai_api_key", None)
        # Map endpoint to base_url
        if "endpoint" in backend_config:
            backend_config["base_url"] = backend_config.pop("endpoint")
    elif backend_type in (
        "openai_gpt4",
        "openai_gpt4_turbo",
        "openai_gpt4o",
        "openai_gpt4o_mini",
    ):
        allowed_keys = {
            "model",
            "openai_api_key",
            "endpoint",
            "prompt_template_id",
            "provider",
        }
        backend_config = {k: v for k, v in backend_config.items() if k in allowed_keys}
        # Map openai_api_key to api_key for RemoteAPIBackend
        if "openai_api_key" in backend_config:
            backend_config["api_key"] = backend_config.pop("openai_api_key")
    elif backend_type in (
        "anthropic_claude",
        "anthropic_claude_sonnet",
        "anthropic_claude_opus",
        "anthropic_claude_haiku",
    ):
        allowed_keys = {
            "model",
            "anthropic_api_key",
            "endpoint",
            "prompt_template_id",
            "max_usd",
            "max_latency_ms",
            "max_tokens",
        }
        backend_config = {k: v for k, v in backend_config.items() if k in allowed_keys}
    elif backend_type == "fallback":
        allowed_keys = set()
        backend_config = {k: v for k, v in backend_config.items() if k in allowed_keys}

    return BackendRegistry.get(backend_type, **backend_config)
