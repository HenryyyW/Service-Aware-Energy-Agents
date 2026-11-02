# Post-merge production-UI review

Owner: Product Design Lead · Date: 2026-11-03
Merge under review: `b7e37c7` "feat: frontend theme system (System/GE/Schneider/dark) + PWA manifest".

## 1. Merge review — did the theme system + PWA survive?

**Yes.** Verified on `main` @ `b7e37c7`:

| Item | Check | Result |
|---|---|---|
| Theme layer | `grep data-theme frontend/src/index.css` | 5 hits (layer intact) |
| Reduced-motion / contrast | `grep prefers-reduced-motion index.css` | present |
| Surface aliases (`--color-surface/-space`) | `grep color-surface index.css` | present |
| Theme logic | `frontend/src/config/theme.ts` | present |
| Switcher | `frontend/src/components/ui/ThemeSwitch.tsx` | present |
| Startup wiring | `initTheme` in `frontend/src/main.tsx` | present |
| PWA manifest | `frontend/public/manifest.webmanifest` | present |

The warning that `index.css` was "resolved to main's version" did **not** drop the theme layer —
the `:root[data-theme]` block, the accessibility `@media` blocks, and the token aliases are all still
there. No merge regression found in the theme/PWA surface.

## 2. Production UI-state review (vs the Lighthouse 90+ intent)

| Area | Status | Evidence |
|---|---|---|
| Toasts | ✓ wired | `Toast` used in all 5 pages (CommunityCanvas, ScenarioStudio, Agent, Report, Comparison) |
| Async states | ✗ **gap** | `components/ui/AsyncStates.tsx` exports 9 components (Skeleton/CardSkeleton/TableSkeleton/…) but **no page or component imports it** — loading/empty/error states are not actually rendered from it |
| Responsive | ~ partial | utility breakpoints are used; no viewport audit possible without a running app |
| A11y foundation | ✓ | reduced-motion + high-contrast media queries present; focus ring on `--color-primary` |
| A11y per-widget | ⧗ | ARIA/keyboard on map (canvas is pointer-only) still needs a table alternative |

**P1:** wire `AsyncStates` into every data view (each fetch gets loading → empty → error → success).
This is the single biggest visible "production" gap.

## 3. Lighthouse budgets — the referenced file does not exist

`lighthouserc.js` is **not present anywhere** in the repo (`find -iname '*lighthouse*'` = 0 hits), and
`frontend/package.json` has no `@lhci/*` or `axe` dependency or script. So the acceptance criterion
"review against Lighthouse budgets in `lighthouserc.js`" cannot be met as written — there is nothing
to review against.

Proposed budget file (`frontend/lighthouserc.js`) for DevOps to adopt:

```js
module.exports = {
  ci: {
    collect: { staticDistDir: './dist', numberOfRuns: 3 },
    assert: {
      assertions: {
        'categories:performance': ['error', { minScore: 0.9 }],
        'categories:accessibility': ['error', { minScore: 0.9 }],
        'categories:best-practices': ['error', { minScore: 0.9 }],
        'categories:seo': ['error', { minScore: 0.9 }],
      },
    },
    upload: { target: 'temporary-public-storage' },
  },
};
```

Likely 90+ blockers to pre-empt: deck.gl + plotly + maplibre bundle size (code-split them), web-font
load (self-host / `font-display: swap`), map tile requests, and heading/landmark structure for SEO.

## 4. Production serving (nginx / Docker) — observations

Reviewed `frontend/nginx.conf`, `frontend/Dockerfile`, `docker-compose.yml`.

- ✓ SPA fallback (`try_files $uri $uri/ /index.html`), `/api/` and `/ws/` proxy to `api:8000`,
  security headers (`X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`), hashed-asset
  caching (`1y immutable`).
- ⧗ **P2P WebSocket:** only `/ws/` is proxied; a P2P channel (see the UX spec) needs its own
  location block once the endpoint exists.
- ⧗ **No CSP header** — add a `Content-Security-Policy` (and `Referrer-Policy`) for a hardened build.
- ⧗ **Manifest MIME/caching:** `manifest.webmanifest` is served by the SPA fallback; add an explicit
  `application/manifest+json` type and a short cache to avoid stale manifests.
- ⧗ Proxy target is `api:8000` (Docker) while the Vite dev proxy uses `127.0.0.1:8001` — document both
  so contributors don't chase a port mismatch.
- ⧗ PWA installability still needs 192/512 px PNG icons (manifest ships SVG only).

## 5. Priority

1. Wire `AsyncStates` into all data views (P1).
2. Create `lighthouserc.js` + an axe run, then fix what they report (P1).
3. Add CSP / manifest MIME / P2P WS block to nginx; PNG PWA icons (P2).
