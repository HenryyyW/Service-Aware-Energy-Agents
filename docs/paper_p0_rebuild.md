# Paper P0 Rebuild Specification (B-axis Data)

This document specifies the updates to `arxiv_submission/arxiv_main.tex` based on the 750-run "B-axis" benchmark matrix (10 seeds, fixed physics). The user is requested to apply these changes manually.

## 1. Abstract
**Replace existing abstract with:**
"We present a service-aware multi-agent framework for renewable energy community optimization that integrates pricing regime selection, component failure injection, and a verified LLM-based code-agent repair loop, coupled to CityLearn building-level simulation with pandapower grid validation. We evaluate five controllers (rule-based, multi-agent, centralized, MPC, RL) across three pricing regimes --- pool TOU, LMP, and bilateral P2P --- at 10 seeds each (750 runs), plus a 50-run fallback-mode ablation, a 45-run real-LLM screen, and a 20-run aggressive failure-injection stress test (815 runs total, every manifest recorded with `git_dirty: false`). The multi-agent controller is cost- and peak-minimal in every scenario (paired cost delta vs. rule-based $-11.95$ to $-43.03$ USD across scenarios, $p_{\mathrm{Holm}} < 0.0001$, $n{=}10$) with an explicit EV-completion trade-off (0.057 vs. MPC's 1.000) that we report rather than resolve. Only price-aware controllers (MPC, RL) respond to the LMP regime; price-insensitive heuristics dispatch identically under TOU and LMP. Under aggressive failure injection, all controllers show a zero resolution rate on structural voltage violations --- a detection result, which we do not claim as recovery. The verified-vs.-unverified LLM comparison is a null result on the safety gate (0 unrepaired violations, 0 repair iterations in both arms under the screened proposer), with a secondary observation that the unverified arm incurs significantly larger cost and peak regressions relative to the multi-agent reference ($p{=}0.018$ and $p{=}0.035$, paired); we make no verification-benefit claim from this screen. Same-seed repeat runs are bit-identical, and the 5-to-10-seed CI half-width ratio is 0.539 (median)."

## 2. Experimental Setup (Section \ref{sec:setup})
**Update the run count and seeds:**
"Five scenarios (Table~\ref{tab:scenarios}) differ in device mix and stressors. Each runs 10 seeds (42, 123, 456, 789, 999, 1234, 2024, 3456, 5555, 8888) $\times$ 5 controllers = 250 runs per regime, under three regimes (pool TOU, LMP, bilateral P2P) for 750 runs, plus a 50-run fallback-mode ablation, a 45-run real-LLM screen, and a 20-run aggressive failure-injection stress test --- 815 runs total, every run recorded with a manifest (\texttt{git\_dirty: false})."

**Add Scenario D exclusion note:**
"\textbf{Scenario D exclusion.} A config-propagation defect is under investigation by which scenario~D's energy-sharing configuration does not reach the simulation (D is bit-identical to A including per-member bills, despite a different config hash). All scenario~D rows are excluded from the tables below pending the fix and a re-run; the defect, not the physics, is the cause."

**Add Variance semantics note:**
"\textbf{Variance semantics.} With the restored stock dataset, load and PV profiles are fixed real traces: seeds vary only controller-internal stochasticity (and the synthesized EV connection schedules). Reported CIs therefore quantify controller-level, not environment-level, variability; cross-scenario and cross-regime comparisons carry the treatment signal."

## 3. Cost, Peak and Service (Section \ref{sec:costpeak})
**Update Table \ref{tab:deltas} caption:**
"Paired per-seed deltas vs. \agent{rule\_based} (mean $\pm$ 95\% CI half-width; $n{=}10$ seeds; Holm within each scenario over the four controller comparisons). Scenario D excluded pending the config-propagation fix."

