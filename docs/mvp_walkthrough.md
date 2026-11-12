# MVP acceptance walkthrough (Definition of Success)

Project Partner, 2026-11-12. For a person who did not build the system: walk
the closed loop **without editing code**. Record every step where you needed
code, a workaround, or where a number appeared that you cannot trace to a run.

Current main: `a619917e6`. This script reflects QA's verified smoke
(`docs/qa/phase6_regression_report.md`) plus the landed canvas/table/a11y and
responsive slices.

## Start (two terminals)

```bash
# terminal 1 - backend (port 8001)
cd backend && uvicorn app.main:app --reload --port 8001

# terminal 2 - frontend (http://127.0.0.1:3000)
npm --prefix frontend run dev
```

LLM note: the NL step runs the real planner when the NIM environment is set
(`AGENT_BACKEND=api:poolside/laguna-xs-2.1` + endpoint + key). With no
environment variables it falls back deterministically in ~0.03 s
(`plan_source=rule_based_fallback`). Both are valid; just record which one you
saw - the UI shows the plan source.

## Steps and expected results

1. **Describe a community** - open `http://127.0.0.1:3000/scenarios/generate`.
   Type a small community in plain language (e.g. "a 4-building neighborhood
   with rooftop PV, one shared battery, and two EVs"). Press generate.
   *Expected:* a config preview; rejected/defaulted fields are listed by name;
   the plan source is shown. `success=False` with rejected fields is NOT a
   failure - it is what the confirm step exists for.
2. **Review and confirm** - inspect the summary, field sources and validation
   errors. Fix or accept; confirm.
   *Expected:* the scenario is saved and you land on its detail page
   (`/scenarios/<id>`).
3. **Validate + run** - on the detail page, validate (expect `valid`), then
   start a 24-step run (seed 42 is what QA used).
   *Expected:* lifecycle states progress (pending -> running -> completed,
   ~3 s for a small community); a failure shows the reason and a next step,
   never a blank screen or a fake success. Cancel is available mid-run.
4. **Community canvas** - open `/canvas` (nav entry added) and pick your run.
   *Expected:* buildings, assets, grid flows; the schematic banner
   ("Schematic network layout - not actual geographic data") is visible;
   time playback/scrub updates asset and grid state; the map/table toggle
   works by keyboard and shows the same numbers; loading, empty and failure
   each have an explicit state.
5. **Strategy comparison** - open `/comparison/strategy/<scenario_id>`.
   *Expected:* four strategies (rule_based, MPC, single-agent RL, multi-agent
   RL) with ACTUAL run records and real grid metrics; economics is real and
   strategy-differentiated (e.g. MPC vs multi-agent RL differ in cost, import,
   carbon, peak). **Two known flags (recorded, Backend B owns both):**
   `battery_throughput_kwh` still reads 0.0 - the comparison path's environment
   never updates storage state of charge even though dispatch actions are
   applied; and `single_agent_rl` currently returns byte-identical results to
   `rule_based` because the comparison endpoint silently substitutes the
   rule-based arm when no RL policy is loaded. Both are shown as the system
   computes them - no substitution on your side. If you see a value that is
   neither a real record nor a labeled gap, that is a fail.
6. **Diagnosis** - from the run, open diagnostics.
   *Expected:* findings with evidence and next steps, or an explicit
   "no violations recorded" reading - not an empty panel.
7. **Report** - open `/runs/<run_id>/report` and download it.
   *Expected:* the report contains the scenario configuration, seed, run
   identifiers and the evidence you just saw on screen.
8. **Keyboard + screen reader** - repeat step 4 using Tab/arrows only and the
   table view.
   *Expected:* every control reachable and labeled; violations readable as
   text.

## Pass / fail rules

- **Pass:** all eight steps with no code edits, no untraceable numbers, and
  every empty/loading/failure state explicit.
- **Fail:** any step that required editing code, any silent zero/empty that
  pretends to be data, or any number on screen you cannot trace to a run.

## Known honest flags (not failures)

| Flag | Status |
|---|---|
| F1 economics placeholders (0.0) | closed at `555d28bf7` - economics real |
| battery_throughput_kwh 0.0 in the comparison path | open - Backend B (SOC bookkeeping) |
| single_agent_rl == rule_based (silent substitution) | open - Backend B (label or fix) |
| LLM fallback when NIM env is unset | by design, deterministic |
| Schematic layout is not geographic data | disclosed on the canvas |
| Strategy modification measures 5/9 vs the 7/9 pre-registered bar | recorded, below threshold |
| Research demo vs production deployment (access control, persistence, isolation, monitoring, secrets, multi-user) | `docs/deployment_posture.md` |
