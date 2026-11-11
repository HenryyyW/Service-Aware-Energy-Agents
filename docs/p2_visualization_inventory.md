# P2 Visualization Inventory & Gap List

Scope: P2 — spatiotemporal virtual-community visualization + strategy comparison + NL authoring flow as front door.
Source: `docs/p2_visualization_plan.md` (main @ 5cbbdc452082), `docs/p2_strategy_comparison_design.md`, `docs/nl_config_confirm_design.md`, verified against `frontend/src/pages/` and `frontend/src/components/`.
Data note: real scenario configs + verification verdicts live in `/home/box/OpenBot/Shared/probe_out_full16c` (P1 corpus). Strategy comparison numbers quote the frozen matrix record (83/67/0) — never recomputed.

Status: inventory only. No implementation in this step.

---

## Item 1 — The virtual community as a spatial rail with time playback

Spec asks: buildings, on-site assets (PV/battery/EV/flexible load), grid connection, spatial layout, time playback over the simulated window.

### What exists today
- `frontend/src/pages/CommunityCanvasPage.tsx` → `frontend/src/components/canvas/CommunityCanvas.tsx`: MapGL basemap + deck.gl layers; renders buildings (square markers), PV/battery/EV assets (from `assetMetadata`), feeder lines, transformers, violations (voltage + loading), voltage/loading heatmaps, energy flows, LMP layer. Building locations resolved from real network geometry bus mappings; per-timestep observations + applied actions mapped per building.
- `frontend/src/components/canvas/TimePlayer.tsx`: play/pause/step/speed scrubber over `trajectories` with shared `currentTimestep` (store `useSimulationStore`).
- `frontend/src/components/canvas/MapLayers.tsx`: per-asset layer factories (`createBuildingLayer`, `createPVLayer`, `createBatteryLayer`, `createEVLayer`, `createFeederLayer`, `createTransformerLayer`, `createViolationLayer`, `createVoltageHeatmapLayer`, `createLoadingHeatmapLayer`, `createFlowLayer`, `createLMPLayer`).
- `frontend/src/components/panels/`: `LayerTree`, `AssetInspector`, `GridExplorer`, `TopBar`; asset inspector shows per-asset timestep data.
- `frontend/src/pages/ScenarioStudioPage.tsx` + `ScenarioEditor.tsx`: agent-authored `ScenarioConfig` exists in store (`useScenarioStore.currentScenario`) and can be authored/edited; `materializeScenario` builds runnable config from editor.
- Data shape: `SimulationRun` (`run_id`, `scenario_id`, `controller_type`, `status`, `energy_metrics`, `service_metrics`, `grid_metrics`, `pricing_regime`, `cost_basis`, `generation_status`); `TimeStepData` with `observations`, `applied_actions`, `grid_diagnostics`.

### Gaps vs spec
1. **Not NL-authored as front door**: canvas loads `api.getRuns()` and shows the first run; there is no entry that takes an NL-authored community, shows the agent's plan + named rejections, confirms, then renders that community spatially. P1's `ScenarioGeneratorPage` (confirm gate → POST `/scenarios`) exists in isolation and is not wired into the canvas flow.
2. **Single-strategy only**: canvas renders one `currentRun`'s trajectories; no four-strategy side-by-side on the same community config.
3. **No honest-failure display per strategy**: canvas shows `currentStepData.grid_diagnostics` violations generically; there is no per-strategy compliance chip (ok/warning/failed), no violating-value + limit struck through, no failed run kept in view as a first-class state.
4. **Time playback exists but is single-run**: scrubber moves one run's steps; not shared across four strategy panels.

---

## Item 2 — Strategy comparison view (four strategies, same community)

Spec asks: rule-based / MPC / single-agent-RL / multi-agent-RL side by side on the same community: cost, carbon, grid compliance (import/export limits, voltage violations), dispatch behaviour per strategy; numbers trace to the frozen matrix record (83/67/0) and P1 corpus runs; honest-failure rule (failing run shown, not hidden).

### What exists today
- `frontend/src/pages/ComparisonPage.tsx` → `frontend/src/components/scenario/ScenarioComparison.tsx`: compares TWO runs (`runIdA`/`runIdB`) selected from `runs`; metric groups Energy&Cost / Service&Fairness / Grid Feasibility (total_cost, carbon_emissions_kg, grid_import_kwh, voltage_violations_count, max_voltage_pu, line/transformer loading, LMP metrics incl. OPF fallback steps); KPI summary cards (savings / service improvement / grid safety); export report; radar-chart stub behind `radarChart` feature flag (stub text only).
- `frontend/src/pages/Experiments.tsx`: mock experiment table (DEV-only mock data; controllers `rule_based/mpc/llm_agent/llm_agent_verified/centralized/multi_agent`; regimes `pool_tou/lmp/p2p`) — dev mock, not real data.

### Gaps vs spec
1. **Two runs, not four strategies**: ComparisonPage compares any two runs, not the four strategies on the same community config. No mechanism to run/render all four strategies on one config.
2. **No frozen matrix record**: metrics come from selected runs' `energy_metrics`/`service_metrics`/`grid_metrics`; the recorded level (83/67/0) is not referenced anywhere in frontend code; no quote of the record.
3. **No honest-failure rule**: failed/invalid runs render as `—` (null metric); no violating value + limit struck through; no compliance chip (ok/warning/failed, glyph + text); failed runs not kept in a ranking.
4. **No shared time scrubber + dispatch trace**: no per-strategy dispatch mini-chart; no aligned time scrub moving all four panels; no `DispatchTrace`, `StrategyPanel`, `ComplianceChip`, `MetricCell`, `StrategyMap` components (named in `docs/p2_strategy_comparison_design.md` §8).
5. **Defaults missing**: no default final-timestep scrub, no sort by cost/carbon/max-voltage, no equal-width panel rule.

