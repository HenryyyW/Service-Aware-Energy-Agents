# Frontend Design Plan: Spatio-Temporal Virtual Community Simulator

## Subject Matter & Audience
- **Product**: A virtual community simulator for renewable energy communities (buildings, PV, batteries, EVs, flexible loads)
- **Audience**: Energy researchers, grid operators, community energy planners, policy makers
- **Primary Job**: Enable users to design communities, run time-stepped simulations, observe spatial-temporal energy flows, validate grid constraints, compare scenarios, and interact with physics-grounded code agents

---

## Color Palette (4-6 Core Tokens)

| Token | Hex | Role | Rationale |
|-------|-----|------|-----------|
| `--color-space` | `#0A0F1A` | Deep space background | Night sky over a community; grounds the spatial canvas |
| `--color-surface` | `#111827` | Elevated surfaces, cards | Subtle elevation from base; readable in dark |
| `--color-surface-hover` | `#1A2235` | Hover states | Perceptible but not loud |
| `--color-border` | `#2D3748` | Dividers, outlines | Visible structure without contrast fatigue |
| `--color-text` | `#E8EBF0` | Primary text | High readability on dark |
| `--color-text-muted` | `#7A8494` | Secondary text, labels | Clear hierarchy |
| `--color-sun` | `#F59E0B` | PV generation, solar energy | The color of sunlight on panels—warm, energetic |
| `--color-energy` | `#10B981` | Battery discharge, grid export, positive flow | Green as "energy moving outward" |
| `--color-load` | `#F43F5E` | Building load, grid import, demand | Rose-red as "energy being consumed" |
| `--color-battery` | `#8B5CF6` | Battery SOC, storage | Violet as stored potential |
| `--color-ev` | `#06B6D4` | EV charging, mobility | Cyan as electricity in motion |
| `--color-grid` | `#EAB308` | Grid infrastructure, feeders, transformers | Amber as grid backbone |
| `--color-violation` | `#EF4444` | Voltage/loading violations | Clear danger signal |
| `--color-comfort` | `#22D3EE` | Thermal comfort, flexible loads | Cool cyan for comfort |

**Usage principle**: The canvas background is `--color-space`. The map/base layer uses subtle topography. Asset layers use their semantic colors (sun, energy, load, battery, ev, grid). Violations pulse with `--color-violation`. Text uses `--color-text`/`--color-text-muted`. No generic "primary/secondary/accent" — every color has a physical meaning.

---

## Typography

| Role | Font | Weights | Scale |
|------|------|---------|-------|
| **Display/Headlines** | `Space Grotesk` | 700, 500 | 48/56/64/72px — tight tracking (-0.02em) |
| **UI/Body** | `IBM Plex Sans` | 400, 500, 600 | 14/16/18/20px — normal tracking |
| **Monospace/Data** | `JetBrains Mono` | 400, 500 | 12/13/14px — for timesteps, values, code |

**Rationale**: Space Grotesk has a technical, engineered feel (grotesque with geometric bones) that suits a simulator. IBM Plex Sans is highly legible, neutral but not generic. JetBrains Mono for precise data readout. No serif — this is a technical instrument, not an editorial site.

**Type Scale** (following Elements of Typographic Style):
- Display XL: 72px / 80px, weight 700, tracking -0.02em
- Display L: 48px / 56px, weight 700, tracking -0.015em
- Display M: 32px / 40px, weight 600, tracking -0.01em
- Heading 1: 24px / 32px, weight 600
- Heading 2: 20px / 28px, weight 600
- Heading 3: 16px / 24px, weight 600
- Body LG: 18px / 28px, weight 400
- Body: 16px / 24px, weight 400
- Body SM: 14px / 20px, weight 400
- Caption: 12px / 16px, weight 500, uppercase, tracking 0.05em
- Data: 13px / 20px, weight 500 (monospace)

---

## Layout Concept

