# Verified-vs-unverified LLM agent ablation design (Phase 2)

This slots the ablation directly into the benchmark matrix so the re-run after
`feature/scenario-aware-schemas` merges produces both the main matrix (5
scenarios x 5 controllers x 5 seeds = 125 runs) and the ablation (below) in one
supervised pass.

## 1. Variants

| Label | Implementation | Meaning |
|---|---|---|
| `multi_agent` | existing scaffold | Deterministic planner/coder/executor/verifier fallbacks, no LLM calls. Baseline for the ablation. |
| `llm_agent` | `src/controllers/llm_agent.py::LLMAgentController` (implemented) | LLM produces each dispatch decision in one shot (no execution check); actions applied as-is if they parse, else deterministic fallback for that step. Records repair_iterations = 0 by construction. |
| `llm_agent_verified` | `src/controllers/llm_agent.py::LLMVerifiedController` (implemented) | Same LLM decision path, plus per-step verification (shape + device power bounds from live metadata) with deterministic repair, budget 2 repairs per step, then deterministic fallback. Run-level before/after checks stay with `src/evaluation/verification_harness.py`. |

Both variants run without an LLM backend (labelled `agent_backend: "fallback"`,
recorded in `result.json` and `manifest.json` together with the prompt hash,
prompt version, sampling temperature and sampling seed — see
`tests/test_llm_controllers.py`), so the 50 ablation runs can execute and be
packaged before real LLM credentials are wired.

Interface: both LLM controllers emit the same `Action(value_kw, asset_id)`
contract as every other controller, so the adapter, metrics, and runner are
unchanged. `llm_agent` / `llm_agent_verified` are already declared in
`src/schemas/report.py`.

## 2. Ablation matrix

- Scenarios: A-E (same configs as the main matrix).
- Seeds: 42, 123, 456, 789, 999 (same list; paired with the `multi_agent` runs
  of the same scenario/seed for deltas).
- Runs: 2 variants x 5 scenarios x 5 seeds = **50 additional runs**.
- Statistical protocol: identical to `experiments/BENCHMARK_MATRIX.md` section
  4 (Student-t CIs, paired deltas, Holm within scenario x metric family).

## 3. Metrics

Grid/service/cost KPIs as in the main matrix, plus the agent-execution group
already defined in the evaluation code:

- task success rate and simulation success,
- first-attempt action validity (share of steps needing no repair),
- repair iterations per step (verified variant) / 0 (unverified),
- verification-failure categories (action-shape, bound violation, service
  infeasibility, power-flow risk),
- per-step and per-run agent wall time, and (when an LLM backend is used) token
  counts and estimated cost per run.

## 4. Reproducibility and fallback policy (hard requirements)

1. **No-network runs must still complete.** If no LLM backend is configured,
   both variants run in deterministic-fallback mode and every run is labelled
   `agent_backend: "fallback"` in `result.json` + `manifest.json`. Fallback
   numbers are reported as a separate column in the ablation table and are
   never mixed with LLM-backend numbers.
2. **Seeding.** LLM sampling temperature is fixed and the sampling seed is
   recorded per run; prompts are versioned (prompt hash in the manifest) so an
   LLM-backend rerun is traceable even if the provider is not bit-reproducible.
   In fallback mode (no LLM backend) the sampling seed defaults to the run's
   scenario seed (`LLMAgentController.__init__`), so `sampling_seed ==
   random_seed` in every manifest; there is no independent RNG stream to look
   for, and the deterministic fallback path consumes no sampling randomness.
3. **Failure handling.** A step whose LLM output is unparseable counts as a
   first-attempt failure, applies the deterministic fallback for that step, and
   continues; the run only fails on simulation errors like any other run.
4. **No generated trajectories in git** (artifact hygiene): policies/trajectories
   publish via `scripts/package_results.py` zips as with the main matrix.

## 5. Paper claims this supports

- Verified vs unverified: does the repair loop buy service-level compliance
  (EV deadlines, flex deadlines, grid feasibility) cheaply enough?
- Unverified vs deterministic baseline: does the LLM add anything over the
  scaffold once actions are constrained to the same interface?
- Cost-of-verification: repair iterations and wall time vs. KPI improvement.
