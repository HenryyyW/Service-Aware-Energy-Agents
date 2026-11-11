# P2 — Strategy Comparison View (interaction spec)

Owner: Product Design Lead (spec) · Frontend Engineer (build) · Date: 2026-11-12
Status: spec delivered for build; awaiting P1 pipeline verification per Project Partner
Source: docs/p2_visualization_plan.md (main @ 5cbbdc452082); Grounded in src/controllers/ (rule_based, mpc, rl, multi_agent), backend/app/routers/scenarios.py, backend/app/routers/simulations.py, experiments/make_figures.py (F1/F3 figure patterns)

---

## 1. Goal

The comparison view runs the **same community config through four control strategies** — **rule-based, MPC, single-agent-RL, multi-agent-RL** — and presents cost, carbon, and grid compliance side by side so an engineer can see at a glance **which strategy wins on what, and where any of them fails**.

Governing rules (from p2_visualization_plan.md):
- **Same community config** across all four strategies — nothing is recomputed; metrics come from the frozen matrix record (83/67/0) and P1 corpus runs.
- **Honest-failure rule**: a failing run is shown, never hidden. A strategy that did not converge or breached an import/export limit is rendered as a failed state, not omitted.
- **Traceability**: every number on screen traces to a record (run id → /simulations/{run_id} → /reports/{run_id}); no invented metrics.

---

## 2. What is compared

| Dimension | Strategies compared | Metric (unit) | Source record |
|-----------|--------------------|---------------|---------------|
| Cost | all four | total_cost ($) | EnergyMetrics.total_cost |
| Carbon | all four | carbon_emissions_kg (kg) | EnergyMetrics.carbon_emissions_kg |
| Grid compliance — import | all four | grid_import_kwh vs import_limit_kw | GridMetrics.grid_import_kwh + EnergySharingConfig.import_limit_kw |
| Grid compliance — export | all four | grid_export_kwh vs export_limit_kw | GridMetrics.grid_export_kwh + EnergySharingConfig.export_limit_kw |
| Grid compliance — voltage | all four | voltage_violations_count + max_voltage_pu vs [0.95, 1.05] pu | GridMetrics.voltage_violations_count / max_voltage_pu |
| Dispatch behaviour | all four | per-timestep battery/EV/flex action (kW) | grid_diagnostics.jsonl trajectories |

The four strategies are the **only** candidates. There is no "baseline vs everything else" — each strategy stands on the same community config, and the view makes that explicit so no strategy looks like it ran on an easier community.

---

## 3. Layout — four side-by-side panels

Single viewport, **four equal vertical panels** (one per strategy), all locked to the **same time axis**. Each panel:

```
┌─────────────────────────────┐
│  rule_based        [● ok]   │  ← header: strategy name + compliance chip
├─────────────────────────────┤
│  KPI strip: $… | kg… | kWh   │  ← three headline metrics
├─────────────────────────────┤
│  [map]: spatial layout      │  ← buildings + assets + grid connection
│  + time scrubber            │  ← shared across all four panels
└─────────────────────────────┘
```

- **Header**: strategy name + compliance chip (ok / warning / fail — see §5). The chip is a glyph + text pair, never color-only.
- **KPI strip**: three headline metrics — total cost ($), carbon (kg CO₂), grid import (kWh vs limit). Each shows the value with its limit in parentheses when applicable (`$1,842` / `import 480/500 kWh`).
- **Map panel**: spatial layout of the community (buildings as polygons, PV/battery/EV/flexible-load as icons, grid connection as feeder lines), colored by the strategy's dispatch at the current time step. Uses the existing CommunityCanvas geometry (schematic until surveyed coordinates exist — same constraint as the rest of the frontend).
- **Time scrubber**: shared across all four panels; one scrub moves all four. Discrete steps matching the sim window (15 min default).

Below the four panels (or in a toggleable drawer): **dispatch trace** — per-timestep battery charge/discharge, EV charge, flexible load on/off for the selected strategy, as a small multiple (four mini line charts, one per strategy, aligned in time). Clicking a point in the trace scrubs all four maps to that time step.

Layout rule: the four panels are **equal width and equal height** — no panel is enlarged to "look important". Importance is conveyed by the compliance chip and color, not by panel size. This is what distinguishes the view from a generic dashboard where one KPI tile dominates.

---

## 4. Defaults

- **Active metric for sorting**: total cost ($) — lowest first. User can re-sort by carbon or max voltage violation; the panel order follows the sort, but the four strategies stay visible (no strategy is dropped from the view).
- **Default time step**: the final timestep of the window (end state), with the scrubber at the right edge; dragging left shows earlier states in all four panels simultaneously.
- **No strategy pre-selected**: all four are always visible. "Selection" means highlighting one panel's dispatch trace in the trace drawer, not hiding the others.

---

## 5. Compliance states (honest-failure rule)

Each strategy panel carries a compliance chip with glyph + text:

