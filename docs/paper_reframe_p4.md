# P4 — Paper reframe draft: platform core, code-repair as a component result

Owner: Research Engineer · Date: 2026-11-10 · Status: draft for the PM's merge coordination
Decision basis: user recalibration (2026-11-10) — the project is the **Renewable Energy Community Virtual Simulator**: NL scenario description → Coding Agent → executable sim config → virtual community; rule-based / MPC / single-RL / multi-RL strategies; the agent is the **workflow assistant**, not a fifth algorithm. No arXiv upload (user decision, PM holds).
Constraint honoured: every number below is copied verbatim from `arxiv_submission/arxiv_main.tex` or from the benchmark record (`docs/reviewer_response/code_repair_results.md`); nothing is newly computed, and nothing is claimed that a run has not produced.

**Positioning of record (recalibrated on `origin/main` `cda47891a4`, cited per the PM):** `project brief.md` (its "Current status and phase plan" table, the five workflow stages, and the agent-as-assistant section), `README.md`, `README.zh-CN.md`. The five workflow stages are **Scenario Construction → Simulation → Visualization → Strategy Comparison → Agent-assisted Optimization**; the control strategies of record are **rule-based, MPC, single-agent RL, multi-agent RL, plus the centralized heuristic**; the coding agent is the **engineering assistant, explicitly NOT a fifth control baseline**, and its own evaluation is by workflow capability (scenario-construction success rate, strategy-modification verification rate under the physics/service gates, diagnosis quality, report completeness) — never by energy performance as a controller. The brief's phase table places the strategy-modification benchmark under **P3** as "real capability, below threshold" (5/9 detector-verified modifications, pre-registered ≥7/9 not met) and this reframe under **P4**.

---

## 1. Drop-in abstract (platform-first)

> We present a renewable energy community virtual simulator whose authoring
> workflow is assisted by a coding agent: an engineer describes a community in
> natural language, the agent produces an executable simulation configuration,
> the engineer confirms it field-by-field before anything runs, and the
> simulator then evaluates the control strategies of record --- rule-based, MPC,
> single-agent RL, and multi-agent RL, plus the centralized heuristic --- across
> five scenarios (A--E) covering coordination baselines,
> battery/PV assets, deferrable loads, energy sharing with community
> settlement, and mid-run component failures. The simulator couples CityLearn
> building-level simulation with pandapower grid validation across three
> pricing regimes --- pool TOU, locational marginal prices (LMP), and bilateral
> P2P --- at ten seeds each (750 runs), with a further 150-run scenario-D
> re-run after an energy-sharing configuration defect was fixed; every run
> carries a manifest recording its full provenance. The agent-authored front
> door is held to an explicit acceptance standard rather than trust: a 16-item
> natural-language corpus with five criteria --- complete-config planning,
> required fields, in-range values, clean simulation, and round-trip through
> the scenario API --- including deliberately incomplete and out-of-range
> descriptions whose rejection must name the offending field instead of
> silently auto-correcting it. The multi-agent controller is cost- and
> peak-minimal in every scenario (paired cost delta vs.\ rule-based $-11.95$ to
> $-43.03$ USD across A/B/C/E on the grid-only cost basis, $-78.56$ USD in
> scenario D on the settlement-inclusive basis,
> $p_{\mathrm{Holm}} < 0.0001$, $n{=}10$) with an explicit EV-completion
> trade-off ($0.057$ vs.\ $1.000$ for MPC) that we report rather than resolve;
> scenario D rows are settlement-inclusive while A/B/C/E are grid-only, and all
> cost comparisons are within-scenario. Only price-aware controllers (MPC, RL)
> change dispatch when the pricing regime changes; a fixed trajectory still
> bills differently under different price series, so dispatch identity never
> implies cost identity. Under P2P clearing the A/B/C/E community aggregates
> are bit-identical to pool clearing while member bills redistribute
> significantly, and scenario D --- whose settlement is already active ---
> diverges at the aggregate as well, through the real grid-cost change from
> energy sharing. Thermal comfort is unmeasurable on the stock dataset (the
> indoor-temperature series is entirely NaN), so no comfort claim is made. On
> the agent layer, the real-LLM dispatch screen is a safety-metrics null
> (unrepaired violations in 1 of 50 unverified runs, 0 of 49 verified runs;
> repair iterations zero in both arms), and the hostile-proposer study shows
> the verified arm accepting zero out-of-bounds proposals in every kept cell
> against 9.2--13.0 per step unverified, with corrective re-prompt recovering
> 0.909--1.000 of corrupted proposals (mean 0.970). As a **strategy-modification
> component**, the five-agent repair loop repairs 5 of 9 seeded controller
> defects under a pre-registered acceptance bar of 7 of 9 (deterministic
> comparator: 0 of 9), reported as a component result, not a headline claim;
> runtime verification of LLM dispatch proposals remains the agent layer's
> demonstrated safety property. All artifacts are reproducible: manifests
> throughout, bit-identical same-seed repeats, and a measured 0.539 median CI
> half-width ratio from five to ten seeds.