### High-Level Structure
```
┌─────────────────────────────────────────────────────────────────────┐
│  TOP BAR: Community name · Scenario · Connection status             │
├──────────────────┬──────────────────────────────────────┬──────────┤
│                  │                                      │          │
│  LEFT PANEL      │         CENTRAL CANVAS               │ RIGHT    │
│  (Collapsible)   │                                      │ PANEL    │
│                  │   ┌─────────────────────────────┐    │ (Context │
│  • Layer Tree    │   │   VIRTUAL COMMUNITY MAP     │    │  Dependent)│
│  • Asset List    │   │   (MapLibre + deck.gl)      │    │          │
│  • Filters       │   │                             │    │  • Asset  │
│  • Search        │   │   Buildings as extruded     │    │    Inspector│
│                  │   │   polygons                  │    │  • Time   │
│  [TIME PLAYER]   │   │   PV as rooftop layers      │    │    Series │
│  ──────────────  │   │   Batteries as icons        │    │  • Grid   │
│  ▶ ⏸ ⏮ ⏭       │   │   EVs as parking icons      │    │    Details│
│  Slider: 0-96    │   │   Feeders as lines          │    │  • Agent  │
│  Speed: 1x/2x/4x │   │   Violations as pulses      │    │    Log    │
│  ──────────────  │   │                             │    │          │
│                  │   └─────────────────────────────┘    │          │
│                  │                                      │          │
└──────────────────┴──────────────────────────────────────┴──────────┘
```

### Alignment Guidance
- **Canvas**: Center-aligned map viewport; UI panels left/right aligned to canvas edges
- **Top bar**: Left-aligned community identity, center-aligned scenario, right-aligned status/actions
- **Left panel**: Top-aligned, scrollable layer tree
- **Right panel**: Top-aligned, context-dependent content
- **Time player**: Fixed bottom-center, spanning full canvas width
- **All text**: Left-aligned in panels; map labels follow MapLibre conventions

### Responsive Breakpoints
- **Desktop (≥1440px)**: Three-panel layout as above
- **Tablet (1024-1439px)**: Left panel collapses to icon rail; right panel becomes bottom sheet
- **Mobile (<1024px)**: Single panel; canvas full-screen; panels as drawers/sheets

---

## Principles (What Makes This Unique)

1. **Space is the primary canvas, not charts** — The map is the hero. Charts are secondary, invoked from selection.

2. **Time is a first-class dimension** — The time player is always visible. Every view is time-aware. Scrubbing is instantaneous.

3. **Colors mean physics** — Sun = generation (amber), Load = consumption (rose), Battery = storage (violet), EV = mobility (cyan), Grid = infrastructure (amber-yellow). No decorative color.

4. **Violations are spatial events** — Voltage/loading violations appear on the map at their location, not just in a table.

5. **Agent workspace is a timeline, not a chat** — Show plan → code → execution → verification → repair as a horizontal timeline with evidence at each step.

6. **Scenario comparison is spatial-temporal** — Side-by-side map sync, or temporal diff on single map.

7. **No dashboard chrome** — No card grids, no KPI tiles unless explicitly requested. The map *is* the dashboard.

8. **Data density over whitespace** — This is an engineering tool. Information density is a feature. But: clear visual hierarchy, not clutter.

---

## Component Architecture (React + TypeScript)

### Pages (Routes)
| Route | Purpose |
|-------|---------|
| `/` | Community Canvas (default) |
| `/scenarios` | Scenario Studio |
| `/agent` | Agent Workspace |
| `/reports/:runId` | Report Viewer |
| `/compare/:runIdA/:runIdB` | Scenario Comparison |

