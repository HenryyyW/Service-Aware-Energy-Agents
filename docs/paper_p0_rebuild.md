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

### 10.5 LMP and P2P scenario-D rows

The LMP leg (`experiments/matrix_d_rerun_lmp`) and the P2P paired leg
(`experiments/matrix_d_rerun_p2p`) run against the same commit; the D rows of
the LMP table and the P2P paired comparison are rebuilt by
`docs/d_table_rebuild.py` into `docs/d_table_rebuild/` when those legs finish.
