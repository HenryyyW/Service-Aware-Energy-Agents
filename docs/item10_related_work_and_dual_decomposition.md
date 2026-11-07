# Item 10 — related-work additions, dual-decomposition math, end-to-end case study

Author: Research Engineer. Status 2026-11-07: sections 1-2 final; section 3
(case study) waits on the M2a laguna matrix (`experiments/m2a_rerun_laguna`,
150 cells, launched under written PM authorization: `poolside/laguna-xs-2.1`
on NVIDIA NIM, 24 steps, pool_tou, 10 seeds) for its paired numbers.

## 1. Related-work additions (verified citations; no invented entries)

| Slot | Entry | Why it belongs |
|---|---|---|
| Agentic HEM (2026) | S. Jonah, Q. Moses, A. Babatunde, M. Ajao-Olarinoye, D. Bammeke, "LLMs for Agentic Home Energy Management", arXiv:2607.04569, 2026. | Tool-calling ReAct agent over half-hourly dynamic prices; the paper's own conclusion is that "every committed schedule is checked by an independent deterministic feasibility validator before actuation" — the same separation our verified arm implements. |
| Agentic HEMS (2026) | R. El Makroum, S. Zwickl-Bernhard, L. Kranzl, "Agentic AI home energy management system: a large language model framework for residential load scheduling", *Results in Engineering* 29:109857, 2026. | Hierarchical agentic HEMS where the LLM is the decision-maker; contrast with our physics-grounded verification. |
| Agentic HEMS assistant (2026) | W. Jung, "Multi-Agent Home Energy Management Assistant (HEMA)", *SoftwareX* 34:102633, 2026. | Multi-agent HEMS with 36 domain tools; shows the conversational/assistant branch our paper is *not* in. |
| Intent-driven state verification (2026) | S. Mao, M. Liu, J. Chen, D. Nan, J. Ma, "A trustworthy intent-driven LLM-agent workflow with state verification for power system simulation", *Applied Energy* 427(B):128868, 2026, doi:10.1016/j.apenergy.2026.128868. | Closest neighbour: separates LLM workflow planning from solver-side execution and checks admissibility, state-dependent constraints, and execution evidence before accepting results. Our contribution is the same separation applied to *closed-loop control actions* with a physics (pandapower) verification gate and a quantified null result. |
| ElecBench (2025) | X. Zhou, H. Zhao, Y. Cheng, G. Liang, G. Liu, W. Liu, Y. Xu, J. Zhao, "ElecBench: a Power Grid Dispatch Evaluation Benchmark for Large Language Models", *IEEE PESGM 2025* (Best Paper), doi:10.1109/PESGM52009.2025.11225826; arXiv:2407.05365. | Knowledge/dispatch benchmark — 6 metrics, 24 sub-metrics, question-answering style. Our benchmark is action-level and physics-grounded; cite as the knowledge-side reference. |
| PowerAgentBench-SS (2026) | C. Mylonas, M. Foti, A. Pomarico, M. Duarte, Q. Zhang, E. Varvarigos, "PowerAgentBench-SS: a benchmark for agentic AI in power system steady-state studies", arXiv:2606.18789, 2026. | Agent-interface benchmark with hidden evaluator, evidence log and risk-sensitive metrics (submitted/evidence-backed recall, false-safe penalties, residual-violation score). Cite as the agent-interface reference and note that our failure-injection + settlement dimensions are not covered there. |
| Smart-grid MAS survey (2024) | Y. Izmirlioglu, L. Pham, T. C. Son, E. Pontelli, "A Survey of Multi-Agent Systems for Smartgrids", *Energies* 17(15):3620, 2024, doi:10.3390/en17153620. | MAS-for-smartgrids survey; anchors the multi-agent coordination background. |
| Adjacent (optional) | D. Rojas et al., "LLMs and Agentic AI Systems for Smart Grids: A Tutorial on Architectures and Applications", arXiv:2607.18147, 2026 (solver-grounded design principle, verification gate); F. Batole, F. Khomh, H. Rajan, "RefineAct: Automatic Runtime Verification of LLM Agent Actions", ASE 2026. | Tutorial states the principle we instantiate ("a numerical result is reported only when it originates from a trusted tool and passes explicit verification"); RefineAct is the software-engineering runtime-verification neighbour. |

