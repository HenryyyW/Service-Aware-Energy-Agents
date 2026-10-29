# Benchmark matrix and statistical protocol (Phase 1)

Scope: Phase 1 only. This file defines the reproducible benchmark matrix for the
paper, the seed/statistics protocol, the measured runtime budget, and the
measurement caveats that must be resolved before any result is used as a paper
claim. The controls themselves are implemented in `src/controllers/`.

## 1. Controllers under test

| Label | Implementation | Control interface | Notes |
|---|---|---|---|
| `rule_based` | `src/controllers/__init__.py::RuleBasedController` | requested kW per asset | Thresholds on excess PV, deficit, EV SOC and time of day |
| `centralized` | `src/controllers/centralized.py` | requested kW per asset | Heuristic joint dispatch; **not** an optimizer |
| `multi_agent` | `src/controllers/multi_agent.py` + `src/coordination/` | requested kW per asset | Planner/coder/executor/verifier/reporter scaffold with deterministic fallbacks |
| `mpc` | `src/controllers/mpc.py` | requested kW per asset | Deterministic receding-horizon LP (SciPy/HiGHS), 24 h horizon, causal diurnal forecasts |
| `rl` | `src/controllers/rl.py` + `experiments/train_rl.py` | requested kW per asset | Single centralized tabular Q-learning agent, 15 joint battery/EV levels (5 x 3), greedy evaluation from a saved policy (153 states visited in the scenario-A run) |

The brief's verified-vs-unverified agent baselines (`llm_agent`,
`llm_agent_verified`) are declared in `src/schemas/report.py` but are not
implemented yet; they are Phase 2 work and are excluded from this matrix.

## 2. Action interface contract

Controllers emit `Action(value_kw=<power in kW>, asset_id=<configured asset>)`
with ids `{building}_battery`, `{building}_ev_{i}`, `{building}_flex_{i}` (and
`{building}_electrical_storage` / `_electric_vehicle_storage` /
`_deferrable_appliance` for simulator-shaped ids). The CityLearn adapter owns
the translation to CityLearn's normalized device actions:

- battery: `value_kw / battery.nominal_power`
- EV charger: `value_kw / max_charging_power` (or `max_discharging_power` when negative)
- deferrable appliance: fraction of cycle energy, so any positive kW clamps to `1.0`

All values are clamped to `[-1, 1]` (deferrable to `[0, 1]`). Device ratings come
from the live simulator (`CityLearnAdapter.get_device_metadata()`), not the
scenario YAML.

Price observations are also aligned with the scenario tariff: the adapter
overrides `{building}_electricity_pricing` from the YAML time-of-use schedule
(the schedule the cost metrics bill) instead of leaving the CityLearn dataset's
own `pricing.csv` value in place. Before this override the two differed by about
2x on scenario A, so any price-aware controller optimised the wrong objective.

**Why this matters for the matrix:** before this change, the adapter looked up
actions by `asset_id` *and* `action_type` with `action_type=None`, so every
controller action was silently dropped, and the configured-asset ids
(`*_battery`, `*_ev_i`) never matched the simulator-shaped ids. Every archived
result produced before this fix is therefore a no-control simulation and is not
comparable with new results. The adapter now has regression tests for the
id/unit translation (`tests/test_baseline_controllers.py`).

## 3. Matrix

| Dimension | Values | Count |
|---|---|---|
| Scenarios | A baseline, B high EV penetration, C high PV + export cap, D energy sharing, E failures | 5 |
| Controllers | `rule_based`, `multi_agent`, `centralized`, `mpc`, `rl` | 5 |
| Seeds | 42, 123, 456, 789, 999 | 5 |
| **Total runs** | | **125** |

Seeds are shared across controllers within a scenario, so comparisons are
paired by seed. The pilot uses three seeds (42, 123, 456) for scenario A; the
brief's minimum is 3 runs per configuration and the full matrix uses 5.

### Runtime budget

