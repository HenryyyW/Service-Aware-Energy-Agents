# B0 pre-launch report — P2P smoke + settlement-gate validation (2026-11-03)

**Verdict: B1 P2P matrix PAUSED before launch.** The market machinery is wired
and green, but a PV-physics regression on the current tree (present since at
least `b152037`) collapses P2P volume to zero — the matrix would record
nothing to trade. Evidence below; fix belongs to Backend (regression window
identified), then B1 relaunches.

## 1. What was run (B0, per `docs/benchmark_expansion_plan.md` §5)

| Run | Wall time | Regime/basis in manifest |
|---|---:|---|
| `scenario_a_rule_based_42` (`--regime p2p`) | 26.7 s | `pricing_regime=p2p`, `cost_basis=tariff` ✓ |
| `scenario_a_multi_agent_42` (`--regime p2p`) | 18.0 s | ✓ |
| `scenario_c_multi_agent_42` (`--regime p2p`) | 18.1 s | ✓ (added: A is the no-DER baseline — zero trades there is expected; C has 12 kW PV) |

Raw runs kept under `experiments/matrix_p2p/` (gitignored) as B0 evidence.

## 2. Gate results

- **Engine invariant suite: 12/12 PASS** (`SettlementLedgerGate.run_invariant_tests()`):
  money/energy conservation, no-arbitrage, ledger conservation, no-double-settlement,
  partial fill, price-time priority, min spread, uniform price — all green.
- **Run-level acceptance fields present**: `pricing_regime`, `cost_basis`,
  `energy_sharing.*` aggregates, `per_member` settlement ledgers in `result.json` ✓.
- **FAILED IN SUBSTANCE: P2P volume = 0.0 kWh in all three runs.**
  `total_community_volume_kwh = 0`, `total_community_revenue = 0`,
  `total_savings_vs_baseline = 0`, every member's `grid_export_kwh = 0`.
  No seller → no bilateral orders → nothing for the (working) engine to clear.
  This is RQ3's pre-registered risk ("P2P volume is negligible") firing at the
  physics level, not an engine defect.

## 3. Root cause: PV generation collapsed ~100× on the current tree

Same scenario, same seed, same CityLearn/pandapower versions:

| scenario_c multi_agent_42, 7-day | `035a52f` (pool matrix release) | current main (B0 smoke) |
|---|---:|---:|
| pv_generation_kwh | **1455.3** | **14.53** (ratio 0.00999) |
| grid_export_kwh | 928.5 | 0.0 |
| grid_import_kwh | 933.3 | 2498.0 |
| total_cost USD | 52.0 | 332.8 |

- Scenario A (stock devices, no YAML PV): old 970.2 kWh vs current ~14.5 — same ~100×.
- The synthesized schema is healthy on its face: `building_0.csv` carries a
  non-trivial `solar_generation` column (169 rows, Σ 270.46, max 6.78) and the
  adapter writes `nominal_power = capacity_kw = 12.0`. The ~1/100 factor
  (kW/W-style unit slip) appears between the schema and CityLearn's PV model.
- **Present since at least `b152037`**: the M5.2 LMP matrix shows the same
  signature (scenario_c multi_agent pv 14.78 kWh, import 2492.62). Regression
  window: `035a52f..b152037`, simulation-path commits (`ffea547`, `febd607`,
  `41eb9ae` "fix coupling.py dp_config bug", `6495633`, `e257c73`, `8626b04`,
  `99acc46`). Not caused by the uncommitted working-tree changes (adapter
  untouched there; b152037 predates them).
- Environment ruled out: both manifests report `citylearn 3.0.2` /
  `pandapower 3.5.6` (only Python 3.10.9 → 3.11.17 differs).

## 4. Consequences and required actions

1. **B1 (125 p2p runs) paused** — on this tree every run records zero volume;
   RQ3 evidence would be empty. Resume after the PV regression is fixed and a
   B0-re smoke (scenario_c multi_agent: `pv_generation > ~1000 kWh/week` and
   nonzero exports/trades) passes.
2. **B2 (LMP+RL) held** — same tree; adds rows to an LMP matrix that itself
   carries the broken PV. Re-run decision after the fix.
