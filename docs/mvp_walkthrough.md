# MVP acceptance walkthrough (Definition of Success)

Project Partner, 2026-11-13 (v2 - rewritten to the fixed state). For a person
who did not build the system: walk the closed loop **without editing code**.
Current main: `5f30a4626`, CI green. All nine defects found in the first
walkthrough (W1-W9, `docs/mvp_status_baseline.md`) are fixed and verified;
this script reflects the fixed behavior.

## Start (two terminals)

**Run the backend FROM THE REPO ROOT** - starting inside `backend/` breaks
package resolution:

```bash
# terminal 1 - backend (port 8001), from the repo root
python -m uvicorn backend.app.main:app --reload --port 8001

# terminal 2 - frontend (http://127.0.0.1:3000)
npm --prefix frontend run dev
```

- **Windows PowerShell:** `npm` resolves to `npm.ps1`, which execution policy
  may block - use `npm.cmd --prefix frontend run dev` instead.
- **Windows:** set `PYTHONUTF8=1` before starting the backend (scenario
  generate writes UTF-8 artifacts; without it the generate step can raise
  encoding errors).
- The frontend dev proxy defaults to `http://127.0.0.1:8001` (override with
  `VITE_API_PROXY_TARGET`; the documented client env names are
  `VITE_API_BASE_URL` / `VITE_WS_BASE_URL`).

LLM note: the NL step runs the real planner when the NIM environment is set
(`AGENT_BACKEND=api:poolside/laguna-xs-2.1` + endpoint + key). With no
environment variables it falls back deterministically in ~0.03 s
(`plan_source=rule_based_fallback`). Both are valid; record which one you
saw - the UI shows the plan source.

## Steps and expected results

1. **Describe a community** - open `http://127.0.0.1:3000/scenarios/generate`.
   Type a small community in plain language (e.g. "a 4-building neighborhood
   with rooftop PV, one shared battery, and two EVs"). Press generate.
   *Expected (W1 fixed):* the page renders and stays responsive - no blank
   page, no console infinite-loop error. A config preview appears with
   provenance chips (given/assumed/default/missing, glyph + text) and any
   rejected/defaulted fields listed by name. `success=False` with rejected
   fields is NOT a failure - it is what the confirm step exists for.
2. **Review and confirm** - inspect the summary, field sources and validation
   errors. Fix or accept; confirm.
   *Expected (W3 fixed):* the scenario is saved and you land on its detail
   page. The fallback (no-LLM) path now produces a complete config (EV
   arrival/departure filled); an invalid config returns a named 422 error
   naming the field - never a 500.
3. **Validate + run** - on the detail page, validate (expect `valid`), then
   start a 24-step run (seed 42 is what QA used).
   *Expected:* lifecycle states progress (pending -> running -> completed,
   seconds for a small community); a failure shows the reason and a next
   step, never a blank screen or a fake success; cancel works mid-run.
4. **Community canvas** - open `/canvas` (nav entry) or follow the run's
   link, and pick your run.
   *Expected (W2/W4 fixed):* your run appears even if it was created through
   the API (run-based data path: `getRuns` -> `run.scenario_id` ->
   trajectories) - "No community data" only when zero runs exist. Buildings,
   assets, grid flows and violations render; the schematic banner
   ("not actual geographic data") is visible; time playback/scrub updates
   asset and grid state; trajectory timestamps follow the effective
   (dataset-native) timestep shown on the config; the map/table toggle works
   by keyboard and shows the same numbers; loading, empty and failure each
   have an explicit state.
5. **Strategy comparison** - open `/comparison/strategy/<scenario_id>`.
   *Expected (W7 fixed):* four strategies (rule_based, MPC, single-agent RL,
   multi-agent RL) with ACTUAL run records, real grid metrics, and real
   economics (cost/import/carbon/peak differ across strategies). Where a
   controller silently fell back to rule_based (no policy loaded), the panel
   shows steps + reason (e.g. `24 steps / fallback_to_rule_based`); with no
   fallback it shows "no record" - never a fabricated difference.
   *Known flags (recorded, not failures):* with no RL policies loaded, the
   single-agent RL arm's labeled fallback is honest degradation; battery
   throughput is real for all four arms; PV self-consumption is a computed
   fallback value when per-building contributions are unavailable - flag if
   a number looks like 100% from empty data.
6. **Diagnosis** - from the run, open diagnostics.
   *Expected:* findings with evidence and next steps, or an explicit
   "no violations recorded" reading - not an empty panel.
7. **Report** - open `/runs/<run_id>/report` and download it.
   *Expected (W6/W9 fixed):* the download works (button disabled while
   downloading) and the report contains the scenario configuration
   (requested vs effective timestep, buildings with devices, community
   limits, energy sharing, grid network) plus run id, seed, controller and
   the evidence you just saw on screen.
8. **Keyboard + screen reader** - repeat step 4 using Tab/arrows only and the
   table view.
   *Expected:* every control reachable and labeled; violations readable as
   text.

## Pass / fail rules

- **Pass:** all eight steps with no code edits, no untraceable numbers, and
  every empty/loading/failure state explicit.
- **Fail:** any step that required editing code, any silent zero/empty that
  pretends to be data, or any number on screen you cannot trace to a run.

## Known flags (recorded, not failures)

| Flag | Status |
|---|---|
| Generator page blank / React infinite loop | fixed (`e92710b30`) |
| Canvas "No community data" despite real runs | fixed (`9cfcfb6e4`, run-based path) |
| Fallback config 500 on missing EV times | fixed (named 422, `37219e6cf`) |
| Timeline: 15-min config overridden by dataset, repeated timestamps | fixed (`37219e6cf`, effective timestep) |
| PV self-consumption 100% from empty data | fixed (formula, ~49.9% real case) |
| Report missing scenario configuration | fixed (`37219e6cf`) |
| Silent strategy substitution | fixed and labeled (API + UI, QA live-verified) |
| Windows startup traps | fixed (repo-root uvicorn, `npm.cmd`, `PYTHONUTF8`, proxy default) |
| Research demo vs production deployment | `docs/deployment_posture.md` (out of scope: access control, persistence, isolation, monitoring, secrets, multi-user) |
