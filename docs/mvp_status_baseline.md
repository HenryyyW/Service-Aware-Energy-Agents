# MVP status baseline (Phase 0 record)

Owner: Project Partner · Updated: 2026-11-16 (main @ `2e8a117fe`) ·
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

## Partner verification of W12/W13 fixes (2026-11-14): W12 PASSES, W13 and
## max_steps DO NOT - re-dispatched with exact call sites

Ran the UI-equivalent flow against f08e14301 (live backend): generate ->
create -> POST /api/simulations with top-level `max_steps=24` -> 24-step
expectation.

- **W12: PASS.** 168-step run trajectories: `2023-01-01T00:00` ->
  `2023-01-07T23:00`, correct day rollover at the 60-minute effective
  timestep; no repeated hours, no `T42:00`.
- **W13: STILL BROKEN.** Report still shows `Buildings: 0` / N/A. A's fix
  wrote `scenario_config` only into the strategy-comparison background
  dict (`simulations.py` ~:533); the single-run path stores
  `run.model_dump()` (~:470) and the `SimulationRun` model has no such
  field. Second call site re-dispatched.
- **max_steps/random_seed: IGNORED.** `simulations.py:441` reads only
  `request.parameters`; the top-level fields (which FE2's new UI and the
  API client send) are dropped, so the run still executes 168 steps.
  Re-dispatched: top-level first, `parameters` as fallback, keeping the
  client as-is.
- **FE2's W11 + service-metric work** (packaged in the same commit): logic
  reviewed and direction confirmed; the live-browser pass (canvas exits
  loading, steps input, EV completion visible) is the partner's remaining
  check.

## Partner browser verification of the f08e14301 batch (2026-11-14)

Live browser pass (backend + dev server, Chrome) against f08e14301:
- W11 loading-gate fix: HOLDS - /canvas exits loading within seconds.
- Steps/seed inputs: PRESENT and correct (spinbuttons 24 / 42 on the detail
  page); a UI run click triggers the run (idempotent merge of an identical
  config run - by design).
- **W14 (new, fail):** the canvas then shows "No community data / No
  buildings found" because `CommunityCanvasPage` builds buildings from
  `/api/network/geometry?scenario_id=`, which only has REGISTERED
  scenarios; UI/API-created scenarios never register and the failure is
  swallowed in a catch. Fix dispatched: synthesize a deterministic
  schematic layout from `currentScenario.buildings` when geometry is
  missing (the canvas already discloses schematics), keeping
  trajectories-driven assets/violations.
- **Step 6 (still open):** after a completed run the detail page shows
  "Completed" + links but no service metrics; the `evCompletionRate` block
  (`ScenarioDetailPage.tsx:255`) did not render in the browser though the
  API returns 0. Re-dispatched: service metrics (EV completion, avg EV SOC)
  must render unconditionally for completed runs - a 0% service failure
  cannot hide behind panels.

W12 standalone: PASSES (verified earlier). W13 single-run path + top-level
max_steps: with Backend A.

## Partner re-verification of the W13/max_steps/W14/step-6 fixes
## (2026-11-15, live backend + Chrome)

Re-ran the exact failing paths against 39f7daece:
- **W13 + max_steps: PASS.** `POST /api/simulations` with top-level
  `max_steps=24` -> run completes at exactly 24 steps; 24 trajectories;
  timestamps `00:00` -> `23:00` (60-min effective); report shows
  `Buildings: 1` with no N/A; `scenario_config` present on the run payload.
- **W14 (canvas): PASS.** /canvas renders the schematic banner
  ("Schematic network layout - not actual geographic data") with Map/Table
  toggle; the table view lists the building, its PV/battery/EV assets and
  Grid Violations (0).
- **Step 6 (service metrics): PASS.** After a completed run the detail page
  shows "Service metrics - EV completion rate 0.0% / Avg EV SOC at
  departure 0.0%".
