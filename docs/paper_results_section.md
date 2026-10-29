# Results section (draft)

Draft text for the paper's results section, following
`docs/paper_results_outline.md`. **Status: v0.1 — structure, conventions and
artifact map are final; every number marked `⟨pending⟩` is filled from the
paper matrix (`experiments/matrix_full_v2`) and the ablation
(`experiments/ablation_fallback`) once QA's runs land.** Numbers quoted from the
first 125-run matrix are labelled *v1 diagnostic* and are not paper results:
that matrix predates the controller-action fix and the scenario-aware schemas,
so several scenarios collapse onto each other and `multi_agent` reports a
spurious 0.000 EV completion (see Caveats).

All tables/figures in this section are generated from committed summaries plus
release artifacts:

| Element | Command / source |
|---|---|
| T2, T3 | `python -m experiments.summarize_results --input experiments/matrix_full_v2 --reference rule_based` |
| T3 (ablation reference) | same, `--reference multi_agent`, input `experiments/ablation_fallback` |
| F1, F2, F3 | `python -m experiments.make_figures --input experiments/matrix_full_v2 --out experiments/figures` |
| F4 | reference-controller `plots/*.png` produced by `experiments/run_experiment.py` |
| F5 | `grid_diagnostics.jsonl` + failure-injector log from the `scenario_e` runs |
| F6 | `result.json` → `agent_execution` block of the ablation runs |
| T5 | per-run `manifest.json`, `failed_runs.json`, `scripts/check_artifacts.py` |

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

⟨pending⟩ Replace the v1 magnitudes with matrix_full_v2 T2/T3 values; state
whether the ordering of the front is unchanged and report the paired CIs.

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
2. **The multi_agent EV-completion artifact.** The published v1 matrix reports
   `multi_agent` EV completion 0.000. This is a clock bug (agents scheduled on a
   15-minute grid while the scenario steps hourly) plus a YAML-versus-dataset EV
   mismatch, not a strategy outcome. The paper matrix re-runs on the fixed clock;
   if completion is still 0.000 the fix was insufficient and the number must be
   investigated before publication.
3. **Scenario fidelity.** Synthetic load traces depend only on (seed, filename),
   so cross-scenario load-profile differentiation remains limited even though
   device mixes now differ. Reported scenario effects are device-mix effects.
4. **Fallback-mode ablation.** See §5.4 — labelled in every table; no claims
   about LLM proposal quality.
5. **Seed count.** Five seeds give narrow CIs; significance is assessed on
   paired per-seed deltas with Holm correction, and effect sizes are reported
   next to p-values.
6. **Runtime tail.** Three `multi_agent` runs in v1 hung on a killed subprocess
   and were reclaimed by the per-run timeout; runtime is reported as median/IQR
   with that footnote rather than as a mean.
