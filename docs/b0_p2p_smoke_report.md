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

## B0-re (2026-11-04): 89b36d7 OVERSHOOTS — gate FAIL, B1 still paused

Backend B's `89b36d7` (nominal_power x 1000, "CityLearn expects WATTS") is
contradicted by the pinned library's own source (`citylearn/energy_model.py`,
CityLearn 3.0.2 in `.venv`):

- `PV` docstring: "nominal_power : float ... PV array output power in [kW]"
- `PV.get_generation`: `generation = nominal_power[kW] x inverter_ac_power_per_kw[W/kW] / 1000 x dt[h]`
  — the /1000 converts the *solar series*, not nominal_power.

Measured B0-re smoke (`scenario_c_multi_agent_42`, `--regime p2p`; archived as
`experiments/b0_broken_pv_evidence/scenario_c_multi_agent_42_OVERSHOOT_B0RE`):

| Quantity | release `035a52f` | broken tree | 89b36d7 tree |
|---|---:|---:|---:|
| pv_generation (kWh/wk) | 1455.3 | 14.53 | 14,528.1 |
| capacity factor (43.5 kW installed) | 19.9% OK | 0.2% FAIL | 199% IMPOSSIBLE |
| grid_export (kWh) | 928.5 | 0.0 | 13,347.9 |
| total_cost (USD) | 52.0 | 332.8 | -565.4 (negative) |
| p2p_volume (kWh) | - | 0.0 | 990.5 |

Notes: (a) "14,528 matches 035a52f" is a misread — the release value is
1455.3 (a 10x gap, not a match); (b) the one positive result: the market
engine is verified end-to-end on real trades — `market_results.jsonl` carries
per-step `clearing_price` / `trades` / `settlements` / `total_volume_kwh`
(e.g. t=0: price 0.125, volume 3.41 kWh, 4 parties settled) — so once PV is
sane, B1 is mechanically ready.

**True root cause of the original 100x collapse**: the synthesized per-run
`building_*.csv` `solar_generation` series is ~450x too small —
`data/schemas/scenario_c/building_0.csv` has sum 270.46 / max 6.78 over 169
steps (mean ~1.6 W/kW), while the release-era series implied by the release
KPIs is SAM-style W/kW (mean ~717, max ~1000). With kW nominal_power and a
proper series, `per_kw` mode reproduces the release scale (CF ~20%).

**Required fix (Backend B):**
1. Revert the x1000 in `89b36d7` (nominal_power = `capacity_kw`).
2. Repair schema synthesis: copy the dataset's stock `solar_generation`
   W/kW series instead of the tiny synthesized values (regression window
   `035a52f..b152037`, schema-copy path).
3. Replace the absolute test expectation (14,528) with a capacity-factor
   band (CF 10-35% => scenario_c ~700-2,500 kWh/week).

**B0-re acceptance (pre-registered):** scenario_c multi_agent_42 p2p run with
pv_generation within ~+/-20% of the 1455.3 kWh release anchor AND nonzero p2p
trades AND settlement-gate pass. The 750-run queue stays paused until then.
