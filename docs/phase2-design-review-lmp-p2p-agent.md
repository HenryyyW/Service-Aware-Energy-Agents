# Phase 2 Design Review & UX Spec — LMP / P2P / Agent surfaces

Author: Product Design Lead · Date: 2026-10-31
Scope: design review of the Phase 2 frontend surfaces + token extensions + a11y/motion specs.
Verified against `main` @ `99acc46` ("LMP report wiring"); updated 2026-10-31 after Backend B
reported the P0-1 LMP fix and P0-4 P2P prep merged.

> **Accent recolor 2026-11-01 (user request):** all yellow/amber in the frontend is replaced with
> IEEE blues taken from IEEE SA's own theme (`standards.ieee.org`): IEEE SA Main Blue `#00C0EF`
> (primary/electric accent, was `--color-sun` amber `#F59E0B`) and IEEE SA Medium Blue `#4AC9E3`
> (grid/yellow role, was `--color-grid` `#EAB308`). Hover/active tonal steps `#0099C7` / `#0080A8`.
> IEEE Master Brand Blue `#005d94` is *not* used as accent because it fails contrast on the dark
> canvas (~2.7:1); it remains available for fills. Applied to `index.css` tokens, the focus-ring
> glow, the primary-button shadow, `TimeSeriesChart` series colors, and every hardcoded amber/yellow
> RGBA in `canvas/MapLayers/*` and `LMPLayer` (ramp is now an IEEE-blue sequential ramp). See the
> CSS comments "(was …)" for each swap.
Grounding: `FRONTEND_DESIGN_PLAN.md` (§Color Palette, §Typography, §Motion, §Accessibility),
`docs/phase2_experiment_plan.md` (§4.1 regimes, §4.2 run id, T6/T7 metrics, P0-1), and
`briefs/phase2-lmp-pricing-ui-brief.md` (the pricing-surfaces brief already relayed).

---

## 0. Answers to the three questions (asked first)

1. **Format.** Markdown **in the repo is the source of truth** (this file + a tokens block that
   can be pasted into `src/index.css`). Figma is optional and, if used, must mirror these
   decisions — not introduce parallel ones. No Figma-only specs: the design system must be
   diffable and reviewable in the same PR as the component.
2. **New tokens.** Yes. Four groups are needed beyond `FRONTEND_DESIGN_PLAN.md` Table 1:
   **price** (neutral, non-physics), **market metadata** (regime / cost_basis / claim-grade),
   **carbon**, and (optional) **agent step identity**. See §3. No new *physics* colors.
3. **Cadence.** Review at **two gates**, not continuously: (a) **spec/PR open** — tokens + states
   + a11y checklist present; (b) **pre-merge** — a11y checklist signed off, reduced-motion
   verified, snapshots green. Sync to the FE sprint: gate (a) at branch start, gate (b) at PR review.

---

## 1. Blocking findings (fix before these surfaces ship)

### B1 — Reusing physics colors for price violates the core principle
The proposed LMP ramp (`--color-energy` → `--color-sun` → `--color-violation`) and the shipped
`LMPLayer.tsx` ramp (`#3B82F6` generic blue → `--color-sun` → `--color-load`) both reuse colors
that already *mean* generation, solar, and load/violation. `FRONTEND_DESIGN_PLAN.md` §Principle 3
("Colors mean physics — no decorative color") and the pricing brief both forbid this, and the
generic Tailwind blue is also a "generic default" the plan rejects. **Price is a measured
quantity, not a physics flow.** Give price its own neutral ramp (§3.1). Also drop the uses of
`--color-sun` for PV, `--color-energy` for self-consumption, `--color-battery` for EV-ready in
`ScenarioComparison.tsx`; those are metrics, not those physical flows.

### B2 — Spread is dispersion, never "savings"/"better-lower"
`ScenarioComparison.tsx` marks `lmp_price_spread` / `lmp_price_spread_pct` as `better: 'lower'`
(lines 41–42) and shows a top-row **"Energy Savings"** KPI (`calculateSavings`, line 469) with
green/red valence. Both imply a preferred direction. Spread is congestion *evidence*: lower is
not better, and `0 %` spread means the OPF failed (P0-1), not "great". Set the LMP price metrics
to `better: 'neutral'`, remove the savings/improvement/safety KPI tiles (they violate
§Principle 7 "no KPI tiles unless requested" and carry no CI), and show deltas as signed Δ with a
95 % CI plus a "no detectable pricing effect" fallback (see §5).