Measured on the development machine (Python 3.10, CityLearn 3.0.2, no GPU):
**~110 s per full one-week run** (~49 s CityLearn simulation plus pandapower
power flow and metric/plot generation). Plot generation and result I/O are a
material share of that, so a run is not dominated by the optimizers.

| Setup | Measured | Projection |
|---|---|---|
| Cold single run (first run, dataset bootstrap) | 109 s | — |
| Pilot: 1 scenario x 4 controllers x 3 seeds = 12 runs | **172 s wall clock at `--workers 3`**; per-run 32.7-50.1 s, mean 42.4 s | — |
| Full matrix: 125 runs | — | ~30 min at `--workers 3` (~2 h serial) |

MPC adds one small LP per step (169 steps, 24-step horizon, ~50 variables per
building); it did not materially change the measured per-run time. A 60-episode
RL training pass takes ~10 min and is a one-off per scenario, not part of the
matrix runtime.

Long-run orchestration (full matrix, retries, artifact collection) is handed to
QA/DevOps. The benchmark runner is resumable in the practical sense that run ids
are deterministic (`{scenario}_{controller}_{seed}`), so re-running only
attempts runs whose `result.json` is missing; failed runs are listed in
`failed_runs.json`.

## 4. Statistical protocol

- Per configuration: mean, sample standard deviation, min, max, n.
- 95% CI: Student-t half-width `t(0.975, n-1) * s / sqrt(n)`, not the 1.96
  normal approximation (the old harness used 1.96, which understates intervals
  at n = 3-5).
- Paired comparisons: `experiments/summarize_results.py` reports per-seed deltas
  against `rule_based` with the same t intervals. With 4 comparisons per
  scenario, apply Holm correction (or report the intervals as exploratory) before
  claiming significance.
- With n = 5, a paired difference is only distinguishable from zero if it is
  large relative to between-seed variation; the paper must report interval width,
  not only point estimates.
- Seeds change CityLearn's generated fallback data and therefore the simulated
  load/PV traces. They are not merely process-level randomness: repeated runs
  with different seeds produced different costs on scenario A (e.g. rule-based
  total cost 96.28 vs 100.37 USD for seeds 42 and 123 before the interface fix).
  Variance is small relative to controller effects, which makes 3-5 seeds workable
  but means CIs will be narrow and should not be over-interpreted.

## 5. Pilot: scenario A head-to-head

Pilot command: scenario A, controllers `rule_based`, `multi_agent`, `mpc`, `rl`, seeds 42/123/456, output `experiments/phase1_pilot`. 12/12 runs succeeded in 219.5 s at `--workers 3` (re-run after the determinism fixes; numbers below supersede any earlier pilot).

| Controller | Cost USD | Grid import kWh | Peak kW | PV self-consumption kWh | EV completion |
|---|---|---|---|---|---|
| `rule_based` | 104.29 +/- 1.90 | 1056.23 +/- 18.75 | 20.82 +/- 2.03 | 512.65 +/- 2.98 | 0.05 +/- 0.00 |
| `multi_agent` | 96.42 +/- 2.01 | 987.51 +/- 19.01 | 13.77 +/- 0.90 | 466.31 +/- 0.06 | 0.00 +/- 0.00 |
| `mpc` | 157.64 +/- 3.13 | 1609.70 +/- 26.26 | 50.82 +/- 2.60 | 507.05 +/- 7.43 | 1.00 +/- 0.00 |
| `rl` | 196.98 +/- 10.32 | 1879.22 +/- 69.51 | 52.93 +/- 15.44 | 315.93 +/- 28.32 | 0.86 +/- 0.00 |

Cells are mean +/- Student-t 95% confidence half-width over three seeds. Paired per-seed deltas are in `experiments/phase1_pilot/summary.md`.

### What the pilot shows

