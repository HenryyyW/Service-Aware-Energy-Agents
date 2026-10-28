# Reproducibility and artifact policy

This repository treats experiment output as a build product: it is generated from
a scenario config plus a seed, and it is published as a release artifact rather
than committed. CI enforces both rules.

## What CI runs

`.github/workflows/ci.yml` runs on every pull request and on pushes to `main`:

| Job | Command | Gate |
|---|---|---|
| Python tests | `pytest -q tests` | any failure blocks merge |
| Frontend build | `npm ci && npm run build` (in `frontend/`) | any failure blocks merge |
| Seed reproducibility | `python -m experiments.check_reproducibility ... --max-steps 8` | non-identical repeated runs block merge |
| Artifact hygiene | `python scripts/check_artifacts.py` | generated/oversized tracked files block merge |

Enable branch protection on `main` with these four checks required.

## Seed reproducibility

Run the same scenario/controller/seed twice (or more) and compare both the
normalized `result.json` and the raw `trajectories.jsonl`:

```powershell
python -m experiments.check_reproducibility `
  --config configs/scenario_a.yaml `
  --controller rule_based `
  --seeds 42 123 `
  --replicates 2 `
  --max-steps 8
```

Exit code 0 means every replicate matched exactly. `--report path.json` writes
a machine-readable report with the config hash, library versions, per-seed
hashes and the list of differing metric blocks.

Volatile fields (`run_id`, timestamps, output paths, wall-clock time) are
excluded from the comparison; every scientific field is included.

### Determinism contract

Two sources of nondeterminism were removed so the gate can pass:

1. `CityLearnAdapter.reset()` seeds Python's `random` and `numpy.random` in
   addition to `env.reset(seed=...)`, because CityLearn samples device state
   through the process-wide RNGs.
2. `_create_dummy_energy_file()` uses `numpy.random.default_rng` keyed on the
   scenario seed and the building filename, so regenerated CSVs are identical
   across runs and stable per building.

Each run also writes `manifest.json` with the semantic scenario-config SHA-256,
seed, git commit and dirty flag, Python and library versions, and step count. A
published number can therefore be traced to its exact inputs.

## Artifact hygiene

Generated run output is ignored by git:

- `results/` — saved run browser data (the Vite dev middleware scans it at runtime)
- `experiments/*/` — benchmark/experiment run directories
- `data/schemas/` — CityLearn schema and CSV copies, rebuilt on adapter init
- `*.jsonl`, `*.log`, `__pycache__/`, `reports/`

`python scripts/check_artifacts.py` fails when a tracked file matches a
generated pattern, lives under a generated directory, or exceeds 2 MB. Curated
fixtures belong under `experiments/reference/` and must stay small.

If a paper needs the raw trajectories, publish them as a GitHub release asset or
an archive with a DOI, and reference the release in the paper's artifact section.

## Packaging a release artifact

```powershell
python scripts/package_results.py `
  --runs experiments/benchmark/seed_42 `
  --runs experiments/benchmark/seed_123 `
  --output dist/benchmark-2026-10.zip
```

The archive contains each run's `result.json`, `manifest.json` and
`trajectories.jsonl`, plus `SHA256SUMS` and a small `INDEX.json` with run
metadata. The generated zip is ignored by git (`dist/`).
