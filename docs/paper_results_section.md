# Results section (draft)

Draft text for the paper's results section, following
`docs/paper_results_outline.md`. **Status: v1.0 — every number is filled from
the metric-fixed paper matrix and ablation.** The matrix is 125/125 runs on the
merged fix commit `035a52f` (`git_dirty: false`, `failed_runs.json = []`) and the
ablation is 50/50 runs on the same commit; both were re-run after the three
metric-collection fixes recorded in Caveats 2–3 (the earlier pre-fix matrix is
superseded and no longer cited). Generated summaries, figures and tables live in
`Shared/paper_artifacts/analysis/`.

All tables/figures in this section are generated from those artifacts:

| Element | Command / source |
|---|---|
| T2, T3 | `python -m experiments.summarize_results --input <matrix> --reference rule_based` |
| T3, T4 (reference) | `... --reference multi_agent` |
| T4 | `python -m experiments.ablation_analysis ablation --input <ablation> --reference multi_agent --reference-input <matrix>` → `ablation_kpis.md`, `ablation_agent_execution.md` |
| F1, F2, F3 | `python -m experiments.make_figures --input <matrix> --out <figures>` |
| F4 | reference-controller `plots/*.png` produced by `experiments/run_experiment.py` |
| F5 | `grid_diagnostics.jsonl` + failure-injector log from the `scenario_e` runs |
| F6 | manifest `agent` block of the ablation runs |
| T5 | per-run `manifest.json`, `failed_runs.json`, `scripts/check_artifacts.py` |
| T5 table | `python -m experiments.ablation_analysis repro --input <matrix>` → `reproducibility.md` |

`<matrix>` and `<ablation>` are the release copies
(`Shared/paper_artifacts/matrix`, `Shared/paper_artifacts/ablation`); analysis
output is collected in `Shared/paper_artifacts/analysis/`.

## 5.1 Experimental setup (T1)

Five scenarios (A–E) differ in device mix, tariff exposure and stressors:
A is the coordination baseline, B adds battery/PV assets, C adds deferrable
flexible loads, D stresses comfort bounds, E injects component failures during
the run. Every scenario is run with `rule_based`, `multi_agent`, `centralized`,
`mpc` and `rl` controllers on seeds 42, 123, 456, 789 and 999 (125 runs), plus a
50-run ablation of `llm_agent` and `llm_agent_verified` against `multi_agent` on
the same five seeds.

The controller list is the paper's comparability spine: `rule_based` is the
non-learning reference, `multi_agent` is the contribution, `centralized` is a
single-optimizer upper-bound-by-construction baseline, `mpc` is a receding-horizon
LP with perfect forecasts, and `rl` is tabular Q-learning trained per scenario
(60 episodes, seed 0; policies committed under
`experiments/reference/rl_policy/`).

## 5.2 Cost, peak and service (T2, T3)

T2 reports mean ± 95% CI (Student-t half-width) per (scenario, controller) for
the five core KPIs; T3 reports paired per-seed deltas against `rule_based` with
Holm-adjusted p-values over the family of controller comparisons.

The section's spine is the **cost-versus-service Pareto front** (F3), not a
single KPI. Paired per-seed deltas against `rule_based` (mean ± 95% CI
half-width; Holm within each scenario × metric family; `summary_vs_rule_based.md`):

| Scenario | Controller | Δ total cost (USD) | Δ peak demand (kW) | Δ EV completion | p_Holm (cost) |
|---|---|---|---|---|---|
| A | multi_agent | −17.68 ± 0.13 | −18.35 ± 0.84 | −0.11 ± 0.07 | < 0.0001 |
| B | multi_agent | −41.37 ± 3.18 | −26.77 ± 1.49 | −0.12 ± 0.06 | < 0.0001 |
| C | multi_agent | −13.42 ± 0.06 | −18.34 ± 0.81 | −0.11 ± 0.07 | < 0.0001 |
| D | multi_agent | −17.68 ± 0.13 | −18.35 ± 0.84 | −0.11 ± 0.07 | < 0.0001 |
| E | multi_agent | −17.90 ± 0.10 | −18.52 ± 0.98 | −0.11 ± 0.07 | < 0.0001 |
| A | mpc | +64.30 ± 17.49 | +29.14 ± 0.77 | +0.82 ± 0.15 | 0.0005 |
| A | rl | +86.84 ± 4.74 | +43.35 ± 4.44 | +0.49 ± 0.11 | < 0.0001 |
| A | centralized | −3.87 ± 0.35 | +1.29 ± 0.96 | +0.01 ± 0.02 | < 0.0001 |