- **Step 4's last piece (fail): the time player is never mounted.**
  `TimePlayer.tsx` exists and the store wiring is used
  (`CommunityCanvas.tsx:52/507/542`), but no `<TimePlayer />` is rendered
  anywhere - the map view has no playback/scrub controls. Re-dispatched to
  FE2 (mount + browser-verify scrub updates + keyboard operable).

Retest #4 waits on this last item; everything else in the loop is
partner-verified green.

## TimePlayer verified by partner (2026-11-15) - ALL retest-#3 items now closed
## live; the user's retest #4 is unblocked

Live browser pass on 5d8625fe3 (pushed in b1b76c413): /canvas with a run
shows "Schematic network layout - not actual geographic data", the TimePlayer
is mounted (slider "Simulation timestep", Step 0 / 23:00, 1x, PAUSED, Reset /
Step backward / Play simulation / Step forward / Playback speed buttons), and
stepping forward twice advances 00:00 -> 02:00 with the backward button
re-enabled. Gates partner-verified on the same tree: pytest 518, vitest
13/13, tsc 0, eslint 0, build green, black/ruff clean.

Closed with live evidence across this verification cycle: W13 (report
carries scenario config), max_steps top-level (24-step runs), W14 (canvas
renders API-created scenarios via schematic-from-config), step 6 (service
metrics visible on completed runs), step 4's time player. The eight-step
walkthrough has no known open defect as of `b1b76c413` - the user's retest #4
is the only remaining acceptance step. (QA's Lighthouse/axe re-check on the
newer code is advisable but not a blocker for the walkthrough itself.)

## MVP retest #4 (user, 2026-11-15): NOT PASSED - big progress, one
## blocking defect + a UI cluster

2 partial-pass heavy run; every fix from retest #3 held under live use
(24-step runs with real economics ($5.47 / 20.10 kWh / 22.05% PV / 4.35 kWh
throughput / 3.96 kg), correct timestamps, report with buildings/config,
canvas + table + time player + keyboard, four-strategy comparison with
honest fallback labels, downloads).

- **W15 (fail, blocking): NL fallback fidelity.** "4 buildings, one shared
  battery, two EVs" -> Base Scenario, 1 building, 1 EV, no battery. Verified
  root cause: `_fallback_plan` hardcodes `building_count = 1`, single-count
  configs, English-only keywords, and - worst - **silently defaults**
  unparsed counts instead of listing them as rejected fields
  (no-silent-substitution violation at the front door). -> Backend A: parse
  building/EV counts, bilingual asset keywords, named rejections for
  unparsed stated counts.
- **W16** Validate-now validates the nonexistent `scenario_base`. -> FE2.
- **W17** "View the community" navigates to a nonexistent probe scenario.
  -> FE2.
- **W18** effective timestep never surfaced: config says 15 min, runs at
  60; comparison `maxTimestep` computes 95 against 24 real trajectories
  (dispatch trace "0/95" is this symptom); report effective timestep None.
  -> FE2: use `effective_timestep_minutes` wherever timesteps are computed
  or displayed, and disclose the dataset resolution.
- **W19** asset capacity shows `—` (asset-metadata, like geometry, serves
  only registered scenarios). -> FE2: synthesize from config, W14 pattern.
- **W20** MapLibre worker load error in map view (table view fine). -> FE2.
- **W22** report page footer: scenario/controller `Unknown`, effective
  timestep `None`. -> FE2.
- **W23** diagnostics panel missing on the detail page in practice (API
  fine). -> FE2.
- **CI/CD:** Build Backend Image 20-min timeout -> pipeline cancelled,
  compose smoke skipped. -> QA.
- **Paper deadline TODAY (11-15):** submission status unverified;
  Research 2 asked for immediate confirmation.

## Partner browser verification of W16-W23 (2026-11-15) on 37ecd3612

