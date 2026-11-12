# P1 — NL → ScenarioConfig confirmation interaction: confirm-then-run flow spec

Owner: Product Design Lead · Date: 2026-11-12 · Status: built & QA-verified (main @ de884c091)
Recipient: Frontend Engineer 2 (builds this); contract owner: Backend (existing `/scenarios` router, unchanged).
Companion: `docs/nl_config_confirm_design.md` (confirm-screen UX: provenance chips, diff, rejection path).

---

## Decision: Candidate A — confirm = create scenario, launch run from details page

**Decision: Candidate A.** The confirm screen creates the scenario (`POST /scenarios` → 201) and navigates to the scenario details page; running the simulation is a separate, explicit action on the details page.

**Why A over B (confirm = launch run directly):**
- The confirm screen's job is config review ("did the agent get my intent right?"). It must remain a pure review gate, not conflated with "spend compute to run." Running consumes compute and produces decision-relevant results — it deserves its own explicit act.
- Approving a config and executing it are two different commitments. Separating them respects that.
- The scenario details page is the natural run-control center: validate → run → monitor progress → view diagnostics → onward to canvas / comparison / report.
- No rework: P1 already built and QA-verified on `main` — commit `edea241e5` (11-11, mock removed, real `api.generateScenario` wired); QA smoke end-to-end: generate 13.5s → confirm 201 → run completed → four-strategy comparison 4 records → diagnostics 200; report docs/qa/phase6_regression_report.md, QA PR #64.

## State transition — user journey

```
NL task
   │  generateScenario (POST /scenarios/generate)
   ▼
┌──────────────┐
│ Generator    │  input: describe community in NL → agent parses to ScenarioConfig
│   (input)    │  Shows: provenance chips (given/assumed/default/missing, glyph+text),
│              │           rejected fields named inline
└──────┬──────┘
       │ generateScenario → setStep('confirm')
       ▼
┌──────────────┐
│ Confirm      │  Review the generated config before running.
│   screen     │  Community summary: buildings w/ PV/battery/EV/flexible loads,
│              │           tariffs, weather, grid, sim window/timestep.
│              │  Field-level diff vs existing scenario (if editing).
│              │  Validate now (GET /scenarios/{id}/validate): block Run if invalid.
│              │  Buttons: Edit & reject (re-parse agent, pre-filled retry) |
│              │           Run scenario (primary, POST /scenarios → 201)
└──────┬──────┘
       │ Run scenario (POST /scenarios → 201 + scenario_id)
       ▼
┌──────────────┐
│ Scenario     │  detail page = run-control center
│   Detail     │  Shows config + validation badge:
│   (run       │    • "Validated — ready to run" (green) when valid === true
│   control)   │    • error list naming fields when invalid (Run disabled)
│              │  Buttons: Run simulation (POST /simulations) | Cancel (while running)
│              │  Run lifecycle polled every 2 s: pending → running → completed/failed/cancelled
│              │  glyph (…/▶/✓/✗/■) + stage + progress % + eta + outcome_sentence
│              │  On completed: diagnostics (findings + KPI summary) + interpretation
│              │  Onward links: Community Canvas (spatial map + time scrubber),
│              │           Strategy Comparison (4 strategies side by side),
│              │           Download report (Markdown + JSON)
└──────┬──────┘
       │ Run simulation (POST /simulations)
       ▼
┌──────────────┐
│ Run in       │  status glyph + stage + progress % + eta_seconds, updating live
│   progress   │  Cancel available while running
│   (polling)  │  On failed: error + reason + "retry" (run deduplicated by config+seed)
└──────┬──────┘
       │ completed
       ▼
┌──────────────┐
│ Run results  │  diagnostics findings + KPI summary + interpretation
│              │  Onward: Canvas / Comparison / Report download
└──────────────┘
```

## Contract (backend, unchanged — no new endpoints)

| Step | Endpoint | Method | Purpose |
|------|----------|--------|---------|
| Generate config | `/scenarios/generate` | POST | NL → ScenarioConfig + provenance + rejected_fields |
| Create scenario | `/scenarios` | POST | Persist ScenarioConfig → 201 + scenario_id |
| Validate | `/scenarios/{scenario_id}/validate` | GET | `{valid, errors, warnings}` — block Run if invalid |
| Start run | `/simulations` | POST | `{scenario_id, controller_type, ...}` → run_id |
| Get run | `/simulations/{run_id}` | GET | status/stage/progress/eta_seconds/outcome_sentence/error/controller_type |
| Run diagnostics | `/simulations/{run_id}` | GET | findings + KPI summary + interpretation |

## Component inventory (Frontend build targets)

| Component | Responsibility |
|-----------|----------------|
| ScenarioGeneratorPage | input (NL entry) → confirm screen (provenance chips, diff, validate-before-run, Edit & reject / Run) |
| ScenarioDetailPage | config + validation badge + Run simulation button + run lifecycle + diagnostics + onward links |
| CommunityCanvasPage | spatial map + time playback (P2 reuse) |
| ComparisonPage | four-strategy side-by-side comparison (P2) |
| ReportPage | report download (Markdown + JSON) |

## Acceptance criteria (Frontend)

An uninvolved developer should walk this end-to-end without changing code:

1. **Generate**: Paste NL text → `POST /scenarios/generate` → confirm screen shows community summary with provenance chips (`given`/`assumed`/`default`/`missing`, glyph + text, never color-only).
2. **Confirm**: Click "Run scenario" → `POST /scenarios` → 201 → navigate to `/scenarios/{scenario_id}` detail page.
3. **Validate**: Detail page shows validation badge ("Validated — ready to run" or error list naming fields). Run button disabled until `valid === true`.
4. **Launch**: Click "Run simulation" → `POST /simulations` → status `pending → running`, progress polls every 2 s.
5. **Playback**: While running/cancelled/completed, status glyph + stage + progress % + eta update live; Cancel available while running.
6. **Complete**: On completed → outcome_sentence + diagnostics (findings + KPI summary) + interpretation text.
7. **Compare → Canvas → Report**: From results, navigate to Community Canvas (spatial map + time scrubber), Strategy Comparison (4 strategies side by side), Report (download Markdown + JSON).
8. **Rejection path**: If `validate` returns invalid OR user clicks Edit & reject → return to input with the invalid field named + pre-filled retry ("Fix <field>: <detail>").
9. **No silent corrections**: rejected/defaulted fields always named inline; never auto-corrected.

## Open item (decision, not a blocker)

Whether, after Run starts, the details page auto-navigates to the Community Canvas once the run completes, or stays on the detail page with canvas/comparison as onward links. Spec'd as detail page first (run-control center), onward links secondary. Revisit with Frontend during build if the detail page feels redundant.
