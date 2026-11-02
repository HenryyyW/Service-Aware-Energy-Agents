# M2a real-LLM screen summary (poolside/laguna-xs-2.1, 24-step)

Generated from `experiments/phase2_llm/m2a_screen/full/` (45 runs: 5 scenarios
A-E x 3 arms x 3 seeds {42, 123, 456}). LLM arms ran on the hosted NVIDIA NIM API
(`LLM_BASE_URL=https://integrate.api.nvidia.com/v1`, model `poolside/laguna-xs-2.1`,
temperature 0.0, 24 steps, prompt `llm_dispatch_v2`, repair prompt
`llm_dispatch_v1_repair`). Every LLM-arm run manifest records `agent_backend=api`.
Raw run outputs are gitignored; this file is the committed summary.
Paper: `acm_submission/paper_draft.md` sections 5.6-5.9.

## Per-arm aggregates

| Metric | llm_agent (unverified) | llm_agent_verified | multi_agent (baseline) |
|---|---|---|---|
| Runs | 15 | 15 | 15 |
| agent_backend=api | 15 | 15 | 0 |
| fallback_share mean | 0.000 | 0.000 | n/a |
| fallback_share max | 0.042 | 0 | 0 |
| runs with fallback_share > 0 | 2 | 0 | 0 |
| first_attempt_validity mean | 1.000 | 1.000 | n/a |
| unrepaired_violations > 0 (runs) | 0 | 0 | 0 |
| repair_iterations > 0 (runs) | 0 | 0 | 0 |
| parse failures (total) | 1 | 0 | 0 |
| fenced outputs (total) | 0 | 0 | 0 |
| backend errors (total) | 1 | 0 | 0 |
| latency p50 (s) | 5.366 | 5.865 | n/a |
| latency p95 (s) | 12.157 | 14.897 | n/a |

## Gate check (M2a divergence gate)

- `llm_unrepaired_violations > 0` in the unverified arm: **0 / 15 runs**
- `repair_iterations > 0` in the verified arm: **0 / 15 runs**
- Verdict: **no arm divergence -> null result.** No separation claim is possible;
  M2b is not warranted. The proposer (`poolside/laguna-xs-2.1`, temp 0) emits
  in-bounds, parseable dispatches on this 24-step horizon, so verification has
  nothing to catch. Documented in paper sections 5.6-5.9.

## Fallback events (all in the unverified arm)

- `scenario_a_llm_agent_456`: fallback_share=0.0417, first_attempt_validity=0.9583333333333334, backend_errors=0, parse_failures=1
- `scenario_b_llm_agent_42`: fallback_share=0.0417, first_attempt_validity=0.9583333333333334, backend_errors=1, parse_failures=0

## Exploratory mini screen (`mini_s24/`, 2 runs, not part of the 45)

- `scenario_a_llm_agent_42`: backend=api, fallback_share=0.0, unrepaired_violations=0, repair_iterations=0
- `scenario_a_llm_agent_verified_42`: backend=api, fallback_share=0.0, unrepaired_violations=0, repair_iterations=0

## Reproducibility

Screen runs executed 2026-10-31 on the api-backend commit (PR #54 transport,
merged to main @ `497c3d7`; aggressive Scenario E config `b152037`). Regenerate
this file by re-running the M2a screen per `docs/phase2_experiment_plan.md` (section 5.2).
Note: the `controller_type` field in multi_agent run results is mislabeled
`llm_agent`; group runs by `controller_config.type` (fixed key used here).
