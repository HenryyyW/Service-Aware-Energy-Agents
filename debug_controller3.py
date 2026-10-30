import sys
sys.path.insert(0, r'C:\Users\henry\OpenBot\Agents\agent-889663d5-9d43-48dc-b056-c0b809212193\Service-Aware-Energy-Agents')

from src.schemas.action import Action, ActionType
from src.agents.backend.interface import BackendResponse, CostBudget
from src.agents.backend.fallback import FallbackBackend
import asyncio

class MockBackend:
    def __init__(self, actions):
        self._actions = actions
        self._call_count = 0

    @property
    def backend_id(self):
        return 'mock'

    @property
    def supports_streaming(self):
        return False

    async def generate_actions(self, scenario, observations, timestep, context=None, budget=None):
        print('generate_actions called!')
        return BackendResponse(
            actions=self._actions,
            raw_output='mock',
            prompt_hash='test',
            token_usage={'prompt': 100, 'completion': 50, 'total': 150},
            latency_ms=10.0,
            cost_usd=0.0,
        )

    async def health_check(self):
        return True

    def estimate_cost(self, prompt_tokens, max_completion_tokens):
        return 0.0


def _make_mock_actions():
    from src.schemas.action import Action, ActionType
    return [
        Action(asset_id='ab_battery', action_type=ActionType.BATTERY_CHARGE, value_kw=2.0, timestep=0),
        Action(asset_id='ab_ev_0', action_type=ActionType.EV_CHARGE, value_kw=5.0, timestep=0),
    ]


def _metadata():
    return {
        'ab': {
            'battery': {'power_kw': 6.0},
            'chargers': [{'max_charge_kw': 7.0}],
            'deferrable': [{'power_kw': 3.0}],
        }
    }


def _observations(timestep=0):
    return {
        'ab_building_0_net_electricity_consumption': 3.0,
        'ab_building_0_solar_generation': 1.0,
        'ab_building_0_non_shiftable_load': 2.0,
        'ab_building_0_electrical_storage_soc': 0.5,
    }


scenario = type('ScenarioConfig', (), {
    'scenario_id': 'test',
    'name': 'Test',
    'description': 'Test',
    'random_seed': 42,
    'timestep_minutes': 60,
    'community_import_limit_kw': 200.0,
    'community_export_limit_kw': 150.0,
    'buildings': [],
})()


from src.controllers import LLMAgentController
from src.schemas.action import Action, ActionType
from src.agents.backend.interface import BackendResponse, CostBudget
from src.agents.backend.fallback import FallbackBackend
import asyncio

mock_backend = type('MockBackend', (), {
    'backend_id': 'mock',
    'supports_streaming': False,
    'generate_actions': lambda self, scenario, observations, timestep, context=None, budget=None: BackendResponse(
        actions=[
            type('Action', (), {'asset_id': 'ab_battery', 'value_kw': 2.0, 'action_type': 'battery_charge', 'timestep': 0})(),
            type('Action', (), {'asset_id': 'ab_ev_0', 'value_kw': 5.0, 'action_type': 'ev_charge', 'timestep': 0})(),
        ],
        raw_output='mock',
        prompt_hash='test',
        token_usage={'prompt': 100, 'completion': 50, 'total': 150},
        latency_ms=10.0,
        cost_usd=0.0,
    ),
    'health_check': lambda self: True,
    'estimate_cost': lambda self, p, m: 0.0,
})()

scenario = type('ScenarioConfig', (), {
    'scenario_id': 'test',
    'name': 'Test',
    'description': 'Test',
    'random_seed': 42,
    'timestep_minutes': 60,
    'community_import_limit_kw': 200.0,
    'community_export_limit_kw': 150.0,
    'buildings': [],
})()

from src.controllers import LLMAgentController
from src.schemas.action import Action, ActionType
from src.agents.backend.interface import BackendResponse, CostBudget
from src.agents.backend.fallback import FallbackBackend
import asyncio

llm = LLMAgentController(
    scenario, device_metadata={'ab': {'battery': {'power_kw': 6.0}, 'chargers': [{'max_charge_kw': 7.0}], 'deferrable': [{'power_kw': 3.0}]}}, backend=type('MockBackend', (), {
    'backend_id': 'mock',
    'supports_streaming': False,
    'generate_actions': lambda self, scenario, observations, timestep, context=None, budget=None: BackendResponse(
        actions=[
            type('Action', (), {'asset_id': 'ab_battery', 'value_kw': 2.0, 'action_type': 'battery_charge', 'timestep': 0})(),
            type('Action', (), {'asset_id': 'ab_ev_0', 'value_kw': 5.0, 'action_type': 'ev_charge', 'timestep': 0})(),
        ],
        raw_output='mock',
        prompt_hash='test',
        token_usage={'prompt': 100, 'completion': 50, 'total': 150},
        latency_ms=10.0,
        cost_usd=0.0,
    ),
    'health_check': lambda self: True,
    'estimate_cost': lambda self, p, m: 0.0,
})()

print('Backend:', llm._backend)
print('Agent backend:', llm.agent_backend)

obs = {
    'ab_building_0_net_electricity_consumption': 3.0,
    'ab_building_0_solar_generation': 1.0,
    'ab_building_0_non_shiftable_load': 2.0,
    'ab_building_0_electrical_storage_soc': 0.5,
}

import asyncio
async def test():
    result = await llm._propose_via_llm(obs, 0)
    print('Proposed actions:', result)
    if result:
        for a in result:
            print(f'  asset_id: {a.asset_id}, value_kw: {a.value_kw}')
    else:
        print('No actions proposed')

import asyncio
asyncio.run(test())