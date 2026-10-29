# Phase 2: Real-LLM Backend Integration Design Document

**Status**: Draft for review  
**Branch**: `feature/phase2-llm-design`  
**Target**: Phase 2 gate decision document  
**Related**: Phase 1 code complete (PRs #1-19 merged)

---

## 1. Executive Summary

This document specifies the integration of a real LLM backend into the Service-Aware Energy Agents simulation framework. The design maintains backward compatibility with existing ablation controllers (`llm_agent`, `llm_agent_verified`) while introducing a pluggable `AgentBackend` interface that enables swapping between local LLMs, remote APIs, and the existing no-network fallback.

**Key constraints**:
- No secrets in repository — API keys via environment variables only
- Cost/latency budgets enforced per run
- Prompt versioning via existing `prompt_hash` in manifest
- No-network fallback contract already implemented (Phase 1)

---

## 2. Architecture Overview

### 2.1 Current State (Phase 1)
```
┌─────────────────────────────────────────────────────────────┐
│                    SimulationCoupler                         │
├─────────────────────────────────────────────────────────────┤
│  Controllers (src/controllers/)                              │
│  ├── RuleBasedController        ✓ implemented               │
│  ├── MultiAgentController       ✓ implemented               │
│  ├── CentralizedController      ✓ implemented               │
│  ├── LLM_Agent (llm_agent)      ✓ stub — ablation only      │
│  └── LLM_Agent_Verified         ✓ stub — ablation only      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Target State (Phase 2)
```
┌─────────────────────────────────────────────────────────────┐
│                    SimulationCoupler                         │
├─────────────────────────────────────────────────────────────┤
│  Controllers (src/controllers/)                              │
│  ├── RuleBasedController        ✓ implemented               │
│  ├── MultiAgentController       ✓ implemented               │
│  ├── CentralizedController      ✓ implemented               │
│  ├── LLMAgent (llm_agent)       ← uses AgentBackend         │
│  └── LLMAgentVerified           ← uses AgentBackend         │
├─────────────────────────────────────────────────────────────┤
│  AgentBackend Interface (src/agents/backend/)                │
│  ├── LocalLLMBackend            ← llama.cpp / Ollama        │
│  ├── RemoteAPIBackend           ← OpenAI / Anthropic / etc. │
│  └── FallbackBackend            ✓ already implemented       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. AgentBackend Interface

### 3.1 Interface Definition

```python
# src/agents/backend/__init__.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from src.schemas.action import RequestedActions, Action
from src.schemas.scenario import ScenarioConfig

@dataclass
class BackendResponse:
    """Response from an LLM backend."""
    actions: List[Action]
    raw_output: str
    prompt_hash: str
    token_usage: Dict[str, int]
    latency_ms: float
    cost_usd: float

class AgentBackend(ABC):
    """Abstract interface for LLM backends."""
    
    @property
    @abstractmethod
    def backend_id(self) -> str:
        """Unique identifier: 'local_llama', 'openai_gpt4', 'anthropic_claude', 'fallback'."""
        pass
    
    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether backend supports streaming responses."""
        pass
    
    @abstractmethod
    async def generate_actions(
        self,
        scenario: ScenarioConfig,
        observations: Dict[str, Any],
        timestep: int,
        context: Optional[Dict[str, Any]] = None,
        budget: Optional["CostBudget"] = None,
    ) -> BackendResponse:
        """Generate control actions from observations."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Verify backend is available."""
        pass
    
    @abstractmethod
    def estimate_cost(self, prompt_tokens: int, max_completion_tokens: int) -> float:
        """Estimate USD cost for a request."""
        pass

@dataclass
class CostBudget:
    """Per-run cost/latency budget."""
    max_usd: float = 1.0
    max_latency_ms: int = 5000
    max_tokens: int = 4000
```

### 3.2 Backend Registry

```python
# src/agents/backend/registry.py
from typing import Dict, Type
from src.agents.backend import AgentBackend, LocalLLMBackend, RemoteAPIBackend, FallbackBackend

class BackendRegistry:
    """Registry of available backends."""
    
    _backends: Dict[str, Type[AgentBackend]] = {
        "local_llama": LocalLLMBackend,
        "openai_gpt4": RemoteAPIBackend,
        "anthropic_claude": RemoteAPIBackend,
        "fallback": FallbackBackend,
    }
    
    @classmethod
    def get(cls, backend_id: str) -> AgentBackend:
        if backend_id not in cls._backends:
            raise ValueError(f"Unknown backend: {backend_id}")
        return cls._backends[backend_id]()
    
    @classmethod
    def register(cls, backend_id: str, backend_class: Type[AgentBackend]):
        cls._backends[backend_id] = backend_class
```

---

## 4. Prompt Versioning Scheme

### 4.1 Prompt Hash in Manifest (Already in Phase 1)

The existing manifest schema includes `prompt_hash`:

```python
# src/schemas/report.py (existing)
class Manifest(BaseModel):
    run_id: str
    scenario_config_sha256: str
    prompt_hash: str  # ← Already exists
    git_commit: Optional[str]
    ...
```

### 4.2 Prompt Template Versioning

```python
# src/agents/prompts/__init__.py
import hashlib
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class PromptTemplate:
    """Versioned prompt template."""
    template_id: str           # e.g., "llm_agent_v1", "llm_agent_v2"
    system_prompt: str
    user_prompt_template: str
    version: int
    metadata: Dict[str, Any]
    
    @property
    def prompt_hash(self) -> str:
        """SHA256 of concatenated prompts + version."""
        content = f"{self.system_prompt}|{self.user_prompt_template}|{self.version}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def render(self, **kwargs) -> str:
        return self.user_prompt_template.format(**kwargs)

# Registry of versioned prompts
PROMPT_REGISTRY = {
    "llm_agent_v1": PromptTemplate(
        template_id="llm_agent_v1",
        version=1,
        system_prompt="You are a grid-aware energy community controller...",
        user_prompt_template="Observations: {observations}\nTimestep: {timestep}\nGenerate actions...",
        metadata={"author": "team", "date": "2026-10-29"}
    ),
    # Future versions added here
}
```

### 4.3 Manifest Integration

```python
# In ExperimentRunner._write_manifest() — add to existing manifest
manifest["prompt_template_id"] = controller.prompt_template_id
manifest["prompt_hash"] = controller.prompt_template.prompt_hash
```

---

## 5. Cost/Latency Budget per Run

### 5.1 Budget Configuration

```yaml
# configs/llm_budget.yaml (new file)
llm_budget:
  # Per-run limits
  max_usd_per_run: 1.00
  max_latency_ms_per_step: 5000
  max_tokens_per_step: 4000
  
  # Per-model pricing (USD per 1M tokens)
  model_pricing:
    gpt-4:
      input: 30.00
      output: 60.00
    gpt-4-turbo:
      input: 10.00
      output: 30.00
    claude-3-opus:
      input: 15.00
      output: 75.00
    claude-3-sonnet:
      input: 3.00
      output: 15.00
    local_llama:
      input: 0.00
      output: 0.00
  
  # Fallback trigger thresholds
  fallback_triggers:
    budget_exceeded: true
    latency_exceeded: true
    backend_unhealthy: true
```

### 5.2 Budget Enforcement in Controller

```python
# src/controllers/llm_agent.py (new implementation)
class LLMAgent(BaseController):
    def __init__(
        self,
        scenario_config: ScenarioConfig,
        backend: str = "fallback",
        budget: CostBudget = None,
        prompt_template_id: str = "llm_agent_v1",
    ):
        super().__init__(scenario_config)
        self.backend = BackendRegistry.get(backend)
        self.budget = budget or CostBudget()
        self.prompt_template = PROMPT_REGISTRY[prompt_template_id]
        self.token_usage = {"prompt": 0, "completion": 0}
        self.total_cost = 0.0
        self.total_latency = 0.0
    
    async def get_actions(self, observations: Dict, timestep: int) -> RequestedActions:
        # Check budget before request
        if self.total_cost >= self.budget.max_usd:
            return await self._fallback_actions(observations, timestep, "budget_exceeded")
        
        if self.total_latency >= self.budget.max_latency_ms:
            return await self._fallback_actions(observations, timestep, "latency_budget")
        
        try:
            response = await self.backend.generate_actions(
                scenario=self.scenario_config,
                observations=observations,
                timestep=timestep,
                context={"grid_diagnostics": self.last_grid_diagnostics},
                budget=self.budget,
            )
            
            # Update budget tracking
            self.token_usage["prompt"] += response.token_usage.get("prompt", 0)
            self.token_usage["completion"] += response.token_usage.get("completion", 0)
            self.total_cost += response.cost_usd
            self.total_latency += response.latency_ms
            
            # Verify response prompt_hash matches manifest
            if response.prompt_hash != self.prompt_template.prompt_hash:
                logger.warning(f"Prompt hash mismatch: expected {self.prompt_template.prompt_hash}, got {response.prompt_hash}")
            
            return self._create_requested_actions(response.actions)
            
        except Exception as e:
            logger.error(f"LLM backend failed: {e}")
            return await self._fallback_actions(observations, timestep, str(e))
```

---

## 6. No-Network Fallback Contract (Already Implemented)

### 6.1 Existing FallbackBackend (Phase 1)

```python
# src/agents/backend/fallback.py (already exists in Phase 1)
class FallbackBackend(AgentBackend):
    """Deterministic rule-based fallback when no LLM available."""
    
    backend_id = "fallback"
    supports_streaming = False
    
    async def generate_actions(self, scenario, observations, timestep, context=None, budget=None):
        # Uses RuleBasedController logic internally
        from src.controllers import RuleBasedController
        controller = RuleBasedController(scenario)
        requested = controller.get_actions(observations, timestep)
        return BackendResponse(
            actions=requested.actions,
            raw_output="fallback",
            prompt_hash="fallback",
            token_usage={"prompt": 0, "completion": 0},
            latency_ms=0.0,
            cost_usd=0.0,
        )
    
    async def health_check(self) -> bool:
        return True
    
    def estimate_cost(self, prompt_tokens: int, max_completion_tokens: int) -> float:
        return 0.0
```

### 6.2 Fallback Trigger Conditions

| Condition | Action |
|-----------|--------|
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` not set | Auto-fallback |
| Budget exceeded (`total_cost >= max_usd`) | Auto-fallback |
| Latency budget exceeded | Auto-fallback |
| Backend health check fails | Auto-fallback |
| Prompt hash mismatch | Log warning, continue (configurable) |

---

## 7. API Key / Config Surface (No Secrets in Repo)

### 7.1 Environment Variables Only

```bash
# .env.example (committed to repo — template only)
# LLM Backend Configuration
LLM_BACKEND=fallback                    # local_llama | openai_gpt4 | anthropic_claude | fallback
LLM_MODEL=gpt-4-turbo                   # Model identifier
LLM_PROMPT_TEMPLATE=llm_agent_v1        # Prompt template ID

# API Keys (NEVER commit actual values)
OPENAI_API_KEY=                         # Required for openai_* backends
ANTHROPIC_API_KEY=                      # Required for anthropic_* backends

# Optional: Local LLM (llama.cpp / Ollama)
LLM_LOCAL_ENDPOINT=http://localhost:11434
LLM_LOCAL_MODEL=llama3

# Budget (optional — defaults in code)
LLM_MAX_USD=1.00
LLM_MAX_LATENCY_MS=5000
LLM_MAX_TOKENS=4000
```

### 7.2 Configuration Loading

```python
# src/config/llm.py
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class LLMConfig:
    backend: str = os.getenv("LLM_BACKEND", "fallback")
    model: str = os.getenv("LLM_MODEL", "gpt-4-turbo")
    prompt_template_id: str = os.getenv("LLM_PROMPT_TEMPLATE", "llm_agent_v1")
    
    # API keys — never have defaults
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    
    # Local LLM
    local_endpoint: str = os.getenv("LLM_LOCAL_ENDPOINT", "http://localhost:11434")
    local_model: str = os.getenv("LLM_LOCAL_MODEL", "llama3")
    
    # Budget
    max_usd: float = float(os.getenv("LLM_MAX_USD", "1.00"))
    max_latency_ms: int = int(os.getenv("LLM_MAX_LATENCY_MS", "5000"))
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4000"))
    
    def validate(self) -> List[str]:
        """Return list of validation errors."""
        errors = []
        if self.backend in ("openai_gpt4", "openai_gpt4_turbo") and not self.openai_api_key:
            errors.append("OPENAI_API_KEY required for OpenAI backend")
        if self.backend in ("anthropic_claude", "anthropic_claude_sonnet") and not self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY required for Anthropic backend")
        return errors
```

---

## 8. Integration with Existing Ablation Controllers

### 8.1 Controller Selection Logic

```python
# src/controllers/__init__.py (extend existing)
def create_controller(
    controller_type: str,
    scenario_config: ScenarioConfig,
    llm_config: LLMConfig = None,
) -> BaseController:
    if controller_type == "rule_based":
        return RuleBasedController(scenario_config)
    elif controller_type == "multi_agent":
        return MultiAgentController(scenario_config)
    elif controller_type == "centralized":
        return CentralizedController(scenario_config)
    elif controller_type == "llm_agent":
        if llm_config is None:
            llm_config = LLMConfig()
        return LLMAgent(scenario_config, llm_config)
    elif controller_type == "llm_agent_verified":
        if llm_config is None:
            llm_config = LLMConfig()
        return LLMAgentVerified(scenario_config, llm_config)
    else:
        raise ValueError(f"Unknown controller: {controller_type}")
```

### 8.2 Experiment Runner Integration

```python
# experiments/run_experiment.py (extend existing)
def main():
    parser.add_argument("--llm-backend", type=str, default="fallback",
                        choices=["fallback", "local_llama", "openai_gpt4", "anthropic_claude"])
    parser.add_argument("--llm-model", type=str, default="gpt-4-turbo")
    parser.add_argument("--llm-prompt-template", type=str, default="llm_agent_v1")
    parser.add_argument("--llm-max-usd", type=float, default=1.00)
    parser.add_argument("--llm-max-latency-ms", type=int, default=5000)
    ...
    
    # Pass LLM config to controller factory
    controller = create_controller(args.controller, scenario, llm_config=llm_config)
```

---

## 9. Testing Strategy

### 9.1 Unit Tests

```python
# tests/test_llm_backend.py
import pytest
from src.agents.backend import LocalLLMBackend, RemoteAPIBackend, FallbackBackend, CostBudget
from src.controllers.llm_agent import LLMAgent

def test_fallback_backend_always_works():
    backend = FallbackBackend()
    assert backend.health_check() is True
    assert backend.estimate_cost(1000, 1000) == 0.0

def test_budget_enforcement():
    budget = CostBudget(max_usd=0.01, max_latency_ms=100)
    # Should trigger fallback when budget exceeded

def test_prompt_hash_in_manifest():
    # Verify prompt_hash written to manifest.json
```

### 9.2 Integration Tests

```python
# tests/test_llm_integration.py
def test_llm_agent_with_fallback():
    """LLM agent should use fallback when no API key."""
    scenario = create_scenario_a()
    controller = create_controller("llm_agent", scenario, LLMConfig(backend="fallback"))
    actions = controller.get_actions(observations, 0)
    assert len(actions.actions) > 0

def test_llm_agent_with_openai_mock():
    """Test with mocked OpenAI responses."""
    # Use pytest-mock to simulate API responses
```

---

## 10. Implementation Phases

| Phase | Deliverable | Est. Effort |
|-------|-------------|-------------|
| 2.1 | `AgentBackend` interface + `FallbackBackend` (refactor existing) | 1 week |
| 2.2 | `LocalLLMBackend` (llama.cpp/Ollama) | 1 week |
| 2.3 | `RemoteAPIBackend` (OpenAI/Anthropic) | 1 week |
| 2.4 | Prompt versioning + manifest integration | 3 days |
| 2.5 | Cost/latency budget enforcement | 3 days |
| 2.6 | Config/env var surface + validation | 2 days |
| 2.7 | Update `LLMAgent`/`LLMAgentVerified` to use `AgentBackend` | 1 week |
| 2.8 | Tests + documentation | 1 week |
| **Total** | | **~6 weeks** |

---

## 11. Decision Matrix for Gate Review

| Criterion | Threshold | Measurement |
|-----------|-----------|-------------|
| Fallback correctness | 100% | All tests pass with `LLM_BACKEND=fallback` |
| Budget enforcement | ≤1% overrun | Integration test with mock backend |
| Prompt hash in manifest | 100% runs | Verify `prompt_hash` field populated |
| No secrets in repo | 0 findings | `git-secrets` scan in CI |
| Cost per run (GPT-4 Turbo) | < $1.00 | Benchmark with 10 runs |
| Latency P99 | < 5s | Benchmark with 10 runs |
| Fallback trigger latency | < 100ms | Chaos test: kill API mid-run |

---

## 12. References

- Phase 1 PRs: #1-19 (merged)
- `src/controllers/llm_agent.py` — existing stub
- `src/controllers/__init__.py` — controller factory
- `experiments/run_experiment.py` — CLI integration point
- `docs/paper_results_section.md` — ablation methodology
- `experiments/ABLATION_DESIGN.md` — controller comparison design

---

*Document version: 1.0*  
*Author: Backend/Simulation Engineer A*  
*Reviewers: Project Manager, Product Design Lead, Backend Engineer B*