**Changes vs. the current abstract:** opening re-centered on the NL → agent →
config → simulate workflow (the brief's five stages, with Visualization as the
platform's presentation stage rather than a paper result); the strategy list
renamed to the four strategies of record plus the centralized heuristic (the
paper's measured controllers map one-to-one: multi-agent → multi-agent RL, RL →
single-agent RL, centralized → the centralized heuristic, so the 750-run matrix
and every number in it stay traceable); the 150-cell real-LLM screen and
60-cell hostile-proposer study kept with their numbers but folded into one
"agent layer" sentence; the code-repair sentence replaced by the
component-result sentence (Section 4 below); everything else verbatim.

## 2. Introduction restructure

Keep the three literature-established gaps (they are the intro's spine) and add the platform framing as the first move:

1. **New opening paragraph** — the workflow, not the controller zoo: "Renewable energy community studies presuppose an executable scenario: a device mix, a tariff, a grid model, a weather file. Building that scenario is expert busywork, and it is the part practitioners cannot check. We present a simulator whose authoring step is itself assisted by a coding agent and gated by field-level confirmation, so the scenario an experiment runs is the scenario the engineer approved." Then the existing REC-control paragraph follows.
2. **RQ0 (new, platform):** can an agent-authored scenario config be held to an acceptance standard that names its own failures? Answer: the corpus + rubric (16 items, 5 criteria, rejection path names the field) — **instrument ready; pipeline results pending A's P1 build**, so the paper cites the instrument and reports the outcome when the pipeline lands.
3. **RQs 1–3 keep** (pricing-regime diversity; verified-dispatch safety; strategy comparison), each still "established by a distinct literature" per the current text.
4. **The agent is not a fifth controller** — one explicit sentence so the strategy suite stays the four-plus-baseline design and the agent's role (authoring, verification gating, strategy modification) is separated from the strategies themselves.
5. **Contributions list updated:** (C1) platform + coupling; (C2) 750-run strategy matrix findings; (C3) agent-layer safety results (screen null + hostile-proposer); (C4) the NL acceptance corpus; (C5) the strategy-modification component result at its measured level.

## 3. Results restructure (section map)

| Current | Reframed |
|---|---|
| (opening) Cost, Peak and Service | **Platform: simulation coupling and provenance** (new §, short) — coupling, manifests, same-seed bit-identity, CI half-width — moves the reproducibility claim up front as a platform property |
| Cost, Peak and Service; LMP; P2P; Scenario E | **Strategy comparison** (same subsections, same numbers, same within-scenario basis) |
| Ablation: Verified vs Unverified; Real-LLM Screen; Hostile-Proposer | **Agent layer: dispatch verification** (same subsections; the 150/50/49 and 13-cell numbers verbatim) |
| — | **Agent layer: scenario authoring acceptance** (new §) — the 16-item corpus, the five criteria, the pre-registered bar (≥14/16, all 8 domains, all 4 rejection items), and the pipeline score when A's pipeline is verified; until then the section states the instrument |
| — | **Agent layer: strategy modification (component result)** (new §) — the two-arm code-repair benchmark: acceptance of record = driver criteria (a)–(f) with `loop_claimed_success` beside every verdict; deterministic comparator 0/9 with 10/10 loop/driver agreement; LLM arm 5/9 detector-verified repairs on the converting contract, threshold ≥7/9 not met; both arms unpooled; earlier bases' 0/9 labelled as located-defect evidence, not model measurement |
| Service-Level Constraints; Reproducibility | unchanged |
| Discussion/Limitations; Case Study; Conclusion | Discussion gains one limitation paragraph: the authoring-acceptance results are pending the pipeline; the code-repair component is below its pre-registered bar |

## 4. The A2 sentence (before → after)

- **Before (current paper):** "The five-agent code-repair loop is implemented and instrumented but its behaviour-changing code patches are scaffolded, not yet demonstrated; the results reported here cover runtime verification of LLM dispatch proposals."
- **After:** "The coding agent's demonstrated role is the workflow one — authoring executable scenario configurations under a named-field acceptance standard and gating dispatch proposals at runtime — while its autonomous strategy-modification component is measured, not assumed: a two-arm benchmark of the five-agent repair loop repairs 5 of 9 seeded controller defects against a pre-registered bar of 7 of 9 (deterministic comparator 0 of 9, loop and driver verdicts agreeing 10/10), a component result we report at its measured level rather than as a platform claim."

Rationale: the old sentence claims nothing (correctly), but under the reframe the honest positive claim is the workflow role plus a measured component result — the sentence now says what *is* demonstrated and at what level the modification component sits.

## 5. Keywords / title (for the PM's call)

- Keywords: drop "LLM code agents" from the lead; proposed set — *renewable energy communities, virtual simulator, LLM-assisted scenario authoring, multi-agent control, power system simulation, pricing regimes, verification*.
- Title direction (user's recalibration): lead with the simulator/workflow, keep the strategy result as the second clause. Two candidates in the migration notes below.

## 5a. Alignment with the positioning of record (checked against `project brief.md`, `README.md`, `README.zh-CN.md`, main `cda47891a4`)

| Reframe element | Positioning of record | This draft |
|---|---|---|
| Platform identity | Renewable Energy Community Virtual Simulator | §1 abstract opening; title direction |
| Workflow | five stages: Scenario Construction → Simulation → Visualization → Strategy Comparison → Agent-assisted Optimization | §1/§2 follow the five stages; Visualization is the platform's stage (P2, last per the phase table) and carries no paper result |
| Strategies | four of record (rule-based, MPC, single-agent RL, multi-agent RL) + centralized heuristic | §1 abstract + §3 strategy comparison; mapping to the paper's five measured controllers in §1's changes note |
| Agent role | engineering assistant, NOT a fifth control baseline; "the agent's code never enters the results as a control strategy" (binding) | §2 item 4 and the new Discussion limitation |
| Agent evaluation | workflow capability metrics (scenario-construction success rate, strategy-modification verification rate under the gates, diagnosis quality, report completeness) — never energy performance | §3 agent-layer sections; the corpus supplies the scenario-construction metric |
| Component number | P3: 5/9 detector-verified strategy modifications, threshold ≥7/9 not met — "real capability, below threshold" | §3 component section + §4 A2 sentence, worded at exactly that level |
| Phase order | P1 → P3 → P4 → P2 | the reframe cites the phase table rather than re-justifying the order |

## 6. Open items for the PM (not decided unilaterally)

1. RQ0's results are pending A's pipeline — does the reframed paper go out with the instrument only (accepted with the limitation), or hold the abstract's acceptance sentence until the pipeline is verified?
2. Whether the 750-run matrix stays the quantitative core (it is the strongest measured result) or shares the core with the platform acceptance once the pipeline lands.
3. Title wording (two candidates drafted for the PM's pick) and whether "service-aware" stays in the title.

## 7. Migration notes (mechanical, for the merge)

- All moved text is a re-order of existing `\section`/`\subsection` blocks in `arxiv_submission/arxiv_main.tex` plus the two new sections; the only new prose is §1's abstract sentence pair, §2's opening paragraph, and §3's two new sections.
- Every number in §1 is copied from the current abstract; the code-repair numbers in §3/§4 come from `docs/reviewer_response/code_repair_results.md` (converting-contract section) — no new runs, no re-statistics.
- The PDF rebuild path stays `/tmp/opencode/tectonic` with the author block verbatim; the no-arXiv-upload decision means the merge lands on main only.