**Replace Table \ref{tab:deltas} data (Partial view - apply these 16 rows):**
- A: multi_agent $-18.11 \pm 0.03$, $-16.59 \pm 0.00$, $p < 0.0001$
- A: centralized $-5.26 \pm 0.22$, $+1.43 \pm 0.00$, $p < 0.0001$
- A: mpc $+69.60 \pm 8.54$, $+29.44 \pm 0.00$, $p < 0.0001$
- A: rl $+110.09 \pm 8.41$, $+49.28 \pm 3.37$, $p < 0.0001$
- B: multi_agent $-43.03 \pm 1.45$, $-25.68 \pm 0.00$, $p < 0.0001$
- B: centralized $-2.06 \pm 0.62$, $-4.71 \pm 1.41$, $p < 0.0001$
- B: mpc $+16.35 \pm 2.66$, $-18.73 \pm 0.00$, $p < 0.0001$
- B: rl $+34.41 \pm 2.14$, $+10.10 \pm 0.42$, $p < 0.0001$
- C: multi_agent $-11.95 \pm 0.04$, $-16.59 \pm 0.00$, $p < 0.0001$
- C: centralized $-3.68 \pm 0.16$, $+1.20 \pm 0.00$, $p < 0.0001$
- C: mpc $+68.03 \pm 8.33$, $+29.44 \pm 0.00$, $p < 0.0001$
- C: rl $+52.69 \pm 3.06$, $+12.83 \pm 1.47$, $p < 0.0001$
- E: multi_agent $-17.46 \pm 0.03$, $-17.26 \pm 0.00$, $p < 0.0001$
- E: centralized $-5.06 \pm 0.22$, $+1.43 \pm 0.00$, $p < 0.0001$
- E: mpc $+68.18 \pm 8.48$, $+29.44 \pm 0.00$, $p < 0.0001$
- E: rl $+108.45 \pm 8.09$, $+49.28 \pm 3.37$, $p < 0.0001$

**Add Service Trade-off discussion:**
"\textbf{The service trade-off, stated explicitly.} \agent{multi\_agent} is cost-minimal (e.g.\ $22.39 \pm 0.00$ vs.\ rule-based $40.49 \pm 0.03$ USD in scenario~A) but completes only $0.057$ of EV departure requirements, against $0.154$ for rule-based and $1.000$ for MPC. Under the paper's service-aware objective this is a defect, not a win: the controller buys cost and peak reductions ($-16.59$ kW) by under-charging EVs. We therefore report cost, peak, and EV completion as jointly necessary, and treat closing the EV gap under cost parity as open work rather than an achieved property. With restored PV, several scenario~C configurations are net exporters and their total cost is negative (export credit exceeding import cost); negative totals are flagged as export-credit, not as profit."

## 4. LMP-Regime Benchmark (Section \ref{sec:lmp})
**Replace section text:**
"250 runs under \texttt{lmp} pricing (5 controllers $\times$ 5 scenarios $\times$ 10 seeds; scenario~D excluded as in Section~\ref{sec:setup}). The central finding is a \emph{price-awareness split}: only the two price-aware controllers react to the regime. MPC's cost rises from $110.09 \pm 8.54$ USD (TOU) to $168.47 \pm 10.69$ (LMP) in scenario~A and its EV completion drops (1.000 $\to$ 0.966), and RL's arm shifts similarly (150.58 $\to$ 106.22 in scenario~A), while rule-based, multi-agent, and centralized --- none of which condition on prices --- produce dispatch- and cost-identical results under both regimes (e.g.\ multi\_agent $22.39 \pm 0.00$ in both). Ranking within a regime is unchanged: \agent{multi\_agent} cost-minimal (all $p_{\mathrm{Holm}} < 0.0001$), \agent{centralized} close to \agent{rule\_based}. The identical-to-TOU behavior of the price-insensitive heuristics is reported as a finding: pricing-regime changes are invisible to controllers that do not read prices, which is the mechanism the P2P regime (Section~\ref{sec:results}) is designed to probe."