---

## Item 3 — NL authoring flow as front door (plan + named rejections as first-class states)

Spec asks: P1's confirm flow (NL → plan → config → verified run) as front door, including confirmation interaction and named rejections as a first-class UI state.

### What exists today
- `frontend/src/pages/ScenarioGeneratorPage.tsx` (P1): NL description box → mock agent `ScenarioConfig` (pluggable `generateScenario` prop for Backend A's pipeline) → confirm screen with community summary cards, per-field provenance chips (given/assumed/default/missing, glyph + text), diff view vs default, validate-before-run (`GET /scenarios/{id}/validate`), `POST /sccenarios` run, rejection path naming the invalid field. Disclosure banner when mock active.
- `frontend/src/pages/ScenarioStudioPage.tsx` + `ScenarioEditor.tsx`: agent plan → code → execute → verify → report rail; `materializeScenario`; saved scenarios list.
- `frontend/src/pages/AgentWorkspacePage.tsx` + `AgentTimeline.tsx`: `TaskInput` + `AgentTimeline` (Planner→Coder→Executor→Verifier→Repairer→Reporter rail, compact + full/rail variants).
- Real rejection evidence: `/home/box/OpenBot/Shared/probe_out_full16c/r04_out_of_range_limit.json` — planner/coder/executor/verifier/reporter iteration outputs with `rejected_fields: ["buildings"]`, verification verdict `schema_valid: false`, error `community_import_limit_kw: Limits must be positive`, reporter `recommendation: "escalate"`; full corpus `c01..c12` plans + `r01..r04` rejection cases + `summary.json`.

### Gaps vs spec
1. **NL flow not the canvas front door**: CommunityCanvasPage starts from `api.getRuns()`; there is no path from an NL-authored community into a rendered spatial community with the agent's plan + rejections visible before running.
2. **Named rejections not first-class UI states**: probe corpus carries `rejected_fields`, verification verdicts, and escalation recommendations as data, but no frontend surface renders them as a named rejection state (canvas/comparison show metrics or `—`, never a "rejected field" state).
3. **Confirm interaction isolated**: P1's confirm screen exists under `/scenarios/generate` but is not linked into the authoring → canvas flow (no "author in NL → confirm → render spatially" single screen).

---

## Recommended first slice

Build **one acceptance-checkable slice**: the NL authoring front door → confirm → spatial render for ONE community, using the probe corpus as the data source (no recompute, no backend change).

Slice: a page (e.g. `/scenarios/author`) that
1. loads one probe corpus scenario config + its verification verdict (e.g. a successful `c0X` run and the rejected `r04_out_of_range_limit` to show both states),
2. renders the P1 confirm screen (community summary + provenance chips + validate-before-run + named rejection state),
3. on confirm, renders the community spatially using the EXISTING `CommunityCanvas` geometry (buildings as polygons from the scenario's `buildings[].location`, assets from `assets[]`, grid connection from `pandapower` bus_mappings — already supported by `CommunityCanvas` via `currentScenario` + `currentRun`),
4. shows the agent's plan + named rejection (from `reporter_output.plan.rejected_fields`, `verifier_output.schema_errors`) as a first-class UI state when the config failed validation.

Acceptance criteria:
- One screen: NL-authored config → confirm → spatial render, no recompute.
- Numbers trace to `probe_out_full16c` records (scenario_id + run id cited on screen).
- Named rejection rendered as glyph + text state when validation failed (never hidden or shown as a generic error).
- `tsc --noEmit` 0, `eslint --max-warnings 0`, `npm run build` 0 on the merged tree.

Not in scope this slice: four-strategy comparison panel, dispatch trace drawer, ComplianceChip/DispatchTrace/StrategyMap/StrategyPanel components (those are Item 2 build, spec'd in `docs/p2_strategy_comparison_design.md`).

---

## References
- `docs/p2_visualization_plan.md` (main @ 5cbbdc452082) — P2 scoping plan.
- `docs/p2_strategy_comparison_design.md` — four-panel comparison interaction spec (components: StrategyComparison, StrategyPanel, ComplianceChip, MetricCell, DispatchTrace, StrategyMap).
- `docs/nl_config_confirm_design.md` — P1 confirm interaction spec (already built in `ScenarioGeneratorPage`).
- `frontend/src/pages/CommunityCanvasPage.tsx`, `CommunityCanvas.tsx`, `MapLayers.tsx`, `TimePlayer.tsx` — existing spatiotemporal canvas to extend/re-frame.
- `frontend/src/pages/ComparisonPage.tsx`, `ScenarioComparison.tsx` — existing two-run comparison to extend/re-frame.
- `frontend/src/pages/ScenarioGeneratorPage.tsx` — P1 confirm gate to reuse as the front door.
- `/home/box/OpenBot/Shared/probe_out_full16c/` — P1 corpus: `c01..c12` plans/configs, `r01..r04` rejection cases, `summary.json`.
