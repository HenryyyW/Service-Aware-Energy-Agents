# B-axis re-run and paper table rebuild (2026-11-13/14, Research 2)

**Why.** The paper's B-axis KPI tables (Tables 2/3/4, figures, abstract ranges)
were recorded on 2026-11-04/11-07 builds — before the 2026-11-12 evening
economics/settlement rework and before the action-delivery repair. The
Project Partner ordered option (1): re-run everything on final code, keep no
old numbers.

**What the verification found (the inherited legs were not usable):**

* `p2p` legacy leg (250/250 on disk): manifests span three commits
  (`de08894b6` 48, `cbcc6e937` 168, `572cdbcb8` 34) with 100 cells
  `git_dirty=true`; no per-cell reproduction artifact existed on disk.
* `pool_tou` legacy leg (230/250): 20 cells failed (`scenario_e` mpc/rl crash,
  pre-fix build) and — decisive — all 230 manifests lacked `pricing_regime`,
  i.e. the runs never passed `--regime pool_tou` (base config
  `energy_sharing.enabled: false`), so the "pool TOU baseline" leg actually ran
  with sharing disabled.

**What was run.** Three fresh legs, 5 scenarios × 5 controllers × 10 seeds = 750
runs, on final code, via `scripts/run_benchmark_supervisor.py` (8 workers):

| leg | dir | regime | RL policy | manifests |
|---|---|---|---|---|
| pool TOU | `experiments/baxis_rerun_pooltou` | `pool_tou` | `scenario_<s>.json` | 250 × `9763bd7b0`, `git_dirty=false` |
| LMP | `experiments/baxis_rerun_lmp` | `lmp` | `lmp_scenario_<s>.json` | 250 × `05a925219` (docs-only delta from `9763bd7b0`; `git diff` = docs file only), `git_dirty=false` |
| P2P | `experiments/baxis_rerun_p2p` | `p2p` | `scenario_<s>.json` | 250 × `05a925219`, `git_dirty=false` |

Determinism probes (re-run one cell at HEAD, compare every numeric KPI):
`scenario_e × mpc × 42` and `scenario_a × rl × 8888` (pool TOU),
`scenario_c × mpc × 5555` (LMP), `scenario_d × multi_agent × 8888` (P2P) — all
KPI-identical. No LLM arms in this matrix (deterministic controllers only; no
DashScope key used). Committed per leg: `raw_results.json`, `status.json`,
`summary.json`, and all `manifest.json` (full run dirs are ~1.5 GB each and
stay on disk under `experiments/`).

**Rebuild.** `docs/baxis_table_rebuild.py` recomputes every paper number from
the three `raw_results.json` files into `docs/baxis_rebuild/` (deltas table,
KPI tables, LMP shift, P2P pairing + member bills, RL fallback, provenance).
Statistics protocol unchanged: paired per-seed deltas vs `rule_based`,
Student-t 95% CI half-width, Holm within scenario. Figures F1/F3 regenerated
from the new pool-TOU leg (`experiments/make_figures.py`). No number in
`arxiv_submission/arxiv_main.tex` was hand-entered.

**Findings that changed the paper's claims (all measured, n=10):**

1. **Positioning flip.** `multi_agent`'s paired cost delta vs `rule_based` is
   **positive in all five scenarios** (+49.08 … +100.01 USD, all
   p_Holm < 0.0001) — it is no longer cheapest anywhere. `centralized` is
   cost-minimal in A/C/D/E (175.83 / 159.65 / 175.83 / 175.91 USD), `mpc` in B
   (222.74 USD). Root cause: the legacy `multi_agent` rows predate the
   action-delivery fix (its actions never reached the assets).
2. **Cost basis.** The regime override enables community sharing community-wide,
   so every scenario is settlement-inclusive now; scenario D's runs are
   **bit-identical to A's at equal seed** (D's distinguishing file flag
   coincides with the regime default). The W5 PV-path repair scales recorded
   energies to the dataset's native hourly resolution (legacy PV/import were
   ~4× inflated).
3. **Service.** `multi_agent` completes 0.703/0.391/0.714 (A/B/C) of EV
   departure requirements vs `rule_based` 0.309/0.100/0.297 and `mpc`
   0.997/0.107/0.991 — the old "0.057 vs 0.154" trade-off is reversed;
   `multi_agent` is dominated on both axes.
4. **Regimes.** Dispatch is price-aware-only under LMP (10/10 identical for
   rule_based/multi_agent/centralized; 0/10 for mpc/rl) but **bills differ for
   300/300** paired price-insensitive cells across the three regimes (zero
   bit-identical) — settlement is active everywhere, so the LMP series reaches
   every bill. Under P2P dispatch is identical for all controllers (250/250),
   aggregates move in every cell, and member bills redistribute (building_2
   −2.64 ± 0.53 USD; building_1/3/4 +0.78…+1.73, p < 0.0001; n=40 per member).
5. **RL fallback.** Tabular policy out of coverage in every scenario: 2–9 of
   168 steps fall back to rule-based (1.2–5.4%), disclosed in the paper.
6. Scenario C is a net energy exporter (export 245–253 vs import 138–148 kWh)
   but **no cell has negative total cost** — the old "negative totals" flagging
   is removed.

**Provenance.** Rebuilt PDF: 21 pages. Every number traces to
`docs/baxis_rebuild/` ← `experiments/baxis_rerun_*/raw_results.json` ←
per-run `result.json` + `manifest.json`.

**Artifact provenance (repo hygiene).** The repo artifact-hygiene rule
(`scripts/check_artifacts.py`) permits only source files (`.py/.sh/.md/.yml/.toml`)
under `experiments/`; generated run directories must stay on disk or object
storage. Accordingly, the three re-run legs are **not committed** (they are in
`.gitignore`). On the experiment machine they remain at:

```
experiments/baxis_rerun_pooltou/   # 250 runs, 9763bd7b0
experiments/baxis_rerun_lmp/       # 250 runs, 05a925219
experiments/baxis_rerun_p2p/       # 250 runs, 05a925219
```

Each contains 250 per-run directories with `result.json` + `manifest.json` +
`trajectories.jsonl` + logs, plus the aggregated `raw_results.json`,
`status.json`, `summary.json`. The baseline/provenance for each leg is
recorded in `summary.json` (`git_commit`, `git_dirty=false`,
`pricing_regime` for every manifest). The rebuild script (`docs/baxis_table_rebuild.py`)
and its outputs (`docs/baxis_rebuild/summary.json`, `docs/baxis_rebuild/*.md`)
**are committed** and serve as the reproducible paper trail.