1. **Cost alone ranks the controllers backwards.** The two cheapest controllers
   (`multi_agent` 96 USD, `rule_based` 104 USD) meet 0% and 5% of EV departure
   requirements, while `mpc` meets 100% at 158 USD and `rl` meets 86% at 197 USD.
   The ~53 USD MPC premium buys the EV service level; any cost comparison that
   does not condition on the service constraint is not a valid controller
   comparison.
2. **The legacy controllers under-charge EVs because their bookkeeping uses the
    YAML EV parameters** (e.g. target SOC/capacity), while the simulator runs the
   dataset EV (60 kWh, required SOC 0.87). They therefore stop charging early and
   report low SOC at departure. This is a scenario-fidelity issue, not an EV
   charging strategy result.
3. **Peak demand needs reconciliation before publication.** `mpc` and `rl` charge
   EVs at charger maximum when they start, producing 51-53 kW community peaks;
   the heuristics spread charging over the day (14-21 kW). Scenario tariffs carry
   a 5 USD/kW demand charge, but the energy metrics do not bill it, so peak and
   cost currently measure different objectives. The MPC includes only a small
   0.1 USD/kW peak proxy.
4. **Seed variance is small relative to controller gaps** (most CIs are under 3%
   of the mean), so 3 seeds already separate these controllers. The paper still
   needs the full 5-seed matrix, and the scenario-fidelity fixes, before these
   numbers are claims.
5. **The EV metric itself was wrong and is now fixed for departure SOC.** Before
   this work every controller scored exactly 0.60 completion because the metric
   compared the (mis-sourced) `*_at_charger_soc` column against a fractional
   target. `compute_service_metrics` now prefers the adapter's explicit
   `{building}_ev_{i}_{soc,required_soc,connected}` keys and scores each observed
   connection-to-disconnection event against the simulator's required SOC.
   Departure SOC, worst departure SOC and completion therefore differ across
   controllers for the first time. Departed SOC is still only defined for
   observed departures (21 per week); configured-vs-simulated EV mismatches remain
   (see caveats).
6. **Distinctness checks (run by QA/DevOps):** on `main` (before the adapter
   action-translation fix landed) a 12-run matrix produced byte-identical
   `rule_based` and `multi_agent` metrics per seed, because every controller
   action was silently dropped there. On this branch the four pilot controllers
   produce distinct physics per seed (table above). Separately, scenario B's
   energy totals equal scenario A's at the same seed even on this branch: the
   synthetic building traces depend only on (seed, filename), and scenario YAML
   differences currently reach the simulation only as community limits and
   sharing flags (caveats 1 and 4). Scenario B/C/E rows in the full matrix
   therefore measure the same physics as A with different community limits until
   caveat 1 is resolved. **Update: caveat 1 is now fixed on
   `feature/scenario-aware-schemas`** — device mixes reach the simulation, and
   A vs B diverge at equal seed; the synthetic building *load* traces still
   depend only on (seed, filename) by design, so cross-scenario load-profile
   differences remain future work.


## 6. Caveats that block paper-level claims

1. **Scenario YAML device parameters are ignored.** The adapter builds the
   CityLearn schema from `citylearn_challenge_2022_phase_all_plus_evs`, so
   configured battery capacities, PV sizes and charger counts generally do not
   match the simulation (e.g. scenario A configures 13.5 kWh / 5 kW batteries,
   the dataset provides 6.4 kWh / 5 kW; some buildings have no EV or deferrable
   appliance in the dataset despite a configured one). Scenario B, C and E
   differences are therefore mostly community limits and sharing flags, not the
   device mixes their YAML describes.
   **Fixed on `feature/scenario-aware-schemas`:** the adapter now applies the
   scenario YAML's device parameters (battery capacity/power/efficiency, PV
   size or removal at zero capacity, one charger + synthesized connection
   schedule per EV, one deferrable appliance + synthesized cycle/flexibility
   CSVs per flexible load), with unconfigured devices keeping stock dataset
   defaults and explicit `[]`/zero-capacity removing them. Action vectors are
   per-device (one dimension per charger/appliance). Scenario A and B now
   produce different physics at the same seed. This changes simulation physics
   for every scenario, so matrix results produced on
   `feature/baselines-mpc-rl` must be re-run after this branch merges, and the
   RL policies must be retrained (they encode the old device ratings).
