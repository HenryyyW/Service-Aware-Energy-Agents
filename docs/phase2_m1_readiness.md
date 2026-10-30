# M1 pricing-matrix readiness (prep only — no runs executed)

Status: configs drafted + supervisor argument surface dry-run on 2026-10-31.
**No benchmark or local-model runs were executed** (user order: all Ollama /
local-model experiments paused; `multi_agent` runs through the supervisor use
the deterministic fallback backend only).

## 1. Regime config sets (`configs/m1/`)

Three sets, per docs/phase2_experiment_plan.md §4.1 and the PM tasking
(2026-10-31). Each file is a **regime overlay only** on the untouched
`configs/scenario_{a..e}.yaml` (buildings, pandapower, tariffs unchanged) and
validates against `src.schemas.scenario.ScenarioConfig`.

| Set | `energy_sharing` | Files | State |
|---|---|---|---|
| `pool_tou` | `enabled: true`, `market_type: uniform_price` | `configs/m1/pool_tou/scenario_{a..e}.yaml` | ready (baseline arm) |
| `lmp` | `enabled: true`, `market_type: lmp` + `dynamic_pricing: {enabled: true, pricing_type: lmp, congestion_cost_method: dc_approx, price_cap_per_kwh: 1.0, fallback_to_tariff: true}` | `configs/m1/lmp/scenario_{a..e}.yaml` | ready (pricing-effect arm) |
| `p2p` | `enabled: true`, `market_type: p2p` | `configs/m1/p2p/scenario_{a..e}.yaml` | **SCHEDULE-LATER** (PM order): `P2PClearing` exists (#46) but T6 metric wiring and paired-baseline validation are unverified. Dry-runnable only — do not schedule without PM confirmation. |

Notes:
- Scenario C LMP cap sensitivity ({0.35, 0.50} USD/kWh, plan §4.2) is **not**
  in the base `lmp` set (`price_cap_per_kwh: 1.0`); those are separate config
  variants to draft with the sensitivity arms (55 extra runs total with the
  MPC perfect-foresight arm).
- The plan's `tou_solo` regime (§4.1) was not part of this tasking; the
  sharing effect (`pool_tou − tou_solo`) still needs it. Existing scenario
  configs with `energy_sharing.enabled: false` already approximate it (A/B/C/E
  are exactly that; D would need a sharing-off variant).

## 2. Naming and layout

Supervisor run id is `{scenario_id}_{controller}_{seed}` (verified in the
dry-run, e.g. `scenario_e_mpc_456`) — regime identity is carried by the
**config path + one `--output-dir` per regime**, so `scenario_id` stays clean
for paired analysis on `(scenario, controller, seed)` (plan §4.2):

```
python scripts/run_benchmark_supervisor.py \
    --scenarios configs/m1/pool_tou/scenario_{a,b,c,d,e}.yaml \
    --controllers rule_based multi_agent centralized mpc \
    --seeds 42 123 456 789 999 \
    --output-dir experiments/m1/pool_tou
```

Final 4-part identity = `{regime}/{scenario_id}/{run_id}` in the output tree,
equivalent to §4.2's `{scenario}_{regime}_{controller}_{seed}` without a code
change.

## 3. Dry-run result (per regime, plan only)

100 planned runs per regime = 5 scenarios × 4 controllers × 5 seeds. The full
M1 core is 125 per regime; the missing 25 are the `rl` arm — see gap G1.

## 4. Gaps before the matrix starts

- **G1 (fixed here):** supervisor `--controllers` rejected `mpc`/`rl`;
  `mpc` is now admitted (pure pass-through). `rl` is still **not** admittable:
  the supervisor has no RL-policy resolution, and `run_experiment.py --controller rl`
  without `--rl-policy` dies in `QLearningController` setup. Fix: mirror
  `run_benchmark.py::rl_policy_path` (per-scenario JSON from `--rl-policy-dir`,
  skip-with-message when missing; Phase-1 fixtures at
  `experiments/reference/rl_policy/scenario_{a..e}.json`, LMP arms will need
  `lmp_<scenario>.json` policies per §4.3).
- **G2:** plan §4.2 wants `pricing_regime` and `cost_basis` in
  `result.json`/`manifest.json` and a `--regime` flag in `run_benchmark.py`;
  none exist on main (`run_experiment.py` emits neither field). Interim: regime
  is only implied by the output dir. Needed before paired T7 analysis.
- **G3:** `p2p` regime = SCHEDULE-LATER (above). `p2p` is schema-valid
  (`EnergySharingConfig.market_type` accepts it since #46) and `P2PClearing`
  clears, but T6 metrics (`market_volume_kwh`, spread) and settlement wiring
  through `P2PMatchingEngine` are unverified end-to-end.
- **G4:** sensitivity arms (C cap {0.35, 0.50}, MPC perfect-foresight LMP)
  have no configs yet — draft with the arm itself.