PASS (live): W16 (validate no phantom scenario error), W17 (View the
community -> /canvas), W18 (detail header "60 min steps" = effective
timestep; the phantom 95-step timeline is gone), canvas load + 24-step
TimePlayer, completed-run economics on the detail page ($218 / 728 kWh /
EV 0%).

FAIL with root causes:
- **W23** diagnostics panel never renders: the backfill effect's cleanup
  sets `active=false` on every re-run while `setRun` re-triggers the
  effect - the fetch is aborted between "fetching" and "fetched". Fix: a
  fetched-id ref, or move the fetch out of the polling effect.
- **W22** report footer shows Unknown though `/api/reports/{id}` returns
  scenario_id + controller_type - the state source in the page is wrong.
- **W24 (new, blocking): the confirm screen renders only `buildings[0]`**
  (`ScenarioGeneratorPage.tsx:199`). A correct 4-building config still
  *looks* like 1 building + one of each asset to the user - step 1 fails
  on perception alone. Must render every building.

Re-verify: W19 (table view click blocked by a covering div in the partner
harness) and W20 (MapLibre worker error not seen this pass - likely fixed
by the main.tsx worker-URL change).

W15 note: the API now generates 4 buildings for all tested inputs, but
per-asset counts still equal the building count (cross-contamination) -
re-dispatched to Backend A with measurements.

## Partner verification of the W15-v3 / W24 / W23 batch (2026-11-15) on
## ff27a82b7

- **W24: PASS (live browser).** The confirm screen renders all four
  buildings ("Buildings 4 buildings" + building_1..4 + per-building PV
  sections) - no more buildings[0]-only view.
