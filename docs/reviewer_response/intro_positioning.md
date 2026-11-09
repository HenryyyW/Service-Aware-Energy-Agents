# Introduction / positioning rewrite (user critique, 2026-11-09)

Source: the user's critique of the Introduction (forwarded by the Project
Partner): the three "gaps" read as a feature list rather than
literature-established research gaps. This doc is the positioning argument; the
rebuilt section in `arxiv_submission/arxiv_main.tex` is the paper-facing
version of the same text.

## The single positioning statement (replaces the duplicated gap text on pages 1-2)

Renewable-energy-community control couples three things that prior work treats
separately: physical grid constraints, service-level commitments, and the
market mechanism that prices energy. Existing studies optimise within one fixed
setting — one tariff, one device mix, one assumption that controllers execute
what they compute. Three research questions follow, each established by a
distinct literature, and this paper answers the parts of them our experiments
actually support.

## Gap 1 — Pricing-regime diversity

**Established by the literature.** Community-control benchmarks and datasets fix
a single price-formation mechanism: the CityLearn challenge series ships
time-of-use tariffs; ElecBench scores power-dispatch knowledge under fixed
assumptions \cite{zhou2025elecbench}; PowerAgentBench-SS scores tool-using
agents on steady-state studies \cite{mylonas2026poweragentbench}; distributed
MPC and dual-decomposition formulations \cite{yfantis2024dual, su2021dual}
assume a given price signal as input. Agentic energy work \cite{jonah2026agentic,
elmakroum2026agentic} optimises schedules against dynamic tariffs but does not
vary the price-formation mechanism itself.

**What is unresolved.** Whether a controller's *dispatch* and the *billed cost*
respond differently when the mechanism changes (TOU → LMP → bilateral P2P).
Prior comparisons that price one fixed trajectory under two series cannot
separate the two responses, and "dispatch identical ⇒ cost identical" is a
category error: cost is a function of prices on any fixed trajectory.

**What this paper produces (demonstrated).** A 750-run matrix (5 scenarios × 5
controllers × 10 seeds × 3 regimes) plus a 150-run scenario-D re-run, and the
separation itself: only the price-aware controllers (MPC, RL) change dispatch
across regimes; the price-insensitive heuristics dispatch identically; the LMP
series reaches the bills only where settlement and dynamic pricing are active
(scenario D), so A/B/C/E costs are regime-invariant in these builds while D's
move; and P2P clearing redistributes member bills while the A/B/C/E community
aggregate is bit-identical to pool clearing. The new finding is the
dispatch/billing separation and the mechanism account of which regime reaches
the bills — not a TOU-vs-LMP cost comparison.

## Gap 2 — Failure injection

**Established by the literature.** Failure injection is standard practice in
power-systems and building-simulation benchmarks; CityLearn-based studies
inject component faults routinely. Injection, however, measures the scenario,
not the agent.

**What is unresolved (the actual research question).** The four-step chain a
controller must complete when a failure occurs: (i) identify the failure type,
(ii) localise the affected controller, (iii) produce an effective repair,
(iv) maintain grid constraints and participant service after the repair.
No benchmark in this literature reports the chain; agentic energy work reports
scheduling quality, not repair under faults.

**What this paper answers — and what it does not.** Scenario E injects PV
inverter, battery, EV-charger and sensor failures at severity 1.0 plus a
grid-service limit reduction, in 150 runs across all three regime legs.
(i) Identification at the grid level: **none** — power flow converges in every
step of all 150 runs with zero voltage/line/transformer violations and zero
re-dispatches, so no controller can observe the failures; detection is
configuration-oracle only. (ii) Localisation: oracle-side only, by construction
of the injection. (iii) Repair: **not demonstrated** — the commissioned
code-repair benchmark measured 0/9 seeded defects repaired with the current
pipeline (Section on the code-repair benchmark), so the workflow is reported as
scaffolded, not demonstrated. (iv) Maintain: trivially satisfied because no
injected failure produced a violation in these runs. We claim no detection and
no recovery for any failure type.

## Gap 3 — Verified LLM code agents (the paper's contribution)

**Why general LLM code generation is insufficient here.** Control code is
executable: an emitted "change" that does not change behaviour is not a repair.
Without an executable check, the failure mode is silent — our own instrumented
Coder produced comment-level patches until an AST-transformation layer was
restored, and the ten-task code-repair benchmark measured **0/9 measured
repairs** with a hosted model in the loop, because the model emitted change
*descriptions* while the edit was applied by a fixed transformation vocabulary.
Verification is not an add-on to code generation in this domain; it is the
measurement that separates a repair from a description.

**What existing code-agent verification lacks.** Adjacent layers are covered:
solver-grounded reporting — a numerical result is reported only from a trusted
tool and passes verification \cite{rojas2026smartgridllm}; intent-driven
workflows that separate LLM planning from solver-side execution with
state-dependent gates \cite{mao2026intent}; runtime verification that
intercepts proposed *actions* against derived specifications
\cite{batole2026refineact}. None of these measures whether agent-generated
*code* changes behaviour, and none prices the verification layer itself against
a deterministic alternative.

**Why five specialised agents rather than one agent plus a deterministic
verifier.** The loop separates diagnosis (Planner: analyse the violation set,
target functions, define success criteria), generation (Coder), execution
(Executor: run the patched controller in a sandbox with the real test suite and
a quick simulation), checking (Verifier: violation resolution against
held-harmless service criteria), and reporting (Reporter: machine-readable
per-iteration audit). A single agent plus a deterministic verifier collapses
the first two stages into the unchecked part; the decomposition is what puts a
deterministic checkpoint at every boundary and makes each stage's output
independently auditable — the property our measurements exploit.

**What the workflow offers, measured.** The verification machinery is a no-op
under an in-bounds proposer (the M2a real-LLM screen: a safety-metrics null
reported as such), and it engages fully under a deliberately out-of-bounds
proposer (the M2b hostile-proposer study: the verified arm accepted zero
out-of-bounds proposals in every kept cell; 13/13 paired directional wins,
exact sign test p = 2.4×10⁻⁴, reference-only). That is runtime proposal
verification measured against ground truth — the first such measurement in this
setting — and it is the contribution the Introduction now argues.

## Claim discipline (unchanged, restated for the rewrite)

The abstract keeps only demonstrated claims. The code-repair pipeline stays
"scaffolded, not yet demonstrated" until a re-run under the rearmed benchmark
says otherwise; the failure-injection section reports oracle-only detection and
no recovery; the safety claim is proposal-layer (both arms share the adapter
clamp).
