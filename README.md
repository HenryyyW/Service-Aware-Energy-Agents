# Service-Aware Multi-Agent Energy Communities

Physics-grounded code agents for coordinating renewable energy communities with explicit service guarantees, settlement rules, and grid-constraint compliance.

## Overview

This research prototype investigates whether LLM-based code agents can generate and iteratively repair coordination policies that improve community-level cost, peak demand, renewable self-consumption, and carbon outcomes **without sacrificing individual service guarantees or violating electrical constraints**.

## Key Features

- **CityLearn v3** as the community/building-energy simulation environment
- **pandapower** distribution-grid co-simulation for voltage, loading, and power-flow validation
- Multi-agent coordination under explicit service deadlines, electrical limits, local energy sharing, and settlement rules
- Executable Python control/scheduling code generation with iterative repair
- Auditable experiment reports with metrics, plots, code diffs, and failure evidence

## Installation

### Using pip
```bash
pip install -e .
```

### Using conda
```bash
conda env create -f environment.yml
conda activate service-aware-energy-agents
```

## Quick Start

```bash
# Run baseline experiment (Scenario A)
python experiments/run_experiment.py --config configs/scenario_a.yaml

# Run all scenarios
bash experiments/run_all.sh
```

## Project Structure

```
service-aware-energy-agents/
├── configs/           # Scenario configurations
├── src/
│   ├── agents/        # Agent implementations (planner, coder, executor, verifier, repairer, reporter)
│   ├── simulation/    # CityLearn and pandapower adapters
│   ├── controllers/   # Baseline and agent-based controllers
│   ├── evaluation/    # Metrics, fairness, and plotting
│   └── schemas/       # Pydantic models for structured data
├── experiments/       # Experiment runners
├── tests/             # Unit tests
└── reports/           # Generated reports
```

## Scenarios

- **Scenario A**: Baseline Renewable Energy Community
- **Scenario B**: High EV Penetration
- **Scenario C**: PV Export and Grid Constraints
- **Scenario D**: Local Energy Sharing and Settlement
- **Scenario E**: Failures and Robustness

## Research Contributions

1. **Service-aware multi-agent coordination** - Respects EV deadlines, comfort bounds, battery limits, DR obligations
2. **Physics-grounded code-agent workflow** - Generate, execute, verify, repair, re-run
3. **Building-grid co-simulation validation** - pandapower power-flow verification
4. **Reproducible benchmark** - Fixed seeds, logged configs, regenerable figures

## License

MIT License - see LICENSE file for details.