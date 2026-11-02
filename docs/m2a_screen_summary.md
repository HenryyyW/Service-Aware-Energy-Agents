# M2a real-LLM screen summary (poolside/laguna-xs-2.1, 24-step)

Generated from `experiments/phase2_llm/m2a_screen/full/` (45 runs: 5 scenarios
A-E x 3 arms x 3 seeds {42, 123, 456}). LLM arms ran on the hosted NVIDIA NIM API
(`LLM_BASE_URL=https://integrate.api.nvidia.com/v1`, model `poolside/laguna-xs-2.1`,
temperature 0.0, 24 steps, prompt `llm_dispatch_v2`, repair prompt
`llm_dispatch_v1_repair`). Every LLM-arm run manifest records `agent_backend=api`.
Raw run outputs are gitignored; this file is the committed summary.
Paper: `arxiv_submission/arxiv_main.tex`, subsection "Real-LLM Screen: M2a
(Null Result)" (`sec:m2a`).

## Per-arm aggregates

| Metric | llm_agent (unverified) | llm_agent_verified | multi_agent (baseline) |
|---|---|---|---|
| Runs | 15 | 15 | 15 |
| agent_backend=api | 15 | 15 | 0 |
| fallback_share mean | 0.006 | 0.000 | n/a |
| fallback_share max | 0.042 | 0 | 0 |
| runs with fallback_share > 0 | 2 | 0 | 0 |
| first_attempt_validity mean | 0.994 | 1.000 | n/a |
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
  nothing to catch. Documented in the arXiv paper's M2a subsection (`sec:m2a`).

## KPI deltas vs the 15 multi_agent 24-step reference runs

Paired per (scenario, seed), all 15 runs per arm:

| Arm | d_cost USD (mean; range) | d_peak kW (mean; max) | d_EV completion | KPI-identical runs |
|---|---|---|---|---|
| llm_agent | +1.37; 0.00 to +4.80 | +10.0; max +50.3 | 0.000 | 6/15 |
| llm_agent_verified | +0.10; 0.00 to +1.06 | +0.2; max +2.4 | 0.000 | 13/15 |

The verified arm tracks the multi_agent reference (13/15 runs bit-identical);
the unverified arm introduces cost/peak regressions (suboptimality, not grid
violations - unrepaired_violations is 0 in both arms). These KPI differences
are outside the pre-registered M2b gate metrics, so the gate verdict (null,
M2b not warranted) stands.

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