### B3 — Uniform prices must not render as real geography (false-positive guard)
In `LMPLayer.tsx`, `normalizedPrice = priceSpread > 0 ? … : 0.5` paints a **uniform mid-scale map
with no warning** when spread is 0 — i.e. when OPF fell back. That is exactly the
"publishable-looking number" the plan warns about. When `lmp_price_spread_pct == 0`, render the
layer **flat** (single `--color-price-uniform`) with an explicit "uniform prices — not claim-grade"
note. Gate any LMP *claim* on the fields that exist in `EnergyMetrics` today —
`lmp_opf_fallback_steps == 0 && cost_coverage == 1.0 && invalid_cost_steps == 0`; otherwise show a
muted "fallback-dominated / not claim-grade" chip. **Data gap:** `lmp_at_cap_steps` is *not*
exposed by the backend (`src/schemas/report.py` lists `cost_basis`, `lmp_cost_usd`,
`lmp_price_mean`, `lmp_price_spread`, `lmp_price_spread_pct`, `lmp_total_cost_usd`, `cost_coverage`,
`invalid_cost_steps`) — drop it from the gate or request the field from Backend.

### B4 — Reduced-motion and high-contrast support is entirely missing
`FRONTEND_DESIGN_PLAN.md` §Motion and §Accessibility both claim support, but a repo-wide search
finds **no `@media (prefers-reduced-motion: reduce)` and no `@media (prefers-contrast: high)`**.
Infinite `animate-pulse` (agent active step, clock icon, violation pulse), spring transitions, and
stagger reveals all run unconditionally. Add the global blocks in §6 before shipping new animation.

### B5 — Token-path + token-name drift (token-file correction)
- `frontend/src/styles/tokens.css` **now exists** (created 2026-10-31) with the additive Phase 2
  token block from §3, wired from `frontend/src/index.css` by
  `@import "./styles/tokens.css";`. Base physics/surface tokens stay in the `index.css` `@theme`.
  One source of truth for new tokens; do not duplicate.