- `multi_agent` is the cost- and peak-minimal coordinated controller in **every**
  scenario (A: −17.68 USD, −18.35 kW vs `rule_based`; B: −41.37 USD,
  −26.77 kW; E: −17.90 USD, −18.52 kW; all p_Holm < 0.0001). The price is real
  and measurable: EV completion falls to 0.07 ± 0.08 against `rule_based`
  0.18 ± 0.15 (Δ = −0.11, p_Holm = 0.023 in A, C, D, E; p_Holm = 0.0275 in B).
- `mpc`, with perfect forecasts, buys near-complete EV service — 1.00 ± 0.00 in
  A, C and E, and 0.14 ± 0.06 in B where the device mix limits sessions — for
  +19 to +69 USD and up to +29 kW peak. It is the service-maximal end of the
  front, not a cost-competitive one.
- `rl` **does not** recover the service benefit cheaply: in every scenario it has
  both higher cost and lower EV completion than `mpc` (A: +86.84 ± 4.74 USD,
  EV 0.66 ± 0.12 vs `mpc` 1.00), so the retrained model-free baseline is
  dominated by `mpc` on this front. Its peak demand is the highest of all
  controllers (A: 75.54 kW).
- `centralized` again does **not** dominate: it shaves 3–4 USD off `rule_based`
  cost, but its peak change is a small, significant *increase* in A/C/E
  (+1.2–1.3 kW, p_Holm ≈ 0.02) and a decrease only in B (−7.31 kW), while its EV
  service is statistically indistinguishable from `rule_based` (Δ = +0.01,
  p_Holm = 0.37). The coordination gain is therefore not an artefact of "having
  an optimizer at all".

Scenarios A and D are numerically identical under every controller: they share a
device mix and the synthetic traces depend only on (seed, filename), so D's
comfort stressor changes bounds but not the realised cost/peak/EV trajectory
(Caveat 4). The ordering of the front — `multi_agent` at the cost-minimal end,
`mpc` at the service-maximal end — is unchanged from the v1 diagnostic, but the
magnitudes are not, and `rl`'s position moved from "between them" to "dominated
by `mpc`" once EV service was measured correctly.

**F1** (per-scenario KPI bars with CI whiskers) and **F2** (per-seed strips)
carry the variance evidence; **F3** is the Pareto panel annotated with peak
demand. CIs are narrow because the simulator is deterministic given the seed:
5 seeds give tight intervals, so significance is read from the paired deltas
rather than from interval width (Caveat 6).

## 5.3 Scenario E: failure injection (F5)

Scenario E injects component failures mid-run. Two things must be reported
together, or the comparison is misleading:

1. **What the failure costs the economy** — community cost, peak, import.
2. **How much of the community is still measurable** — the failure can
   interrupt a member's cost accounting entirely.

**Reporting convention (fixed before the paper runs).** A member whose per-step
cost data is corrupted by an injected failure (NaN) is reported with per-member
cost `None` — *service interrupted, cost undefined*. It is never 0.0, because
zero-filling would score a failed member as free and make Scenario E look
*cheaper* after a failure. Economic aggregates (Gini, worst/best member cost)
are computed over valid members only, so a single interrupted member cannot
turn a KPI into NaN or drag fairness toward a fictitious zero. Every Scenario E
economic comparison is reported alongside two explicit covariates:

| Field | Meaning |
|---|---|
| `members_interrupted` | ids of members whose cost accounting was interrupted |
| `member_cost_coverage` | valid members / total members (1.0 = none interrupted) |
| `members_interrupted_count` | per-run count, aggregated into T2/T3 like any KPI |

Savings versus baseline are `None` for interrupted members, for the same reason.
The convention is implemented in `src/evaluation/fairness.py`, typed in
`src/schemas/report.py`, documented in `experiments/BENCHMARK_MATRIX.md` §4 and
covered by `tests/test_member_cost_convention.py` (including strict-JSON
serialisation, `allow_nan=False`).

**Result.** The interruption is a property of the scenario, not of the strategy:
in **all 25** Scenario E runs, for **every** controller,
`members_interrupted = ["building_3"]` → `members_interrupted_count = 1.00 ± 0.00`
and `member_cost_coverage = 0.80 ± 0.00`. The injected sensor failure on
`building_3_net_electricity_consumption` (steps 96–119) is the only cost-blanking
event, and no controller avoids or triggers it. Consequently there is **no**
Scenario E subset with coverage 1.0 to compare against; the E deltas in §5.2 are
already computed over valid members only, with `building_3` excluded from the
Gini, worst/best-member and savings aggregates. Gini over the four valid members
ranges 0.293–0.650 (median 0.523) across the 25 E runs.

Scenario E community cost and peak, mean ± 95% CI (all 25 runs finite):

| Controller | total cost (USD) | peak demand (kW) |
|---|---|---|
| rule_based | 104.22 ± 2.88 | 32.19 ± 0.84 |
| multi_agent | 86.31 ± 2.90 | 13.66 ± 0.67 |
| centralized | 100.00 ± 2.74 | 33.48 ± 0.72 |
| mpc | 166.77 ± 18.78 | 61.33 ± 0.96 |
| rl | 189.14 ± 5.50 | 75.54 ± 4.61 |

