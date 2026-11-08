# Reviewer response - SAEA paper revision plan (2026-11-08)

Source: reviewer critique `pasted-text.txt` (user-forwarded, against the rebuilt
`arxiv_submission/arxiv_main.pdf`). Verdict accepted: **not arXiv-ready as-is**;
this is an experiment-data-claims consistency job, not polish.

Each item below is marked:
- **[SRC]** = already confirmed against our own code/docs on origin/main (reviewer is right as far as we checked);
- **[VER]** = plausible, must be verified against source/raw data before we answer;
- **[EXP]** = needs new experiments/instrumentation (cost/authorization implications).

Grounding facts already confirmed (origin/main `7a93b4861b5e` unless noted):
- `src/controllers/llm_agent.py` header: "simulation adapter clamps values to device
  limits downstream"; "the unverified arm executes the clamped" values. So both arms
  end clamped -> proposal-level unsafe acceptance is NOT a physical-safety gain.
- `experiments/BENCHMARK_MATRIX.md`: main matrix is 5 scenarios x 5 controllers x 10
  seeds = **250 runs**; A/B/C/E therefore = 200, not 160. `centralized` is documented
  there as "**not** an optimizer" (the paper calls it an optimizer - claim error).
- No accounting-invariant test (sum of member net bills = external grid bill +
  explicit fees - subsidies) exists in `tests/` today.

## A. Positioning: what the experiments actually show [SRC]

Reviewer point 1 (the critical one): §2.3 promises code repair (planner/coder/
executor/verifier with AST patches); §4.7/§5.3 measure runtime action verification
(JSON dispatch, bounds check, re-prompt, deterministic replacement). Our own
`Coder._apply_changes` never emitted behavior-changing patches until the
in-flight layer-23 fix - i.e. the paper's code-repair claim currently has no
successful experiment behind it, exactly as the reviewer infers.

- **A1 [EXP] Real code-repair benchmark is the honest fix for the claim**: broken
  controller + failing tests + real diff + before/after full simulation + functional
  regression tests. Depends on the coder fix (issue #59 / branch
  `fix/coder-ast-transformations`) landing first. Scope: ~5-10 seeded repair tasks
  on the rule-based/grid controllers; success = violations resolved by the patched
  code with held-harmless criteria; report as a pilot with the same caveat style as
  M2b. **Requires written authorization if any LLM calls (model/provider/count/
  purpose) - ask user.**
- **A2 [paper] Re-scope the abstract/intro/conclusion** to what is measured until A1
  exists: runtime verification of LLM dispatch proposals + a scaffolded (not yet
  demonstrated) code-repair pipeline described as such.

## B. Price-insensitivity logic and billing identity [SRC + VER]

Reviewer point 2: "dispatch unchanged -> cost unchanged" is invalid (cost is a
function of prices even on a fixed trajectory); Table 4(Scenario D) itself shows cost
changes under unchanged dispatch, contradicting the general explanation; "LMP" needs
a definition (external price series vs nodal duals).

- **B1 [VER] Billing engine check (Backend B)**: does the reported cost metric price
  the same trajectory under TOU and LMP series? Run the identical trajectory under
  both price series; if costs are bit-identical, prove why (same series? billing uses
  TOU only?); if not, fix the paper's claim. Deliverable: one-page evidence memo +
  a regression test that prices a fixed trajectory.
- **B2 [paper] Distinguish dispatch sensitivity from billing sensitivity** in §4.2;
  state LMP's construction (it is an external price series in our builds, not a
  network-dual LMP) or rename.

## C. Scenario D settlement accounting [SRC gap]

Reviewer point 3: internal P2P payments must cancel in the community aggregate; a
second settlement layer cannot by itself change community cost; the "correct
post-fix behaviour" claim is unproven and reads like double counting.

- **C1 [EXP] Accounting invariant test (Backend B)**: per run, assert
  `sum(member net bills) == external grid bill + explicit external fees - explicit
  subsidies`. If it fails, D's aggregate cost change is a settlement bug, not a
  feature - fix the engine, then re-run D rows.
