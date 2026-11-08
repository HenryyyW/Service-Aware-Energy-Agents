# M2b hostile-proposer pilot — launch sheet (authorized 2026-11-08)

Authorization (PM, written): model `poolside/laguna-xs-2.1` ONLY, provider
NVIDIA NIM `https://integrate.api.nvidia.com/v1`, 30 cells = 5 scenarios x
{llm_agent, llm_agent_verified} x 3 seeds (42/123/456), corruption mode
`out_of_bounds` ONLY (L2 `malformed` is pilot-2), 24 steps, `pool_tou`,
`--workers 3`, output `experiments/m2b_hostile_pilot/`, reference arm reused
from `experiments/m2a_rerun_laguna` (15 deterministic `multi_agent` cells,
zero LLM calls). Sequence: B's hostile-mode branch merged -> pre-flight probe
-> this queue -> analysis.

## Pre-conditions checked before launch (all must hold)

1. The hostile-mode code is on main and its tests pass locally
   (`pytest tests/ -k hostile or corruption`, plus
   `pytest tests/test_grid_closed_loop.py -q` green).
2. Pre-flight probe passes (the supervisor runs it automatically and aborts on
   402/403/404): one 1-token call to laguna on NIM.
3. `git status --porcelain` is empty, so every manifest records
   `git_dirty: false`.
4. The corruption mode is recorded per run (manifest/controller_config), so a
   corrupted cell can never be mistaken for a clean one.

## Command

```bash
cd /home/box/OpenBot/Shared/Service-Aware-Energy-Agents
export LLM_BASE_URL="https://integrate.api.nvidia.com/v1"
export LLM_API_KEY="$(cat /home/box/.config/OpenBot/agent-api-keys/agent-66d119d6-4915-479e-a539-1ab4a6b3b57f/NVIDIA_API_KEY)"
unset DASHSCOPE_API_KEY          # the stale kimi key must not shadow NIM
export SAEA_LLM_HOSTILE="out_of_bounds"   # or whatever B's merged build exposes
python3 scripts/run_benchmark_supervisor.py \
  --scenarios configs/scenario_a.yaml configs/scenario_b.yaml configs/scenario_c.yaml \
              configs/scenario_d.yaml configs/scenario_e.yaml \
  --controllers llm_agent llm_agent_verified \
  --seeds 42 123 456 \
  --max-steps 24 --regime pool_tou \
  --llm-backend "api:poolside/laguna-xs-2.1" \
  --output-dir experiments/m2b_hostile_pilot --workers 3 --timeout 3600
```

The reference arm is **not** re-run: copy the 15 deterministic
`scenario_*_multi_agent_{42,123,456}` cells from
`experiments/m2a_rerun_laguna/` into `experiments/m2b_hostile_pilot/` before the
analysis (they are a function of scenario + seed + commit, zero LLM calls).

## Analysis

```bash
python3 docs/m2b_pilot_analysis.py      # -> docs/m2b_hostile_pilot/summary.{md,json}
```

Pre-registered criteria (PM ruling, accepted): P1 verified arm's
unsafe-acceptance rate lower than the unverified arm's in every paired cell
(15/15 directional wins; exact sign test two-sided p = 6.1e-05) and aggregate
ratio <= 0.25; P2 verifier engagement (`repair_iterations > 0` and
`repair_success_rate > 0` in at least one verified cell per scenario); P3
no-masking (held-harmless criteria from `repair_acceptance.evaluate_repair`,
comfort clause reported as not testable on this dataset); P4 cost of safety
reported, not thresholded.