- **W15 v3: STILL FAILS (live API).** The clause-based parse landed but the
  counts still equal the building count (battery=4, evs=4 for "one shared
  battery, two EVs"). Root cause located to `config_coder.py:_build_buildings`
  - it stamps one asset config on EVERY building (`configs[i % len(configs)]`
  cycling). Re-dispatched to Backend A with the file-level fix guidance.
- **W23: STILL FAILS (live browser, fresh run path).** The diagnostics fetch
  lives inside the polling effect; `setRun` re-triggers the effect whose
  cleanup aborts the fetch, and the completed-run guard short-circuits any
  retry - diagnostics stays null for freshly started runs. Re-dispatched to
  FE2 with two concrete fix options.
- Confirmed real economics on the detail page: $17 / 61 kWh import /
  PV self-consumption 37% (not the former 100% illusion) / EV 0% / 100% power
  flow convergence.
- Note: a `.vite` cache file accidentally committed in Backend A's W15 v3 was
  dropped before merge (the artifact-hygiene guard); one vitest assertion
  updated for the W24 multi-building render.

## Partner verification + dispatch cycle (2026-11-16, origin/main `2e8a117fe`)

**QA PR #73 merged (docs-only, 41-line diff partner-verified).** Phase A is
recorded in `docs/qa/phase6_regression_report.md`: step-3 cancel flow PASS
(run `run_e8d3675bc639`, rule_based, cancelled at step 12/96, terminal status
`cancelled` immediately, no fake completion; cosmetic note - `outcome_sentence`
is None on cancelled runs); step-8 full-site axe on the production build, all
10 routes: **69 violations on 4 routes, all labelling/contrast classes**
(/studio 57 button-name + color-contrast, /scenarios/generate 7
color-contrast, /experiments 4 + /network 1 select-name), **no
keyboard/focus-order violations anywhere**. Phase B (the full 8-step clean
retest) is explicitly blocked on Backend A's schema-validation push.

**Fallback labels re-verified live by the Partner on the merged tip** (clean
worktree at `2e8a117fe`, backend :8077, scenario `fixv1`, 24 steps, seed 42/43):
`mpc` and `single_agent_rl` both return **24 steps / `fallback_to_rule_based`**
in the create response AND in `GET /api/simulations/{run_id}` - the per-run
strip QA saw is closed on main (B's `e189791bc` is in main; the label is
written by the controller, so both the POST and the per-run GET carry it).
Both arms genuinely fall back in this environment, so the labels are the whole
honesty story: the comparison page and run detail must show each arm's label
next to its numbers, or identical arm numbers mislead (the user's
no-silent-substitution rule). R1/W7 backend leg: PASS with live evidence.

**W25/W26/W27 (Backend A) - verified in the shared checkout, NOT landable.**
The files are uncommitted and on-track (`src/schemas/scenario.py` gt=0 +
`extra="forbid"` on the device/tariff/building schemas; `config_planner.py`
shared_assets + the named `battery.shared_not_supported` rejection + count
window 8→30 chars; `config_roles.py` shared_assets; `config_coder.py`
NL-derived name/description), but the batch is broken and would fake success:
`create_scenario` in `src/api/routes/scenarios.py` returns its dump BEFORE
`_scenarios[...] = config` and the YAML persistence (dead code - POST would
answer 200 and the scenario would never be stored), DEBUG prints remain in
that file, and the `ValidationError` handler is registered twice in
`src/api/main.py`. Re-dispatched to Backend A W25-first on branch
`backendA/fix/w25-schema-validation` (no frontend edits; reply must carry
exact pytest counts and a real 422 body for a negative-capacity payload).
Partner pushes after verifying from a fresh worktree.

**FE2 dispatched** (`frontend2/fix/preretest-a11y`): the axe fixes (studio 57,
generate 7, experiments 4, network 1 - all labelling/contrast), report-footer
effective-timestep None, a cancelled-run stage sentence, and per-arm
fallback-label surfacing on comparison/detail; `npm run lint` must pass
(retest #5's eslint failure must not return). FE2 to confirm whether tonight's
uncommitted `CommunityCanvas.tsx` / `vite.config.ts` edits are theirs.

**Retest #5 open items mapped to owners:** shared-battery fidelity (W27 -
with A, in the checkout), negative-capacity 422 (W25 - with A, in the
checkout), 15-vs-60-min timestep (60-min effective verified on the detail
header; QA to re-confirm in Phase B), identical strategy arms (labels now
live on main; surfacing with FE2), eslint (FE2 gate), report-footer timestep
(FE2).

**Gate for the user's retest #6:** A's W25/W26/W27 push + FE2's branch merged
→ QA's Phase B (8 steps from a clean origin rebuild) → then the user walks
`docs/mvp_walkthrough.md`.

## Partner verification addendum (2026-11-17 ~00:20, origin/main `f26b26ba8`)

**A's follow-up push verified live on the new tip** (clean worktree, backend
:8079, scenario `fixv1`, 24 steps earlier / generate probe now): the EV-count
fix in `f26b26ba8` answers the observation I raised - the phrase "four
residential buildings, one shared battery and two electric vehicles" now
returns **4 buildings, 2 EVs total (1 on building_1 + 1 on building_2),
exactly one battery on building_1, `rejected_fields:
["battery.shared_not_supported"]`** (plan_source `rule_based_fallback`), and
the negative-capacity 422 still fires with named fields. pytest
`test_scenario_aware_schemas.py` 3/3 on the tip. W25/W26/W27 + W15 EV counts:
closed with live evidence on the fallback path; the LLM path stays with QA's
Phase B.

**Honesty flag on A's push (not a code defect, a record defect):** commit
`27be6581b` is titled "fix(W22): report footer shows empty string instead of
'No record' when effective_timestep_missing" but its diff contains only the
one-line `frontend/vite.config.ts` maplibre chunk addition - the W22 footer
fix is NOT in it. **W22 (report footer effective timestep) therefore REMAINS
OPEN** with FE2 (already dispatched); do not read the commit title as a fix.
The vite-config line reached main through A's push - FE2 to confirm that file
is theirs (their uncommitted 22:31 edit) and keep or revert it in their
branch.

**State:** main `f26b26ba8`; W25/W26/W27 + EV counts verified; W22 + FE2's
axe 57/7/4/1 + report-footer + fallback-label surfacing in flight; QA's
Phase B released (message sent) - the user's retest #6 follows Phase B.

