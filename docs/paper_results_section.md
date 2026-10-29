# Results section (draft)

Draft text for the paper's results section, following
`docs/paper_results_outline.md`. **Status: v0.2 — structure, conventions and
artifact map are final; every number marked `⟨pending⟩` is filled from a fresh
paper matrix + ablation run on the metric-fixed tree.** The 125-run matrix at
`Shared/paper_artifacts/matrix/` (base `571bdfd`) and 50-run ablation (base
`bb6f24f`) are **not** usable for paper numbers: both predate three
metric-collection fixes landed on this branch (see Caveats) — EV service was
structurally 0.000 everywhere, `scenario_e` community cost was NaN, and
`gini_coefficient`/`member_cost_coverage` were schema defaults rather than
computed values. QA re-runs after this branch merges. Numbers quoted from the
first 125-run matrix are labelled *v1 diagnostic* and are not paper results.

All tables/figures in this section are generated from committed summaries plus
release artifacts:

| Element | Command / source |
|---|---|
| T2, T3 | `python -m experiments.summarize_results --input experiments/matrix_full_v2 --reference rule_based` |
| T3 (ablation reference) | same, `--reference multi_agent`, input `experiments/ablation_fallback` |
| T4 | `python -m experiments.ablation_analysis ablation --input experiments/ablation_fallback --reference multi_agent` → `ablation_kpis.md`, `ablation_agent_execution.md` |
| F1, F2, F3 | `python -m experiments.make_figures --input experiments/matrix_full_v2 --out experiments/figures` |
| F4 | reference-controller `plots/*.png` produced by `experiments/run_experiment.py` |
| F5 | `grid_diagnostics.jsonl` + failure-injector log from the `scenario_e` runs |
| F6 | `result.json` → `agent_execution` block of the ablation runs |
| T5 | per-run `manifest.json`, `failed_runs.json`, `scripts/check_artifacts.py` |
| T5 table | `python -m experiments.ablation_analysis repro --input experiments/matrix_full_v2` → `reproducibility.md` |

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
single KPI:

- `multi_agent` delivers the lowest cost and peak demand of the coordinated
  controllers, at the price of weak EV service.
  *v1 diagnostic:* −7.9 USD cost and −6.8 kW peak versus `rule_based`,
  p_Holm < 0.0001.
- `mpc`, with perfect forecasts, buys near-complete EV service for roughly
  +53 USD relative to `rule_based` (v1 diagnostic), i.e. it sits at the
  service-maximal end of the front.
- `rl` lands between them (~+93 USD, ~86% EV completion in v1), showing that a
  model-free learner recovers most of the service benefit without the LP.
- `centralized` does **not** dominate: its only v1 advantage over `rule_based`
  was a non-significant peak change (+0.22 kW, p_Holm = 0.72). Reviewers should
  read this as evidence that the coordination gain is not an artefact of
  "having an optimizer at all".

⟨pending⟩ Replace the v1 magnitudes with the metric-fixed matrix T2/T3 values;
state whether the ordering of the front is unchanged and report the paired CIs.
The EV-service arm of the front is only meaningful after the EV-definition fix
(Caveat 2), which restores real EV load (e.g. `rule_based` scenario A peak
demand rises 12.4 → 32.6 kW, `mpc` reaches 1.000 completion at avg SOC 0.88).

**F1** (per-scenario KPI bars with CI whiskers) and **F2** (per-seed strips)
carry the variance evidence; **F3** is the Pareto panel annotated with peak
demand.

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

⟨pending⟩ Report per-controller `member_cost_coverage` and
`members_interrupted_count` for Scenario E (both are columns in T2/T3 after the
paper matrix), then the cost/peak comparison restricted to runs with coverage
1.0, with the interrupted-run subset described separately. F5 shows the grid
response timeline around the injected events.

The community cost must be reported with a second coverage covariate,
`energy.cost_coverage` (valid building-steps / total building-steps in the
episode), because the injected sensor failure also blanks individual building
readings: `total_cost` is computed over valid building-steps only, and
`invalid_cost_steps` counts the blanked ones (Scenario E seed 42 on the fixed
tree: `total_cost` 104.51, `cost_coverage` 0.973, 23 invalid steps).

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

⟨pending⟩ Fill from `experiments/ablation_fallback`.

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

⟨pending⟩ Fill commit hash, run counts, failure count, median/IQR runtime.

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
   now exists (completion 0.0286 `rule_based` / 1.000 `mpc` on scenario A, and
   `rule_based` scenario A peak demand 12.4 → 32.6 kW). The matrix must be
   re-run; the pre-fix EV columns are invalid. The charging sessions are not
   compressed by the episode horizon (169 hourly steps = 7 days, with arrivals
   and departures every day), so a short horizon is not an alternative or
   contributing explanation. The market/settlement layer is also ruled out: a
   separate market-scoring trace shows it clears on building-level net demand
   and never masks charger state, so the pre-fix zeros originate at the charger.
3. **Metric-collection defects on the pre-fix base (fixed on this branch).**
   (a) `scenario_e` community `total_cost` was NaN in all 25 runs because an
   injected sensor failure returns NaN for `building_3`'s reading and the metric
   summed it; totals now skip invalid building-steps and report `cost_coverage`.
   (b) `per_member_costs` was `{}` in every run, so `gini_coefficient` 0.0 and
   `member_cost_coverage` 1.0 were `ServiceMetrics` schema defaults, not
   evidence: `FairnessAnalyzer` was never called from the run pipeline and
   CityLearn's step info carries no `cost` entry. Per-member cost is now derived
   in the pipeline from each member's net demand and tariff, and the report
   carries computed member costs, Gini, coverage and interruption. The 50-run
   ablation has the same defects (EV 0/50, `scenario_e` cost non-finite) and is
   re-run too.
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
7. **Runtime tail.** Three `multi_agent` runs in v1 hung on a killed subprocess
   and were reclaimed by the per-run timeout; runtime is reported as median/IQR
   with that footnote rather than as a mean.