## 5. P2P Regime (New Section \ref{sec:p2p})
**Insert after LMP section:**
"\subsection{P2P Regime: Bilateral Clearing Redistributes, Aggregates Unchanged}
\label{sec:p2p}
250 runs under \texttt{p2p} pricing (bilateral double-auction clearing with uniform residual price, same grid as Section~\ref{sec:setup}). Paired against the pool-TOU matrix at identical (scenario, controller, seed), the community aggregates are \emph{bit-identical}: $\Delta$ cost, $\Delta$ peak, and $\Delta$ EV completion are exactly zero across all 200 paired runs, while bilateral trades clear in every run (mean community volume 347.2 kWh, max 563.1, no zero-volume runs). This cost-transparency is by construction: trades reallocate energy between members before power flow, leaving the residual grid exchange unchanged.

The effect is at the member level. Per-member bills shift significantly under P2P (paired, $n{=}40$ runs per member): building\_2 pays $7.60 \pm 1.83$ USD less, while building\_1 ($-5.64 \pm 1.97$), building\_3 ($-7.17 \pm 1.16$), and building\_4 ($-2.37 \pm 2.04$) pay more; building\_0's change is not significant ($+1.92 \pm 4.60$). Aggregate savings vs.\ baseline are statistically indistinguishable from pool clearing ($-5.66 \pm 10.09$ USD, paired $p{=}0.26$). The fairness coefficient as computed is invariant ($0.0926$ in both arms, zero paired variance), which exposes a measurement gap: the current Gini input does not reflect settlement redistribution. We therefore report RQ3 as \emph{redistribution without aggregate benefit} under the tested regime, and defer inequality claims until a settlement-aware fairness metric is defined."

## 6. Real-LLM Screen: M2a (Section \ref{sec:m2a})
**Update model description:**
"The M2a screen replaces the deterministic fallback proposer with a hosted LLM on the same 24-step horizon. All 30 LLM-arm runs completed on the API; per-arm agent-execution aggregates (15 runs per arm):"

**Update Gate Verdict:**
"\textbf{Gate verdict.} The pre-registered M2b gate (proceed to a full-week 169-step confirmation only if the arms differ by $\geq 10$\,pp on \texttt{llm\_unrepaired\_violations} or \texttt{llm\_fallback\_step\_share}, or KPI CIs exclude zero) is \emph{not met}: unrepaired violations and repair iterations are zero in both arms, and the fallback-share difference is $0.6$\,pp. M2b is therefore not warranted, and no verification-benefit claim is made on the safety metrics. The validity gate is passed (fallback share $0.006 \ll 0.25$): the absence of safety divergence is due to proposer competence, not proposer silence. The residual KPI differences are suboptimality, not violations, and are statistically significant as an arm difference: paired over the 15 (scenario, seed) runs, the unverified arm's cost delta exceeds the verified arm's by $+1.27 \pm 1.02$ USD (paired $t{=}2.69$, $p{=}0.018$) and its peak delta by $+9.86$ kW ($t{=}2.33$, $p{=}0.035$) --- per-step verification does not target this suboptimality, so we report it as an observational contrast, not a verification benefit. This null result is specific to the model--prompt--horizon combination; a harsher proposer or longer horizon remains untested (Section~\ref{sec:limitations})."

## 7. Reproducibility (Section \ref{sec:repro})
**Replace section text:**
"All 815 runs (750 B-axis: 3 regimes $\times$ 5 scenarios $\times$ 5 controllers $\times$ 10 seeds, on the post-fix physics; 50 fallback ablation; 45 real-LLM screen; 20 aggressive stress) carry \texttt{manifest.json} with config SHA-256, git commit, package versions, controller, \texttt{agent\_backend}, prompt version/hash, temperature/seed. \texttt{failed\_runs.json = []} (0 failed). Three pieces of evidence beyond per-run manifests: (1) \emph{same-seed bit-identity} --- one configuration re-run three times produces byte-identical KPIs (cost 22.388099, peak 13.025067); (2) \emph{config distinctness} --- each scenario has distinct \texttt{scenario\_config\_sha256} per seed; (3) \emph{CI tightening} --- moving from 5 to 10 seeds shrinks the median 95\% CI half-width by a factor of 0.539. Because the restored stock dataset fixes load/PV profiles across seeds (Section~\ref{sec:setup}), the residual CI width reflects controller-level nondeterminism only (e.g.\ MPC's LP degeneracy, $\pm$8.54 USD), which we state explicitly rather than present as environment variance."

