# Phase 6 regression verification — main @ `e943c1d9c`

QA/DevOps, 2026-11-12. Scope: HEAD regression gates, closed-loop smoke on a
local backend, performance load magnitude. Isolated worktree at exactly
`e943c1d9c`; no product code modified.

## 1. HEAD regression gates

| Gate | Result | Detail |
|---|---|---|
| pytest | **518 passed, 0 failed** (159.3 s) | Matches the previous count (518) exactly; 11 warnings |
| black | ✓ | CI scope (`src/ tests/ experiments/ scripts/ backend/`), 170 files |
| ruff | ✓ | Same CI scope, 0 errors |
| tsc --noEmit | ✓ | 0 errors |
| eslint | ✓ | 0 errors |
| vite build | ✓ | dist 3.0 MB |

**Non-gating note (outside CI's ruff scope):** 10 ruff errors in `docs/`
analysis scripts — `docs/build_raw_results.py` (F841), `docs/m2b_pilot_analysis.py`
(4×), `docs/reviewer_response/code_repair_analysis.py` (3×),
`docs/reviewer_response/e1_safety_stratification.py` (F401). Owner: Research
Engineer; CI does not gate on `docs/`, so main stays green.

## 2. Closed-loop smoke (local backend, standalone uvicorn, no Redis —
BackgroundTasks execution path)

LLM environment: `AGENT_BACKEND=api:poolside/laguna-xs-2.1` + NIM endpoint +
key-store credential (the `run_p1_probe.py` shared-key-store pattern).
**NIM was reachable** during this run (2026-11-12); the 11-11 downtime did
not recur. Without the env vars the pipeline falls back deterministically in
0.03 s (`plan_source=rule_based_fallback`) — verified, working as designed.

| Step | Call | Result |
|---|---|---|
| generate | `POST /api/scenarios/generate` {nl, max_iterations=2} | 200, **13.5 s**, `plan_source=llm`, verdict `accept`, **7 rejected/defaulted fields** (pv.capacity_kw, battery.capacity_kwh/power_kw, evs.capacity_kwh/max_charge_kw/arrival_time/departure_time), config produced with **4 buildings**. `success=False` reflects the rejected fields the confirm step exists for — not a pipeline failure. |
| confirm | `POST /api/scenarios` with the generated config | **201**, scenario_id `phase6_smoke` |
| confirm | `GET /api/scenarios/phase6_smoke/validate` | 200, `valid=True`, 0 errors, 0 warnings |
| run | `POST /api/simulations` {rule_based, 24 steps, seed 42} | 201, run `run_478194f37769`, terminal `completed` in ≤3 s; `voltage_violations_count=0` (default loose limits); top-level `total_cost` absent |
| compare | `POST /api/simulations/strategy-comparison` {seed 42, 24 steps} | 200 — **4 strategies with actual records**: `mpc`, `multi_agent_rl`, `rule_based`, `single_agent_rl`, all terminal `completed`, all with real `grid_metrics` (voltage/line/trafo from pandapower) |
| diagnose | `GET /api/simulations/{run_id}/diagnostics` | 200, 0 findings, kpi_summary populated (7 keys), interpretation "No constraint violations were recorded in this run." |

### Defects found (recorded honestly, not fixed — owners notified)

- **F1 — economics placeholders (Backend B):** `energy_metrics` is **all
  0.0** for all four strategies (`total_cost`, `grid_import_kwh`,
  `pv_generation_kwh`, `battery_throughput_kwh`, `carbon_emissions_kg`,
  `peak_demand_kw`). A 24-step, 4-building community run with zero energy
  flow is not a real result: the energy/KPI accounting does not reach the
  comparison-path API payload. Corroborated by the `!!! COST NOT FOUND IN
  INFO !!!` / `Info keys: []` lines in CI backend logs. The comparison
  surface therefore cannot show meaningful strategy economics yet; per the
  no-substitution rule, the runs are reported as recorded (0.0), flagged as
  placeholders.
- **F2 — trajectories endpoint 500 (Backend A/B):** `GET
  /api/simulations/{run_id}/trajectories` → **500** with
  `ValueError: Out of range float values are not JSON compliant` (NaN/Inf in
  the serialized payload). The canvas and trajectory views consume this
  endpoint and will error on such runs. Reproducible on both the comparison
  runs and the plain run above.
- **F3 — non-gating:** the `docs/` ruff errors listed in §1.

## 3. Performance load magnitude (build-level proxy)

- Initial JS: `index` 438.7 KB raw / **117.2 KB gz**, `vendor` 164.2 / 53.5,
  `ui` 25.3 / 5.6; CSS 77.7 / **14.1** → **≈ 190 KB gz initial load**.
- **No route-level code splitting**: all pages (canvas, comparison,
  generator) ship in one index chunk — fine at this size, worth revisiting
  when the canvas grows.
- dist total 3.0 MB (1.6 MB of that is source maps, not shipped to users).
- Lighthouse not run this session (needs a served build + browser);
  build-level numbers above are the recorded magnitude, labeled as such.

## 4. Known gaps (from the Partner's own audit, not re-verified here)

- `CommunityCanvasPage` not routed (Frontend task in flight).
- Canvas has no table-alternative view.
- README/brief 5-commit drift behind `e943c1d9c` (Partner syncing
  `mvp_status_baseline.md`).

## Verdict

HEAD @ `e943c1d9c`: **all CI-scoped gates green, 518/518 tests, closed loop
mechanically functional end-to-end with the LLM planner live.** The loop's
weak layer is the economics payload (F1) and the trajectories serializer
(F2) — both recorded for the owning engineers; neither blocks the loop
mechanics.
