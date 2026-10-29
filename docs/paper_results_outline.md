# Paper results section: table/figure skeleton and packaging map

Maps every planned results-section element to the artifact that produces it, so
QA/DevOps knows exactly what to package from the (re-run) 125-run matrix on
`feature/scenario-aware-schemas` + the 50-run ablation (`experiments/ABLATION_DESIGN.md`).

## Tables

| # | Element | Source artifact | Producer |
|---|---|---|---|
| T1 | Scenario & controller setup (A-E device mixes, tariffs, controller list, seeds) | `configs/scenario_*.yaml`, `experiments/BENCHMARK_MATRIX.md` section 3 | hand-compiled, numbers checked against manifests |
| T2 | Main results: mean ± 95% CI per (scenario, controller) for the 5 core KPIs | `experiments/matrix_full/summary.csv`, `summary_statistics.json` | `experiments/run_benchmark.py` |
| T3 | Paired deltas vs `rule_based` with Holm-adjusted p, significance flags | `experiments/matrix_full/summary.md` (t-test table) | `experiments/summarize_results.py` |
| T4 | Ablation: `llm_agent` vs `llm_agent_verified` vs `multi_agent` — KPI deltas + agent-execution metrics (first-attempt validity, repairs, wall time, token/cost) | ablation run dirs + `ablation_kpis.md`, `ablation_agent_execution.md` | `experiments/ablation_analysis.py ablation` |
| T5 | Reproducibility/artifact table: seed-pair reproducibility check, manifest fields (config sha256, git commit, versions), run failures | `reproducibility.md`/`.json` from per-run `manifest.json`, `failed_runs.json` | `experiments/ablation_analysis.py repro` + `scripts/check_artifacts.py` |

## Figures

| # | Element | Source artifact | Producer |
|---|---|---|---|
| F1 | KPI comparison bars with CI whiskers per scenario (cost, peak, EV completion) | `summary_statistics.json` | `experiments/make_figures.py` |
| F2 | Seed-variant strips: per-seed values per (scenario, controller) | `raw_results.json` | `experiments/make_figures.py` |
| F3 | Cost vs EV-completion Pareto scatter (annotated with peak) | `raw_results.json` | `experiments/make_figures.py` |
| F4 | Weekly trajectories: community import, battery/EV SOC, price vs dispatch — one panel per scenario | run `trajectories.jsonl` + existing `plots/*.png` of the reference runs | `experiments/run_experiment.py` plots |
| F5 | Scenario E failure-injection response timeline (grid diagnostics around injected events) | run `grid_diagnostics.jsonl` + failure-injector log | failure-injection integration test outputs |
| F6 (appendix) | Verification/repair flow: first-attempt validity vs repair iterations | ablation `ablation_agent_execution.md` + per-run `manifest.json` agent block | ablation controller |

## Packaging instructions for QA

1. Raw trajectories are **not** committed: publish `experiments/matrix_full/`
   zipped via `scripts/package_results.py` (SHA256SUMS + INDEX.json) as release
   artifacts; commit only the summary CSV/JSON/MD + T5 table inputs.
2. Each release artifact must carry the manifests of its runs (config sha256 +
   git commit) so T5 can be generated mechanically.
3. Keep `failed_runs.json` in the package even when empty — reviewers ask.
4. The F4 panel uses the *reference* controller's trajectories per scenario to
   stay within reasonable artifact size; the zip still contains all runs.
5. Before packaging, re-run `python -m experiments.summarize_results --input
   experiments/matrix_full --reference rule_based` so summary.md matches the
   packaged raw_results.json exactly.
