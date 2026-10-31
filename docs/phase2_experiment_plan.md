# Phase 2 experiment plan: pricing structure, real-LLM agents, P2P

**Status**: proposal for review — no runs scheduled from this document
**Branch**: `feature/phase2-experiment-plan`
**Base**: `origin/main` `0996006` (post-#37; results section v1.0 merged)
**Inputs**: `docs/phase2_llm_backend_design.md`, `docs/phase2_market_settlement_design.md`,
`experiments/BENCHMARK_MATRIX.md`, `experiments/ABLATION_DESIGN.md`,
`docs/paper_results_section.md` (v1.0, PR #37)
**Gate decision in force**: local Ollama only (`qwen2.5-coder:7b`), no paid
provider keys (PR #35, `f5048ab`)

---

## 1. What Phase 2 has to establish

| RQ | Claim the paper wants to make | Evidence required | What would falsify it |
|---|---|---|---|
| RQ1 | Locational pricing changes the cost/service Pareto relative to static TOU, and price-aware controllers exploit the locational signal | Paired `lmp` vs `pool_tou` deltas per scenario/controller/seed with 95% CIs; measured LMP dispersion > 0 and non-zero congestion rent; controllers see the price they are billed on | LMP prices uniform across buses, or cost metrics still billed at tariff, or deltas inside a pre-declared equivalence margin |
| RQ2 | Verification adds value on top of an LLM proposer relative to no verification | `llm_agent_verified` vs `llm_agent` on a real backend: fewer unrepaired violations / fewer service failures, cost-service outcome at matched service | Both arms produce identical action streams (the current implementation does), or verified arm only wins by falling back more often |
| RQ3 | Bilateral P2P trading redistributes savings relative to pool clearing without breaking settlement invariants | P2P engine + invariant tests + paired `p2p` vs `pool` runs | Invariants fail, or P2P volume is negligible |

The Phase 1 spine stays: **cost at matched service (F3), not a single KPI.**
Phase 2 adds a pricing-regime axis to that spine, not a new headline metric.

---

## 2. Gate state that constrains the plan

| Item | State at `0996006` | Consequence |
|---|---|---|
| LMP clearing engine (`src/simulation/market.py::LmpClearing`) | Merged, tested in isolation (`tests/test_lmp_market.py`) | Market layer exists but is fed uniform prices (see P0-1) |
| `DynamicPricingConfig` | Schema merged, read only as `enabled` in `coupling.py` | `price_cap_per_kwh`, `lmp_update_interval_minutes`, `congestion_cost_method`, `fallback_to_tariff`, `pricing_type` are inert |
| AgentBackend (`src/agents/backend/`) | Ollama + fallback + remote implementations merged; Ollama reachable on this machine | Available, but not wired into the ablation controllers (P0-2) |
| `llm_agent` / `llm_agent_verified` | Implemented, record `agent_backend`, prompt hash, sampling seed | Arms are not behaviourally distinct (P0-3) |
| P2P | Design doc only; no `p2p` market type, no module | RQ3 cannot be scheduled (P0-4) |

---

## 3. Blocking findings and prerequisites

Each prerequisite has a single exit criterion; owners below are proposed and
need PM confirmation. **No matrix is scheduled until its prerequisite's test is
green.**

### P0-1 — LMP prices are uniform today (correctness, blocks RQ1)

`PandapowerAdapter.compute_lmp_prices()` calls `pp.runopp(...)` and, on any
exception, silently returns `base_energy_price` for every bus. The OPF call
fails on the generated networks:

```
$ python  # adapter built from configs/scenario_a.yaml
>>> pp.runopp(net, algorithm='dc', ...)
KeyError: 'OPF parameters are not set correctly. See error log.'
ERROR:pandapower.run: These columns are missing in sgen: ['min_p_mw' 'max_p_mw']
```

Measured consequence on scenario A, midday loads (30/35/25/40/28 kW) with
−60 kW PV at two buses:

```
building LMPs: {b0: 0.25, b1: 0.25, b2: 0.25, b3: 0.25, b4: 0.25}
price spread: 0.0 %
res_bus['lambda'] present: False   res_bus['lam_p'] present: False
```

A 30-step run with `market_type: lmp` + `dynamic_pricing.enabled: true` clears
30.77 kWh and reports 2.80 USD "savings" — but every trade clears at the
uniform base price. **The merged LMP arm is uniform pricing with a different
label.** This is the same defect class as the pre-fix EV 0.000 result: a silent
fallback producing a publishable-looking number.

**Fix (proposed owner: Backend/Simulation Engineer B — `market.py` and
`pandapower_adapter.py`)**:

1. Set OPF parameters on the network: `min_p_mw`/`max_p_mw` on `sgen` and
   `ext_grid`, `controllable` flags, and a cost curve for the slack (otherwise
   the dual is undefined). Verify `res_bus` exposes `lam_p` (AC OPF) or switch
   the DC formulation to one that returns bus duals.
2. Return a **structured failure** (`LmpResult(prices, status, reason)`) instead
   of a base-price dict; record `lmp_opf_fallback_steps` per run.
3. Apply `price_cap_per_kwh` and honour `lmp_update_interval_minutes` (validate
   it equals the simulation timestep, currently 60 min; reject 15 min with a
   clear error rather than pretending to interpolate).
4. Bill the LMP regime on LMP: add `cost_basis: "tariff" | "lmp"` and
   `lmp_cost_usd` to `EnergyMetrics`; the settlement engine must price imports
   and exports at the building's LMP when the regime is LMP.
5. Give controllers the price they are billed on: when dynamic pricing is on,
   override `{building}_electricity_pricing` from LMP (the Phase 1 lesson —
   controllers optimised a 2×-wrong price until the adapter override).
6. Record per-step LMPs per building in `grid_diagnostics.jsonl` and the run
   summary (`lmp_price_mean`, `lmp_price_spread`, `lmp_price_spread_pct`).

**Exit criterion — `tests/test_lmp_prices.py`** (new; the current tests only
feed synthetic prices into `LmpClearing`):

- unconstrained network → all bus LMPs equal within 1e-9 and equal the base
  price;
- congested network (forced line loading > 0.9 pu) → spread ≥ 1 % and the
  congested bus has the higher price;
- cap applied (`max(price) ≤ price_cap_per_kwh`) and cap-hit steps counted;
- OPF failure sets `status="fallback"`, increments `lmp_opf_fallback_steps`, and
  the run is **not** silently labelled LMP;
- a 5-step integration run on scenario C shows `lmp_price_spread_pct > 0` in
  `result.json`.

### P0-2 — the ablation controllers have no real backend (blocks RQ2)

`src/controllers/llm_agent.py::_backend_from_env()` only builds a debug `echo`
backend; the only live path is `SAEA_LLM_BACKEND=echo`. No Ollama/AgentBackend
bridge exists, so `llm_agent` runs are always `agent_backend: "fallback"`.

Second, the model does not emit bare JSON. Measured on this machine:

```
model qwen2.5-coder:7b (digest dae161e27b0e, 4.4 GB), temperature 0, seed 42
call 1 (cold): 20.1 s   call 2: 8.1 s   call 3: 7.8 s
prompt_eval_count 639, eval_count 327
3/3 responses wrap the array in a markdown json fence  →  json.loads(raw) fails 3/3
```

**With the current parser every LLM step is unparseable and falls back**, so a
"real-LLM" arm would again be fallback in disguise.

**Fix (proposed owners: Backend/Simulation Engineer A for
`src/agents/backend/`, Research Engineer for the controller side)**:

1. New `ollama_prompt_callable(model, endpoint, temperature, seed)` in
   `src/agents/backend/local.py`: a synchronous `prompt -> text` adapter over
   `OllamaBackend` (the controllers take a `Callable[[str], str]`), with a hard
   per-call timeout and a token budget.
   Wire it from `AGENT_BACKEND=ollama:<model>` in `_backend_from_env()`, and
   set `agent_backend = "ollama-local"` plus `agent_model = "qwen2.5-coder:7b"`
   (results tables label the arm `ollama-local`, never a bare `"llm"`).
2. Add `parse_llm_actions(raw) -> (actions, status)` with
   `status ∈ {"clean", "fenced", "invalid"}`. Strip a single markdown fence and
   record it as a **formatting** violation; do not hide it.
3. Record per run: `llm_calls`, `llm_raw_parse_failures`, `llm_fenced_outputs`,
   `llm_latency_p50_ms`, `llm_latency_p95_ms`, `llm_prompt_tokens`,
   `llm_completion_tokens`, `llm_fallback_steps`, `llm_fallback_step_share`,
   plus the Ollama model digest in `manifest.json`.
4. Keep the prompt fixed for the whole matrix (`llm_dispatch_v2`, hash in the
   manifest). Any prompt edit invalidates the arm; there is no per-run prompt
   tuning.

**Exit criterion**: one full-week `llm_agent` run on scenario A at
`agent_backend: "ollama-local"` / `agent_model: "qwen2.5-coder:7b"`, with
`llm_fallback_step_share < 0.25`; a second identical run for reproducibility
records the same model digest and prompt hash.

### P0-3 — the two ablation arms are behaviourally identical (blocks RQ2)

`LLMAgentController.get_actions()` **also** runs the clamp-repair loop
(`while repairs < REPAIR_BUDGET and not self._actions_valid(...)`), and
`LLMVerifiedController` only adds the fallback-mode accounting branch. With a
real backend, both arms clamp bound violations the same way, and the adapter
clamps to `[-1, 1]` again downstream, so **the action streams are identical by
construction**. The Phase 1 T4 null ("both arms equal `rule_based`") therefore
has two causes, not one: the fallback proposer *and* a shared repair path. The
second cause survives a real backend.

**Fix (proposed owner: Research Engineer, this plan's author)**:

| Arm | On parse/validation outcome | Treatment |
|---|---|---|
| `llm_agent` | apply model values as proposed; adapter clamps to device limits; count `llm_unrepaired_violations` | no repair, no replan |
| `llm_agent_verified` | shape/bounds/service check → re-prompt once with the violation text → if still invalid, deterministic fallback for that step; cap 2 repairs | repair + replan |

Verified repair must **replace** the step with the deterministic action, not
clamp silently — clamping is what makes the arms identical. Tests must assert
the asymmetry: a synthetic 50 kW proposal on a 5 kW battery yields 5 kW
(`unverified`, adapter clamp) vs the rule-based setpoint (`verified`).

**Exit criterion**: `tests/test_llm_controllers.py` includes an
out-of-bounds proposal test that produces different action streams per arm, and
`ablation_agent_execution.md` reports non-zero `llm_unrepaired_violations` for
the unverified arm and non-zero `repair_iterations` for the verified arm.

**Paper impact**: `docs/paper_results_section.md` §5.4 currently reports the
fallback-mode ablation. That text stays valid (fallback numbers are unchanged),
but after this fix it must say that fallback-mode T4 cannot separate the arms
for two reasons, and point at the Phase 2 RQ2 result. No numbers are retracted.

### P0-4 — P2P does not exist (blocks RQ3)

No `p2p` market type (`EnergySharingConfig.market_type` validator allows only
`uniform_price | weighted | carbon_aware | fairness_aware | lmp`), no
`src/coordination/p2p.py`, no `P2POrder`/`P2PTrade` schemas. RQ3 is therefore a
**preparation** deliverable in this phase (section 6), not a run matrix.

---

## 4. M1 — pricing-structure matrix (RQ1)

### 4.1 Regimes

Three regimes, so the pricing effect is not confounded with the sharing effect:

| Regime ID | `energy_sharing.enabled` | `market_type` | `dynamic_pricing.enabled` | What it measures | Phase 1 mapping |
|---|---|---|---|---|---|
| `tou_solo` | `false` | — | `false` | no community pool, static TOU | A/B/C/E Phase 1 rows; **D has no counterpart yet** |
| `pool_tou` | `true` | `uniform_price` | `false` | pool clearing at TOU | D Phase 1 rows; new for A/B/C/E |
| `lmp` | `true` | `lmp` | `true` | pool clearing at locational prices | new |

Regime pairs: `pool_tou − tou_solo` = **sharing effect**; `lmp − pool_tou` =
**pricing effect**. Scenario D's `tou_solo` rows are the missing no-sharing
counterfactual for the Phase 1 sharing claim — a bonus result, not a
prerequisite.

### 4.2 Matrix

| Dimension | Values | Count |
|---|---|---|
| Scenarios | A, B, C, D, E | 5 |
| Regimes | `tou_solo`, `pool_tou`, `lmp` | 3 |
| Controllers | `rule_based`, `multi_agent`, `centralized`, `mpc`, `rl` | 5 |
| Seeds | 42, 123, 456, 789, 999 | 5 |
| **M1 core** | | **375** |
| Cap sensitivity (scenario C × 5 controllers × 5 seeds × cap {0.35, 0.50} USD/kWh; C is the high-PV export-cap scenario, and the cap runs are only informative if `lmp_price_spread_pct > 0` there) | | 50 |
| MPC perfect-foresight LMP sensitivity (scenario C × 5 seeds, `mpc` only) | | 5 |
| **M1 total** | | **430** |

Run id: `{scenario}_{regime}_{controller}_{seed}` (requires a `--regime` flag in
`run_benchmark.py`; `scenario_id` stays clean so paired analysis keys on
`(scenario, controller, seed)`). `pricing_regime` and `cost_basis` go into
`result.json` and `manifest.json`.

### 4.3 Controllers under LMP

| Controller | Change needed for the LMP arm |
|---|---|
| `rule_based` | none (price-blind thresholds; it is the reference, not a price responder) |
| `centralized` | none (heuristic joint dispatch) |
| `multi_agent` | read LMP from observations via the adapter override (no code change if the override lands) |
| `mpc` | objective must price against a **causal** LMP forecast: persistent (last observed) LMP over the 24 h horizon; no perfect foresight except the labelled M1 sensitivity arm |
| `rl` | retrain per LMP scenario (`state` price bucket from LMP, 60 episodes, seed 0): 5 policies, ~10 min each; publish to `experiments/reference/rl_policy/lmp_<scenario>.json` |

The `tou_solo` and `pool_tou` arms reuse the Phase 1 policies. Policy files are
fixtures, not generated output, and follow the existing `git add -f` convention.

### 4.4 What M1 reports

- T6: regime table per (scenario, controller): mean ± 95 % CI for
  `total_cost`, `lmp_cost_usd`, `peak_demand_kw`, `ev_completion_rate`,
  `gini_coefficient`, `market_volume_kwh`, `lmp_price_spread_pct`.
- T7: paired regime deltas (`lmp − pool_tou`, `pool_tou − tou_solo`) with Holm
  across the 5 controllers within scenario × metric family.
- F7: cost-vs-service scatter with regime as marker shape (extends F3).
- F8: LMP price spread over the week for scenario C (the congestion case).
- F8b (optional, gated on §11.1): per-step attribution of cost/service changes
  for the LMP and Scenario E runs, once the structured dispatch-events endpoint
  exists.

---

## 5. M2 — real-LLM ablation (RQ2)

### 5.1 Arms

| Arm | Backend | Treatment |
|---|---|---|
| `llm_agent` | `api-hosted` — `AGENT_BACKEND=api:poolside/laguna-xs-2.1` | single-pass proposal, applied as-is (adapter clamps) |
| `llm_agent_verified` | same | verify → re-prompt once → deterministic fallback; 2-repair cap |
| `multi_agent` | none | deterministic reference, paired by scenario/seed |

Same scenario configs and regime as Phase 1 (`tou_solo`, plus D's `pool_tou`)
so the agent effect is not confounded with pricing.

**Backend decision (2026-10-31, PM per user order).** P0-2 runs on the hosted
OpenAI-compatible API, not Ollama: `LLM_BASE_URL=https://integrate.api.nvidia.com/v1`
(NVIDIA NIM), Bearer key from the `LLM_API_KEY` environment variable (never in
the repo), transport `src/agents/backend/api.py::ApiPromptCallable` (PR #54).
Authoritative model: **`poolside/laguna-xs-2.1`** — measured on the full-week
168-step exit run `p02_fullweek_laguna_s42` (scenario A, `pool_tou`, seed 42):
`llm_fallback_step_share` 0.0 (< 0.25), first-attempt validity 1.0, 0 parse
failures, p50 4.2 s / p95 8.6 s per call, 209,841 prompt + 58,652 completion
tokens, wall ~21 min. `z-ai/glm-5.3-flash` is REJECTED on this account
(persistent HTTP 429; reasoning starves the JSON output — 2-step probe showed
fallback_share 1.0 at ~127 s/call); `gpt-4o-mini` is only the library's
default when `AGENT_BACKEND=api` carries no model suffix, not the project
model. The model is runtime config, so it appears in run artifacts
(`manifest.json:agent_model`), not in code or YAML.

### 5.2 Two-stage sizing (measured, not guessed)

Measured on `poolside/laguna-xs-2.1` (full-week exit run, 168 steps): ~1,250
prompt + ~350 completion tokens per call, p50 4.2 s / p95 8.6 s warm; a full
week is 168–169 steps ≈ 21 min wall per LLM run.

| Stage | Design | Runs | Projected wall |
|---|---|---|---|
| M2a screen | 5 scenarios × 2 LLM arms × 3 seeds × 24 steps (= 1 simulated day) + 15 `multi_agent` 24-step reference runs | 45 | ~2 h |
| M2b confirm | scenario A: 2 arms × 5 seeds × 169 steps; scenario E: 2 arms × 3 seeds × 169 steps | 16 | ~6.5 h |
| M2c reproducibility | A / verified / seed 42 repeated twice | 2 | ~50 min |
| **M2 total** | | **63** | **~9 h** |

Rules:

- Run LLM arms at `--workers 1`. Ollama shares the CPU with the simulator
  (16 logical cores, 23.3 GB RAM); parallel workers do not increase throughput
  and do make the per-call latency unreportable.
- 24-step M2a numbers are **not** comparable to full-week Phase 1 numbers; the
  screen only ranks arms and estimates variance. State the horizon in every
  caption.
- M2b is gated on M2a: only run it if the arms differ on
  `llm_unrepaired_violations` or `llm_fallback_step_share` by ≥ 10 percentage
  points, or the KPI CI excludes zero. Otherwise report the screen and a null.
- Validity gate: if `llm_fallback_step_share > 0.25`, label the arm
  "LLM-assisted (fallback-dominated)" and make no agent-capability claim.

### 5.3 Why a 7B local model is a legitimate test

Verification matters most where the proposer is imperfect. A 7B model is a
*harsher* proposer than a frontier model, so it exercises the repair path; the
paper must not generalise the result to frontier models, and the plan should
say so. A remote replication is possible later without re-design: one full-week
run is ~0.17 M prompt + 0.06 M completion tokens (measured 639/327 per call ×
169), priced from the provider's rate card at that time. No key is in scope now.

---

## 6. M3 — P2P preparation (RQ3, no runs this phase)

Deliverables, in order, all gated on P0-1 (LMP) because dual-layer clearing
needs a price signal:

1. `EnergySharingConfig.market_type` gains `p2p`; `P2PConfig`, `P2POrder`,
   `P2PTrade` schemas (from `docs/phase2_market_settlement_design.md`).
2. `src/coordination/p2p.py::P2PMatchingEngine`: batch double auction, uniform
   price within batch, price-time priority, min-spread 0.
3. Dual-layer clearing in `SimulationCoupler.step()`: P2P matches first,
   residual clears in the pool (documented as the choice; the design doc lists
   it as open question 2).
4. Invariant tests before any run: money conservation (`Σ net_settlement = 0`),
   energy conservation per interval, no-arbitrage band
   (`pool_price ∈ [export, import]`), P2P ledger conservation
   (`Σ buyer payments − Σ seller revenue = 0`), no double settlement of the same
   kWh.
5. Matrix (deferred): 5 scenarios × {`pool_tou`, `p2p`} × 5 controllers ×
   5 seeds = 250 runs, P2P-aware `p2p_rule_based` and `p2p_multi_agent`
   baselines, metrics `p2p_volume_kwh`, `p2p_value_usd`, `p2p_trades`,
   `p2p_participation_share`, savings Gini.

Gate: no P2P run is scheduled until the invariant suite is green and the
settlement ledger reconciles on a 24-step smoke run.

---

## 7. New baseline configs

Add under `configs/phase2/`; the Phase 1 configs stay untouched so the Phase 2
`tou_solo` arm is an exact rerun of the published matrix.

| File | Purpose |
|---|---|
| `scenario_{a..e}_lmp.yaml` | `enabled: true`, `market_type: "lmp"`, `dynamic_pricing.enabled: true` |
| `scenario_c_lmp_cap035.yaml`, `scenario_c_lmp_cap050.yaml` | price-cap sensitivity |
| `scenario_{a..e}_pool.yaml` | `enabled: true`, `market_type: "uniform_price"` (`pool_tou` arm) |
| `scenario_d_solo.yaml` | D with `enabled: false` (missing no-sharing counterfactual) |

LMP block — the diff from the Phase 1 config, apart from `scenario_id` and the
settlement interval:

```yaml
energy_sharing:
  enabled: true
  market_type: "lmp"
  settlement_interval: "1h"            # one 60-min simulation step
  dynamic_pricing:
    enabled: true
    pricing_type: "lmp"
    lmp_update_interval_minutes: 60    # must equal the timestep
    congestion_cost_method: "dc_approx"
    loss_factor: 1.0
    price_cap_per_kwh: 1.0
    fallback_to_tariff: true
```

New runner surface:

- `--regime {tou_solo,pool_tou,lmp}` → run id + `pricing_regime` + `cost_basis`;
- `--llm-backend ollama:<model>` (default from `AGENT_BACKEND`) recorded in the
  manifest;
- `run_benchmark` skips `rl` when the LMP policy file is absent and lists the
  run in `failed_runs.json` (existing behaviour, keep it).

---

## 8. Metrics and artifact schema

New fields, all written by the runner (no post-processing):

| Group | Field | Definition |
|---|---|---|
| Pricing | `pricing_regime` | `tou_solo` / `pool_tou` / `lmp` |
| Pricing | `cost_basis` | `tariff` / `lmp` |
| Pricing | `lmp_price_mean`, `lmp_price_spread`, `lmp_price_spread_pct` | per run, over buildings × steps |
| Pricing | `lmp_at_cap_steps`, `lmp_opf_fallback_steps` | counts; both must be 0 for a claim-grade LMP run |
| Pricing | `lmp_cost_usd` | energy + demand charge − export revenue, billed at LMP |
| Market | `market_volume_kwh`, `market_savings_usd`, `clearing_price_mean` | already partially present in `energy_sharing` |
| Agent | `llm_calls`, `llm_fenced_outputs`, `llm_raw_parse_failures`, `llm_unrepaired_violations`, `llm_fallback_steps`, `llm_fallback_step_share`, `llm_latency_p50_ms`, `llm_latency_p95_ms`, `llm_prompt_tokens`, `llm_completion_tokens` | per run |
| Agent | `agent_backend`, `agent_model` | `ollama-local` + `qwen2.5-coder:7b` (+ digest), or `fallback` |

`EnergyMetrics.cost_coverage` / `invalid_cost_steps` (Phase 1) are reused: an
LMP run with `cost_coverage < 1.0` is not claim-grade and must say why.

---

## 9. Statistical protocol

Inherited from `experiments/BENCHMARK_MATRIX.md` §4 (Student-t CIs, paired
seeds, Holm within scenario × metric family, 5 seeds), plus:

1. **Equivalence, not just significance, for the pricing effect.** Declare the
   margin before running: |Δ| < 5 % of the `pool_tou` mean on `total_cost` is
   reported as "no detectable pricing effect", with the CI, never as "LMP does
   not help" without the interval.
2. **Matched-service comparison.** The primary endpoint is cost at
   `ev_completion_rate ≥ 0.9` (the Phase 1 Pareto spine). Controllers that
   cannot reach the band are reported as such, not as cheap.
3. **Validity gate before any agent claim** (section 5.2). Fallback-dominated
   runs are labelled and excluded from capability claims.
4. **No pooling of horizons.** 24-step screen and 169-step confirm runs never
   share a table column.
5. Holm applies to the 5 controllers in M1 and to the 2 arms in M2; the
   agent-execution table is descriptive (no p-values on wall time).

---

## 10. Runtime budget (measured 2026-10-30, this machine)

| Item | Measured | Source |
|---|---|---|
| Phase 1 one-week TOU run | 55.5 s median, 138.7 s max | `analysis/repro/reproducibility.md` |
| 30-step TOU run | 14.9 s | this plan |
| 30-step LMP run (OPF currently failing) | 37.3 s | this plan |
| LMP per-step overhead | +0.75 s/step (failed OPF path) | derived |
| Projected one-week LMP run | ~3.1 min | derived; a working OPF adds to this |
| Ollama call, qwen2.5-coder:7b | 20.1 s cold, 8.1 / 7.8 s warm | this plan |
| Tokens per call | 639 prompt / 327 completion | this plan |
| Projected one-week LLM run | ~23.5 min | derived |
| Projected 24-step LLM run | ~3.5 min | derived |

| Matrix | Runs | Projection |
|---|---|---|
| M1 | 430 | 5–7 h at `--workers 3` |
| M2 | 63 | ~9 h at `--workers 1` (Ollama) |
| M3 | 0 this phase | — |

These are projections for QA scheduling, not commitments; the M1 LMP arm must
be re-timed after P0-1 lands.

---

## 11. Execution order and gates

| Step | Owner | Gate to pass |
|---|---|---|
| 1. P0-1 LMP correctness + tests | Backend B | `tests/test_lmp_prices.py` green; congestion spread ≥ 1 % |
| 2. P0-3 arm separation + tests | Research Engineer (this plan) | arms differ on a synthetic violation |
| 3. P0-2 Ollama bridge + parser + run fields | Backend A | one full-week run at `agent_backend: "ollama-local"`, fallback share < 25 % |
| 4. Configs + runner `--regime` | Research Engineer | 5-step smoke per regime, manifests carry `pricing_regime` |
| 5. M1 on QA/DevOps | QA/DevOps | 430 manifests at one commit, `git_dirty: false`, `failed_runs.json` accounted |
| 6. Analysis T6/T7/F7/F8 | Research Engineer | numbers reproduce from artifacts, no hand edits |
| 7. M2a screen | QA/DevOps | 45 runs, per-run backend/digest recorded |
| 8. M2a → M2b decision | PM + Research Engineer | stopping rule in §5.2 |
| 9. M2b/M2c | QA/DevOps | 18 runs, paired `multi_agent` reference |
| 10. Paper §5.6–5.8 draft | Research Engineer | claims map to T6/T7/T8 and F7/F8 |

Long-run orchestration stays with QA/DevOps; this plan hands over commands and
stopping rules, not runs.

### 11.1 UI and attribution dependencies (not on the M1/M2 critical path)

| Dependency | Estimate | Effect on this plan |
|---|---|---|
| Structured dispatch-events endpoint (Backend B scoping) | 2–3 days | `LmpClearing` today emits metadata only (buyers/sellers, LMP prices), with no per-timestep action/reason/grid_change/verification records. Until it lands, Scenario E and LMP analyses have run-level attribution only. Once it lands: Workspace timeline gains reason/verification columns, and an optional F8b (per-step attribution) becomes possible. **Not a gate for M1/M2 KPIs** — schedule in parallel. |
| `community_id` membership | 1–2 days | Needed for multi-community UI and per-community LMP grouping. All Phase 2 matrices stay single-community, so no matrix change; only the analysis grouping key is future-proofed. |

---

## 12. Risks and honesty rules

1. **Uniform LMP is the main risk.** If P0-1 is not fixed, the LMP arm is a
   relabelled uniform-price market and any "locational" claim is false. The
   `lmp_price_spread_pct > 0` check is mandatory in every claim-grade run.
2. **Cost-basis drift.** If `total_cost` stays tariff-billed while the market
   clears at LMP, controllers optimise one price and are scored on another —
   the exact Phase 1 defect that made every controller optimise a 2×-wrong
   price. `cost_basis` must match the regime.
3. **Arm collapse.** If P0-3 is not fixed, RQ2 is null by construction and the
   null is an implementation artifact, not a finding. Do not report it.
4. **Local-model generalisation.** Results describe a 7B local proposer, not
   frontier LLMs. Say so in the abstract, not only the limitations.
5. **Wall-clock load sensitivity.** The Phase 1 rerun showed a 138.7 s outlier
   on a loaded machine. Report median/IQR; do not compare runtimes across
   artifact cuts.
6. **Scenario fidelity.** A and D remain numerically identical under Phase 1
   settings (device-mix/trace-seed caveat). Phase 2 does not fix that; D's
   `tou_solo` vs `pool_tou` contrast is about settlement, not physics.
7. **No generated artifacts in git.** Policies are fixtures under
   `experiments/reference/`; run directories publish as release zips via
   `scripts/package_results.py`.

---

## 13. Analysis commands (after M1/M2 land)

```powershell
# T6/T7 + F7/F8 (new script, paired on scenario/controller/seed)
python -m experiments.price_regime_analysis --input experiments/phase2_matrix `
  --reference-regime pool_tou --out experiments/phase2_matrix/regime

# T2/T3 reuse for the per-regime tables
python -m experiments.summarize_results --input experiments/phase2_matrix `
  --reference rule_based --out experiments/phase2_matrix/summary.md

# T4/T5 for the real-LLM ablation
python -m experiments.ablation_analysis ablation --input experiments/phase2_llm `
  --reference multi_agent --reference-input experiments/phase2_llm `
  --out experiments/phase2_llm/ablation
python -m experiments.ablation_analysis repro --input experiments/phase2_llm `
  --out experiments/phase2_llm/repro

# Claim-vs-output checker (the one used for PR #37; commit as scripts/check_claims.py)
python scripts/check_claims.py docs/paper_results_section.md
```

`price_regime_analysis.py` and `scripts/check_claims.py` are new; both get unit
tests on synthetic run directories (the Phase 1 analysis layer's pattern).

---

## 14. Appendix — evidence commands for the findings above

```powershell
# P0-1: OPF fails, LMPs uniform
python -c "import yaml, pandapower as pp; from src.schemas.scenario import ScenarioConfig; from src.simulation.pandapower_adapter import create_grid_from_scenario; cfg=ScenarioConfig(**yaml.safe_load(open('configs/scenario_a.yaml', encoding='utf-8'))); ad=create_grid_from_scenario(cfg); ad.update_building_loads({'building_0':30,'building_1':35},{'building_0':-20}); ad.run_power_flow(); print(ad.get_lmp_prices_for_buildings(0.25)); pp.runopp(ad.net, algorithm='dc')"
# KeyError: OPF parameters are not set correctly / sgen missing min_p_mw, max_p_mw

# P0-2: model fences JSON, latency
# POST http://localhost:11434/api/generate {model: qwen2.5-coder:7b, stream:false, temperature:0}
# 639 prompt / 327 completion tokens, 8 s warm, response opens a markdown json fence

# P0-3: both arms repair
Select-String -Path src/controllers/llm_agent.py -Pattern "while repairs < REPAIR_BUDGET"

# P0-4: no P2P surface
Select-String -Path src/schemas/scenario.py -Pattern 'valid = \{'
```

*Document version: 1.1 — Research Engineer, 2026-10-30. v1.1 adds the UI and
per-step attribution dependencies (§11.1) from Backend B's dispatch-events
scoping.*
