# P1 — NL → ScenarioConfig confirmation interaction (design spec)

Owner: Product Design Lead · Date: 2026-11-10 · Status: ready for build
Recipient: Frontend Engineer (builds this); contract owner: Backend (existing `/scenarios` router, unchanged).
Source of truth: `src/schemas/scenario.py` (`ScenarioConfig`, `BuildingConfig`, `TariffConfig`, `PandapowerConfig`, …), `backend/app/routers/scenarios.py` (`POST /scenarios`, `PATCH /scenarios/{id}`, `GET /scenarios/{id}/validate`).

---

## Goal

After the coding agent parses an NL task into a `ScenarioConfig`, the engineer **confirms before it runs**. The confirm screen must show:

1. **Readable summary** of the parsed community — buildings with PV/battery/EVs/flexible loads, tariffs, weather, grid.
2. **Diff vs. existing scenario** when editing (field-level: changed / added / removed).
3. **Confidence per field** — which values are agent-inferred or defaulted (efficiency 0.95, SOC 0.5, timestep 15 min, azimuth 180, …), visually distinct from user-provided facts.
4. **Rejection path** — missing/invalid field named inline, with an actionable retry that pre-fills the correction.

Never run a scenario the engineer hasn't seen and approved. The confirm screen is a gate, not a toast.

---

## Interaction model

```
NL task  →  Coding Agent → ScenarioConfig  →  [Confirm screen]  →  POST /scenarios  →  run
                                  ↘  edit / reject → PATCH /scenarios  →  re-confirm
```

- Gate is modal (dialog) or full-page, triggered after agent parsing completes and **before** any run starts.
- Two buttons at the bottom: **Run scenario** (primary, brand color) and **Edit / reject** (secondary).
- On rejection, the agent gets the named field + user correction and re-parses; the confirm screen re-renders with the new config.
- Edit mode: same screen, inline editable fields + diff highlight; saving posts `PATCH /scenarios/{id}` then re-validates.

---

## Component layout (two panels)

**Left — community summary (scannable, ~40% width)**

| Card | Content |
|------|---------|
| Community | name, description, simulation window (start → end), timestep (min), random seed |
| Buildings | per building: ID, type, location (lat/lon/timezone), on-site assets |
| PV | per building: capacity_kw, azimuth, tilt, efficiency, inverter_efficiency |
| Battery | per building: capacity_kwh, power_kw, soc_min/max, initial_soc |
| EV | per building: count, capacity_kwh, max_charge_kw, arrival → departure, target_soc |
| Flexible load | per building: power_kw, energy_kwh, earliest_start → latest_end, duration_h |
| Tariff | per building: type, import/export price periods, demand_charge |
| Grid | pandapower network_type, voltage limits, line/transformer loading limits, import/export limit (kW), weather file |
| Sharing | energy_sharing.enabled, market_type, settlement_interval (if present) |

Each field row: **label** (left) | **value** (monospace, right) | **confidence chip** (right). Defaulted/uncertain fields get a muted chip: `assumed` / `default` with a tooltip: *"Agent assumed X because the NL task didn't specify it — edit if wrong."*

**Right — preview & diff (when editing)**

- Tabs: Summary | Diff | JSON (raw ScenarioConfig, collapsible).
- Diff view: field-level rows with `+` / `-` / `~` glyphs + color (added green-ish tint, removed red-ish tint, changed yellow-ish — but never color-only; each change also has an icon: plus/minus/arrows and the old → new values side by side).
- Show only changed fields by default; toggle "show unchanged".

**Bottom — action bar (sticky)**

- Primary: `Run scenario` → `POST /scenarios` (or `PATCH /scenarios/{id}` in edit mode) → on 201/200, navigate to the run / canvas.
- Secondary: `Edit & reject` → open inline edit / re-send to agent with named field.
- Link: `Validate now` → `GET /scenarios/{id}/validate`; show errors/warnings inline before running (validate first, block run if `valid === false`).

---

## Confidence display (uncertainty)

For every field, tag its provenance:

| Provenance | Chip | Color (theme-neutral) | Example |
|------------|------|----------------------|---------|
| User-provided (from NL) | `given` | neutral ink | building_id, capacity_kw when stated |
| Agent-inferred | `assumed` | muted | azimuth 180, tilt 30 |
| Schema default | `default` | muted | efficiency 0.95, soc_min 0.1, timestep 15 min |
| Missing but required | `missing` | red outline + icon | `tariff` on a building with load but no price |

Confidence is **never color-only**: every chip carries a glyph (✓ given, ~ assumed, ↻ default, ! missing) and text. Hover tooltip explains source: *"Not in the NL task — assumed south-facing (azimuth 180°). Edit if the roof faces otherwise."*

Missing required fields (per `validate_scenario`: no buildings, unusual timestep, missing pandapower warning) block **Run scenario** with an inline error: *"Missing: buildings — the agent didn't parse any buildings from your task. Retry with: 'Add 3 residential buildings with PV…'"* — the retry text is pre-filled into the agent chat input.

---

## Rejection path

1. Validation fails (`valid === false`) OR engineer clicks **Edit / reject**.
2. Inline error names the field: `"pv.capacity_kw: missing on building_2"`.
3. Retry button: "Retry with fix" — pre-fills the agent chat (or a text field) with: *"Fix pv.capacity_kw on building_2: add a 5 kW PV system."*
4. Agent re-parses → new ScenarioConfig → confirm screen re-renders with the diff highlighted against the rejected version.
5. If validation passes but engineer still rejects: same edit flow via PATCH.

Never silently drop or auto-correct a field.

---

## Tokens & styling (do not invent new colors)

Reuse `frontend/src/styles/tokens.css` (additive, no existing token changes):

| Use | Token |
|-----|-------|
| Surface / cards | `--color-surface`, `--color-surface-hover` |
| Text | `--color-text`, `--color-text-muted`, `--color-text-subtle` |
| Border | `--color-border`, `--color-border-strong` |
| Primary action | `--color-primary` (GE `#005e60` / Schneider `#2e9e45` per theme) |
| Confidence chips | `--color-text-muted` (given), `--color-sun` (assumed), `--color-grid` (default), `--color-violation` (missing) — all with glyph + text |
| Diff | added/removed/changed via glyph + label + subtle bg (`--color-state-hover`); never hue-only |

Icons from `lucide-react`: `Building2` (building), `SolarPanel`/`Sun` (PV), `Battery` (battery), `Car` (EV), `Zap` (load), `FileText` (tariff), `Network` (grid), `AlertCircle` (missing), `CheckCircle` (given), `GitCompare` (diff), `RotateCcw` (retry).

Responsive: single column below 1024 px (summary stacks above diff), full-width on mobile.

---

## Acceptance criteria

- [ ] Every parsed field shows value + provenance chip; defaulted/assumed fields visibly distinct from given.
- [ ] Diff mode shows field-level changes vs. existing scenario (added/removed/changed, old → new).
- [ ] `Run scenario` disabled when `validate` returns `valid === false`; error names the field.
- [ ] Reject → retry pre-fills the agent correction naming the invalid field.
- [ ] Edit saves via `PATCH /scenarios/{id}`, then re-validates and re-shows the confirm screen.
- [ ] No color-only meaning; all chips carry glyph + text; keyboard navigable; ARIA labels on icon buttons.
- [ ] Works in all three themes (GE Vernova / Schneider / dark canvas).

---

## What the Frontend Engineer builds

1. `ConfirmScenarioModal` (or full-page route `/scenarios/new/confirm`) triggered after agent parse.
2. Calls `POST /scenarios` (new) or `PATCH /scenarios/{id}` (edit) with `ScenarioConfig` body; reads `GET /scenarios/{id}/validate` before enabling Run.
3. Diff computed client-side between stored scenario (from `GET /scenarios/{id}`) and parsed config, field-by-field at the `ScenarioConfig`/`BuildingConfig` depth.

Open question to close with Backend: does `POST /scenarios` accept the full `ScenarioConfig` JSON as-is (currently `scenario_data: dict`)? Confirm before building so the confirm screen submits the exact shape.
