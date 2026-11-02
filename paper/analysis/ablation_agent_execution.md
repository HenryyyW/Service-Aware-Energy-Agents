# Ablation agent execution (fallback ablation, reference multi_agent)

Fallback mode is labelled explicitly: `agent_backend: fallback` means no
LLM backend was configured, so these numbers measure the verification
machinery under a deterministic proposer, not LLM proposal quality.

| Scenario | Controller | n | backend | first-attempt validity | repairs/run | repairs/step | verification failures | unparseable | wall s |
|---|---|---|---|---|---|---|---|---|---|
| scenario_a | centralized | 5 | — | — | — | — | — | — | 54.4 |
| scenario_a | mpc | 5 | — | — | — | — | — | — | 84.6 |
| scenario_a | multi_agent | 5 | — | — | — | — | — | — | 54.3 |
| scenario_a | rule_based | 5 | — | — | — | — | — | — | 58.1 |
| scenario_b | centralized | 5 | — | — | — | — | — | — | 55.1 |
| scenario_b | mpc | 5 | — | — | — | — | — | — | 59.7 |
| scenario_b | multi_agent | 5 | — | — | — | — | — | — | 53.4 |
| scenario_b | rule_based | 5 | — | — | — | — | — | — | 54.7 |
| scenario_c | centralized | 5 | — | — | — | — | — | — | 56.1 |
| scenario_c | mpc | 5 | — | — | — | — | — | — | 61.0 |
| scenario_c | multi_agent | 5 | — | — | — | — | — | — | 55.9 |
| scenario_c | rule_based | 5 | — | — | — | — | — | — | 55.2 |
| scenario_d | centralized | 5 | — | — | — | — | — | — | 53.9 |
| scenario_d | mpc | 5 | — | — | — | — | — | — | 59.6 |
| scenario_d | multi_agent | 5 | — | — | — | — | — | — | 55.5 |
| scenario_d | rule_based | 5 | — | — | — | — | — | — | 54.6 |
| scenario_e | centralized | 5 | — | — | — | — | — | — | 53.2 |
| scenario_e | mpc | 5 | — | — | — | — | — | — | 60.5 |
| scenario_e | multi_agent | 5 | — | — | — | — | — | — | 53.9 |
| scenario_e | rule_based | 5 | — | — | — | — | — | — | 53.8 |
