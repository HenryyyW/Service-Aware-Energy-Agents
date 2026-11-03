# Benchmark expansion plan (B-axis) — P2P official matrix, LMP+RL arm, seed expansion

**Status: DESIGNED, PENDING APPROVAL.** No long runs launched. Owner: Research
Engineer (design + analysis); execution orchestration: QA/DevOps per
`experiments/BENCHMARK_MATRIX.md` convention. Design basis: the pre-registered
Phase-2 plan (`docs/phase2_experiment_plan.md` §6 M3 item 5, RQ3), the Phase-1
matrix spec, and the executed run history (~310+ runs; per-controller medians
53.4–61.8 s, overall median ≈ 55.5 s, max 138.7 s — `arxiv_submission`
reproducibility section).

## 0. Feasibility facts checked on main (2026-11-03)

| Fact | State |
|---|---|
| `run_experiment.py --regime p2p` | Supported (`REGIMES = ("tou_solo","pool_tou","lmp","p2p")`); sets `market_type=p2p`, `cost_basis=tariff` (bilateral first, residual at TOU); regime + basis recorded in `result.json`/`manifest.json` |
| Settlement gate | `src/simulation/settlement_gate.py` post-run ledger validation; exercised by `tests/test_p2p_integration.py::test_p2p_settlement_gate_integration` |
| Invariant suite | 7 tests in `tests/test_p2p_integration.py` (bilateral+residual, partial fill, price-time priority, min spread, uniform price, gate integration, invariants) |
| Market clearing is controller-agnostic | Clearing runs in `SimulationCoupler.step()` before power flow (`src/simulation/coupling.py`), so all 5 controllers keep the comparability spine under p2p |
| 138-state LMP RL policies | `experiments/reference/rl_policy/lmp_scenario_{a..e}.json` tracked on main; encoder `encode_state_lmp` (126 base + 12 LMP price buckets) in `src/controllers/rl.py` with metadata-driven auto-resolution; training recipe in `experiments/train_rl.py` header (60 episodes, seed 0, ~10 min/scenario, one-off — already trained) |
| `run_benchmark.py` regimes | **Cannot** drive regimes (fixed subprocess args, no `--regime`, no env fallback). Regime matrices are driven per-run via `run_experiment.py --regime ...` (same pattern as the 100-run `experiments/m52_benchmark` LMP matrix) |
| p2p summary metrics | `p2p_volume_kwh`, `p2p_value_usd`, `p2p_trades`, `p2p_participation_share` are **not** aggregated by the runner; per-step market history (`clearing_price`, `market_type`, `avg_clearing_price`) is in run artifacts — derived at analysis time (Research Engineer remit). Verify field presence in B0 smoke |

## 1. Run-count and wall-time summary

Runtime model: `wall ≈ runs × median_per_run / workers` (+ tail). Per-controller
medians from the executed history: rule_based 56.6 s, multi_agent 53.4 s,
centralized 58.6 s, mpc 61.8 s, rl 54.1 s (mean ≈ 56.9 s); max observed
138.7 s. `--workers 3`, per-run `--timeout 900` (conventions unchanged).

| Phase | Matrix | Runs | Wall @ 3 workers (est.) | Serial equiv. |
|---|---|---:|---:|---:|
| B0 | p2p smoke + gate validation + calibration | 2 | ~2 min | ~2 min |
| B1 | P2P official: 5 scenarios × 5 controllers × 5 seeds | 125 | ~45 min (budget 1 h) | 2.0 h |
| B2 | LMP+RL arm: 5 scenarios × `rl` × 5 seeds | 25 | ~10 min | 22 min |
| B3 | Seed expansion 5→10: +5 seeds × (TOU 125 + LMP 125 + P2P 125) | 375 | ~2.2 h | 5.9 h |
| **Total** | | **527** | **≈ 3 h** (budget 4 h) | ≈ 8.3 h |

Estimates exclude LLM arms (latency-dominated, ~3–4 min/run; unchanged). P2P
settlement overhead is unknown until B0; if it adds >30 s/run, B1 rises to
~1.2 h and B3 to ~2.8 h — still inside the 4 h budget. Disk: ≈ 0.5–0.7 GB for
527 runs (deterministic runs are lighter than the 63 MB/47-run M2a screen).

## 2. B1 — P2P official matrix (125 runs)

Design (implements the deferred plan §6 M3 item 5, minus the new-controller
variants — see §6 Out of scope):

- Grid: scenarios {A, B, C, D, E} × controllers {`rule_based`, `multi_agent`,
  `centralized`, `mpc`, `rl`} × seeds {42, 123, 456, 789, 999}.
- Regime: `--regime p2p`; output **`experiments/matrix_p2p/`** (separate dir is
  mandatory: run ids stay `{scenario}_{controller}_{seed}` and the runner
  skips runs with an existing `result.json`, so p2p runs must not share a dir
  with the pool_tou `matrix_full`).
- Pairing: every p2p run pairs with the existing pool_tou run at the same
  (scenario, controller, seed) in `experiments/matrix_full` — **zero pool
  re-runs**. RQ3 evidence = paired per-seed deltas (p2p − pool) with Student-t
  95% CIs, Holm-corrected across the 4 controller comparisons per scenario.
- `rl` under p2p uses the tracked base policies (`scenario_{a..e}.json`,
  126-state): the billed cost basis under p2p is the residual TOU tariff, so
  the price signal matches the base encoder. Recorded per run via
  `controller_config.policy_path`.