### Core Components
```
src/
├── components/
│   ├── canvas/
│   │   ├── CommunityCanvas.tsx        # Main map viewport
│   │   ├── MapLayers/
│   │   │   ├── BuildingLayer.tsx      # Extruded polygons
│   │   │   ├── PVLayer.tsx            # Rooftop generation
│   │   │   ├── BatteryLayer.tsx       # Storage icons + SOC
│   │   │   ├── EVLayer.tsx            # Charging hubs + SOC
│   │   │   ├── FeederLayer.tsx        # Lines + loading
│   │   │   ├── TransformerLayer.tsx   # Substation icons
│   │   │   ├── ViolationLayer.tsx     # Pulsing alerts
│   │   │   └── FlowLayer.tsx          # Animated energy flows
│   │   └── TimePlayer.tsx             # Bottom-center playback
│   ├── panels/
│   │   ├── LayerTree.tsx              # Left panel - layer toggles
│   │   ├── AssetInspector.tsx         # Right panel - selected asset
│   │   ├── GridExplorer.tsx           # Right panel - grid details
│   │   ├── TimeSeriesChart.tsx        # Reusable chart (Plotly)
│   │   └── AgentTimeline.tsx          # Agent workspace - horizontal timeline
│   ├── scenario/
│   │   ├── ScenarioEditor.tsx         # YAML/JSON editor + form
│   │   ├── ParameterControls.tsx      # Sliders for PV, EV, battery, tariff
│   │   └── ScenarioComparison.tsx     # Diff view
│   ├── agent/
│   │   ├── TaskInput.tsx              # Natural language task
│   │   ├── PlanView.tsx               # Planner output
│   │   ├── CodeView.tsx               # Coder output (monaco)
│   │   ├── ExecutionLog.tsx           # Executor output
│   │   ├── VerificationView.tsx       # Verifier diagnostics
│   │   ├── RepairView.tsx             # Repairer patches
│   │   └── ReportView.tsx             # Reporter output
│   └── ui/
│       ├── Button.tsx
│       ├── Slider.tsx
│       ├── Select.tsx
│       ├── Tooltip.tsx
│       ├── Modal.tsx
│       └── Toast.tsx
├── hooks/
│   ├── useSimulation.ts               # WebSocket/SSE connection
│   ├── useTimePlayer.ts               # Playback state
│   ├── useScenario.ts                 # Scenario CRUD
│   └── useAgent.ts                    # Agent workflow state
├── store/
│   ├── canvasStore.ts                 # Map state, layers, selection
│   ├── simulationStore.ts             # Time, trajectories, current step
│   ├── scenarioStore.ts               # Scenarios, comparison
│   └── agentStore.ts                  # Agent workflow
├── api/
│   ├── client.ts                      # FastAPI client
│   ├── websocket.ts                   # Real-time updates
│   └── types.ts                       # Shared TypeScript types
├── styles/
│   ├── tokens.css                     # CSS custom properties
│   ├── globals.css                    # Reset, base, utilities
│   └── components.css                 # Component-specific
└── pages/
    ├── CommunityCanvasPage.tsx
    ├── ScenarioStudioPage.tsx
    ├── AgentWorkspacePage.tsx
    ├── ReportPage.tsx
    └── ComparisonPage.tsx
```

---

## Motion & Interaction

| Interaction | Motion |
|-------------|--------|
| Time scrubber drag | Instant frame update (no animation) |
| Play button | Smooth frame advance (configurable fps) |
| Layer toggle | 150ms fade + scale |
| Asset select | 200ms panel slide + map flyTo |
| Violation pulse | 1000ms infinite pulse (respects `prefers-reduced-motion`) |
| Energy flow particles | Continuous at 30fps (pause on hover) |
| Agent timeline step reveal | Staggered 100ms per step |
| Panel open/close | 250ms spring |

**Reduced motion**: All non-essential motion disabled; time player shows discrete steps; violations show static alert icons.

---

## Accessibility

- Full keyboard navigation (Tab, Arrow keys for time player, Escape to close panels)
- Visible focus rings (2px `--color-sun` offset 2px)
- ARIA labels on all icon buttons
- Semantic HTML structure (main, aside, nav, section)
- Color-blind safe palette (verified with Coblis)
- Screen reader announcements for time changes, violations, agent steps
- High contrast mode support via `@media (prefers-contrast: high)`

---

## Review Against Brief

| Brief Requirement | Design Decision |
|-------------------|-----------------|
| Virtual community canvas (2.5D map) | MapLibre + deck.gl extruded polygons |
| Time player with play/scrub/step | Fixed bottom-center, full-width slider |
| Asset inspector on click | Right panel context panel |
| Grid explorer with voltage/loading | Dedicated grid layer + right panel |
| Energy flow visualization | Animated particle flows + Sankey in inspector |
| Scenario editor | YAML + form hybrid in Scenario Studio |
| Agent workspace as timeline | Horizontal timeline with evidence |
| Spatial representation per asset | Extruded buildings, rooftop PV, icons for BESS/EV |
| Heatmaps for voltage/loading | Deck.gl heatmap layers |
| Scenario comparison | Side-by-side synced maps or temporal diff |
| Reproducible reports | Markdown/PDF export from agent reporter |

**No generic defaults used**: No SaaS cards, no cream/terracotta, no ALL-CAPS labels, no numbered markers, no gradient washes, no fade-slide-up on everything.

---

## Implementation Priority

1. **Core canvas + time player + MapLibre base** (Week 1)
2. **Asset layers (buildings, PV, battery, EV, feeder)** (Week 1-2)
3. **Time-series data binding + asset inspector** (Week 2)
4. **Grid layer + violation visualization** (Week 2-3)
5. **Scenario Studio** (Week 3)
6. **Agent Workspace timeline** (Week 3-4)
7. **Reports + Comparison** (Week 4)
8. **Polish, accessibility, performance** (Week 4-5)