The community cost is reported with a second coverage covariate,
`energy.cost_coverage` (valid building-steps / total building-steps in the
episode), because the injected sensor failure also blanks individual building
readings: `total_cost` is computed over valid building-steps only, and
`invalid_cost_steps` counts the blanked ones. `cost_coverage = 0.9726`
(23 of 840 building-steps blanked) in **every** E run — identical across
controllers, so it does not confound the E comparison. F5 shows the grid
response timeline around the injected events.

## 5.4 Ablation: verified versus unverified agents (T4, F6)

T4 compares `llm_agent` (single-pass proposal, executed as proposed),
`llm_agent_verified` (per-step verification with a two-repair budget, then
deterministic fallback) and `multi_agent` on the same 5 × 5 grid.

All ablation runs in this paper were produced **without an LLM backend** and are
therefore labelled `agent_backend: "fallback"` in every manifest. In fallback
mode the controller follows its deterministic proposal path: `sampling_seed`
equals the run's scenario seed, and the fallback path consumes no sampling
randomness. These runs measure the *verification machinery* (proposal →
verify → repair → execute) under a deterministic proposer; they are **not**
evidence about LLM proposal quality, and every claim and table caption must say
so. A backend-enabled rerun is the follow-up experiment.

T4 columns: KPI deltas vs `multi_agent`, first-attempt validity rate, mean
repairs per step, fallback rate, and wall time per run. F6 plots first-attempt
validity against repair iterations.

**Result (fallback mode).** In fallback the two LLM controllers are
*KPI-identical to each other and to `rule_based`* — the deterministic proposer is
the rule-based policy. Scenario A, `llm_agent` = `llm_agent_verified` =
106.44 ± 2.88 USD, peak 32.19 ± 0.84 kW, EV 0.18 ± 0.15, i.e. exactly the
`rule_based` row. Against `multi_agent` both are therefore more expensive and
higher-peaking on every scenario, and better on EV service:

| Scenario | Controller | Δ cost (USD) | Δ peak (kW) | Δ EV completion | p_Holm (cost) |
|---|---|---|---|---|---|
| A | llm_agent / llm_agent_verified | +17.68 ± 0.13 | +18.35 ± 0.84 | +0.11 ± 0.07 | < 0.0001 |
| B | llm_agent / llm_agent_verified | +41.37 ± 3.18 | +26.77 ± 1.49 | +0.12 ± 0.06 | < 0.0001 |
| C | llm_agent / llm_agent_verified | +13.42 ± 0.06 | +18.34 ± 0.81 | +0.11 ± 0.07 | < 0.0001 |
| E | llm_agent / llm_agent_verified | +17.90 ± 0.10 | +18.52 ± 0.98 | +0.11 ± 0.07 | < 0.0001 |

The agent-execution evidence shows why the two arms coincide: under the
deterministic proposer every proposal is valid on the first attempt
(`first_attempt_validity = 1.000`), so the verification loop never fires —
`repairs/run = 0.00`, `repairs/step = 0.0000`, `verification_failures = 0.00`,
`unparseable_outputs = 0.00`, and `agent_backend = "fallback"` in all 50
manifests. **The fallback ablation measures the verification machinery, and under
a perfect proposer that machinery is a no-op**; it cannot discriminate
`llm_agent` from `llm_agent_verified`. Wall time is 16–33 s per run (median
20.8 s) and does not separate the arms. The real test — a backend that occasionally emits invalid or
unparseable proposals — is the Phase 2 real-LLM rerun
(`docs/phase2_experiment_plan.md`), contingent on the API-key decision.

## 5.5 Reproducibility (T5)

Each run writes a `manifest.json` with the scenario config SHA-256, the git
commit of the executing tree, `git_dirty`, package versions, controller name,
`agent_backend`, `prompt_version`/`prompt_hash` (ablation only), sampling
temperature/seed and the random seed. `failed_runs.json` is written even when
empty. The paper matrix is produced on the merged fix commit with
`git_dirty: false`; T5 reports the commit, the seed-pair reproducibility check
from `scripts/check_reproducibility.py`, and the failure count.

Runtime is reported as the **median** per controller with the interquartile
range; a footnote records any run that had to be killed by the per-run timeout
and why.

**Result.** Both the matrix and the ablation ran on the merged fix commit
`035a52f30776caa2d02ce7f3e9133a9f477764af` with `git_dirty: false` in all 175
manifests (125 matrix + 50 ablation), Python 3.10.9; `failed_runs.json = []`
(0 failed). Each scenario shows 5 distinct `scenario_config_sha256` values, one
per seed, because the seed is part of the hashed config — the pairing key for T3
is `(scenario, seed)`.