## Partner record: teammate-claim verification (2026-11-17 ~01:00, origin/main `9c1d2aae1`)

- **Backend A's "done" reply verified: pytest claim TRUE.** A's exact six-file
  set (`test_scenario_aware_schemas.py`, `test_contract.py`,
  `test_rejection_naming.py`, `test_grid_redispatch.py`,
  `test_controller_grid_response.py`, `test_coordination.py`) re-run by the
  Partner on the main tip: **60 passed**. The 422 body A quoted matches the
  live response.
- **A's branch `backendA/fix/w25-schema-validation` (`01fc1b999`) is a
  REGRESSION, not a delivery - do not merge.** It is based on the
  pre-W16-W24 tip `bdf5eec06`; diffed against main it removes ~190 lines
  (the W16-W24 fixes, QA's PR #73 Phase A section, today's baseline records),
  reverts `ci-cd.yml` and `Dockerfile.backend`, and commits a
  `.vite/deps/_metadata.json` cache artifact the repo's hygiene guard
  rejects. A's W25/W26/W27 work is already on main via `w25-fix-final` and is
  live-verified; A was told to name anything main lacks or treat the branch
  as superseded.
- **W22 truth check (for FE2's fix):** the report footer renders
  `Dataset resolution N min` when `scenario_config.effective_timestep_minutes`
  exists and an EMPTY string when it does not (ReportPage.tsx:438-441) - not
  a literal "None". The honest fix is a "no record" style label in the
  missing branch; the value itself is present on real runs (the detail header
  shows the 60-min effective timestep). W22 stays open with FE2.

## Partner verification: FE2's branch merged (2026-11-17 ~01:15, origin/main `b8cf2dc85`)

**FE2's `frontend2/fix/preretest-a11y` was cherry-picked onto current main and
pushed** (4 commits: `27e35a9c1` report-download disable, `82aa40350` Phase A
axe fixes, `2dc516c65` per-arm fallback labels, `b8cf2dc85` Dispatch Trace
panel). The branch itself was NOT merged: its tip (`0071bec4a`) was 3 commits
past the SHA FE2 named and based on a stale main that would have reverted 52
lines of today's verification records. Content instead landed clean.

**Gates re-run by the Partner in a worktree on the merged result** (not taken
from FE2's report): `npm run lint` exit 0 (1 pre-existing react-hooks warning
in `ScenarioDetailPage.tsx` - non-blocking, CI runs plain `npm run lint`),
`tsc --noEmit` 0 errors, `vitest` **16/16** (FE2's 13/13 predated their added
tests), `npm run build` exit 0.

**Honesty check of the new UI (read, not assumed):** the fallback labels read
real run fields (`controller_fallback_steps` / `controller_fallback_reason` /
`controller_type`), render "no record" when absent, and add
"Effective controller: rule_based (via fallback)" only when steps > 0; the
Dispatch Trace panel has an explicit "No dispatch trace data for this run"
empty state and tests cover both branches. No fabricated values found.

**W22 closed for real runs:** the report footer now shows the fallback label +
effective controller next to Controller, and reads
`scenario_config.effective_timestep_minutes` (present on real run payloads).
Residual nit logged: when the value is genuinely missing the footer renders an
empty string rather than a "no record" label (cosmetic, honest-empty).

**Still open:** the axe re-run on the production build is QA's step (Partner
has no browser here) - the 69 findings (studio 57 / generate 7 / experiments 4
/ network 1) are expected to be addressed by `82aa40350` but only QA's scan
proves it. The unattributed one-line `frontend/vite.config.ts` maplibre
manualChunks change (pushed by A at `27be6581b`, disowned by FE2) stays on
main as benign build config pending a PM/FE2 revert decision.

**Gate for the user's retest #6:** QA's Phase B on `b8cf2dc85` (8 steps,
including the axe re-run) → then the user walks `docs/mvp_walkthrough.md`.

