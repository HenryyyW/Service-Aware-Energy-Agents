# MVP status baseline (Phase 0 record)

Owner: Project Partner · Updated: 2026-11-12 (evening, main @ `e943c1d9c`) ·
Single source of truth for "what is built / usable in the UI /
research-verified". The product plan of 2026-11-11 is the roadmap; this file
records where each of its phases stands against the repo. Earlier in the day
this record lagged the repo by five commits (phase 2/4/5/6 landed after it);
this refresh closes that gap.

## Product plan → repo state

| Plan phase | Status | Evidence / gap |
|---|---|---|
| 0. MVP & status baseline | **This record** | README L42/L270 + brief P1 synced at `04d1a2ffb` (PM, docs-only, verified); acceptance bar MET on `probe_out_full16f` (14/16 full-bar, all 8 domains, 4/4 rejection; c09 C3 recorded as measured) |
| 1. NL → ScenarioConfig wiring | **Landed** (`edea241e5`) | The generator page's default path calls the real `api.generateScenario`; the mock generator survives only via the injected prop (tests/previews). Confirm still creates the scenario and hands to the detail page, which starts the run - a UX seam, not a blocker. |
| 2. Simulation lifecycle | **Landed** (`550a1dd96`) | `ScenarioDetailPage` validates, starts, polls, cancels and shows the reason + next step on failure; results link onward to diagnostics and reports. |
| 3. Virtual-community canvas | **Landed** (`68072ec96`) | `CommunityCanvasPage` is routed (`/canvas`, nav entry added): map/table toggle on the same run data, schematic-coordinate banner ("not actual geographic data"), honest loading/empty/failure states, keyboard + aria labels. Gates verified by Project Partner: `tsc --noEmit` clean, `eslint --max-warnings 0` clean, `npm run build` success, `vitest` 7/7. Responsive breakpoints and the MVP walkthrough remain open (QA). |
| 4. Strategy comparison | **Landed** (`54a8c4255`; verified `0eeaaa398`) | One config runs through the four strategies of record; the comparison view reads real runs via `api.startStrategyComparison`/`getSimulationRun`; missing metrics show "no record" instead of zero. QA smoke: 200 with four real records (mpc / multi_agent_rl / rule_based / single_agent_rl), real pandapower grid metrics. **Acceptance blocker F1**: `energy_metrics` comes back all 0.0 (cost/import/PV/battery/carbon/peak) - shown as recorded and flagged as placeholders (owner: Backend B). |
| 5. Agent diagnostics | **Landed** (`f260f6412`, `7068d4dc2`) | Read-only diagnosis (breaches located with evidence, interpreted, next steps) and fix proposals behind an approval gate with before/after re-run verification. Honest sub-threshold statement: strategy modification measures **5/9 vs the pre-registered 7/9**. |
| 6. Productization | **Regression landed** (`e943c1d9c`, `68072ec96`, `0eeaaa398`) | Preview pages state their mode; `docs/deployment_posture.md` separates research demo from production; canvas a11y landed. QA's Phase 6 report (`docs/qa/phase6_regression_report.md`, merged as PR #64): pytest 518/518, black/ruff/tsc/eslint/build green, closed loop functional end-to-end with the live LLM planner (generate 13.5s → confirm 201 → run completed → 4-strategy comparison → diagnostics 200). Performance: ~190 KB gz initial load, no route-level code splitting (Lighthouse not run - needs served build). Remaining: **F1/F2 fixes** (below), responsive breakpoints, the MVP walkthrough. |

## P1 acceptance: the bar is met on the final code

No acceptance-rule change was needed. The weather domain (c07) is closed by
real work, not by re-wording: `BuildingConfig.weather_file` is wired into the
CityLearn adapter, a resolvable Singapore-class weather file exists
(`data/weather_files/singapore.csv`), the planner emits the canonical name on
BOTH the LLM and fallback paths, and the behavior is verified (the same schema
with the Singapore file loads 28.5 °C first outdoor temps vs the default's
17.8 °C). Per-item, all 16 corpus items now pass their five criteria.

**MET on the final code (2026-11-12, endpoint recovered):** the clean batch
`probe_out_full16f` (endpoint-healthy, LLM path throughout) scores
**14/16 items full-bar, ALL 8 domains (the weather domain covered), 4/4
rejection items - r03 fell back in that batch and its adjacent LLM-path re-run
(`probe_out_r03fix`, ALL 5 criteria pass, SOC bounds named) supplies the fourth
rejection; quoted per-item, not stitched.** The one item-level failure inside
the batch is c09's C3 (the LLM emitted the self-consistent 2 kW x 6 h = 12 kWh
triple vs the stated 6 kWh - the residual variance the stated-energy prompt
rule reduces but does not eliminate). Two earlier batches are
contamination-stamped by the model-endpoint outage and are NOT agent
measurements: `probe_out_full16d` (5/16, endpoint died mid-run) and
`probe_out_full16e` (3/16, every item on the fallback path).

## Known limitations (carry into the paper and the UI)

1. **The Singapore weather file is a synthetic Singapore-class tropical
   profile, not measured data** (disclosed in `data/weather_files/README.md`).
   Measured data can replace it without pipeline changes.
2. **The model endpoint (NVIDIA NIM) had an outage** during the last batch;
   teammate messages and the LLM planner path are affected. The weather
   extraction is deterministic on the fallback path; other items need the
   endpoint for the agent measurement.
3. ~~**The NL front door is a mock in the UI**~~ - **closed** at `edea241e5`
   (11-11 22:55): the default path is the real backend call. The two-page seam
   (confirm on the generator, run on the detail page) is a product decision,
   not a defect.
4. **Dispatch-trace depth**: "no record" is now the convention across the
   comparison and detail views; per-timestep trajectory records for the four
   strategies are unverified end-to-end (QA smoke in flight).
5. **P3 (agent strategy modification) measures 5/9 vs the pre-registered 7/9**
   - reported either way; below threshold.
6. The 5 unattributed `wan2.7-image-pro` calls from the 2026-11-08 incident
   remain unexplained (recorded in `docs/incident_2026-11-08_dashscope_spend.md`).

## Open defects (QA's Phase 6 report, owners notified by QA - Partner has not
## re-verified the notifications)

- **F1 - economics placeholders (Backend B):** `energy_metrics` returns all
  0.0 for every strategy (cost, grid import, PV, battery, carbon, peak). The
  energy/KPI accounting does not reach the comparison-path API payload; values
  are shown as recorded and flagged, never substituted. Blocks the plan's
  "auditable economics" acceptance for phase 4.
- **F2 - trajectories serializer (Backend A/B):** ~~CLOSED at `2bf540951`~~
  (PR #65, QA): NaN/Inf is sanitized to None in both converters
  (`src/simulation/coupling.py` and the endpoint's `_convert_numpy` in
  `backend/app/routers/simulations.py`). Live-verified 500 -> 200 with 192
  non-finite values nulled. Frontend note: null trajectory fields render as
  gaps - explicit gap markers are optional later work.
- **F3 - non-gating lint:** 10 ruff errors in `docs/` analysis scripts
  (outside CI's ruff scope, main stays green). Owner: Research.

## Remember (user's standing instruction, 2026-11-11)

The paper reframe runs in parallel with product work, but README, the brief
and the paper metadata stay synchronized - **paper completion is not product
completion.**
