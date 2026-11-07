# M2a 10-seed re-run — plan, smoke result, and launch command (2026-11-07)

Author: Research Engineer. Status: **ready, waiting on PM scope confirmation**
(messaged 2026-11-07: item list for "5/7/10" is not in the repo docs, and the
queue is ~12 h of LLM runs, so I want the go-ahead before launching).

## 1. Why a re-run

The 2026-11-04 M2a screen (45 runs, 3 seeds) ran on the pre-fix PV tree, and its
proposer was `poolside/laguna-xs-2.1` over NVIDIA NIM. The paper now withholds
the model identity per operator policy and runs on the hosted API transport
(`ApiPromptCallable`, default model `kimi-k2.7-code` via DashScope). The
re-run reproduces the M2a protocol at **10 seeds** on the post-fix physics so
the absolutes are usable, not just the gate verdict.

## 2. Credential status (verified, no key value recorded)

* Saved `LLM_API_KEY` in the OpenBot key store: **rejected** by
  `dashscope-intl.aliyuncs.com` with `HTTP 401 Incorrect API key` — it belongs
  to the previous NIM endpoint and cannot run the hosted transport.
* A current `DASHSCOPE_API_KEY` was saved by the user via
  `openbot.request_api_key`. Verified with a single call:
  `model_digest=kimi-k2.7-code`, reply OK, 15 prompt / 23 completion tokens,
  1.48 s round-trip.
* The transport reads `DASHSCOPE_API_KEY` (fallback `LLM_API_KEY`) from the
  environment at call time; the key never enters code, configs, logs, or
  manifests.

## 3. Smoke run (one cell, 24 steps, verified arm)

```
scenario_a / llm_agent_verified / seed 42 / regime pool_tou / max-steps 24
--llm-backend api:kimi-k2.7-code
```

| Field | Value |
|---|---|
| exit code | 0 |
| `agent_backend` (manifest) | `api` |
| `agent_model_digest` | `kimi-k2.7-code` |
| `prompt_version` / `prompt_hash` | `llm_dispatch_v2` / `141ea700…` |
| `repair_prompt_hash` | `028a2929…` |
| `sampling_temperature` / `sampling_seed` | 0.0 / 42 |
| `agent.repair_iterations` | 0 |
| `agent.first_attempt_validity` | 1.0 |
| `controller_config.first_attempt_validity` | 0.8 (per-step definition) |
| wall clock | **1344.7 s** (≈22.4 min) |

Runtime is the planning constraint: 100 LLM runs at `--workers 3` ≈ **12 h**
(50 `multi_agent` reference runs add ~30 min). The supervisor runs the LLM arms
since `e58207578`, so the queue is resumable, retried, and per-run isolated
(`SAEA_RUN_ID`); a killed queue continues from `status.json`.

## 4. Scope

| Leg | Runs | Purpose |
|---|---|---|
| `llm_agent` (unverified) × 5 scenarios × 10 seeds | 50 | arm A |
| `llm_agent_verified` × 5 scenarios × 10 seeds | 50 | arm B |
| `multi_agent` 24-step reference × 5 scenarios × 10 seeds | 50 | paired baseline |

Total 150 runs at one commit, `git_dirty: false`, run IDs
`{scenario}_{controller}_{seed}` in `experiments/m2a_rerun/`. All arms on
`regime pool_tou`, `--max-steps 24`.

## 5. Launch command (once approved)

```bash
cd /home/box/OpenBot/Shared/Service-Aware-Energy-Agents
export DASHSCOPE_API_KEY="$(cat /home/box/.config/OpenBot/agent-api-keys/agent-af498092-f4e0-4fe8-a864-954882d74abf/DASHSCOPE_API_KEY)"
unset LLM_API_KEY   # the stale NIM key must not shadow DASHSCOPE_API_KEY

SEEDS="42 123 456 789 999 1234 2024 3456 5555 8888"
python3 scripts/run_benchmark_supervisor.py \
  --scenarios configs/scenario_a.yaml configs/scenario_b.yaml configs/scenario_c.yaml \
              configs/scenario_d.yaml configs/scenario_e.yaml \
  --controllers llm_agent llm_agent_verified multi_agent \
  --seeds $SEEDS --max-steps 24 --regime pool_tou \
  --llm-backend api:kimi-k2.7-code \
  --output-dir experiments/m2a_rerun --workers 3 --timeout 3600
```

Per-run timeout is raised to 3600 s: the measured verified-arm run is 1344 s, so
the 900 s default would kill every LLM run. No repository writes while the queue
runs (any uncommitted file makes `git status --porcelain` non-empty and the
manifests record `git_dirty: true`).

## 6. Analysis

`python3 docs/m2a_rerun_analysis.py` writes `docs/m2a_rerun/summary.md` +
`summary.json`: per-arm aggregates (`first_attempt_validity`,
`repair_iterations`, fallback share, unrepaired violations), the pre-registered
M2b gate check (≥ 10 pp on unrepaired violations or fallback share, or KPI CIs
excluding zero), paired arm difference (unverified − verified) with paired
t-tests, and KPI deltas vs the 50 paired `multi_agent` runs.