| Chip | Meaning | When shown |
|------|---------|------------|
| ✓ compliant | All grid constraints satisfied; run completed | grid_import_kwh ≤ import_limit_kw AND grid_export_kwh ≤ export_limit_kw AND voltage_violations_count = 0 AND run status = completed |
| ⚠ warning | Run completed but at/near a limit | any constraint within 5% of its limit, OR OPF fallback steps > 0, OR power_flow_convergence_rate < 100% |
| ✗ failed | Run did not complete or breached a hard limit | run status ≠ completed, OR grid_import_kwh > import_limit_kw, OR grid_export_kwh > export_limit_kw, OR voltage_violations_count > 0 |

**Hard limits are never silently exceeded.** If grid_import_kwh > import_limit_kw, the panel shows the actual import value in red text with the limit struck through (`520` / `500 kW`), and the dispatch trace for that strategy stops at the failure timestep with a vertical marker. The failed run remains in the side-by-side; it is not replaced by a "no data" placeholder or omitted from the ranking.

The compliance chip is always a glyph + text pair (✓ compliant / ⚠ warning / ✗ failed) so the state survives grayscale printing and color-blind users. Color is used only as reinforcement (green/gray/red tints on the chip background), never as the sole signal.

---

## 6. Traceability — every number traces to a record

Every metric cell carries a small **"open record"** affordance (an external-link icon next to the value) that links:
- Run total → `/simulations/{run_id}` (run summary)
- Grid metrics → `/reports/{run_id}` (report artifact)
- Per-timestep dispatch → the corresponding entry in `grid_diagnostics.jsonl` for that run

The strategy comparison never shows a number that lacks a record path. If a strategy's metrics are missing from the frozen record (e.g., a run that never executed), the panel shows `—` with the text **"no record"** — never a zero, never an estimate, never a blank that looks like zero.

Unit discipline: cost in `$`, carbon in `kg CO₂`, power in `kW`, energy in `kWh`, voltage in `pu`, time in the sim's timestep minutes (15 default). Units are printed once per panel group, not repeated per cell, and never abbreviated ambiguously (`kW` not `kw`, `kg CO₂` not `emissions`).

---

## 7. What distinguishes this from a generic dashboard

| Generic dashboard | This view |
|-------------------|-----------|
| KPI tiles of mixed provenance | Four strategies, same community config, identical layout |
| One "winner" highlighted by size/color | All four strategies equally visible; importance via compliance chip only |
| Single time snapshot | Shared time scrubber across all four strategies |
| Metrics invented by the frontend | Every number traces to /simulations/{run_id} or /reports/{run_id} |
| Failures hidden or shown as "error" | Failed runs shown with the violating value and limit struck through |
| Aggregates only | Per-timestep dispatch trace available per strategy |

The map is the hero within each panel (spatial layout of the actual community), not a decorative icon strip. Charts exist only where they add information the map cannot show (the dispatch trace over time).

---

## 8. Components (Frontend build targets)

| Component | Responsibility |
|-----------|----------------|
| `StrategyComparison` | Shell: four panels + shared time scrubber + trace drawer toggle |
| `StrategyPanel` | One strategy: header + compliance chip + KPI strip + map + dispatch mini-chart |
| `ComplianceChip` | Glyph + text + optional tint badge; disabled state shows `— no record` |
| `MetricCell` | Value + unit + limit + external-link affordance |
| `DispatchTrace` | Four aligned mini line charts (one per strategy), shared time scrubber |
| `StrategyMap` | Reuse CommunityCanvas geometry: buildings + assets + feeder lines, colored by dispatch at current step |

No new physics colors: reuse the existing domain palette (PV amber, load rose, battery violet, EV cyan, grid amber-yellow, violation red) for the map; the strategy chips use the neutral design-system palette, not physics colors.

---

## 9. Acceptance criteria

- [ ] Four strategies shown side by side on the same community config; no strategy omitted when it fails.
- [ ] Cost, carbon, and both import/export limits displayed per strategy with units.
- [ ] Voltage violations shown as count + max pu vs [0.95, 1.05] pu.
- [ ] Honest-failure rule verified: a run that breached a hard limit shows the violating value and limit struck through; remains in the ranking.
- [ ] Every metric cell has an "open record" link to /simulations/{run_id} or /reports/{run_id}.
- [ ] Shared time scrubber moves all four panels; dispatch trace follows the scrub.
- [ ] Compliance chip is glyph + text; survives grayscale and color-blind simulation (Coblis check).
- [ ] Layout is four equal panels; no strategy enlarged by default.

---

## 10. Open items (decisions, not specs)

- Whether the four-panel layout switches to a vertical stack below ~1024 px (tablet) — to be decided with Frontend during build; the equal-panel rule applies to both layouts.
- Whether the dispatch trace drawer opens below or to the right of the panels — Frontend's call, but it must not cover any panel.