## 8. Discussion and Limitations (Section \ref{sec:discussion})
**Update LLM Proposer limit:**
"3. \textbf{LLM proposer}: Real-LLM screen uses a single hosted model at temperature 0 on a 24-step horizon; the null result is specific to this model--prompt--horizon combination. The deployed model identity is withheld by operator policy; manifests retain the full model and prompt provenance for verification under agreement."

**Add Scenario D limit:**
"4. \textbf{Scenario D}: Excluded from all tables pending resolution of a config-propagation defect under investigation (Section~\ref{sec:setup})."

## 9. Conclusion (Section \ref{sec:conclusion})
**Replace section text:**
"We present a service-aware energy agent framework spanning pricing regimes, failure injection, and verified LLM code-agent repair. The multi-agent controller achieves consistent cost/peak reduction across all scenarios and pricing regimes with a measurable EV service trade-off that we report explicitly. Aggressive failure injection confirms correct violation detection (zero resolution on structural violations is correct behavior); recovery remains untested. The LLM ablations show null divergence between verified/unverified arms on the safety gate in both fallback mode and the real-LLM M2a screen, isolating the verification machinery as a no-op under an in-bounds proposer; the unverified arm alone shows cost/peak regressions that verification does not target. All artifacts are reproducible: 815 runs on clean commits with full manifests, zero failures, bit-identical same-seed repeats, and a measured 0.539 median CI half-width ratio at 10 seeds.

Future work: longer-horizon M2b confirmation with a harsher LLM proposer (forcing verifier engagement), multi-LLM replication, a settlement-aware fairness metric for redistribution analysis, and extended horizon stress tests."

---

## 10. Scenario D rows (post-fix, `experiments/matrix_d_rerun`, 2026-11-07)

Scenario D's config-propagation defect is fixed on main (`9f62e027f`): the
`total_cost` KPI now uses `SettlementEngine.actual_total_bill` when energy
sharing is enabled. Only scenario D has `energy_sharing.enabled: true`, so
A/B/C/E are untouched (verified: same-seed A-vs-D grid exchange, PV, peak and
per-member costs are unchanged to <= 3.4e-7 relative; the reported A/B/C/E
deltas below are recomputed from `experiments/matrix_full` and match §4
exactly).

Re-run: 5 controllers x 10 seeds x 3 regimes = 150 runs, all with
`git_dirty: false` (`0e3eb46e`), 0 failed, run IDs matrix-qualified as
`experiments/matrix_d_rerun[_lmp|_p2p]/scenario_d/scenario_d_{controller}_{seed}`.
A-vs-D now diverges at all 10 seeds (A 40.42--40.54 USD grid-only vs. D
190.77--190.87 USD with community settlement).

**Run provenance (final pass, 2026-11-07 14:01--14:22):** 150/150 runs completed,
0 failed, every manifest `git_dirty: false` at one commit (`c326e177e`, which
includes the `SAEA_RUN_ID` per-run schema isolation fix in the supervisor),
`scenario_config_sha256` distinct per seed, Python 3.13.5 / citylearn 3.0.2 /
pandapower 3.5.6 / numpy 2.4.6 recorded per run. Same-seed repeats across the
interim and final passes are bit-identical (e.g. `scenario_d_rule_based_42`
total_cost `190.77508188227625` both passes).

### 10.1 Remove the Scenario-D exclusion notes

Delete the `\textbf{Scenario D exclusion.}` paragraph and the `Scenario D
excluded` clauses in §2/§4/§5/§8 of this spec; the physics and the KPI are now
correct, so scenario D rows return to Tables 2/3 and the LMP/P2P tables.

### 10.2 Table 2 (tab:deltas) scenario-D rows

Paired per-seed deltas vs. `rule_based`, $n{=}10$, Holm within scenario D:

| Scenario | Controller | $\Delta$ cost (USD) | $\Delta$ peak (kW) | $p_{\mathrm{Holm}}$ |
|---|---|---|---|---|
| D | multi\_agent & $-78.56 \pm 0.03$ & $-16.59 \pm 0.00$ & $< 0.0001$ |
| D | centralized & $+3.99 \pm 0.24$ & $+1.43 \pm 0.00$ & $< 0.0001$ |
| D | mpc & $+242.63 \pm 18.93$ & $+29.44 \pm 0.00$ & $< 0.0001$ |
| D | rl & $+374.34 \pm 14.41$ & $+49.28 \pm 3.37$ & $< 0.0001$ |

### 10.3 Scenario-D KPI table (pool TOU)

| Controller | Total cost (USD) | Peak demand (kW) | EV completion |
|---|---|---|---|
| rule\_based | $190.81 \pm 0.03$ | $29.62 \pm 0.00$ | $0.154 \pm 0.062$ |
| multi\_agent | $112.26 \pm 0.00$ | $13.03 \pm 0.00$ | $0.057 \pm 0.039$ |
| centralized | $194.80 \pm 0.25$ | $31.05 \pm 0.00$ | $0.160 \pm 0.065$ |
| mpc | $433.44 \pm 18.93$ | $59.06 \pm 0.00$ | $1.000 \pm 0.000$ |
| rl | $565.15 \pm 14.41$ | $78.90 \pm 3.37$ | $0.977 \pm 0.021$ |

### 10.4 New cost-basis caveat (must be added to Limitations)

Scenario D's `total_cost` is **settlement-inclusive**
(`SettlementEngine.actual_total_bill`: grid bill plus community charges), while
A/B/C/E report the grid-only cost, because only D enables sharing. Cross
**scenario cost magnitudes are therefore not comparable** (D's absolute level
is higher by construction); every cost comparison in the paper is
**within-scenario** (paired deltas vs. `rule_based`), which is unaffected.
State this explicitly rather than leaving the level shift unexplained.
**Label requirement (PM decision 2026-11-07):** every axis and table that
shows D's cost beside A/B/C/E must carry the basis note —
"Scenario D: community bill incl. settlement; A/B/C/E: grid-only bill". The
figure generator now prints exactly this string on the cost panels
(`experiments/make_figures.py`, `COST_BASIS_NOTE`: `f1_total_cost` and
`f3_cost_vs_ev_completion`); the same sentence goes into the Table 2/3
captions.

### 10.5 LMP scenario-D rows (`experiments/matrix_d_rerun_lmp`)

Settlement-inclusive cost basis (§10.4); EV completion shown to 3 dp.

| Controller | Cost TOU (USD) | Cost LMP (USD) | $\Delta$ | EV TOU | EV LMP |
|---|---|---|---|---|---|
| rule\_based | $190.81 \pm 0.03$ | $165.03 \pm 0.00$ | $-25.79$ | 0.154 | 0.154 |
| multi\_agent | $112.26 \pm 0.00$ | $94.32 \pm 0.00$ | $-17.94$ | 0.057 | 0.057 |
| centralized | $194.80 \pm 0.25$ | $173.31 \pm 0.00$ | $-21.49$ | 0.160 | 0.160 |
| mpc | $433.44 \pm 18.93$ | $424.17 \pm 9.03$ | $-9.27$ | 1.000 | 0.971 |
| rl | $565.15 \pm 14.41$ | $310.29 \pm 8.23$ | $-254.86$ | 0.977 | 0.411 |

The price-awareness split (§5) holds in D as in A/B/C/E: the three
price-insensitive heuristics keep identical dispatch and EV completion under
both regimes (cost moves only with the price signal), while MPC ($-9.27$ USD,
EV $1.000 \to 0.971$) and RL ($-254.86$ USD, EV $0.977 \to 0.411$) respond.

### 10.6 P2P scenario-D rows (`experiments/matrix_d_rerun_p2p`) -- claim revision

Paired against the new pool-TOU D runs, D is **not** aggregate-identical under
P2P (unlike A/B/C/E, which the 750-run matrices showed to be bit-identical):

