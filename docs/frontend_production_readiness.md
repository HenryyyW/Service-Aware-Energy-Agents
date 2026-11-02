# Frontend production-readiness — audit & plan

Owner: Product Design Lead · Date: 2026-11-02
Request: "frontend needs to be well designed — I want a production-level one."
Scope assumption (could not show the scope picker): start with the **design-system foundation +
accessibility** (highest leverage, unblocks the rest), then per-view polish. Redirect any time.

---

## P0 — fixed this pass

| # | Issue | Evidence | Fix |
|---|---|---|---|
| P0-1 | `bg-surface` (55×) / `text-space` (6×) used but **undefined** → surfaces render transparent. Cause: Tailwind v4 `@theme` defined `--color-bg`/`--color-bg-elevated`; the leftover v3 `tailwind.config.js` is ignored (no `@config`). | `grep -ro bg-surface src` = 55; no `--color-surface` in `index.css` | Added aliases in `frontend/src/index.css` (`--color-surface`, `--color-surface-hover`, `--color-space`) — one place, no 61-file churn |
| P0-2 | No `prefers-reduced-motion` / `prefers-contrast`, though the design plan promises both; infinite `animate-pulse` runs unconditionally | repo-wide grep = 0 hits | Added both global `@media` blocks in `index.css` |
| P0-3 | Stray `console.log` in a production path | `src/api/client.ts:187,218,260` | Flagged (next batch — question whether to keep for diagnostics gated on `import.meta.env.DEV`) |

Verification: `grep` confirms the aliases + both media queries present; `index.css` braces balanced
(143/143). No build run — `frontend/node_modules` is absent.

---

## P1 — next (functional + states)

| # | Issue | Evidence |
|---|---|---|
| P1-1 | Dead primary action: "Export Report" is `onClick={() => {}}` | `components/scenario/ScenarioComparison.tsx:188` |
| P1-2 | Placeholder shipped: radar chart "(Integrate with recharts or similar)" | `ScenarioComparison.tsx:291` (behind `radarChart` flag) |
| P1-3 | Dead affordance: "Change Selection" no-op | `ScenarioComparison.tsx:431-433` |
| P1-4 | Confirm four async states (empty/loading/error/success) on all five main views; `AsyncStates.tsx` exists but usage must be verified per view | `components/ui/AsyncStates.tsx` |
| P1-5 | Accessibility pass: focus order, `aria-live` for time step / violations / agent steps, keyboard nav on map (canvas is pointer-only → needs a table alternative) | design plan §Accessibility |

## P2 — hardening

| # | Issue | Evidence |
|---|---|---|
| P2-1 | Semantic color misuse: metric tiles colour by physics tokens (e.g. `text-sun` for Cost) — see `docs/phase2-design-review-lmp-p2p-agent.md` B1/B2 | `ScenarioComparison.tsx` |
| P2-2 | i18n partial: `useTranslation` in 9 files; rest hard-coded English | `src/i18n/` |
| P2-3 | Responsive audit at 1024 / 1440 / mobile per design plan breakpoints | design plan §Responsive |
| P2-4 | Performance: map/deck.gl layer budgets, chart rendering, bundle split | — |

---

## Definition of done ("production-level")

1. No undefined design utilities; one token source of truth.
2. A11y: WCAG AA — reduced motion, high contrast, focus rings, keyboard, ARIA, no color-only cues.
3. No dead controls: every button/link does what it says or is visibly disabled with a reason.
4. All five main views have empty / loading / error / success states.
5. Responsive at all three breakpoints; no layout breakage.
6. Copy is consistent and localised (or explicitly single-locale by decision).

## Notes

- Changes land on `main`; Frontend Engineer's `feature/ui-lmp-pricing` is behind and must rebase to
  pick up the token aliases + a11y blocks.
- The token aliases are additive and reversible; existing tokens are unchanged.