- **C2 [paper]** Until C1 passes, the paper must state the mechanism for D's
  aggregate change explicitly (fees?计量边界? rule) or mark it as an open defect.
  No "correct post-fix behaviour" language without the invariant holding.

## D. Multi-agent service fairness [SRC]

Reviewer point 4: multi_agent's cost advantage comes with EV completion 0.057 (5.7%)
while MPC delivers 1.000 at higher cost; abstract/conclusion still lead with
"cost- and peak-minimal".

- **D1 [paper] Comparability rewrite**: report cost at equal service (same EV
  completion threshold), or mark sub-threshold controllers infeasible, or add
  unmet-EV-energy; state per-controller objective/constraints/observations in a
  table (we have the source of truth in BENCHMARK_MATRIX.md - centralized is NOT an
  optimizer; fix §2.2 accordingly).
- **D2 [VER]** The defect behind 0.057 is already disclosed; keep the disclosure,
  add the infeasibility marking so the cost number cannot be read as an advantage.

## E. Safety claims stratification [SRC]

Reviewer point 5: both arms are clamped downstream; we prove interception layer
differences, not physical safety gains; missing deterministic-baseline comparison.

- **E1 [VER] Build the 5-level table from existing telemetry (Research + QA)**:
  (1) raw proposal bound violations, (2) accepted by agent layer, (3) adapter
  interventions/clamps, (4) final applied-action violations, (5) post-execution grid
  and service violations - per arm per cell, from the run logs we already have.
- **E2 [EXP] Deterministic baseline arm (no LLM)**: bounds-check + projection with
  no re-prompt, to show whether the LLM verification layer adds value over a simple
  deterministic safety layer. No LLM calls needed (pure code path) - cheap.
- **E3 [paper]** Re-title the claim to proposal-layer verification until E1/E2 exist;
  keep the honest null where it belongs.

## F. Direct numeric/count errors [SRC mostly]

- **F1** Abstract cost-delta range omits D (-78.56, settlement-inclusive): either
  include D with its basis label or state the exclusion explicitly. [paper]
- **F2** Abstract says "unrepaired violations zero in both arms" vs Table 6's
  0.0200 unverified / 0.0000 verified: direct contradiction; fix to the table.
- **F3** Percentage-point units (2.0/0.17 pp vs 0.02/0.0017) undefined event vs
  proportion: define run-level event rate or step-level rate, use one unit.
- **F4** "5x2x10 = 150-cell screen" arithmetic: it is 100 LLM cells + 50 reference
  cells; §2.3 must match §3.
- **F5** A/B/C/E paired runs: 200 (4x5x10), not 160 (§4.3) - BENCHMARK_MATRIX.md says
  total 250 with 5 controllers; identify whether any controller was excluded and say so.
- **F6** Scenario E "50 runs per controller": main matrix is 10 per regime per
  controller (30 across three regimes); if 50 comes from the stress matrix, label it
  as a separate matrix; also include RL or state its absence.
