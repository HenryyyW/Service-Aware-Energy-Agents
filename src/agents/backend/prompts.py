"""Prompt versioning system with hash-based integrity checking."""

import hashlib
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from pathlib import Path


@dataclass
class PromptTemplate:
    """Versioned prompt template with hash-based integrity."""
    template_id: str           # e.g., "llm_agent_v1", "llm_agent_v2"
    version: int
    system_prompt: str
    user_prompt_template: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def prompt_hash(self) -> str:
        """SHA256 hash of concatenated prompts + version for integrity checking."""
        content = f"{self.system_prompt}|{self.user_prompt_template}|{self.version}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def render(self, **kwargs) -> str:
        """Render user prompt template with provided variables."""
        return self.user_prompt_template.format(**kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "template_id": self.template_id,
            "version": self.version,
            "system_prompt": self.system_prompt,
            "user_prompt_template": self.user_prompt_template,
            "metadata": self.metadata,
            "prompt_hash": self.prompt_hash,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptTemplate":
        """Deserialize from dictionary."""
        return cls(
            template_id=data["template_id"],
            version=data["version"],
            system_prompt=data["system_prompt"],
            user_prompt_template=data["user_prompt_template"],
            metadata=data.get("metadata", {}),
        )


# Registry of versioned prompts
PROMPT_REGISTRY: Dict[str, PromptTemplate] = {}

# Default prompt template for llm_agent
DEFAULT_PROMPT = PromptTemplate(
    template_id="llm_agent_v1",
    version=1,
    system_prompt="""You are an expert energy community controller for a renewable energy microgrid.

Your goal is to optimize the community's energy usage while respecting:
1. Grid constraints (voltage limits, line loading, transformer loading)
2. Community import/export limits
3. Individual building comfort and service requirements
4. Battery and EV charging needs

You receive observations about the current state and must output actions for each controllable device.

ACTION SPACE:
- Battery: charge (positive kW) or discharge (negative kW)
- EV chargers: charge (positive kW)
- Flexible loads: run (1.0) or don't run (0.0)

OUTPUT FORMAT: Return a JSON object with:
{
  "actions": [
    {"asset_id": "building_0_battery", "action_type": "battery_charge", "value_kw": 3.5},
    {"asset_id": "building_0_ev_0", "action_type": "ev_charge", "value_kw": 7.0},
    {"asset_id": "building_0_flex_0", "action_type": "flexible_load", "value_kw": 1.0}
  ]
}

CONSTRAINTS:
- Battery power must be within [-battery_power_kw, +battery_power_kw]
- EV charging power must be within [0, max_charge_kw]
- Flexible loads must be 0 or 1 (on/off)
- Community import limit: {community_import_limit_kw} kW
- Community export limit: {community_export_limit_kw} kW
- Voltage limits: 0.95 - 1.05 pu
- Line loading limit: 100%
""",
    user_prompt_template="""Current timestep: {timestep}

BUILDING STATES:
{buildings}

GRID DIAGNOSTICS:
{grid_diagnostics}

COMMUNITY LIMITS:
- Import limit: {community_import_limit_kw} kW
- Export limit: {community_export_limit_kw} kW

Generate optimal actions for this timestep. Return only valid JSON.""",
    metadata={"author": "team", "date": "2026-10-29", "description": "Default LLM agent prompt v1"}
)

# Register default prompt
PROMPT_REGISTRY["llm_agent_v1"] = DEFAULT_PROMPT


def register_prompt(template: PromptTemplate) -> None:
    """Register a prompt template in the global registry."""
    PROMPT_REGISTRY[template.template_id] = template


def get_prompt(template_id: str) -> Optional[PromptTemplate]:
    """Get a prompt template by ID."""
    return PROMPT_REGISTRY.get(template_id)


def load_prompts_from_dir(prompts_dir: str) -> None:
    """Load prompt templates from JSON files in a directory."""
    import json
    from pathlib import Path
    
    dir_path = Path(prompts_dir)
    if not dir_path.exists():
        return
    
    for json_file in dir_path.glob("*.json"):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            template = PromptTemplate.from_dict(data)
            register_prompt(template)
        except Exception as e:
            print(f"Warning: Failed to load prompt from {json_file}: {e}")


def get_prompt_hash(template_id: str) -> Optional[str]:
    """Get prompt hash for a template ID."""
    template = get_prompt(template_id)
    return template.prompt_hash if template else None