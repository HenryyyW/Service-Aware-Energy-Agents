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
| 1. NL → ScenarioConfig wiring | **Landed** (`edea241e5`) | The generator page's default path calls the real `api.generateScenario`; the mock generator survives only via the injected prop (tests/previews). The confirm-then-run flow is **decided and already built**: Product Design Lead's spec (`docs/nl_confirm_flow_spec.md`, `7601bc42e`, corrected at `5c5c6500e`) chose Candidate A - confirm creates the scenario, the run starts from the details page - which is what is on main, so no rework. The spec's last open item is decided: **the details page keeps its completed-run state with onward links (no auto-navigate to the canvas)** - recorded in the spec at `31761247f`. QA verified the loop end-to-end. |
| 2. Simulation lifecycle | **Landed** (`550a1dd96`) | `ScenarioDetailPage` validates, starts, polls, cancels and shows the reason + next step on failure; results link onward to diagnostics and reports. |
| 3. Virtual-community canvas | **Landed** (`68072ec96`) | `CommunityCanvasPage` is routed (`/canvas`, nav entry added): map/table toggle on the same run data, schematic-coordinate banner ("not actual geographic data"), honest loading/empty/failure states, keyboard + aria labels. Gates verified by Project Partner: `tsc --noEmit` clean, `eslint --max-warnings 0` clean, `npm run build` success, `vitest` 7/7. Responsive breakpoints and the MVP walkthrough remain open (QA). |
| 4. Strategy comparison | **Landed** (`54a8c4255`; verified `0eeaaa398`, F1 closed `555d28bf7`) | One config runs through the four strategies of record; the comparison view reads real runs via `api.startStrategyComparison`/`getSimulationRun`; missing metrics show "no record" instead of zero. QA smoke: 200 with four real records (mpc / multi_agent_rl / rule_based / single_agent_rl), real pandapower grid metrics. **F1 (economics placeholders) closed at `555d28bf7`** - economics is real and strategy-differentiated; one flag remains: `rule_based` and `single_agent_rl` return identical economics (Backend B to confirm the RL arm is not a passthrough). |
| 5. Agent diagnostics | **Landed** (`f260f6412`, `7068d4dc2`) | Read-only diagnosis (breaches located with evidence, interpreted, next steps) and fix proposals behind an approval gate with before/after re-run verification. Honest sub-threshold statement: strategy modification measures **5/9 vs the pre-registered 7/9**. |
| 6. Productization | **Done except walkthrough + one flag** (`e943c1d9c`, `68072ec96`, `0eeaaa398`, `2bf540951`, `bbaad3855`) | Preview pages state their mode; `docs/deployment_posture.md` separates research demo from production; canvas a11y + table view landed; responsive fixed at three breakpoints (Tailwind sm/md/lg + Layout.css overrides); QA's Phase 6 report (`docs/qa/phase6_regression_report.md`, PR #64) has pytest 518/518, black/ruff/tsc/eslint/build green and the closed loop functional end-to-end with the live LLM planner. F2 (trajectories 500) closed at `2bf540951`. **Remaining: the MVP walkthrough (script at `docs/mvp_walkthrough.md`, the user walks it) and the one F1 flag above.** |

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