| Controller | $\Delta$ cost P2P$-$TOU (USD) | $\Delta$ peak (kW) | $\Delta$ EV | community volume (kWh) |
|---|---|---|---|---|
| rule\_based | $+9.58 \pm 0.91$ | $+0.00 \pm 0.00$ | $+0.0000$ | $312.1 \pm 2.7$ |
| multi\_agent | $-24.10 \pm 0.00$ | $+0.00 \pm 0.00$ | $+0.0000$ | $252.1 \pm 0.0$ |
| centralized | $+12.08 \pm 1.04$ | $+0.00 \pm 0.00$ | $+0.0000$ | $283.8 \pm 3.3$ |
| mpc | $+29.06 \pm 4.63$ | $+0.00 \pm 0.00$ | $+0.0000$ | $320.4 \pm 8.9$ |
| rl | $+34.02 \pm 0.91$ | $+0.00 \pm 0.00$ | $+0.0000$ | $520.4 \pm 12.7$ |

Peak and EV completion stay exactly zero-change in every controller. Member
settlement bills redistribute as before (rule\_based, $n{=}10$: building\_2
$-5.65 \pm 0.37$, building\_3 $+7.08 \pm 0.54$, building\_1 $+5.76 \pm
0.23$, building\_0 $+1.53 \pm 0.46$, building\_4 $+0.86 \pm 0.16$ USD).

**Paper consequence:** the RQ3 statement "community aggregates are
bit-identical under P2P" is now true for the 160 A/B/C/E paired runs only.
With community settlement already active in D, bilateral clearing also moves
the aggregate (the residual pool price is no longer the uniform settlement
price). Re-word RQ3 as: *P2P clearing is cost-transparent where no community
settlement is active, and adds a further redistribution on top of an already
settled community (D)* -- and keep the gini/measurement-gap caveat from §6.

### 10.7 Figures f1-f3 (regenerated 2026-11-07)

`experiments/figures/` is rebuilt from `experiments/matrix_full_postfix`
(scenarios A/B/C/E symlinked from `experiments/matrix_full`, scenario D from
`experiments/matrix_d_rerun`), via `docs/build_raw_results.py` (supervisor
matrix -> `raw_results.json`) and `experiments/make_figures.py`. Because D's
cost basis is settlement-inclusive (§10.4), D's bars sit ~5x higher than A/B/C/E
on the same axis; either annotate D in the figure caption or add a panel-level
note -- do not silently mix bases in one axis.

---

## 11. Service-metrics honesty: thermal comfort is UNMEASURABLE (PM decision 2026-11-07)

Add to the service-metrics section of the paper (and mirror in Limitations):

> ``service.comfort_violation_degree_hours`` is **0.0 in every run of this
> study -- a data-availability artefact, not evidence of comfort
> satisfaction.** The stock CityLearn 2022 dataset ships
> ``indoor_dry_bulb_temperature`` entirely NaN, so the [20, 25] degC band
> check in ``src/evaluation/metrics.py`` cannot accumulate a violation. EV
> service is fully reported (completion rate and average/worst SOC at
> departure, per scenario and controller, 10 seeds); thermal comfort is out of
> scope on this dataset and we make no comfort claim. A dataset with real
> indoor temperature (or a CityLearn thermal building model) is required
> before any comfort statement.

Rules that follow from it:

* no table, figure, caption, or sentence may present `comfort_violation_degree_hours = 0`
  as "no comfort violations" or as a controller property;
* the 22.0 degC comfort fill (commit `705923481`) exists only so gymnasium >= 1.1 can
  build the observation space; it is not comfort data and changes no reported number
  (comfort stays exactly 0.0, as in every pre-fix run);
* the EV trade-off already reported for `multi_agent` (0.057 vs 1.000 for MPC) stays the
  service headline; comfort is listed as unmeasurable in the Limitations.

Source of the claim: `docs/item7_service_and_failures/comfort_report.md` and
`ev_report.md` (`docs/item7_analysis.py`), computed from the 250-run pool-TOU
matrix `experiments/matrix_full_postfix`.