Positioning paragraph for the paper: our work is the first to run the
planning/verification separation over a *multi-step closed-loop control* task
where the verification gate recomputes the physics (pandapower power flow) and
the economics (settlement) of the proposed actions, and to report a quantified
null result (0 repairs / 0 unrepaired violations across all arms) rather than a
capability claim.

## 2. Dual-decomposition formulation and convergence

Architecture as implemented (`src/controllers/multi_agent.py`,
`src/coordination/`): building / battery / EV / flexible-load agents each
propose dispatch; an aggregator reconciles against the community constraint;
the result is validated by the grid check; the loop runs at most
`max_iterations` (default 3).

Dual-decomposition view (for the paper's method section): let building *i*
own a local decision $x_i$ (battery / EV / flexible-load dispatch) with local
objective $f_i(x_i)$ (import cost) and local constraint set $\mathcal{X}_i$
(device ratings, EV departure SOC, comfort band). The community couples the
agents through the shared exchange limit
$\sum_i g_i(x_i) \le G$ (and through shared storage / settlement). Relax the
coupling constraint with multiplier $\lambda \ge 0$:

$$
\min_{x_i \in \mathcal{X}_i} \; f_i(x_i) + \lambda\, g_i(x_i)
\quad \forall i,
\qquad
\lambda^{k+1} = \big[\lambda^k + \alpha_k \big(\textstyle\sum_i g_i(x_i^k) - G\big)\big]_+ .
$$

Each agent then sees only its own objective plus a price $\lambda$ on the
shared resource — the same information structure the LMP regime exposes — and
the coordinator's job reduces to a price update. Convergence facts to state
(pre-registered, theory only):

* with **convex** $f_i$, compact $\mathcal{X}_i$ and a **diminishing but
  non-summable** step size $\alpha_k$, dual ascent converges to the optimal
  multiplier and the primal iterates to an optimal solution at rate
  $\mathcal{O}(1/k)$ (subgradient descent on the dual);
* **asynchrony** in the price update or **inexact** local solves degrade the
  rate to $\mathcal{O}(1/\sqrt{k})$ and leave a residual neighbourhood
  (Yfantis et al. 2024 benchmarks exactly these variants; Su et al. 2021
  prove the asynchrony/inexactness interaction);
* **non-convex** local problems (rule-based heuristics, tabular RL, LLM
  proposals) carry **no** such guarantee.

Honesty statement for the paper: the shipped coordinator does **not**
implement dual ascent — the aggregator uses a deterministic reconciliation
with a 3-iteration cap and a grid-feasibility re-dispatch, so no convergence
claim is made for the controller. The formulation is included because it
explains (i) why the LMP regime is the natural price signal for a decomposed
architecture, (ii) why the verification gate must sit at the coordinator
(only the coordinator sees the coupling constraint), and (iii) what a
convergent distributed version would require.
## 3. End-to-end agent case study (draft — numbers to be filled from the M2a re-run)

Constraint found while drafting: **no repair patch exists in any artifact** —
`repair_iterations = 0` in all 47 archived M2a-screen runs, all 150
scenario-D runs, and the 750-run B-axis matrices, and `code_diffs` is empty
everywhere (the 22 kimi cells that did run before the quota died were all
multi_agent reference cells). That is the null result, so the case study must
present the *no-repair* path and say so, rather than fabricate a patch.

Case study shape (fill from `experiments/m2a_rerun_laguna`, 24-step horizon,
scenario A, seed 42, verified arm, laguna):

1. **Input**: scenario A observations at $t=0$ (load, PV forecast, battery
   SOC, EV arrival/departure state, TOU price), packaged by the planner.
2. **Proposal**: the coder agent's dispatch proposal (requested actions) —
   record the raw proposal, the parse verdict, and the token/latency cost.
3. **Sandbox**: executor applies it in a 50-step sandbox; syntax + unit tests.
4. **Verification**: full-simulation before/after comparison (physics,
   service, grid) — the verification harness verdict and the KPI deltas.
5. **Outcome**: first-attempt validity, repair iterations (0), fallback share.
6. **Before/after metrics**: cost, peak, EV completion for
   `llm_agent_verified` vs `llm_agent` vs the paired `multi_agent` reference at
   the same (scenario, seed).
7. **Patch diff**: none produced (0 repairs); the hostile-proposer M2b
   experiment (item 4) is the queued source of a repair case.

Deliverable text will be written to `docs/end_to_end_case_study.md` once the
M2a matrix provides the paired numbers, together with the reproducibility
appendix (run IDs, manifests, prompt hashes, model digest).