- Per-run acceptance: exit 0 **and** settlement-gate validation of the run's
  ledger passes; gate failures mark the run failed (re-run, don't waive).
- Analysis deliverables (Research Engineer): `experiments/matrix_p2p/`
  summary tables + paired-delta stats + derived p2p metrics
  (`p2p_volume_kwh`, `p2p_value_usd`, `p2p_trades`, `p2p_participation_share`,
  savings Gini) in the m52-analysis format.

Command template (per run; QA wraps in the supervisor loop):

```bash
python -m experiments.run_experiment \
  --config configs/scenario_${S}.yaml \
  --controller ${C} --seed ${SEED} \
  --regime p2p \
  [--rl-policy experiments/reference/rl_policy/scenario_${S}.json] \
  --output-dir experiments/matrix_p2p
```

## 3. B2 — LMP+RL arm (25 runs)

Completes the LMP matrix to the full 5×5×5 = 125 (currently 100, `rl`
excluded). Removes the paper limitation "RL excluded from LMP matrix (no
tracked LMP policies)" — the policies are now tracked fixtures.

- Grid: scenarios {A–E} × `rl` × seeds {42, 123, 456, 789, 999}.
- Regime: `--regime lmp`; policy: `--rl-policy
  experiments/reference/rl_policy/lmp_scenario_${S}.json` (138-state,
  12 LMP price buckets; auto-resolved by the controller from policy metadata).
- Output: **`experiments/m52_benchmark/`** (append; run ids
  `scenario_${S}_rl_${SEED}` don't collide with the existing 100 — skip-existing
  is safe, and one dir keeps the LMP summary single-tabled).
- No training needed (policies committed; evaluation seeds change environment
  traces only, per the Phase-1 convention).
- Paper: LMP tables (T2/T3 LMP subsection) gain the `rl` row.

## 4. B3 — Seed expansion 5 → 10 (375 runs)

**Proposal: expand all deterministic-controller matrices to 10 seeds**:
existing {42, 123, 456, 789, 999} + new {1234, 2024, 3456, 5555, 8888}
(documented, collision-free). LLM ablation arms (`llm_agent`,
`llm_agent_verified`, fallback and real-LLM) stay at 5 seeds — they are
latency-dominated (~3–4 min/run; +50 runs ≈ +3.3 h) and their null result is
not CI-limited.

| Matrix | Dir | New runs | Wall @ 3 workers |
|---|---|---:|---:|
| pool_tou | `experiments/matrix_full` (append) | +125 | ~45 min |
| lmp | `experiments/m52_benchmark` (append, now incl. `rl`) | +125 | ~45 min |
| p2p | `experiments/matrix_p2p` (append) | +125 | ~45 min |

Statistical payoff (§4 protocol of BENCHMARK_MATRIX.md): 95% CI half-width =
t(0.975, n−1)·s/√n → factor drops from 1.241 (n=5) to 0.715 (n=10), i.e.
**~42% tighter CIs** (t-critical 2.776→2.262 plus the √n gain); paired t gains
df 4→9, materially improving Holm-corrected power on the small controller
gaps the pilot flagged. Cost: ~45 min per matrix at 3 workers — the cheapest
rigor-per-minute buy available before the deadline.

## 5. Pre-launch checklist (blocking)

1. **B0 smoke** (first 2 runs of B1): `scenario_a` × {`rule_based`,
   `multi_agent`} × seed 42 under `--regime p2p`; then (a) settlement-gate
   validation passes, (b) `result.json` contains the market fields
   (`avg_clearing_price`, `market_type`, per-step clearing history) — if the
   derived-metric inputs are absent, that is a Backend blocker, not a runner
   toggle, (c) calibrate actual per-run time vs the 56.9 s estimate.
2. Invariant suite green on current main: `pytest tests/test_p2p_integration.py
   tests/test_market_redispatch_integration.py tests/test_settlement_reporting.py -q`.
3. Pool counterparts complete for pairing: 125/125 `result.json` present in
   `experiments/matrix_full` (skip-existing makes gaps visible in
   `failed_runs.json`).
4. Output dirs as in §2–§4; never mix regimes in one dir.
5. LMP+RL dry run: 1 run (scenario_a, seed 42) and confirm
   `controller_config.policy_path` points at the `lmp_` policy and the
   manifest records `pricing_regime=lmp`.
6. Conventions: `--workers 3`, per-run `--timeout 900`, `PYTHONHASHSEED` per
   run (handled by the runner), `failed_runs.json` reviewed before summary.

## 6. Out of scope (flagged, not scheduled)

- **P2P-aware controller variants** (`p2p_rule_based`, `p2p_multi_agent` —
  plan §6 M3 item 5): new controller code + tests. The official matrix above
  keeps the existing comparability spine; variants are a follow-up decision
  after B1 results.
- LLM arms under p2p / LMP at 24 steps: post-B1/B2 decision.
- `run_benchmark.py` `--regime` passthrough: nice-to-have for QA's supervisor;
  the runner file is frozen for the Research Engineer (project rule), so this
  is QA's call. The per-run `run_experiment.py` loop works without it.
- Re-running the M2a screen or fallback ablation at 10 seeds.

## 7. What lands in the paper

| Paper change | Source |
|---|---|
| New results subsection "P2P regime: bilateral trading vs pool" (RQ3): paired deltas, p2p volume/value/trades/participation, savings Gini, settlement-gate pass statement | B1 + analysis |
| LMP tables gain the `rl` row; Limitations item "RL excluded from LMP matrix" removed | B2 |
| T2/T3/T4 recomputed at n=10 (~42% tighter CIs); T5 reproducibility protocol states 10 seeds; abstract run-count updates | B3 |
| `experiments/BENCHMARK_MATRIX.md` §8 addendum = new source of truth for the expanded matrix | this plan |