Median per-run runtime and interquartile range (matrix):

| Controller | median (s) | IQR (s) |
|---|---|---|
| rule_based | 56.6 | 53.8–72.1 |
| multi_agent | 53.4 | 50.8–54.9 |
| centralized | 58.6 | 53.8–83.4 |
| mpc | 61.8 | 55.5–69.2 |
| rl | 54.1 | 52.0–60.5 |

Overall median 55.5 s, maximum 138.7 s. **No run was killed by the per-run
timeout** in the fixed matrix (contrast the v1 diagnostic, where three
`multi_agent` runs hung), so the runtime tail caveat is retired. The ablation
runs are the same order (16–33 s per run, median 20.8 s, §5.4). Wall-clock time
on this shared machine is load-sensitive (the 138.7 s outlier ran while other
jobs were active), which is why the table reports median/IQR rather than the
mean.

## Caveats (must appear in the paper, in this order)

1. **Resolved before the paper matrix.** On the pre-fix base every controller
   action was silently dropped, which made all controllers behave like
   `rule_based`; the scenario YAML device parameters also did not reach
   CityLearn, so scenarios B/C/E collapsed onto A. Both defects are fixed on
   the paper tree (`scenario-aware schemas`, per-device action dimensions,
   coordination clock). The v1 125-run matrix is retained only as a
   controller-distinctness diagnostic and must not be cited as a result.
2. **The EV-completion artifact (root cause found; fixed on this branch).** The
   0.000 EV completion in every one of the 125 runs was not a strategy outcome
   and not the clock: the synthesized charger schedules named a fixed
   `Electric_Vehicle_scenario`, which had no entry in the schema's
   `electric_vehicles_def`, so CityLearn resolved no vehicle and never plugged
   one (`connected` stayed 0 for all 168 steps). Fixed by registering one
   `Electric_Vehicle_{building}_{index}` definition per charger; verified EV load
   now exists (`rule_based` scenario A peak demand 12.39 kW pre-fix → 32.19 ± 0.84
   kW in the fixed matrix, 32.6 kW on the seed-42 smoke run; `mpc` EV completion
   1.000 at avg SOC 0.88). The matrix and ablation
   were re-run on the fixed tree, where EV completion is non-zero in 116/125 and
   50/50 runs and separates the controllers (mpc 0.83, rl 0.54, centralized
   0.18, rule_based 0.17, multi_agent 0.06 mean). Charging sessions are not
   compressed by the episode horizon (169 hourly steps = 7 days, with arrivals
   and departures every day), so a short horizon is not an alternative or
   contributing explanation. The market/settlement layer is also ruled out: a
   separate market-scoring trace shows it clears on building-level net demand
   and never masks charger state, so the pre-fix zeros originated at the charger.
3. **Metric-collection defects on the pre-fix base (fixed on this branch).**
   (a) `scenario_e` community `total_cost` was NaN in all 25 runs because an
   injected sensor failure returns NaN for `building_3`'s reading and the metric
   summed it; totals now skip invalid building-steps and report `cost_coverage`.
   (b) `per_member_costs` was `{}` in every run, so `gini_coefficient` 0.0 and
   `member_cost_coverage` 1.0 were `ServiceMetrics` schema defaults, not
   evidence: `FairnessAnalyzer` was never called from the run pipeline and
   CityLearn's step info carries no `cost` entry. Per-member cost is now derived
   in the pipeline from each member's net demand and tariff, and the report
   carries computed member costs, Gini, coverage and interruption. The re-run
   artifacts confirm finite cost in 175/175 runs, `member_cost_coverage` 0.80 in
   every Scenario E run and a real per-member cost vector, e.g.
   `{building_0 66.71, building_1 13.28, building_2 0.67, building_3 null,
   building_4 11.39}` with Gini 0.543 for `scenario_e_centralized_123`.
4. **Scenario fidelity.** Synthetic load traces depend only on (seed, filename),
   so cross-scenario load-profile differentiation remains limited even though
   device mixes now differ. Reported scenario effects are device-mix effects.
   With the EV fix in place, retrained Q-learning policies for A, D and E share
   the same 126-state table (same device mix); only B and C differ.
5. **Fallback-mode ablation.** See §5.4 — labelled in every table; no claims
   about LLM proposal quality.
6. **Seed count.** Five seeds give narrow CIs; significance is assessed on
   paired per-seed deltas with Holm correction, and effect sizes are reported
   next to p-values.
7. **Runtime tail (retired for the fixed matrix).** Three `multi_agent` runs in
   the v1 diagnostic hung on a killed subprocess; in the fixed matrix no run hit
   the per-run timeout (max 56.5 s), so runtime is reported as median/IQR on a
   complete 125-run set.
