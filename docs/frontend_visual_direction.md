# Frontend visual direction — enterprise industrial (Schneider / GE)

Owner: Product Design Lead · Date: 2026-11-02
Request: "make the UI look like Schneider or GE — those electrical-giant products."
Mockup: `docs/mockups/enterprise_ui_mockup.html`

## Subject, audience, job

Community-energy simulator used by **grid operators, energy planners, researchers** to design a
community, run time-stepped simulations, check grid constraints, and compare pricing regimes. The
job is operational: read dense data, spot a violation, decide. That is **industrial software**, not
a consumer dashboard — so the visual language should be the one Schneider EcoStruxure and GE
Digital/Vernova use: light, dense, restrained, and legible in an office or a control room.

## The direction (one paragraph)

**Light enterprise chrome, deep evergreen primary, one lime accent, neutral grays, data-dense.**
White/`#fafafa` surfaces, hairline `#e3e3e3` borders, near-black `#212121` text, a left icon rail, a
breadcrumb header, KPI cards, and dense tables with tabular numerals. Accent is used sparingly — for
the primary action, active nav, and focus — never as decoration. The map stays the hero of the canvas
view but sits in the same disciplined chrome.

## Palette — grounded in GE Vernova's own tokens

Pulled from `gevernova.com` CSS (`:root` Gutenberg palette on 2026-11-02), which serves as the
"GE" reference. Schneider's language is the same family with a green primary instead of evergreen.

| Role | Token | Value | Source |
|---|---|---|---|
| Primary / brand | `--brand` | `#005e60` | GE `ge-evergreen` |
| Primary dark (hover) | `--brand-dark` | `#004a4c` | derived |
| Accent (sparingly) | `--accent` | `#c8ff08` | GE `ge-urgency-green` |
| Ink / text | `--ink` | `#212121` | GE `ge-night` |
| Muted text | `--muted` | `#696969` | GE `ge-gray-4` |
| Surface | `--surface` | `#ffffff` | GE `ge-day` |
| App background | `--bg` | `#fafafa` | GE `ge-gray-1` |
| Hairline border | `--line` | `#e3e3e3` | GE `ge-gray-2` |
| Border strong | `--line-strong` | `#cccccc` | GE `ge-gray-3` |
| Data series | `--sky` `--forest` `--earth` | `#59c3c9` `#75ca64` `#bfa682` | GE palette |
| Ok / warn / fail | | `#0a7d72` / `#b7791f` / `#b3261e` | restrained status |

- **Schneider variant:** swap primary to Schneider green (`--brand ≈ #3DCD58`, dark `#2AA544`) on the
  same light chrome; everything else identical. (Schneider hex to be confirmed from their brand kit.)
- **Physics colors stay meaningful** for the map/energy encoding (PV, load, battery, EV, feeder); they
  are *data* colors and coexist with the brand chrome — they do not tint the chrome.

## Typography

- **UI/body:** a neutral humanist sans — Segoe UI / Inter / system stack (GE Vernova uses "Sons" for
  display; we approximate with system sans). Headings 600, body 400/500.
- **Data/numbers:** monospace (JetBrains Mono), **tabular numerals**, right-aligned in tables and KPIs.
- Sizes: 11–13 px UI, 24 px KPI values. Dense by design (this is an engineering tool).

## Layout logic

- **Top bar:** brand · breadcrumb (`Communities / Eco-District A / Run review`) · env/regime chip · user.
- **Left rail:** icon + label nav (Canvas, Scenarios, Agent, Reports, Compare, Settings); active item
  carries the primary-color left border.
- **Toolbar:** tabs + filter chips + primary action on the right.
- **KPI strip:** 4 metric cards — uppercase micro-label, mono value, small delta.
- **Work area:** data table (left, primary) + canvas/panel (right). The map is the hero on the canvas
  view; tables are the hero in run/report views.
- **Status bar:** run count, last sync, connection dot.

## Signature element

The **left rail + breadcrumb + KPI strip** triad, and the **regime tag** (`LMP`, `POOL·TOU`) — a small
outlined chip in the primary hue that keeps the pricing regime legible in every table row without
grabbing attention.

## Kill-list (current look to drop)

1. Dark "sci-fi" canvas + neon glows → light enterprise chrome.
2. Decorative color on chrome (amber/cyan on buttons, badges) → primary + neutrals; color reserved for data.
3. Card grids as the default → dense tables and a canvas; cards only for KPIs.
4. Large display type on every screen → compact 11–13 px UI.

## Migration (tokens, not a rewrite)

The current `index.css` `@theme` maps 1:1 onto this direction: repoint the surface/text/border tokens
to the light palette, set `--color-primary` to `--brand`, keep the physics tokens untouched, and add
the mono/tabular-numerals rules already used by `.metric-value`. Components keep their classes; only
token values and a few layout primitives change.

## Open items

- Confirm **Schneider green vs GE evergreen** as the primary.
- Confirm **light-only** (recommended for Schneider/GE fidelity) vs a dark control-room variant.
- Frontend branch `feature/ui-lmp-pricing` is behind `main`; rebase before applying.
