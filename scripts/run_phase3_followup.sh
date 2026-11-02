#!/usr/bin/env bash
# Phase 3 follow-up runs: 125 runs with 0317388 aggressive config (80/50 grid limit + 10 failures)
# Run after 0317388 merges to origin/main

set -euo pipefail

echo "=== Phase 3 Follow-up Benchmark ==="
echo "Config: 0317388 (80% import / 50% export grid limit + 10 failure injections)"
echo "Regimes: pool_tou + lmp"
echo "Scenarios: 5 (a,b,c,d,e) × Controllers: 5 × Seeds: 5 = 125 per regime"
echo ""

# Check we're on updated main
git fetch origin
git status

# Verify scenario_e.yaml has the aggressive config
echo "Verifying aggressive config in configs/scenario_e.yaml..."
grep -A 2 "community_import_limit_kw\|community_export_limit_kw" configs/scenario_e.yaml
grep -c "failure_id:" configs/scenario_e.yaml || true

# Run pool_tou regime (125 runs)
echo ""
echo "=== Starting pool_tou regime (125 runs) ==="
.venv/bin/python scripts/run_benchmark_supervisor.py \
  --scenarios configs/m1/pool_tou/scenario_{a,b,c,d,e}.yaml \
  --controllers rule_based multi_agent centralized mpc rl \
  --seeds 42 123 456 789 999 \
  --output-dir experiments/phase3/pool_tou \
  --regime pool_tou \
  --rl-policy-dir experiments/reference/rl_policy \
  --workers 3 \
  --timeout 900 \
  --retries 1

# Run lmp regime (125 runs)
echo ""
echo "=== Starting lmp regime (125 runs) ==="
.venv/bin/python scripts/run_benchmark_supervisor.py \
  --scenarios configs/m1/lmp/scenario_{a,b,c,d,e}.yaml \
  --controllers rule_based multi_agent centralized mpc rl \
  --seeds 42 123 456 789 999 \
  --output-dir experiments/phase3/lmp \
  --regime lmp \
  --rl-policy-dir experiments/reference/rl_policy \
  --rl-policy-prefix lmp_ \
  --workers 3 \
  --timeout 900 \
  --retries 1

echo ""
echo "=== Phase 3 complete ==="
echo "Results in experiments/phase3/{pool_tou,lmp}/"
echo "Run summary: cat experiments/phase3/*/summary.json"
