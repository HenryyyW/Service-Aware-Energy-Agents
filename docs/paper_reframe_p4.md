# P4 — Paper reframe draft: platform core, code-repair as a component result

Owner: Research Engineer · Date: 2026-11-10 · Status: draft for the PM's merge coordination
Decision basis: user recalibration (2026-11-10) — the project is the **Renewable Energy Community Virtual Simulator**: NL scenario description → Coding Agent → executable sim config → virtual community; rule-based / MPC / single-RL / multi-RL strategies; the agent is the **workflow assistant**, not a fifth algorithm. No arXiv upload (user decision, PM holds).
Constraint honoured: every number below is copied verbatim from `arxiv_submission/arxiv_main.tex` or from the benchmark record (`docs/reviewer_response/code_repair_results.md`); nothing is newly computed, and nothing is claimed that a run has not produced.

---

## 1. Drop-in abstract (platform-first)

> We present a renewable energy community virtual simulator whose authoring
> workflow is assisted by a coding agent: an engineer describes a community in
> natural language, the agent produces an executable simulation configuration,
> the engineer confirms it field-by-field before anything runs, and the
> simulator then evaluates rule-based, multi-agent, centralized, MPC, and RL
> strategies across five scenarios (A--E) covering coordination baselines,
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
config → simulate workflow; the 150-cell real-LLM screen and 60-cell
hostile-proposer study kept with their numbers but folded into one "agent
layer" sentence; the code-repair sentence replaced by the component-result
sentence (Section 4 below); everything else verbatim.

## 2. Introduction restructure

