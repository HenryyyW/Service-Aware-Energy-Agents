# Phase 4 · M4.1 — Agent Workspace Design

Owner: Product Design Lead · Date: 2026-11-01
Status: spec delivered; components already exist in-repo and are reviewed here against it.
References: `FRONTEND_DESIGN_PLAN.md` (§Principles 3 "colors mean physics", 5 "agent workspace is a
timeline, not a chat", §Motion, §Accessibility); `docs/phase2-design-review-lmp-p2p-agent.md` §4.3;
`frontend/src/styles/tokens.css`.

> **Missing input:** `PHASE4_PLAN.md` (cited as §M4.1) is **not present** anywhere in the shared repo
> (`find` + `git ls-files` = 0 hits). This spec follows the Phase-4 request text and the design plan;
> if `PHASE4_PLAN.md` exists elsewhere, share the path and I will reconcile.

---

## 0. Principles

1. **Agent states are UI states, not physics.** Do **not** reuse `--color-sun` / `energy` / `load` /
   `battery` / `ev` / `grid` / `violation` as step identity accents. Physics colors keep their
   meaning on the map and charts.
2. **Identity by icon + label + position; state by color + glyph.** Color is never the only cue.
3. **Horizontal timeline, not a chat** (design plan §Principle 5). The stage rail is the spine;
   evidence is attached to each stage.
4. **No yellow/amber.** Per the 2026-11-01 accent decision, the accent is IEEE blue (`#00C0EF`);
   no agent token contains amber/yellow.

---

## 1. Timeline structure

**Six stages, left → right:** `Plan → Code → Execute → Verify → Repair → Report`
(maps to the store ids `planner, coder, executor, verifier, repairer, reporter`).

```
┌────────┐   ┌────────┐   ┌──────────┐   ┌──────────┐   ┌────────┐   ┌────────┐
│ ① Plan │──▶│② Code  │──▶│③ Execute │──▶│④ Verify  │──▶│⑤ Repair│──▶│⑥ Report│
│  icon  │   │  icon  │   │   icon   │   │   icon   │   │  icon  │   │  icon  │
└────────┘   └────────┘   └──────────┘   └──────────┘   └────────┘   └────────┘
     └─────────────── evidence panel for the selected stage ───────────────┘
```

- **Step anatomy:** index badge (1–6) · step icon · label · status glyph · connector line to the
  next stage. Active stage = `aria-current="step"`.
- **Evidence placement:** rail spans the top; the **evidence card** for the active stage sits below on
  narrow widths, or in a right-hand panel ≥1440px (three-panel layout).
- **Responsive:** ≥1440px full rail + side evidence; 1024–1439px rail + below-panel; <1024px rail
  scrolls horizontally (snap), evidence full-width below.
- **Repair loop:** Repair may return to Verify — render a dashed "retry" connector Repair→Verify,
  not a second rail. Show the repair count as `n/max`, where `max` is the **configured**
  `max_iterations` (observed values 2 and 3 — do not hardcode 3); when exhausted, Repair renders a
  terminal **"budget exhausted"** state and the rail ends at Verify.

> **Gap vs current code:** `components/agent/AgentTimeline.tsx` renders a **vertical** step list; the
> design plan requires **horizontal**. Either convert it or update the plan — the two must agree.
> (`components/workspace/WorkspaceTimeline.tsx` is a *different* component: a dispatch-events log for
> the simulation, not the agent workflow — leave it separate.)

---

## 2. State model

| State | Meaning | Color token | Glyph (non-color cue) | Connector |
|---|---|---|---|---|
| Pending | not started | `--color-text-muted` | hollow circle + index | muted |
| Active | running now | `--color-primary` (IEEE blue) | spinner / pulse dot | animated fill |
| Done | succeeded | `--color-success` | check | filled |
| Failed | errored | `--color-danger` | ✕ / alert triangle | filled to failure |
| Repaired | patched after failure | `--color-agent-repair` | wrench | dashed retry arrow |
| Skipped | not applicable | `--color-text-subtle` | slash circle | dashed, dim |

Rules: every state pairs its color with the glyph and text; failed steps keep the error text in the
evidence card; "Repaired" never hides the original failure (both are visible).

---

## 3. Motion

| Interaction | Motion | Reduced-motion variant |
|---|---|---|
| Step reveal on arrival | staggered **100 ms/step**, spring (`--ease-spring`) | instant reveal, no stagger |
| Active-step indicator | subtle pulse | static dot |
| Connector fill done→next | 200 ms width/opacity | instant |
| Evidence card enter | 150 ms fade + slight scale | instant |
| Progress bar | 500 ms ease | instant |

`prefers-reduced-motion: reduce` must be honored globally (see §6) — it is currently **not** defined
in the frontend.

---

## 4. Evidence cards (per stage)

| Stage | Content | Format |
|---|---|---|
| Plan | structured task spec: goal, target assets, constraints, success criteria | read-only YAML (Monaco, `yaml`) |
| Code | proposed → repaired source | Monaco **diff** (`python`), hunk highlight |
| Execute | stdout / stderr, exit code, wall latency, token counts, engine flags (CityLearn/pandapower) | JetBrains Mono log + metric chips |
| Verify | diagnostics list (physics / electrical / service), severity + location | list; each row links to the map/asset |
| Repair | patch diff, re-prompt text, iteration counter `n/max` (configured), budget-exhausted state, **fallback indicator** | Monaco diff + callout |
| Report | summary, artifacts/links, reproducibility hashes | **Markdown + JSON** (decided M4.2; no PDF export) |

Every card: a header (stage name + status), a copy affordance, and an `aria-label`ed scroll region.
Long logs: monospace, tabular numerals, virtualized if >2k lines (deferred — see D1 scope memory).

---

## 5. Tokens (`frontend/src/styles/tokens.css`)

Defined and wired (additive):

```css
--color-agent-plan:         #E8EBF0;  /* neutral ink */
--color-agent-code:         #7FB3D5;  /* steel blue */
--color-agent-execution:    #9DB4A0;  /* muted green */
--color-agent-verification: #8FA9C4;  /* slate blue */
--color-agent-repair:       #B49AC4;  /* muted mauve */
--color-agent-report:       #C2C9D2;  /* light graphite */
/* step-* aliases mirror agent-* to prevent drift */
```

All six are muted/desaturated, non-physics, and **yellow-free**, and all clear ≥3:1 against the
`#0A0F1A` canvas (large/graphic); step *state* colors (`primary`/`success`/`danger`) clear text
contrast. These are identity accents only — see §2.

---

## 6. Accessibility (WCAG AA checklist)

- [ ] **Reduced motion:** add `@media (prefers-reduced-motion: reduce)` globally (currently absent);
      step reveal → instant, no pulse, no connector animation.
- [ ] **High contrast:** add `@media (prefers-contrast: high)` (currently absent); borders/text bumped.
- [ ] **Keyboard:** roving tabindex on the rail; ←/→ move stage, Home/End first/last, Enter/Space
      expands the evidence card, Esc collapses. No traps; visible `2px --color-sun` focus ring.
- [ ] **ARIA:** rail = `role="list"`/"listitem" (or `tablist`/`tab` if implemented as tabs);
      active stage `aria-current="step"`; evidence card labelled by its stage; log regions
      `role="log"`/`aria-live="polite"`; status changes announced politely.
- [ ] **Color not sole cue:** state → glyph + text (§2); order index always visible.
- [ ] **Contrast:** agent accents ≥3:1 on canvas; body text ≥4.5:1; status text ≥4.5:1.
- [ ] **Monaco:** ensure the editor is keyboard-focusable and has an accessible name; provide a
      "copy raw" text alternative for diff/code content.
- [ ] **Semantics:** page uses `main`; rail and evidence are `section`/`aside` with headings.
- [ ] **Typography:** Space Grotesk 700/500 headings, IBM Plex Sans 400/500/600 UI, JetBrains Mono
      400/500 data.

---

## 7. Component inventory

| Component | Path | Status |
|---|---|---|
| AgentTimeline | `components/agent/AgentTimeline.tsx` | exists — **vertical**; convert to horizontal + §§2–4 |
| PlanView | `components/agent/PlanView.tsx` | exists — align to §4 |
| CodeView | `components/agent/CodeView.tsx` | exists — confirm Monaco **diff** mode |
| ExecutionLog | `components/agent/ExecutionLog.tsx` | exists — add latency/token/exit-code chips |
| VerificationView | `components/agent/VerificationView.tsx` | exists — severity + map link |
| RepairView | `components/agent/RepairView.tsx` | exists — add fallback indicator |
| ReportView | `components/agent/ReportView.tsx` | exists — add artifacts/hashes |
| TaskInput | `components/agent/TaskInput.tsx` | exists |

---

## 8. Acceptance criteria

1. Rail is horizontal with the six stages and correct connectors; keyboard-operable end to end.
2. Every state shows color **and** glyph; no state relies on color alone.
3. Reduced-motion and high-contrast media queries exist and are verified.
4. `--color-agent-report` and the five accents are present in `tokens.css`; no yellow.
5. Each evidence card matches §4 and has an accessible name + copy affordance.

---

## 9. Open items

- **`PHASE4_PLAN.md` not found** in the shared repo — reconcile §M4.1 when located.
- `AgentTimeline` axis (vertical vs horizontal) must be settled with Frontend Engineer.
- Frontend branch `feature/ui-lmp-pricing` is behind `main`; the tokens/`@import` land only after a rebase.
- Neutral price/caution tokens still include muted warm clays (`#B9A48C`, `#D8BE9E`, `#C99A6A`); flagged
  to the user in case they also want those de-yellowed.
