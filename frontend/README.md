# Virtual Community Frontend

React and TypeScript interface for exploring renewable-energy-community simulations. The main canvas combines saved run selection, a spatial community view, asset layers, grid diagnostics, an inspector, and a time player.

## Run locally

```powershell
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite (normally `http://localhost:3000`).

During development, the Vite server exposes a read-only API over the repository's `results/` directory. It discovers `result.json` files and their sibling `trajectories.jsonl` files, so saved experiments can be browsed without a separate backend.

## Build

```powershell
npm run build
npm run preview
```

The local results API is development-only. A deployed build needs a backend implementing the `/api/simulations` and `/api/simulations/{run_id}/trajectories` endpoints; the FastAPI service in `../backend/` provides these (`cd ../backend && uvicorn app.main:app --reload --port 8001`, matching the Vite proxy). Set `VITE_API_BASE_URL` / `VITE_WS_BASE_URL` when the API is hosted separately.

Community map positions are schematic until surveyed coordinates are provided. Scenario editing, agent workflows, and report generation are backed by the service in `../backend/`.

## Visual style (switchable)

Three styles switch at runtime via `<html data-theme>` — components are unchanged; only token values swap:

| Style | `data-theme` | Look |
|---|---|---|
| GE Vernova | `ge` (default) | Light enterprise, evergreen `#005e60` primary, lime accent |
| Schneider | `schneider` | Light enterprise, green primary |
| Canvas | `dark` | Original dark map theme |

- UI: the `<ThemeSwitch />` control in `src/components/ui/ThemeSwitch.tsx` — drop it in the top bar.
- Code: `applyTheme('ge')` from `src/config/theme.ts`; `initTheme()` runs at startup in `src/main.tsx`.
- Palette + rationale: `../docs/frontend_visual_direction.md`.

## Colour scheme

- **Chrome / focus:** IEEE-blue accent `#00C0EF`. The locational-price (LMP) map layer uses a neutral, non-valence ramp — price is a measured quantity, never a good/bad signal.
- **Violations:** red (`--color-violation`); the violation layer's selection highlight uses the accent, not amber.
- Physics colours (PV, load, battery, EV, feeder) keep their meaning on the map.

## Agent Workspace

The agent timeline is a **horizontal** rail — `Plan → Code → Execute → Verify → Repair → Report` — with per-step evidence cards and a staggered reveal that honours `prefers-reduced-motion`. Spec: `../docs/phase4_agent_workspace_design.md`.