3. **Existing b152037-based results are affected**: the M5.2 LMP benchmark
   (100 runs, paper §5.2 LMP subsection), the M2a screen's absolute KPIs
   (45 runs, §5.6–5.9; within-tree arm comparisons survive, absolute levels do
   not), and `m52_aggressive` (20 runs) all ran with PV ~1/100. After the fix,
   plan a re-run of the affected matrices (the Phase-1 pool matrix @ `035a52f`
   is clean and unaffected).
4. **Pool pairing note**: the `035a52f` pool reference is NOT same-tree with
   current main regardless (import 933 vs 2498 at identical scenario/seed), so
   even post-fix, paired p2p−pool deltas need a fresh same-commit pool_tou
   reference (+125 runs, ~45 min at measured ~20–27 s/run) — superseding the
   plan doc's "zero pool re-runs" assumption.
5. Measured B0 runtime (~18–27 s/run on today's idle machine) is ~2.5× faster
   than the 55 s history median — matrix wall-time estimates improve
   accordingly (B1 ≈ 20–25 min at `--workers 3`).

## 5. Ask

Backend/Simulation A or B: locate the ~÷100 PV scaling in the
`035a52f..b152037` simulation changes (suspect: units slip where
`solar_generation`/`nominal_power` meet CityLearn's PV model, or a
normalization added with the LMP OPF wiring), add a regression test
(scenario_c 7-day pv_generation ≥ ~1000 kWh at seed 42), and land the fix on
main. Then B0-re + B1 relaunch per §4.1.

---

## B0-re ADJUDICATION (2026-11-04, Research Engineer ruling): REJECTED as pushed

**Ruling on `fix/pv-schema-synthesis` (b7efcb9): REJECT — the described fix is
not on origin.** Verified facts:

1. The pushed branch contains ONLY the x1000 revert (+ test 4000.0 -> 4.0,
   correct) and a 49-line deletion of this evidence doc (must be restored).
   Searched ALL refs: no synthesis-fix commit exists on any remote branch.
2. **Reproducibility test**: ran scenario_c multi_agent_42 p2p on a worktree of
   the pushed branch -> **pv_gen = 14.53 kWh, export 0.0, cost 332.8 USD —
   byte-identical to the broken tree.** Backend B's claimed 1914.8 kWh is not
   reproducible from origin; the fix exists only in his local checkout.
3. **CF arithmetic correction (54.0 kW installed, 5 buildings incl. the 10.5 kW
   one my earlier table missed)**: release 1455.3 kWh = CF 16.0%; broken
   14.53 = 0.16%; 89b36d7 14,528 = 160% (still impossible); B's claimed
   1914.8 = CF 21.1% (his denominator is right; the partner's 26.2% used the
   wrong 43.5 kW).
4. **New blocking finding — no base dataset on this machine**: `data/` holds
   only synthesized schemas; `_copy_dataset_files` SILENTLY falls back to
   `_create_dummy_energy_file` (sine solar 0.45*sin + noise, uniform 1-5 kW
   random loads, fake temperatures) whenever a building CSV is missing, and
   CityLearn 3.0.2's package bundles no dataset. Every run on this machine is
   therefore on synthetic profiles. The release (035a52f, python 3.10.9,
   another machine) evidently had real dataset files — its copy path succeeded.
   A solar-only copy is insufficient: loads/demands are synthetic too.

**Required from Backend B (specific deficiencies):**
a. PUSH the actual synthesis-fix commit — it exists only locally.
b. Copy the FULL stock building CSVs (solar + loads + demands), not solar
   only, with the building-name mapping (building_0 -> Building_1 etc.) and
   episode_time_steps slicing; provision the real CityLearn 2022
   all_plus_evs dataset into the schema source_dir on THIS machine.
c. Make the `_create_dummy_energy_file` fallback a HARD FAILURE (or at minimum
   a gate-flagged, logged warning) so no benchmark run ever silently executes
   on synthetic physics.
d. Restore the deleted 49 lines of this doc.

**Acceptance unchanged:** B0-re on merged main = scenario_c multi_agent_42 p2p
with pv_generation within +/-20% of the 1455.3 kWh anchor (or, if the restored
mapping legitimately differs from the release's, verified first-principles:
expected PV from the restored series x YAML capacities within 5% of measured,
CF in 10-35% — 907 to 3,175 kWh/week at 54 kW) AND nonzero p2p trades AND
settlement-gate pass. His 1914.8 (CF 21.1%) would satisfy the band if pushed
and reproduced. The 750-run queue stays paused.