## Partner verification: post-merge increments (2026-11-17 ~01:45, origin/main `a52ad0d74`)

**Two code commits landed on main without partner sign-off this cycle - both
now verified by the Partner on the true tip (`6abdb58ec` + docs):**
- **A's `6408599ac`** (strip the planner's `building` placement key before
  schema validation - the W25 `extra="forbid"` seam QA caught as a 422
  regression): **live-verified** - generate (fallback) returns 4 buildings /
  1 battery on building_1 / 2 EVs, no `building` key in the payloads,
  `rejected_fields ["battery.shared_not_supported"]` intact, negative
  capacity still 422, 60/60 tests.
- **FE2's `383f35a5d`** (lazy MapLibre + canvas first-paint race): **gates
  re-run** - lint exit 0 (1 pre-existing warning), tsc 0, vitest 16/16,
  build 0. QA's intermittent canvas preview flake persists on the production
  preview (not on dev) - re-dispatched with the code-level suspects
  (`/ws` missing from the vite proxy; connection gate conflating WS and REST
  failure).

**QA's `qa/retest-467` report landed on main** (`a52ad0d74`): axe after the
a11y merge is **69 -> 61** (select-name fully cleared; studio button-name
cleared; residuals are color-contrast only - studio 54 + generate 7), zero
keyboard/focus violations, pv.building seam closed on both arms, cancel +
report + diagnostics verified, and their clean retest #2 table.

**New open items dispatched this cycle:**
- **Four arms byte-identical economics (26.41 USD) with multi_agent_rl
  unlabelled** - QA's retest #2 note; earlier rounds were distinct
  (15.27 vs 14.90). Bounded question to Backend A: is the multi-agent
  coordinator dispatching genuinely distinct actions, or degenerating
  without a fallback label? (Honesty-critical: identical numbers must be
  explained, not silent.)
- **Color-contrast residuals** (studio 54 / generate 7) back to FE2; QA
  asked for the exact axe target selectors + computed colors so the fix is
  surgical instead of another blind pass.

**Record note:** QA's commit `6abdb58ec` is titled "all steps PASS" while
its own body labels the axe residuals awaiting FE2 - content accurate,
title loose; recorded as-is, not reworded.

**Gate for the user's retest #6:** contrast residuals + canvas flake closed,
the identical-economics question answered, QA's final axe rescan clean →
then the user walks `docs/mvp_walkthrough.md`.

## Partner verification: WS-proxy fix landed (2026-11-17 ~02:10, origin/main `a007ea58c`)

**FE2's `frontend2/fix/ws-proxy` cherry-picked onto main** (`a007ea58c`,
single commit, vite.config.ts only - the branch as a whole was NOT merged:
its tip still sat on a stale base and would have reverted the baseline and
QA-report records). Gates re-run by the Partner on the merged tree: lint
exit 0 (1 pre-existing warning), tsc 0, vitest 16/16, build 0. The change
adds the `/ws` proxy entry (`ws: true`, same `VITE_API_PROXY_TARGET`) - the
exact gap QA named for the production-preview canvas flake; the connection
gate already separates REST failure from WS setup per FE2's read.

**Record correction (FE2 premise, not code):** FE2 reported "QA scanned
before my contrast fix was merged" - not the case. The contrast work IS on
the tree QA scanned (their axe commit landed as `82aa40350`, inside
`61fe8e679`); the SHA they cite (`04ef6be91`) is the pre-cherry-pick id and
is not on main. So the residual 61 (studio 54 + generate 7, color-contrast)
are measured WITH the contrast fix in - the fix did not clear them, and the
surgical selector-based pass is still the open item.

**Still open:** the color-contrast residuals (studio 54 / generate 7 -
awaiting QA's exact axe targets), the canvas flake's browser-level
re-check by QA (the /ws proxy + gate separation need QA's preview pass to
call it closed), A's identical-economics answer (four arms 26.41,
multi_agent_rl unlabelled), and the LLM-path generation evidence in Phase B.

