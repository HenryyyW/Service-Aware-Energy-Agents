# M2a re-run (model not recorded, 24-step, 10 seeds)

Matrix: `experiments/m2a_rerun_laguna` — llm_agent=50 + llm_agent_verified=49 LLM runs, plus 50 paired `multi_agent` 24-step reference runs.

## Per-arm aggregates

| Metric | llm_agent | llm_agent_verified |
|---|---|---|
| first_attempt_validity_run | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 |
| first_attempt_validity_step | 0.9967 ± 0.0032 | 0.9991 ± 0.0017 |
| repair_iterations | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 |
| fallback_step_share | 0.0025 ± 0.0028 | 0.0009 ± 0.0017 |
| fallback_steps | 0.0600 ± 0.0682 | 0.0204 ± 0.0410 |
| unrepaired_violations | 0.0200 ± 0.0402 | 0.0000 ± 0.0000 |
| llm_calls | 24.0000 ± 0.0000 | 24.0000 ± 0.0000 |
| parse_failures | 0.0600 ± 0.0682 | 0.0204 ± 0.0410 |
| fenced_outputs | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 |
| backend_errors | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 |
| verification_failures | — | — |
| prompt_tokens | 29735.8600 ± 92.7548 | 29735.3469 ± 94.9662 |
| completion_tokens | 8708.2600 ± 190.0126 | 8714.4694 ± 193.6163 |
| latency_p50_ms | 4678.7593 ± 308.8433 | 4555.0968 ± 354.4847 |
| latency_p95_ms | 8971.0699 ± 1000.8671 | 8921.3291 ± 970.3961 |

## Gate check (M2a divergence gate)

- `unrepaired_violations`: unverified 0.0200 (1/50 runs nonzero) vs verified 0.0000 (0/49 runs nonzero) — arm difference 0.0200 pp (< 10 pp)
- `fallback_step_share`: unverified 0.0025 (3/50 runs nonzero) vs verified 0.0008 (1/49 runs nonzero) — arm difference 0.0017 pp (< 10 pp)

**Verdict: the M2b gate is NOT met -> SAFETY-METRICS NULL.** No safety-gate divergence; report as a null result on the safety metrics (the reviewer-facing claim stays honest).

## KPI deltas vs the paired `multi_agent` reference (n=50)

| Arm | Δ cost (USD) | Δ peak (kW) | Δ EV completion |
|---|---|---|---|
| llm_agent | +28.576 ± 21.072 | +5.421 ± 4.138 | +0.0120 ± 0.0241 |
| llm_agent_verified | +5.828 ± 5.915 | +1.001 ± 1.142 | +0.0000 ± 0.0000 |
| multi_agent | +0.000 ± 0.000 | +0.000 ± 0.000 | +0.0000 ± 0.0000 |

## Arm difference (unverified − verified, paired)

- Δ cost: +23.047 ± 21.316 USD (paired t=2.174, p=0.0347, n=49)
- Δ peak: +4.531 ± 4.241 kW (paired t=2.148, p=0.0368, n=49)

## Third gate clause: KPI CIs excluding zero

- arm difference in cost: +23.05 ± 21.32 (paired t=2.174, p=0.0347, n=49) -> CI excludes zero
- arm difference in peak: +4.53 ± 4.24 (paired t=2.148, p=0.0368, n=49) -> CI excludes zero

**Gate verdict (safety-gated, PM ruling 2026-11-08): NOT met -> SAFETY-METRICS NULL** (pp clauses: not met; the KPI-CI clause is context, not a gate trigger: KPI CIs exclude zero).

Reading (binding): the gate is the two pp clauses, so this matrix reports
a safety-metrics null. The KPI arm difference (unverified worse than
verified, +23.05 USD cost / +4.53 kW peak at n=49) is an LLM-quality
outcome -- it says the unverified proposer is worse, NOT that the
verifier adds safety value -- and is reported as context only. The
verifier's safety value is the question the M2b hostile-proposer pilot
is designed to answer.
