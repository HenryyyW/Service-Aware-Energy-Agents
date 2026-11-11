# MVP status baseline (Phase 0 record)

Owner: Project Partner · Updated: 2026-11-12 · Single source of truth for
"what is built / usable in the UI / research-verified". The product plan of
2026-11-11 is the roadmap; this file records where each of its phases stands
against the repo.

## Product plan → repo state

| Plan phase | Status | Evidence / gap |
|---|---|---|
| 0. MVP & status baseline | **This record** | brief + README aligned below; acceptance rules stated |
| 1. NL → ScenarioConfig wiring | **Backend done; UI gap** | The pipeline, corpus (16 items), scoring instruments and the rejection path are all on main and verified. `ScenarioGeneratorPage.tsx` still defaults to a MOCK generator and its confirm action creates (not starts) a scenario - the product gap the plan names. Frontend's wiring slice is the next buildable item (testable against the local backend; the model endpoint is in an outage). |
| 2. Simulation lifecycle | **Backend exists; UI partial** | The executor runs scenarios with progress/results; the UI start/track/cancel/error states are not yet wired as one flow. |
| 3. Virtual-community canvas | **Largely exists** | `CommunityCanvasPage` renders real run data with a TimePlayer; needs the front-door entry and honest loading/empty/failed states. |
| 4. Strategy comparison | **Shell exists; data gap** | The four-panel shell (slice 2) is built and spec'd; panels stay empty until one config is run through all four strategies (controller wiring) and dispatch-trace data exists. |
| 5. Agent diagnostics | Future | Analysis/diagnosis/candidate-fix proposals with verification gates. |
| 6. Productization | Future | A11y, error states, deployment posture. |

## P1 acceptance: the bar is met on the final code

No acceptance-rule change was needed. The weather domain (c07) is closed by
real work, not by re-wording: `BuildingConfig.weather_file` is wired into the
CityLearn adapter, a resolvable Singapore-class weather file exists
(`data/weather_files/singapore.csv`), the planner emits the canonical name on
BOTH the LLM and fallback paths, and the behavior is verified (the same schema
with the Singapore file loads 28.5 °C first outdoor temps vs the default's
17.8 °C). Per-item, all 16 corpus items now pass their five criteria.

**Pending:** one clean single-batch re-run. Two batches are
contamination-stamped by the model-endpoint outage: `probe_out_full16d` (5/16 -
the endpoint died mid-run) and `probe_out_full16e` (every item planned via the
deterministic fallback - the endpoint was down for all calls; scored 3/16,
which measures the FALLBACK's limits, not the agent's). A watchdog is armed
(`/tmp/opencode/endpoint_watchdog.sh`): it probes the LLM path every 5 minutes
and launches the clean batch automatically when the endpoint answers on the
LLM path. Useful side-evidence from full16e: c07 passes on the FALLBACK path
too, so the weather-domain closure is path-independent.

## Known limitations (carry into the paper and the UI)

1. **The Singapore weather file is a synthetic Singapore-class tropical
   profile, not measured data** (disclosed in `data/weather_files/README.md`).
   Measured data can replace it without pipeline changes.
2. **The model endpoint (NVIDIA NIM) had an outage** during the last batch;
   teammate messages and the LLM planner path are affected. The weather
   extraction is deterministic on the fallback path; other items need the
   endpoint for the agent measurement.
3. **The NL front door is a mock in the UI** until Frontend's wiring slice
   lands (the backend API is real).
4. **Dispatch trace shows "no record"** - no per-timestep trajectory data in
   the probe records yet.
5. **P3 (agent strategy modification) measures 5/9 vs the pre-registered 7/9**
   - reported either way; below threshold.
6. The 5 unattributed `wan2.7-image-pro` calls from the 2026-11-08 incident
   remain unexplained (recorded in `docs/incident_2026-11-08_dashscope_spend.md`).

## Remember (user's standing instruction, 2026-11-11)

The paper reframe runs in parallel with product work, but README, the brief
and the paper metadata stay synchronized - **paper completion is not product
completion.**