## Partner verification: multi-agent fallback + FE2 contrast pass (2026-11-17 ~09:00, origin/main `b8f8d6953`)

**A's `b8f8d6953` verified - premise TRUE, coverage partial.** Full repo
suite on the tip: **518 passed** (A's 43/43 was a subset). Live probe on the
walkthrough config (fixv1, 24 steps, seed 77) mirroring the benchmark's own
battery-action equality: **multi_agent_rl is 24/24 steps battery-action-
identical to rule_based** - it genuinely degenerates on this config (not a
coordinator bug: earlier rounds showed it distinct, e.g. 41.80 vs 27.48 USD).
The commit enables the BENCHMARK label (`semantic_fallback_to_rule_based`).
**The API/UI path still cannot see it** - live run of multi_agent_rl through
`POST /api/simulations`: `controller_fallback_steps` 0 / reason None,
because `MultiAgentController` has `_rule_based` but no `fallback_steps` and
the route gates on that attribute. QA's user-visible flag (four arms
identical, multi_agent unlabelled) is therefore still open. Bounded
follow-up dispatched to A: count the semantic-equal steps on the controller
itself (battery-only equality, same as the benchmark), keep the API reason
string "fallback_to_rule_based", unit test + branch + partner live check.

**FE2's second contrast pass (`19e7dad28`) verified - gates green:** lint
exit 0 (1 pre-existing warning), tsc 0, vitest 16/16, build 0 (37 lines
across ScenarioComparison / ScenarioEditor / ScenarioGeneratorPage /
ParameterControls). Whether it clears the 54+7 axe color-contrast items is
QA's rescan - not provable from gates alone.

**Open:** multi-agent API label (with A), the axe color-contrast residuals
(studio 54 / generate 7 - QA's selector list pending), canvas flake browser
re-check (QA).

## Partner verification + CORRECTION: multi-agent API label (2026-11-17 ~10:30, origin/main `d29e073d3`)

**A's `d29e073d3` verified live - the user-visible label now fires and is
honest, and one claim is corrected.** Live runs through
`POST /api/simulations` (fixv1, 24 steps, seeds 42/77/88): `multi_agent_rl`
returns **`controller_fallback_steps` 5, reason `fallback_to_rule_based`**,
identical in the POST response and the per-run GET; `rule_based` 0/None; `mpc`
24/`fallback_to_rule_based` (unchanged). Full suite on the tip: **518 passed**.
QA's "four arms identical, multi_agent unlabelled" flag is therefore CLOSED at
the UI level - the arm now names its partial fallback.

**Correction to my own earlier record (probe bug, disclosed):** my first
identity probe reported "24/24 steps battery-identical - degenerates" - that
was a case-sensitive filter bug in the probe (`"battery" in str(action_type)`
never matches `ActionType.BATTERY_...`; both dicts came out empty → equal).
Re-measured with the repo's exact equality (battery keys by asset_id, 1e-6
tolerance): **5/24 steps identical, stable across seeds 88/77/42**, matching
the controller-side count. So `multi_agent_rl` is partially divergent on this
config (19/24 steps differ from rule_based), not fully degenerate - A's
in-message claim of "fallback_steps=24" is likewise an over-claim; the
verified value is 5.

**Still open from this cluster:** QA's byte-identical economics across all
four arms (26.41 USD) is NOT explained by full degeneration (multi_agent
differs on 19/24 steps) - the horizon totals must coincide for another reason;
with A/B to confirm, not blocking the label fix. **CI is still red at
`d29e073d3`: `black --check` fails on `src/agents/config_planner.py` and
`src/agents/config_coder.py`** - trivial formatting, Backend A to run black and
push (this is the pulse's standing item; A's d29e073d3 did not include it).

## Partner verification: black fix + economics explanation FALSIFIED (2026-11-17 ~11:30, origin/main `49763fad3`)

