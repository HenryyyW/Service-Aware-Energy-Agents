# results/

Runtime location for saved runs. The Vite development middleware scans this
directory for `result.json` files, so local runs appear in the frontend without
configuration.

The contents are **not tracked by git**. Keep runs out of commits and publish
them as release artifacts instead; see `docs/reproducibility.md`.

A typical run directory (written by `experiments/run_experiment.py`) contains:

```
results/<group>/<scenario_id>/<run_id>/
├── result.json          # metrics summary
├── manifest.json        # config hash, seed, git commit, library versions
├── trajectories.jsonl   # per-step observations/actions (large)
└── plots/               # generated figures
```
