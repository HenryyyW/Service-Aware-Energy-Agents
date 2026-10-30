import sys
sys.path.insert(0, r'C:\Users\henry\OpenBot\Agents\agent-889663d5-9d43-48dc-b056-c0b809212193\Service-Aware-Energy-Agents')

from tests.test_llm_controllers import _make_mock_actions

actions = _make_mock_actions()
for a in actions:
    print(f'asset_id: {a.asset_id}, value_kw: {a.value_kw}')
by_id = {a.asset_id: a.value_kw for a in actions}
print('Keys:', list(by_id.keys()))
print('ab_battery:', by_id.get('ab_battery'))
print('ab_ev_0:', by_id.get('ab_ev_0'))