- **F1 - economics placeholders (Backend B):** ~~CLOSED at `555d28bf7`~~
  (PR #66, Backend B, QA-verified on a live 4-strategy comparison):
  economics falls back to observations - real and strategy-differentiated
  (mpc 30.70 USD vs multi_agent_rl 16.64 USD; grid_import 107.4 vs 63.5 kWh;
  carbon 22.7 vs 12.5 kg; peak 19.0 vs 14.8 kW). Throughput closed at
  `14094dcea` (SOC initialized from config, default 0.5): SOC tracks
  (0.26 -> ~0.089 soc_min) and battery_throughput_kwh is non-zero (4.63 kWh
  for rule_based / mpc / single_agent_rl on a 24-step 10 kWh config).
  **Two remaining notes for Backend B (non-blocking, honesty-critical):
  (1) multi_agent_rl shows 0.0 throughput while keeping its real cost
  advantage - B's noted separate controller issue. (2) In environments
  without their policies/artifacts, mpc AND single_agent_rl return
  byte-identical results to rule_based - the comparison endpoint silently
  falls back to rule_based, the exact pattern the no-silent-substitution
  rule targets; those arms must be labeled (or skipped) in the payload
  before the four-strategy comparison is a claim.**
  Both closed on main (B's `e21e468`, merge `b5e4a9e92`): multi_agent
  throughput 0.0 -> real (coordinator message delivery + action asset_id
  fixes) and the comparison payload now carries `controller_fallback_steps`
  / `controller_fallback_reason` (`/api/compare`, `ExperimentResult`) so a
  falling-back arm is named, not silently substituted. **Partner's
  merge-quality note** (`cc2337a65`): B's branch was not clean against
  merged main - a missing `Optional` import broke 3 test modules'
  collection, `self.controller` was used in a module-scope function (a
  latent NameError), `abs(net_kw)` broke the codebase's signed-discharge
  convention, and test asset_ids still used pre-adapter names. Fixed and
  verified: 518 passed, black/ruff clean. **QA re-verified live on
  `cc2337a65` (merged `bc9c43cbe`, PR #67):** throughput is real for all
  four arms (4.63 / 4.63 / 4.63 / 7.35 kWh) and multi_agent_rl is shown
  worse than baseline (41.80 vs 27.48 USD) - no substitution, no padding.
  B's branch magnitudes (368.89 / 207.35 kWh) do NOT reproduce on the
  smoke config; treat as environment-bound and quote QA's numbers.
  **Fallback labelling rework merged** (`a1f3e8a56`, B's `8a25ab9`): the RL
  controller increments `fallback_steps` at the real fallback (state not
  in Q-table) and MPC had both fallback paths incrementing, so the
  tracking reads a live attribute; the benchmark extractor propagates the
  two fields. Partner verified after merge: 518 passed, black/ruff clean
  (kept the None-guarded simulations.py version in a conflict;
  black-formatted run_benchmark.py). **Awaiting QA's live re-check that
  the label actually fires for mpc/single_agent_rl on the comparison
  path.**
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

## MVP walkthrough (user, 2026-11-12): NOT PASSED - defect register

Walked on main `78c2fd9e1` from a Windows machine, no code edits, honest verdict:
**fail**. API-assisted complement confirmed the simulation core runs, but the UI
loop is broken at entry and in the canvas. Register (owner in brackets):

| ID | Defect | Evidence from the walkthrough | Owner |
|---|---|---|---|
| W1 | Generator page renders blank / React infinite update | Step 1 fails in the browser; API path works | Frontend (FE2) |
| W2 | Canvas shows "No community data" although 24 trajectories exist | Step 4 fails | Frontend (FE2) + QA repro |
| W3 | Fallback config (no LLM) is degraded AND invalid: missing EV arrival/departure times; `POST /scenarios` returns **500** instead of a named 4xx | Step 2 | Backend A |
| W4 | Timeline inconsistent: 15-min config overridden by the 60-min dataset; trajectory timestamps on another scale, early steps repeat | Steps 3-4 | Backend A |
| W5 | PV self-consumption 100% is computed from empty data (no building contributions in 24 steps) - a fallback value presented as a KPI | Step 3 | Backend B |
| W6 | Report carries run id + seed but **not the full scenario configuration** (the script promises it) | Step 7 | Backend A |

**W3/W4/W6: CLOSED (`37219e6cf`, Backend A, partner-verified in an isolated
worktree on origin).** W3: the fallback EV config carries
arrival/departure/target/initial values and invalid configs return named 422s
(not 500); W4: `ScenarioConfig.effective_timestep_minutes` added and
trajectories use the effective (dataset-native) timestep; W6: the report
download includes the full scenario configuration. A's patch needed black/ruff
cleanup before landing (518 green after). The shared repo still holds A's
uncommitted overlap - A decides discard-or-commit (2026-11-13).
| W7 | Silent strategy substitution unexplained in the UI (three arms identical) | Step 5 | Backend B (label) + FE2 (surface) |

**W7 backend part: PASSED (QA live on `a1f3e8a56`, PR #68):** mpc and
single_agent_rl are labelled 24 steps / `fallback_to_rule_based` via
`GET /api/compare`; rule_based and multi_agent_rl correctly None; four
throughputs non-zero. Residual R1 (Backend B): CLOSED at `ca1ac551a` (B's `92d37f7a4`) - the
`SimulationRun` response model carries the two fields; QA live re-check
in flight on the merged main. UI surfacing stays with FE2.
| W8 | Windows/local startup friction: `npm.ps1` blocked by execution policy; backend launched from `backend/` cannot resolve packages; default frontend proxy targets an unresolvable `api` host; backend needs `PYTHONUTF8` to avoid generation encoding errors | Start | QA/DevOps |

**W8: CLOSED (`4a2ab9bad`, QA):** README starts the backend from the repo
root (`python -m uvicorn backend.app.main:app`), documents `npm.cmd` for
PowerShell and `PYTHONUTF8=1` on Windows, and the vite dev proxy defaults to
`http://127.0.0.1:8001` (was `http://api:8000`, docker-compose-only); the
`.env.example` names now match the client (`VITE_API_BASE_URL` /
`VITE_WS_BASE_URL`). Partner verified: merged, tsc 0 errors, build green.
**W1/W2/W9: CLOSED (`e92710b30` + `67572134d`, FE2, partner-verified and
pushed).** W1's root cause was an object-literal zustand selector (a new
object every render) tripping `useSyncExternalStore`'s infinite-loop abort -
fixed with atomic selectors; W2 adds loading/error/empty canvas states;
W9 disables the report download button while downloading. Partner verified:
tsc 0 errors, eslint 0, vitest 7/7, build green.
**W2 root cause deepened (QA browser repro, `b819f4788`, merged):** the
canvas only renders API-registered scenarios (`/api/network/geometry` ->
in-memory `_scenarios`); the walkthrough's API/CLI-created scenarios never
register, so "No community data" was correct-but-unreachable. **Decision
(Partners): run-based data path.** **CLOSED (`9cfcfb6e4`, FE2,
partner-verified in the shared repo: tsc 0, eslint 0, vitest 10/10,
build green):** the canvas falls back to `getRuns()` -> `run.scenario_id`
-> scenarios + trajectories, so any real run displays; empty state only
when zero runs exist. Known limitation recorded: scenario persistence is
resolution-dependent (same-process reads fine; cross-restart loss is the
documented research-demo posture).
**W7 (UI): CLOSED (`249667489`, FE2, partner-verified):** the page's
`strategyData` builder now maps `run.controller_fallback_steps/reason`, the
panel renders them (or "no record"), and a new component test covers both
branches (vitest 9/9, 4 files). **Still gated by R1** on the per-run path:
`GET /api/simulations/{run_id}` strips the fields until Backend B's
response-model addition lands - the labels QA verified via `/api/compare`
already flow; the per-run source is the remaining leg.
| W9 | UI download button not exercisable (click timeout); diagnostics step only verified via API | Steps 6-7 | FE2 + QA |

Note: the walkthrough build `78c2fd9e1` predates the fallback-labelling
merge (`a1f3e8a56`); QA's live check of W7's labelling is still in flight.
The other defects are independent of that merge.

Priority (from the walkthrough): W1/W8 (entry + startup) -> W2 (canvas data
chain) -> W4/W5 (timeline + KPI honesty) -> W3/W6/W7 (config integrity,
report, labelling).

## Fallback-label mechanism decided (Backend B, 2026-11-13): option A

Main keeps the controller-attribute mechanism (`controller.fallback_steps`,
reason `fallback_to_rule_based`, QA-verified: mpc 24 steps). B's semantic
action comparison (which would count 2 steps and change the marker's
semantics, requiring a full live re-verification) is **deferred** to the P3
strategy-modification stage if finer granularity is needed there. No action.

## Final verification (QA, PR #70, live on e17d77562): no open defects

- **R1 (per-run fallback fields): PASS end-to-end.** `GET
  /api/simulations/{run_id}` carries the marker: mpc and single_agent_rl
  return **24 steps / fallback_to_rule_based**, rule_based and multi_agent_rl
  return 0/None (genuine); `/api/compare` normalizes genuine to None.
  Throughputs all non-zero (4.63 / 7.35 / 4.63 / 4.63 kWh). The
  no-silent-substitution rule holds from controller to API to UI.
- **W5 (PV self-consumption): PASS.** With export forced (1 building, PV
  50 kW, no battery): reported 0.9265 == implied (pv - export)/pv exactly
  (import 192.27 / export 14.22 / pv 193.46 kWh); the control case with
  export = 0 correctly reads 1.0 - the formula discriminates both regimes.

**All nine walkthrough defects are closed and verified; MVP retest (the
user, per docs/mvp_walkthrough.md) is the only remaining acceptance step.**

## Pre-retest preflight (QA, PR #71, production build @ 328df3568)

- **Lighthouse (3 runs, median): all budgets met.** Performance 0.99,
  Accessibility 0.94, Best-Practices 0.96, SEO 1.00; FCP 729 ms, LCP 769 ms,
  CLS 0.0002, TBT 0 ms (exit 0).
- **axe (axe-core 4.14.0): 0 violations** (exit 0).
- **Responsive (3 viewports x 4 pages): no broken layouts.** One cosmetic
  item dispatched to FE2: the mobile hamburger overlaps the generator page
  title (non-blocking, fix in flight).
- QA's environment note: the W1 blank page was dev-server-specific (zustand
  `getSnapshot` loop protection kills the dev render only) - the production
  build renders the generator at all viewports. The dev-mode render was
  separately verified by FE2 (all four routes mount, 0 React exceptions).

**Pre-retest status: script v2 pushed (`328df3568`), CI green, preflight
green, one cosmetic fix in flight. The user's walkthrough retest is the only
remaining acceptance step.**

## Paper sync audit (Research, 2026-11-13): reviewer items closed, but a
## material KPI-table deviation found and re-run ordered

**Confirmed by Research (and my text-level audit):** the reviewer pass 1 /
disclosure / bar-met / P4-reframe merges stand; the tex reads the final P1
numbers (14/16 + all 8 domains + 4/4, c09 C3 disclosed); tex and PDF are in
sync (11-12 13:40, 21 pages, 0 warnings); the reviewer-response open items
(D != A, Table 2/3 D rebuilt, recovery claim removed) are all closed; the
docs/ ruff cleanup (F3) landed (`5433b83e0`).

**Deviation (material):** the paper's B-axis KPI tables (Tables 2/3/4) and
figures were recorded on 11-04/11-07 builds - BEFORE the 11-12 evening
economics rework. Controlled reproduction: scenario_a x centralized x 123
= 12.19 on final vs 35.16 recorded; every re-runnable cell moves 8-17 KPIs;
the recorded PV self-consumption was the pre-W5 illusory path; and the
positioning claim flips - multi_agent's paired cost delta vs rule_based goes
from -18.11 (recorded, "cost-minimal in every scenario") to +17.51, i.e. it
is no longer cheapest in ANY scenario. Root cause: the recorded multi_agent
numbers predate the action-delivery fix (`e21e4688`) - its actions never
reached the assets. Environment ruled out (old builds reproduce the recorded
values exactly).

**Blocker CLOSED (`cbcc6e937` + `572cdbcb8`, Backend A):** the E-arm crash is
fixed and the guards decoupled - all controllers receive grid-diagnostics
updates, only RuleBased/MultiAgent/Centralized perform redispatch. Re-run
baseline: `572cdbcb8` (partner-verified, 518 green).

**Old blocker record (kept for provenance):** 20/250 cells crashed on final
code - scenario_E mpc/rl died at `src/simulation/coupling.py:580` (`hasattr` guard passes for
BaseController subclasses, then calls a method only
RuleBased/MultiAgent/Centralized define). The call landed after the paper's
E rows were recorded, so those rows cannot be reproduced on any build since.

**Decision (Partner): option (1) - re-run everything on final code.** pool_tou
already re-run (230/250); p2p and LMP legs next (~1h each, deterministic);
A's E-fix first for the 20 crashed cells; then rebuild Tables 2/3/4, figures,
abstract ranges and re-word the positioning claims. M2a/M2b stay as published
records (their counts are unaffected). QA independently re-verifies one cell
before the re-run is trusted. The paper must not be re-submitted with the old
B-axis numbers.

## Paper rebuild handoff (Research 2, 2026-11-13): full re-run re-ordered

Research 2's audit of the inherited artifacts found both "completed" legs
UNTRACEABLE - the plan adjustment is confirmed (Partner):
- **p2p leg (inherited): invalid.** Manifests span three commits, 100/250
  cells ran with `git_dirty=true`, and the previous "probe-verified
  final-code reproduction" records do not exist on disk. Fails the
  traceability rule; re-run ordered. (The Partner had relayed the old
  claim - teammate self-reports are not facts until independently verified.)
- **pool_tou leg (inherited): invalid AND mis-baselined.** 230/250 cells
  ran pre-crash-fix, and none of the manifests carry `pricing_regime` - the
  old run never passed `--regime pool_tou`, so energy_sharing was actually
  off. Reusing it would poison the baseline. Re-run ordered.
- **Re-run in flight on the clean tree `9763bd7b0`:** pool_tou (250 cells,
  `--regime pool_tou`, ~15 min, 8 workers) -> lmp (`--regime lmp`,
  `lmp_` policy prefix) -> p2p (`--regime p2p`), each leg reported, then the
  scripted Tables 2/3/4 + abstract rebuild, the positioning re-wording
  (multi_agent no longer cheapest in any scenario), the RL fallback-share
  disclosure, and the PDF rebuild.

## Paper rebuild: all three legs complete and partner-verified (2026-11-13)

- **pool_tou**: 250 manifests, all `git_commit=9763bd7b0`, `git_dirty=false`,
  `pricing_regime=pool_tou`; raw_results 250 rows. Partner-verified in-repo.
- **lmp**: 250 manifests, all `git_commit=05a925219` (docs-only delta from
  9763bd7b0 - partner-verified: no code difference), `git_dirty=false`,
  `pricing_regime=lmp`; raw_results 250 rows. Partner-verified.
- **p2p**: 250 manifests, all `git_commit=05a925219`, `git_dirty=false`,
  `pricing_regime=p2p`; raw_results 250 rows. Partner-verified (this leg's
  artifacts were found complete on disk after Research 2's turn died to the
  NVIDIA NIM outage mid-report).

All three legs meet the traceability rule: single baseline, clean tree,
explicit regime, lossless raw_results. Remaining: the scripted rebuild of
Tables 2/3/4, figures and abstract ranges; the positioning re-wording; the
RL fallback-share disclosure; the PDF rebuild. Re-dispatched to Research 2
(2026-11-13; their session had died to the NIM outage).

## Paper rebuild: content verified, artifact-hygiene fix in flight (2026-11-14)

Research 2's rebuild (`0fda3e120`, partner-verified and pushed): Tables 2/3/4,
figures f1/f3, abstract ranges and the positioning re-wording all rebuilt
scripted from the three verified legs (`docs/baxis_table_rebuild.py` +
`docs/baxis_rebuild/summary.json`); multi_agent's paired cost delta is
positive in all five scenarios (+49.08 to +100.01 USD, p_Holm < 0.0001) -
the "cost-minimal in every scenario" claim is dead and replaced; centralized
is cost-minimal in A/C/D/E, mpc in B; RL fallback shares (2-9/168 steps)
disclosed; PDF 21 pages rebuilt; M2a/M2b untouched as published records.

**CI red on that head:** `Artifact hygiene` rejected 759 files - the 750
manifests/raw_results were committed under `experiments/` (the Partner's own
"land artifacts in the repo" instruction - revoked; the repo's
`scripts/check_artifacts.py` rule wins). Fix dispatched to Research 2:
untrack the three legs (keep on disk for verification), .gitignore them, keep
the script + summary + note + paper in git, document the traceability path.
Content itself needs no change.

## Paper rebuild: COMPLETE and green (2026-11-14, main 3171de289)

Research 2's rebuild is verified and pushed; CI and the full CI/CD pipeline
are green on the head. The three B-axis legs are rebuilt on scripted,
traceable data (`docs/baxis_table_rebuild.py` -> `docs/baxis_rebuild/`; the
750 raw runs stay on the experiment machine per the repo's artifact-hygiene
rule, with their baseline/regime provenance recorded in `summary.json`).

Paper state now matches the final code: multi_agent's paired cost delta is
positive in all five scenarios (+49.08 to +100.01 USD, p_Holm < 0.0001,
settlement-inclusive), the "cost-minimal in every scenario" claim is
replaced, centralized is cost-minimal in A/C/D/E and mpc in B, the RL
fallback share (2-9/168 steps) is disclosed, and M2a/M2b remain published
records. PDF: 21 pages.

## MVP retest #2 (user, 2026-11-14): NOT PASSED - W10, generator confirm screen

Walked per script v2 on Windows, no code edits. **Failed at step 1 again,
with a NEW root cause**: generate returns 200 but the confirm/preview screen
white-screens with React "element type is invalid / undefined".

**Root cause verified on origin/main:** `ScenarioGeneratorPage.tsx:224`
resolves the icon via `ICON_FOR[s.title]` while section titles are
capitalized ('Community', 'Buildings', 'PV', 'Battery') and the `ICON_FOR`
table (:132) only has lowercase keys -> `undefined` -> `SummaryCard` renders
`<Icon/>` with an undefined component. The sections themselves carry an
`icon` field (:212-215) that the render path ignores - the lookup is the
defect.

**Why the gates missed it:** tsc/eslint/build/vitest all green because the
failure is a runtime lookup (the `ICON_FOR` type is `Record<string, any>`),
and no test renders the confirm screen - the exact class of gap that also
hid W1 (dev-only) earlier. **Process correction:** the generator's
generate->confirm path must be exercised in a live dev server and covered by
a rendering test before any future "verified" claim.

**Dispatched to FE2 (2026-11-14):** use the sections' own icon (or a
case-insensitive lookup), degrade safely when an icon is missing, add a
confirm-screen render test, and verify in a live dev server. Partner will
personally re-run generate->confirm before asking the user to retest.

## W10 closed (2026-11-14, 4defbf05c) - partner browser-verified

FE2 fixed the confirm-screen white screen: the sections render their own
`icon` field (the case-mismatched `ICON_FOR` lookup table is gone) and
`SummaryCard` degrades to a text fallback when an icon is missing. New
`ScenarioGeneratorPage.test.tsx` renders the confirm step with all sections.

**Partner verification (the step that was missing twice):** started a clean
backend + dev server, opened `/scenarios/generate` in a real browser, typed
the walkthrough description through the trusted input path, clicked Generate.
The confirm screen rendered fully - preview-mode banner, named rejections,
all seven sections with provenance chips (given/assumed/default/missing),
and Run Scenario / Edit-reject / Validate-now buttons. Backend log shows the
full generate pipeline returning 200 twice with recommendation "accept". No
white screen, no React error.

Gates re-verified by the Partner: tsc 0, eslint 0, vitest 13/13, build green,
pytest 518, black/ruff clean. Pushed `4defbf05c`.

**Process change (durable):** for any generator-flow fix, the acceptance
check is a live browser pass through input -> generate -> confirm, not gate
summaries. The user may retry the walkthrough now.

## MVP retest #3 (user, 2026-11-14): NOT PASSED - 2 pass / 3 partial / 3 fail;
## W10 confirmed fixed

Full eight-step run on Windows, no code edits. **Verdict: 2 pass, 3 partial,
3 fail.** W10's fix holds (step 1 shows preview + provenance + rejections,
step 2 saves and validates) and the strategy comparison surfaces fallback
labels correctly (step 5 conditional pass: mpc/single_agent_rl both
`24 steps / fallback_to_rule_based`, numbers identical because both arms
fall back - honestly labeled).

New defects (all three root causes partner-verified in-repo before
dispatch):

- **W11 (fail) - canvas stuck on "Loading community data"** despite API
  data: `CommunityCanvas.tsx:206` exits the loading state only when
  `!currentRun?.scenario_id` - with a real run the inverted condition never
  clears. -> FE2.
- **W12 (fail) - trajectory timestamps broken beyond 24 steps**:
  `simulations.py:606` formats `h.timestep * 0.25` as a zero-padded HOUR -
  hours accumulate without day rollover (168 steps -> `T42:00`) and the
  0.25 factor hardcodes 15-min steps while the effective timestep is
  60 min. A's W4 fix touched the schema, not this serializer. -> Backend A.
- **W13 (fail) - report shows `Buildings: 0` / N/A limits**: `reports.py:122`
  reads `run['scenario_config']` but the run dict (`simulations.py` ~:533)
  never writes it - the W6 fix assumed a field that does not exist on the
  UI-created path. -> Backend A.

Partial items to close:
- **Step 3:** the UI does not expose `max_steps` (API has it), so runs start
  with 168 steps instead of the walkthrough's 24 - steps input on the run
  control (default 24) -> FE2.
- **Step 6:** EV completion 0% exists only in the API; the diagnostics UI
  must surface service metrics (a 0% service failure cannot hide behind
  "no violations") -> FE2.
- **README line 20** still carries the stale "mock generator" banner text
  (the 04d1a2ffb sync covered L42/L270 but missed L20) -> PM.

Retest discipline reaffirmed: every fix must be walked in a live browser
with real data before the user is asked to retry.
