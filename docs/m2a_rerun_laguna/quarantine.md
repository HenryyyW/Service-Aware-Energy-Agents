# Quarantine record — M2a laguna matrix (`experiments/m2a_rerun_laguna`)

One cell of the 150-cell matrix is quarantined and is **not** part of the
released artifact or any analysis.

| Field | Value |
|---|---|
| Run id | `scenario_d_llm_agent_verified_1234` |
| Arm | `llm_agent_verified` (scenario D, seed 1234) |
| Model / provider | `poolside/laguna-xs-2.1`, NVIDIA NIM |
| `llm_backend_errors` | 1 (of 24 steps) |
| `first_attempt_validity` (per step) | 0.9583 (23/24) |
| `llm_fallback_steps` | 1 |
| Wall clock | 203.2 s |

**Why**: the guard agreed with the PM (2026-11-08) — a cell with any
`llm_backend_errors` is fallback-degraded, and no fallback-degraded cell may
enter the matrix. The failed step was served by the deterministic proposer, so
the cell does not measure the LLM arm.

**Where**: moved out of the matrix to `/tmp/opencode/laguna_quarantine/`
(untracked, outside the repo). Re-runnable with
`--force` if a clean replacement cell is ever wanted; the matrix then reports
n=50/50 again.

**Effect on the artifact**: `dist/m2a-laguna-matrix-2026-11-08.zip` contains
**149 runs** (50 `llm_agent` + 49 `llm_agent_verified` + 50 `multi_agent`), with
`INDEX.json` and per-file `SHA256SUMS`. Every statistic that involves the
verified arm uses n=49 and says so.