- The project is Tailwind **v4** (`tailwindcss ^4.3.3`, `@tailwindcss/postcss`), but a leftover
  **v3 `tailwind.config.js`** is *not* referenced via `@config`, so it is ignored. Components use
  `bg-surface` (55×) and `text-space` (6×), but `@theme` defines `--color-bg` /
  `--color-bg-elevated`, **not** `--color-surface` / `--color-space`. Those utilities therefore
  generate no CSS → transparent surfaces. Either rename `@theme` keys back to `space`/`surface`
  (matching the design plan's names) or delete the ignored v3 config and standardize the names.
  Treat the design plan's token names as canonical.

### B6 — P2P engine merged, but the regime is still SCHEDULE-LATER (don't build live UI yet)
Verified on `main` @ `99acc46`: `market_type` accepts `p2p` (`src/schemas/scenario.py:134`);
`P2POrder` / `P2PTrade` / `P2PMatchingEngine` exist (`src/coordination/p2p.py`); `P2PClearing`
exists (`src/simulation/market.py:831`); `tests/test_p2p.py` covers creation, partial fill,
price-time priority, uniform price, and money/energy/ledger/no-arbitrage invariants.
**However** `docs/phase2_m1_readiness.md` still marks the `p2p` regime
**SCHEDULE-LATER (PM order)**: "T6 metric wiring and paired-baseline validation are unverified …
do not schedule without PM confirmation." And there is **no `/ws/p2p/{run_id}` endpoint** in the
backend yet (Project Partner lists it as *needed*, not built; `grep` over `src/` finds no WS route).
So the data structures are real, but a live `P2POrderbook` has no validated data source. Build it
**behind a feature flag** only after (a) PM confirms p2p runs are scheduled/validated and (b) the
WS contract is defined. Keep it out of the LMP sprint. Nothing P2P exists in the frontend today
(`grep` for `P2P`/`orderbook` = 0 hits).
*Update 2026-10-31:* the P2P **clearing rule** (P2P first → pool residual) and **contract length**
(1 settlement interval = 1 h, batch double auction per interval) are now decided (PM). The blocker
to a live UI is unchanged: no scheduled/validated `p2p` runs and no WS endpoint yet.

---

## 2. Design review verdicts

| Surface | Verdict | Must-fix |
|---|---|---|
| LMPLayer.tsx | **Revise** | B1 neutral price ramp; switch points→building polygons; single encoding of price (drop size-encodes-price); uniform/no-spread flat state + claim-grade gate (B3); selection uses a focus token, not `--color-sun` |
| ScenarioComparison.tsx | **Revise** | B1 metric colors; B2 remove savings tiles + neutral spread; add 95 % CI + Holm + "no detectable effect"; regime/cost_basis chips use §3.2 tokens; dead "Export Report" button gets a real handler or is hidden |
| AgentTimeline.tsx | **Refine** | Vertical list ≠ "horizontal swimlanes"; add reduced-motion (B4); arrow-key/roving-tabindex nav; staggered reveal per plan |
| P2POrderbook | **Defer (2b)** | B6; if specced, buy/sell colors are currently inverted (see §4.2) |
| Design tokens | **Revise** | B5 path/name drift; add §3 groups |

---

## 3. Token extensions for `frontend/src/index.css` (`@theme`)

Paste into the existing `@theme` block. These are **additive**; no existing physics token changes.

### 3.1 Price — measured, non-physics, diverging around the community mean
```css
/* Price: a measured quantity. Cool→neutral→warm, never red/green/amber-green. */
--color-price:           #94A3B8;  /* price ink / axis / value text */
--color-price-1:         #475569;  /* low LMP  */
--color-price-2:         #64748B;
--color-price-3:         #94A3B8;  /* == community mean anchor */
--color-price-4:         #B9A48C;
--color-price-5:         #D8BE9E;  /* high LMP */
--color-price-uniform:   #475569;  /* flat state when spread == 0 (B3) */
--color-price-congestion:#C9A36A;  /* optional: congestion overlay accent (feeder stroke) */
```

### 3.2 Market metadata — regime / cost_basis / claim-grade (structural, not physical)
```css
/* Regime = how the market clears; cost_basis = what the score is billed on. Two tokens, never merged. */
--color-regime:          #A5B4FC;  /* market-regime chip */
--color-cost-basis:      #8AA8C4;  /* billing-basis chip (distinct hue family) */
--color-meta:            #8A93A6;  /* structural metadata: run ids, seeds, units */
--color-meta-strong:     #B8C0CE;
--color-claim-ok:        #8FBFA8;  /* claim-grade gate passed (muted sage — NOT --color-energy) */
--color-claim-fail:      #C99A6A;  /* not claim-grade (muted clay — NOT --color-violation) */
--color-caution:         #C99A6A;  /* caution chip: uniform / not-claim-grade */
```

### 3.3 P2P (Phase 2b, design-only) — buy/sell follow import/export physics
```css
/* Buy = consumption/import side, Sell = generation/export side (consistent with --color-load / --color-energy). */
--color-p2p-buy:         var(--color-load);    /* rose */
--color-p2p-sell:        var(--color-energy);  /* emerald */
--color-p2p-match:       #CBD5E1;              /* neutral ink for match connector */
--color-p2p-link-style:  dashed;               /* shape carries "matched", not color alone */
```

### 3.4 Carbon — its own quantity (never derive from LMP)
```css
/* Carbon = generation mix × emission factor. Distinct from price and from all physics flows. */
--color-carbon:          #A8A29E;
--color-carbon-lo:       #78716C;
--color-carbon-hi:       #D6D3D1;
```

### 3.5 Agent step identity (optional; use UI aliases if you prefer)
```css
/* Agent workflow states are UI states, not physics. Prefer --color-primary/--color-success/--color-danger. */
--color-step-plan:   #93A5C4;
--color-step-code:   #7FB3D5;
--color-step-exec:   #9DB4A0;
--color-step-verify: #C9B88F;
--color-step-repair: #C99A6A;
```

---

## 4. Component specs

### 4.1 LMPLayer
- **Geometry:** per-building **polygon fill** (choropleth on extruded buildings), sibling to
  `ViolationLayer`; **not** a point/scatter layer. Fill = *where power is expensive*; feeder stroke
  in `FeederLayer` = *why* (congestion). Keep fill and stroke distinct.
- **Encoding (one variable, one channel):** color only. **Do not also scale radius/marker size by
  price** — double-encoding price implies magnitude and misleads. Time-scrubbed: recolor per step.
- **Ramp:** §3.1, anchored at the community mean; text label always shows `$/kWh`.
- **States:**
  | State | Render |
  |---|---|
  | Normal spread | Quadrant fill from §3.1 ramp |
  | `spread_pct == 0` | Flat `--color-price-uniform` + "uniform prices" note (B3) |
  | Fallback / at-cap / coverage<1 | Flat + "not claim-grade" `--color-caution` chip |
  | Selected building | Focus outline `2px var(--color-sun)`; **do not** replace fill with sun |
  | Hover/select shown | Sparkline tooltip (JetBrains Mono 12px) + mean, spread, fallback count |
  | Layer off (default) | Off by default in `LayerTree` |
- **Legend:** 5-stop ramp with `min / mean / max` in `$/kWh`, a scope note (buildings × steps), and
  the formula (`spread_pct = (max−min)/mean`) in a tooltip.
- **Data shown with the number (counter-facts):** `lmp_price_mean`, `lmp_price_spread`,
  `lmp_price_spread_pct`, `lmp_opf_fallback_steps`, `cost_coverage`, `invalid_cost_steps`
  (`lmp_at_cap_steps` is not yet exposed — see B3).

### 4.2 P2POrderbook (design now, build behind a flag — engine merged but regime SCHEDULE-LATER; no live WS source yet, §B6)
- **Layout:** split view. **Buy = left, `--color-p2p-buy` (rose, import side); Sell = right,
  `--color-p2p-sell` (emerald, export side).** *The proposed mapping (buyer green ↔ seller rose) is
  inverted* — green already means export/generation (supply/seller) and rose means consumption
  (demand/buyer).
- **Preference match:** neutral **dashed** connector (`--color-p2p-match`, `--color-p2p-link-style`)
  plus a "matched" glyph — not `--color-comfort` (that token means thermal comfort).
- **Carbon badge:** from `--color-carbon` group, computed from **generation mix × emission factor**.
  Never label a value derived from LMP as carbon intensity.
- **Locality filter:** slider in bus-hops (structural → `--color-meta`).
- **Contract duration — LOCKED (PM, 2026-10-31): 1 settlement interval = 1 h.** Do **not** offer a
  1-interval / 1-hour / 1-day dropdown; only 1 h is supported. The orderbook groups orders into
  **per-interval clearing batches** (batch double auction, uniform price within batch) — show a
  batch/interval header, and after clearing the **residual volume routed to the pool** (clearing
  rule: P2P first → pool residual). Note: `docs/phase2_market_settlement_design.md` §261 still
  lists contract duration as an open question — update it to the locked value.
- **Order states (never color alone):**
  | State | Render |
  |---|---|
  | Pending | static dot + label (pulse only if motion allowed) |
  | Partial | stripe pattern + label |
  | Filled | solid + label |
  | Cancelled | strikethrough + label |
- **Density:** semantic `<table>` with `<caption>` and `<th scope>`; prices/quantities in JetBrains
  Mono 14/20.

### 4.3 Agent Workspace timeline
- **Structure:** **horizontal swimlanes** — Plan · Code · Execution · Verification · Repair
  (Reporter as a terminal node). The current `AgentTimeline.tsx` is a vertical step list; either
  align to the plan or update the plan, but the two must agree.
- **Evidence cards:** Plan = structured spec (YAML preview); Code = Monaco diff (proposed→repaired);
  Execution = stdout/stderr, latency, token counts; Verification = diagnostics list; Repair = patch
  diff, re-prompt text, fallback indicator.
- **Reveal:** staggered 100 ms per step (spring) → **instant when reduced-motion**.
- **Keyboard:** roving tabindex; ←/→ move steps, Enter/Space expands evidence, Esc closes.
- **States:** use `--color-primary` (active), `--color-success` (done), `--color-danger` (failed),
  with icon + label so state survives grayscale.

### 4.4 Scenario comparison (deltas)
- **Layout:** side-by-side synced maps **or** single-map A/B tint toggle; shared time scrubber;
  synced viewport, layers, time step.
- **Delta presentation:** signed Δ **with 95 % CI bars**; regime deltas carry the **Holm** flag and
  the reference regime. If |Δ| < 5 % of the `pool_tou` mean → **"no detectable pricing effect"**,
  never "LMP saves/costs".
- **Valence:** metric deltas are neutral by default. The only place up/down color is allowed is
  where a metric has a genuine direction *and* it is not a price/spread (e.g. comfort violations):
  even then, pair color with an arrow glyph and a text value. Price and spread are always neutral.
- **Remove** the "Energy Savings / Service Improvement / Grid Safety" KPI tiles (no CI, implies a
  single winner).

---

## 5. Regime / cost_basis badge spec (run lists)

- Two **separate** tokens, never merged: `regime` ∈ {`tou_solo`, `pool_tou`, `lmp`}; `cost_basis` ∈
  {`tariff`, `lmp`}. A mismatch (e.g. regime `lmp` but `cost_basis tariff`) is a **defect** — flag it.
- Compact mono labels `TOU`, `POOL·TOU`, `LMP`, with a basis suffix chip `·tariff` / `·lmp`
  (`--color-regime` / `--color-cost-basis`).
- Columns: Run id · Regime · Cost basis · Spread % · Claim-grade.
- Run id is `{scenario}_{controller}_{seed}` (PM-locked); the regime is **not** in the run-id string —
  it is carried per-regime by the output directory and the run-level `pricing_regime` field. Read
  `pricing_regime` from the run/summary and filter by that field; never parse regime out of `run_id`.
- Claim-grade chip: `--color-claim-ok` (check glyph) vs `--color-claim-fail` (caution glyph,
  "fallback-dominated / not claim-grade"). Color + glyph + text.

---

## 6. Accessibility checklist (new components)

- [ ] **Reduced motion:** add `@media (prefers-reduced-motion: reduce)` (§7) — currently absent (B4).
- [ ] **High contrast:** add `@media (prefers-contrast: high)` (§7) — currently absent (B4).
- [ ] **Focus:** visible `2px var(--color-sun)` ring, `2px` offset (already global via
      `*:focus-visible`; verify it applies inside map controls and orderbook).
- [ ] **No color-only meaning:** regime, cost_basis, order state, claim-grade, and delta direction
      each carry a glyph and/or text label.
- [ ] **Color-blind:** price ramp is single-hue-family (safe). Verify §3.2 chip pairs with Coblis
      (deuteranopia/protanopia); if any pair fails, add shape.
- [ ] **Contrast:** text labels ≥ 4.5:1 on `--color-bg`/`--color-bg-elevated`; UI fills/ramp steps ≥ 3:1.
- [ ] **Map is not the only access path:** deck.gl canvas is pointer-only and invisible to screen
      readers. Provide an accessible **"buildings by LMP" data table** and an `aria-label` on the
      layer toggle; the hover sparkline needs a text equivalent.
- [ ] **Keyboard:** orderbook and timeline reachable and operable by keyboard; roving tabindex on
      timeline; Esc closes panels; no keyboard traps.
- [ ] **Semantics:** orderbook uses `<table>/<caption>/<th scope>`; panels use `main/aside/section`.
- [ ] **Live regions:** `aria-live="polite"` for time-step changes, new violations, agent-step
      completion.
- [ ] **ICON labels:** every icon-only button has `aria-label` (e.g. "Clear comparison").
- [ ] **Typography:** Space Grotesk 700/500 headlines, IBM Plex Sans 400/500/600 UI, JetBrains Mono
      400/500 data (12/13/14px) — no substitutions.

---

## 7. Reduced-motion & contrast variants

Global (add once to `src/index.css`):
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;   /* kills infinite pulses */
    transition-duration: 0.001ms !important;
    scroll-behavior: auto !important;
  }
}
@media (prefers-contrast: high) {
  :root {
    --color-border: #94A3B8;
    --color-text-muted: #CBD5E1;
  }
  /* Guarantee non-color state cues are always present regardless of media. */
}
```
Per-component:
- **LMPLayer:** no animation on scrub (already instant); no pulse; ramp is static; reduced-motion
  changes nothing visually except disabling the optional congestion shimmer.
- **P2POrderbook:** Pending pulse → static dot; match connector stays dashed (static).
- **AgentTimeline:** staggered 100 ms reveal → instant; `animate-pulse` on active node and clock →
  static; progress-bar `transition-500` → instant; step icons unchanged.
- **ScenarioComparison:** A/B tint fade → instant; CI bars and deltas are static.

---

## 8. Handoff for Frontend Engineer

1. Apply §3 tokens in `src/index.css` `@theme`; resolve B5 naming (`space`/`surface`).
2. Rebuild the LMP ramp on §3.1 and add the uniform/claim-grade states (§4.1, B3).
3. De-couple price from physics colors and neuter spread valence in `ScenarioComparison.tsx` (§1 B1/B2).
4. Add §7 global media blocks; verify reduced-motion and contrast in Storybook or a manual pass.
5. P2P orderbook: hold to Phase 2b; if specced, fix the buy/sell inversion (§4.2, B6).

*Design system is the single source of truth; no generic SaaS defaults.*
