# P2 — Spatiotemporal virtual-community visualization + strategy comparison (scoping)

Owner: Frontend Engineer (build) + Product Design Lead (interaction spec) · PM coordination
Date: 2026-11-12 · Status: scoping (no implementation authorized yet)

## What this phase is (from the project brief)

The platform is the product: an engineer describes a community in natural language,
the Coding Agent produces an executable sim config, the virtual community runs, and
the four control strategies are compared. P2 makes that visible:

1. **The virtual community itself** — buildings, on-site assets (PV / battery / EV /
   flexible load), the grid connection, in a spatial layout with time playback
   (the "spatiotemporal" part: the community's state over the simulated window).
2. **The strategy comparison view** — rule-based / MPC / single-agent-RL /
   multi-agent-RL side by side on the same community: cost, carbon, grid compliance
   (import/export limits, voltage violations), and the dispatch behaviour per strategy.
3. **The agent-assisted authoring flow, surfaced** — what P1 built end-to-end
   (NL → plan → config → verified run) shown as the front door, including the
   confirmation interaction (`docs/nl_config_confirm_design.md`) and the named
   rejections (the plan's refusal path is a first-class UI state, not an error page).

## What already exists (verify, don't assume)

The productization phase built `CommunityCanvasPage`, `ComparisonPage`,
`ScenarioStudioPage`, `ScenarioEditor`, `ParameterControls`, `Experiments`,
`Dashboard`. P2 is very likely EXTENSION and RE-FRAMING of those (to the four
strategies, the NL front door, the verification states), not a greenfield build.
Frontend's first deliverable is the honest inventory: what each existing page
renders today vs the three items above.

## Data the views consume

- Strategy comparison results of record (the frozen matrix record: 83/67/0 — quote
  from the benchmark records, never recompute).
- The P1 corpus runs (`/home/box/OpenBot/Shared/probe_out_full16c` and the other
  batches) for real scenario configs and their verification verdicts.
- The four strategy controllers (`src/controllers/`: rule_based, mpc, rl single,
  multi-agent) — the comparison view runs the same community through each.

## Acceptance shape (for the spec)

- A community authored in NL renders spatially within one screen of the authoring
  flow, with the agent's plan + the named rejections visible before running.
- The comparison view runs the four strategies on the same config and shows the
  recorded metrics side by side, with the grid-compliance violations the run
  actually surfaced (the honest-failure rule: a failing run is shown, not hidden).
- Every number on screen traces to a record (the same traceability discipline as
  the paper: no invented metrics).

## First deliverables

1. Frontend: the inventory + gap list (what exists, what's missing, per item above).
2. Product Design: the interaction spec for the comparison view (what makes the
   four strategies legible at a glance — the distinctive-interface brief).