2. **EV service metrics are partially repaired.** The dataset observation
   columns are mismatched (`*_at_charger_soc` carries battery capacity in some
   rows, `*_battery_capacity` carries hours-to-departure). The adapter now emits
   unambiguous `{building}_ev_{i}_*` keys and `compute_service_metrics` scores
   observed connection-to-disconnection events against the simulator's required
   SOC. That removes the old constant 0.60 artifact. Residual limits: only 21
   observed departures per week, departure SOC is the last connected-step value,
   and configured-vs-simulated EV parameters still differ (caveat 1).
3. **Timestep mismatch.** Scenarios declare 15-minute steps; the dataset is
   hourly and the adapter overrides the scenario timestep to 60 minutes (169
   steps/week). Metric code that assumes 15-minute steps mis-scales duration-based
   KPIs (comfort degree-hours, delays).
4. **Scenario D (sharing) and E (failures) are configuration-only.** Market
   clearing/settlement placeholders and failure injection are not implemented,
   so their rows in the matrix measure the same physics as A with different
   community limits.
5. **MPC is myopic at the horizon end.** It has no terminal battery value and a
   soft EV shortfall penalty, so it can end a horizon with an empty battery and
   it does not plan beyond 24 h.
6. **RL is deliberately small.** One tabular agent over a coarse SOC/price/time discretization
   trained on one scenario; it cannot generalize across scenarios, and `rl` policy
   files must be trained per scenario (`experiments/rl_policy/<scenario>.json`).
7. **`multi_agent` is not an LLM run.** The controller uses the coordination
   scaffold with deterministic fallbacks; no token consumption or agent repair is
   exercised, so it does not test the paper's agent claim.

## 7. Reproduce

```powershell
# One run (smoke)
python -m experiments.run_experiment --config configs/scenario_a.yaml `
  --controller mpc --seed 42 --max-steps 24 --output-dir experiments/_smoke

# Train the RL baseline for a scenario
python -m experiments.train_rl --config configs/scenario_a.yaml `
  --out experiments/rl_policy/scenario_a.json --episodes 60

# Pilot (scenario A, 4 controllers, 3 seeds)
python -m experiments.run_benchmark --scenarios configs/scenario_a.yaml `
  --controllers rule_based multi_agent mpc rl `
  --seeds 42 123 456 --workers 3 `
  --output experiments/phase1_pilot --rl-policy-dir experiments/rl_policy

# Full matrix (hand to QA/DevOps)
python -m experiments.run_benchmark --scenarios configs/scenario_a.yaml `
  configs/scenario_b.yaml configs/scenario_c.yaml configs/scenario_d.yaml `
  configs/scenario_e.yaml `
  --controllers rule_based multi_agent centralized mpc rl `
  --seeds 42 123 456 789 999 --workers 3 `
  --output experiments/matrix_full --rl-policy-dir experiments/rl_policy

# Summary table
python -m experiments.summarize_results --input experiments/phase1_pilot `
  --reference rule_based --out experiments/phase1_pilot/summary.md
```

The RL policies for all five scenarios are checked in as curated fixtures under
`experiments/reference/rl_policy/<scenario>.json` (trained with `--seed 0`, 60
episodes, on this branch's adapter; `experiments/rl_policy/` itself stays
untracked — the artifact-hygiene gate forbids generated output under
`experiments/`, so regenerated or newly trained policies are published as
release artifacts, or copied into `experiments/reference/rl_policy/` only after
a deliberate review). Point the runner at them with
`--rl-policy-dir experiments/reference/rl_policy`. If a policy file is missing,
the runner skips `rl` runs for that scenario and lists them in
`failed_runs.json` rather than substituting a different controller.
