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

The local results API is development-only. A deployed build needs a backend implementing the `/api/simulations` and `/api/simulations/{run_id}/trajectories` endpoints; set `VITE_API_BASE_URL` when the API is hosted separately.

Community map positions are schematic until surveyed coordinates are provided. Scenario editing, agent workflows, and report generation still require their backend endpoints to become fully operational.