- **F7** Table 7 detection/recovery rows suspiciously identical (18/360 fallback,
  442.62 both epochs): rebuild from raw run logs, not prose. "Two 30-cell pilots"
  framing must make the epoch difference explicit (detection epoch's fav/fallback
  semantics differ from recovery's).

## G. Dataset/scenario description conflicts [VER]

- **G1** §4.9 "stock dataset fixes load/PV across seeds" vs §5.2 "profiles depend
  only on (seed, filename)": state which data the final results use; list dataset
  name/version, buildings/dates/step, original-vs-synthetic fields, what a seed
  changes, what only the controller changes.
- **G2** "LP degeneracy" attribution for MPC cost variance has no evidence chain:
  either show same-input-different-solve evidence + solver settings, or drop the
  label and report variance unexplained.
- **G3** Table 1: A = "no DERs" but A's EV completion is a headline result; D =
  "thermal comfort stress" but comfort is unmeasurable (all-NaN indoor temp).
  Either rename D to the settlement scenario or add real comfort instrumentation;
  fix A's asset list definition (EV inside/outside "DER").

## Sequencing and dependencies

1. C1 (accounting invariant) and B1 (billing identity) are **blocking correctness
   questions** - answers may invalidate numbers already in the paper; they go first
   (Backend B).
2. E1/E2 (safety stratification + deterministic baseline) go in parallel; E2 is cheap
   and strengthens the paper without new LLM authorization.
3. A1 (real code-repair benchmark) depends on the coder fix landing; scope decision
   is the user's (authorization + effort).
4. Paper edits (A2, B2, D1, E3, F1-F7, G1-G3) land after 1-3 settle, in one rebuild.

## Decisions the user owns

- D-A: re-scope now to runtime verification (cheap, honest) vs also commit to the
  code-repair benchmark (needs coder fix + LLM authorization).
- D-B: if Scenario D's aggregate change survives C1 as a real mechanism, keep D
  labelled settlement-inclusive; if it is a bug, D rows come out of the headline
  tables until fixed.
- D-C: arXiv timing - publish the re-scoped version now, or hold until A1/E2 exist.

## Decisions (user, 2026-11-08)

- **D-A = re-scope AND build the benchmark.** The paper is re-scoped to what the
  experiments measure (runtime verification of LLM dispatch proposals; code-repair
  pipeline described as scaffolded/not-yet-demonstrated), AND a real code-repair
  benchmark is commissioned as the evidence for the code-repair claim.
  Benchmark envelope (authorized scope): model `poolside/laguna-xs-2.1`, provider
  NVIDIA NIM, purpose = code-repair benchmark for the paper, count <= 10 seeded
  repair tasks x <= 3 iterations each; same hostile-flag discipline and keep rule as
  M2b; single matrix directory `experiments/m2b_code_repair/`. No other model, no
  other provider. Gated on the coder fix (issue #59) landing first.
- **D-B = decide by the accounting invariant.** If C1 (Backend B) shows the
  settlement invariant holds, D's aggregate change keeps its settlement-inclusive
  label with the mechanism stated; if it fails, D rows come out of the headline
  tables until the engine is fixed and D is re-run.
- **D-C = no arXiv upload.** No submission action is taken; the rebuild lands on
  main only. (No scheduled upload, no deadline-driven shortcut.)

## H. Dev-log register (reviewer's added point, 2026-11-09)

Rule the user endorsed: the body reads research question -> method -> experimental
design -> results -> interpretation; GitHub docs and one Reproducibility section
carry install/run/reproduce detail. Open-source and reproducibility info STAYS -
only the process narration moves out. Line inventory against origin/main
`b732dbd3b6` tex (verified by grep, no false positives counted):

- L413 `P0-3 fix` - internal defect-tracking language; delete the label, state the
  final method property only (both arms share one clamp-repair path).
- L87 + L494 `user-approved re-run` - ops language; replace with "a confirmation
  re-run of three cells" (or fold into the keep-rule note).
- Re-run narration ~15 lines (L63, L88, L158-160, L235, L288-292, L300, L317, L365,
  L427, L429, L494, L518-519, L545, L651): keep ONE validity-threat statement
  (defect found, fixed, rows re-run, D rows settlement-inclusive) + the D basis
  labels on tables; delete the retelling elsewhere.
- `post-fix` x4 (L235, L300, L317, L365) -> "final" / "re-run" basis wording.
- Quarantine detail x8: body keeps the keep rule + counts (13/2); per-cell error
  counts move to the appendix.
- manifest/SHA-256: L66-67 and L617 already form a reproducibility sentence pair;
  consolidate ALL manifest field lists into the Reproducibility section (L143 and
  L427-430 fold in).
- ALREADY CLEAN (reviewer's general impression overcounts): API paths 0, Python
  filenames 0, Redis 0 (the single "Redis" grep hit is the word "Redistributes" in
  a subsection title), docker/RQ 0.
- ALSO STILL UNFIXED from F4: L427 still reads "5 scenarios x 2 LLM arms x 10" as
  the 150-cell screen - the arithmetic error QA flagged is still in the tex.
