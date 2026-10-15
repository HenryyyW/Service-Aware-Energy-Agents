#!/bin/bash
# Run all experiment scenarios

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "Running all experiment scenarios"
echo "========================================"

cd "$PROJECT_ROOT"

# Activate conda environment if exists
if command -v conda &> /dev/null; then
    eval "$(conda shell.bash hook)"
    conda activate service-aware-energy-agents 2>/dev/null || true
fi

# Create results directory
mkdir -p experiments/results

# Scenario A: Baseline
echo ""
echo "========================================"
echo "Running Scenario A: Baseline REC"
echo "========================================"
python experiments/run_experiment.py --config configs/scenario_a.yaml --controller rule_based

# Scenario B: High EV Penetration (when implemented)
# echo ""
# echo "========================================"
# echo "Running Scenario B: High EV Penetration"
# echo "========================================"
# python experiments/run_experiment.py --config configs/scenario_b.yaml --controller rule_based

# Scenario C: PV Export and Grid Constraints (when implemented)
# echo ""
# echo "========================================"
# echo "Running Scenario C: PV Export and Grid Constraints"
# echo "========================================"
# python experiments/run_experiment.py --config configs/scenario_c.yaml --controller rule_based

echo ""
echo "========================================"
echo "All experiments completed!"
echo "========================================"
echo "Results saved in experiments/results/"
ls -la experiments/results/