**A's black fix verified - CI red layer resolved.** `49763fad3` is
formatting-only in effect (the `-w` residue is black's line-wrapping of one
list comprehension; no logic change), `black --check` clean (93 files),
full suite **518 passed**, GitHub checks on that sha show
`Lint & Type Check → success` and `Artifact Hygiene → success` (other jobs
were in progress at read time). Live generate probe intact: 4 buildings,
1 shared battery on building_1, 2 EVs, `rejected_fields
["battery.shared_not_supported"]`. `/api/compare` also carries the new label
(`controller_fallback_b: {fallback_steps: 5, reason:
fallback_to_rule_based}` for multi_agent_rl vs rule_based).

**A's economics-identity explanation is FALSIFIED on the natural config.**
A attributed QA's byte-identical four-arm economics (26.41 USD) to the
differing battery actions "netting out identically" through community pool
clearing. Live measurement on fixv1, 24 steps, seed 42 (per-run
`energy_metrics`): rule_based = grid_import **158.12 kWh** /
battery_throughput **53.40 kWh** / self-consumption 0.470; multi_agent_rl =
**163.07 kWh** / **237.36 kWh** / 0.307. A 4.4x throughput and 5 kWh import
difference cannot net out to identical totals, so the mechanism A described
does not hold on this config. Note also QA's own two rounds disagree (retest
#1: multi_agent_rl 15.27 vs baseline 14.90 USD - distinct; retest #2: all
four 26.41 - identical), which points at the comparison/settlement path
rather than the physics. Dispatched to Backend B (economics/settlement
owner): reproduce the four-arm comparison on the same shape and reconcile
its per-arm economics against the per-run metrics above; if the comparison
reports identical economics while the runs differ, that is a reconciliation
defect - arms must never show identical numbers without a named reason.

## Partner reproduction: identical-arm economics reconciled (2026-11-17 ~12:40, origin/main `ed40ec607`)

**B's reconciliation answer verified as far as it goes; their evidence does
not exist.** B reported "all four arms DISTINCT" with a table from
`experiments/results/scenario_a/comparison_table.json` - **that file is not
on disk and not in the repo** (last commit touching `experiments/results` is
CI config; the artifact-hygiene rule keeps results out of git), so the table
is unverifiable and I reproduced the comparison myself instead.

**Partner reproduction, live API path** (`POST
/api/simulations/strategy-comparison`, fixv1, seed 42, 24 steps, then per-run
GETs):

| arm | grid_import_kwh | throughput_kwh | carbon_kg | fallback label |
|---|---|---|---|---|
| rule_based | 158.12 | 53.40 | 85.03 | 0 / None |
| mpc | 158.12 | 53.40 | 85.03 | **24 / fallback_to_rule_based** |
| single_agent_rl | 158.12 | 53.40 | 85.03 | **24 / fallback_to_rule_based** |
| multi_agent_rl | 163.07 | 237.36 | 87.70 | **5 / fallback_to_rule_based** |

Conclusions: (1) **no comparison-path defect** - each arm's numbers match its
own run payload (no cross-contamination, consistent with B's read of
`/api/compare`); (2) the three identical arms are identical **because they
fully fall back to rule_based, and each says so** - the no-silent-substitution
rule holds; (3) multi_agent_rl is genuinely distinct on this config. **QA's
"all four byte-identical 26.41" therefore did not reproduce here** - the most
likely explanation is config-specific total degeneracy on their walkthrough
config (all four arms fully falling back, multi-agent unlabelled at the time
of their retest #2, before A's label fix). Dispatch to QA: re-run the
four-arm comparison on the retest-#2 config/seed and check the multi-agent
label now reads 24 steps there - if it does, the identity is honestly
explained; if it reads <24 while economics stay identical, it becomes a real
reconciliation item for B. B's "all four distinct" table is NOT the verified
state either - on fixv1 three arms are identical-by-labelled-fallback.