Keep the three literature-established gaps (they are the intro's spine) and add the platform framing as the first move:

1. **New opening paragraph** — the workflow, not the controller zoo: "Renewable energy community studies presuppose an executable scenario: a device mix, a tariff, a grid model, a weather file. Building that scenario is expert busywork, and it is the part practitioners cannot check. We present a simulator whose authoring step is itself assisted by a coding agent and gated by field-level confirmation, so the scenario an experiment runs is the scenario the engineer approved." Then the existing REC-control paragraph follows.
2. **RQ0 (new, platform) — INSTRUMENT-LEVEL per the PM's call:** can an agent-authored scenario config be held to an acceptance standard that names its own failures? The paper states this as **what the framework enables measuring** — the 16-item corpus, the five criteria, and the pre-registered bar (≥14/16 items, all 8 domains covered, all 4 rejection items pass) — and **cites authoring-acceptance numbers only after the in-envelope probe on the verified pipeline reports them**. Per the PM's decision: no authoring claim enters the abstract before that probe.
3. **RQs 1–3 keep** (pricing-regime diversity; verified-dispatch safety; strategy comparison), each still "established by a distinct literature" per the current text.
4. **The agent is not a fifth controller** — one explicit sentence so the strategy suite stays the four-plus-baseline design and the agent's role (authoring, verification gating, strategy modification) is separated from the strategies themselves.
5. **Contributions list updated:** (C1) platform + coupling; (C2) 750-run strategy matrix findings; (C3) agent-layer safety results (screen null + hostile-proposer); (C4) the NL acceptance corpus; (C5) the strategy-modification component result at its measured level.

## 3. Results restructure (section map) — per the PM's call: the 750-run matrix is NOT the sole quantitative core

**Cores of record:** **two cores today** — (1) the **strategy comparison**, frozen and cited at its recorded level (the PM's record: 83/67/0); and (2) the **agent layer**: the strategy-modification component at its measured level (LLM arm 5/9 detector-verified repairs vs the pre-registered 7/9; deterministic comparator 0/9; loop/driver agreement 10/10; both arms unpooled) plus the dispatch-verification results. A **third core — authoring acceptance** — arrives once A's pipeline passes verification and the in-envelope probe runs the corpus through it. Section order: platform/provenance → strategy comparison → agent layer → the two agent-result sections.

| Current | Reframed |
|---|---|
| (opening) Cost, Peak and Service | **Platform: simulation coupling and provenance** (new §, short) — coupling, manifests, same-seed bit-identity, CI half-width — the reproducibility claim up front as a platform property |
| Cost, Peak and Service; LMP; P2P; Scenario E | **Core 1 — Strategy comparison** (same subsections, same numbers, same within-scenario basis; frozen, cited at the recorded 83/67/0 level) |
| Ablation: Verified vs Unverified; Real-LLM Screen; Hostile-Proposer | **Core 2 (agent layer, part 1) — Dispatch verification** (same subsections; the 150/50/49 and 13-cell numbers verbatim) |
| — | **Core 2 (agent layer, part 2) — Strategy modification (component result)** (new §) — the two-arm benchmark: acceptance of record = driver criteria (a)–(f) with `loop_claimed_success` beside every verdict; LLM arm 5/9 detector-verified repairs on the converting contract vs the pre-registered ≥7/9 (not met); deterministic comparator 0/9 with 10/10 loop/driver agreement; both arms unpooled; earlier bases' 0/9 labelled as located-defect evidence, not model measurement |
| — | **Core 3 (after the probe) — Scenario authoring acceptance** (new §) — the 16-item corpus, the five criteria, the pre-registered bar (≥14/16, all 8 domains, all 4 rejection items), and the pipeline score; **instrument-level until the in-envelope probe reports; no authoring numbers before it** (PM's call (a)) |
| Service-Level Constraints; Reproducibility | unchanged |
| Discussion/Limitations; Case Study; Conclusion | Discussion gains one limitation paragraph: the authoring-acceptance results are pending the probe; the code-repair component is below its pre-registered bar |

## 4. The A2 sentence (before → after)

- **Before (current paper):** "The five-agent code-repair loop is implemented and instrumented but its behaviour-changing code patches are scaffolded, not yet demonstrated; the results reported here cover runtime verification of LLM dispatch proposals."
- **After:** "The coding agent's demonstrated role is the workflow one — authoring executable scenario configurations under a named-field acceptance standard and gating dispatch proposals at runtime — while its autonomous strategy-modification component is measured, not assumed: a two-arm benchmark of the five-agent repair loop repairs 5 of 9 seeded controller defects against a pre-registered bar of 7 of 9 (deterministic comparator 0 of 9, loop and driver verdicts agreeing 10/10), a component result we report at its measured level rather than as a platform claim."

Rationale: the old sentence claims nothing (correctly), but under the reframe the honest positive claim is the workflow role plus a measured component result — the sentence now says what *is* demonstrated and at what level the modification component sits.

## 5. Keywords / title

- **Title (PROPOSAL — the PM's wording, held until the user weighs in; the PM is flagging it upward):** *A Renewable Energy Community Virtual Simulator with a Physics-Grounded Coding-Agent Assistant*.
- **Subtitle (kept from the platform-first draft, carrying the service-awareness / grid-compliance clause):** *service-aware multi-agent control, failure injection, and agent-assisted scenario authoring under grid-compliance verification*. The current paper's title (Service-Aware Energy Agents: Pricing Regimes, Failure Injection, and a Verified LLM Code-Agent Workflow for Community Energy Simulation) is the "before" text this replaces.
- Keywords: drop "LLM code agents" from the lead; proposed set — *renewable energy communities, virtual simulator, LLM-assisted scenario authoring, multi-agent control, power system simulation, pricing regimes, verification*.

## 6. Items decided by the PM (2026-11-10) — applied to this draft; nothing open on my side

1. **RQ0 stays instrument-level** (call (a)): the paper states what the framework enables measuring; authoring-acceptance numbers are cited only after the in-envelope probe on the verified pipeline (≥14/16 bar + domains + rejections, per the rubric); no authoring claim in the abstract before that probe.
2. **Title is a proposal held for the user** (call (b)): the PM's wording is in §5 as a proposal, flagged upward; the platform-first subtitle with the service-awareness/grid-compliance clause is kept.
3. **The 750-run matrix is not the sole quantitative core** (call (c)): two cores today (strategy comparison frozen at 83/67/0; agent layer with the 5/9-vs-7/9 component and the dispatch-verification results), a third (authoring acceptance) after the probe; the results map in §3 is restructured to that order.

**Remaining hold (not mine to decide):** the title wording awaits the user's call — the PM's proposal stands until then.

## 7. Migration notes (mechanical, for the merge)

- All moved text is a re-order of existing `\section`/`\subsection` blocks in `arxiv_submission/arxiv_main.tex` plus the two new sections; the only new prose is §1's abstract sentence pair, §2's opening paragraph, and §3's two new sections.
- Every number in §1 is copied from the current abstract; the code-repair numbers in §3/§4 come from `docs/reviewer_response/code_repair_results.md` (converting-contract section) — no new runs, no re-statistics.
- The PDF rebuild path stays `/tmp/opencode/tectonic` with the author block verbatim; the no-arXiv-upload decision means the merge lands on main only.
