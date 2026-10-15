# Project Brief: Service-Aware Multi-Agent Energy Communities with Physics-Grounded Code Agents

## 1. Objective

Build an open-source research prototype in which **LLM-based code agents** coordinate a renewable energy community containing buildings, rooftop PV, batteries, electric vehicles (EVs), and flexible loads.

The system must:

1. Use **CityLearn v3** as the community/building-energy simulation environment.
2. Couple community-level energy flows to a **pandapower** distribution-grid model for voltage, loading, and power-flow validation.
3. Let multiple agents coordinate energy use under explicit **service deadlines**, **electrical limits**, **local energy sharing**, **settlement rules**, and **equipment/observation failures**.
4. Generate executable Python control/scheduling code, run it in the simulation, detect constraint violations, repair it, and produce an auditable experiment report.

The central research question is:

> Can code agents generate and iteratively repair coordination policies that improve community-level cost, peak demand, renewable self-consumption, and carbon outcomes **without sacrificing individual service guarantees or violating electrical constraints**?

## 2. Why This Matters

Traditional building-energy controllers often optimize aggregate KPIs such as total cost or grid import. However, an aggregate improvement can hide unfair or unacceptable outcomes for individual participants—for example, an EV that misses its departure-time charging deadline, a building that loses comfort, or a battery owner whose asset is disproportionately used.

CityLearn v3 supports configurable renewable energy communities with buildings, PV, batteries, EVs, flexible loads, electrical-service limits, local energy sharing and settlement, demand-response requests, changing members/assets, and failures. It explicitly distinguishes requested, limited, and applied actions, which makes it suitable for studying service-aware coordination rather than only aggregate optimization.

The project should therefore evaluate both:

- **System-level performance**: cost, peak, grid import, renewable utilization, emissions.
- **Participant-level fairness and service**: EV charging completion, comfort violations, battery degradation proxy, settlement savings, unmet demand-response obligations.

## 3. System Overview

```text
User / Researcher
      |
      | Natural-language task or experiment config
      v
Code Agent Orchestrator
      |
      +-- Scenario Planner Agent
      |       - Parses task, assets, constraints, KPIs
      |       - Produces experiment plan and JSON configuration
      |
      +-- Code Generation Agent
      |       - Writes Python controllers / schedulers
      |       - Uses typed interfaces and tool schemas
      |
      +-- Simulation Executor
      |       - Runs CityLearn v3 episode
      |       - Maps aggregate building demand to pandapower buses
      |       - Runs power flow / constraint checks
      |
      +-- Physics & Service Verifier
      |       - Checks voltage, line/transformer loading, power-flow convergence
      |       - Checks EV deadlines, comfort, battery limits, DR delivery
      |       - Compares requested vs. limited vs. applied actions
      |
      +-- Repair / Reflection Agent
      |       - Explains failures from logs and metrics
      |       - Produces targeted code or configuration patches
      |
      +-- Report Generator
              - Produces reproducible Markdown/JSON report
              - Includes metrics, plots, code diffs, failure evidence
```

## 4. Technical Stack

### Required

- Python 3.11+
- CityLearn v3
- pandapower
- pandas, NumPy, Matplotlib
- Gymnasium-compatible environment interface
- Pydantic for configuration and result schemas
- JSON/JSONL logging
- pytest
- Docker or uv-based reproducible environment

### Agent Framework

Use a lightweight, inspectable agent loop. Do not depend on a specific commercial framework.

Recommended architecture:

```text
Planner -> Coder -> Executor -> Verifier -> Repairer -> Reporter
```

Each agent may be implemented as a role around the same LLM, but must maintain separate prompts, tools, memory, and validation responsibilities.

### Simulation Coupling

At each simulation step:

1. CityLearn produces building-level demand, PV generation, battery/EV/flexible-load actions, and community energy flows.
2. The orchestrator maps aggregated nodal demand to selected buses in a pandapower network.
3. pandapower performs power-flow analysis.
4. The verifier checks grid constraints and returns structured diagnostics.
5. If violations occur, the repair agent receives a compact, structured failure report and proposes a patch.

Do not allow the LLM to claim feasibility without an actual simulation result.

## 5. Core Research Contributions

### Contribution 1: Service-aware multi-agent coordination

Design agents that coordinate local energy resources while respecting:

- EV departure-time SOC requirements
- Building thermal-comfort bounds
- Battery state-of-charge and degradation constraints
- Flexible-load completion deadlines
- Per-phase and total active-power import/export limits
- Demand-response delivery obligations
- Local energy-sharing and settlement rules

The key novelty is not merely minimizing cost. The system must explicitly trade off community benefit against participant-level service reliability and fairness.

### Contribution 2: Physics-grounded code-agent workflow

The code agent must:

- Generate Python controllers from structured task specifications.
- Execute them against CityLearn.
- Interpret simulation logs and KPI outputs.
- Detect service failures and constraint violations.
- Produce minimal, testable patches.
- Re-run experiments after repair.
- Refuse to report success unless validation passes.

### Contribution 3: Building-grid co-simulation validation

Use pandapower to validate that community-level schedules are feasible at the distribution-grid level.

At minimum, evaluate:

- Power-flow convergence
- Bus-voltage limits
- Line and transformer loading
- Nodal power balance
- Impact of PV export and coordinated EV charging
- Sensitivity to PV penetration, EV penetration, and battery capacity

pandapower provides IEEE, CIGRE, and synthetic low-voltage test networks; SimBench provides full-year load, generation, and storage profiles suitable for reproducible energy-system studies.

### Contribution 4: Reproducible benchmark

Release:

- Task definitions
- Scenario configurations
- Agent prompts
- Tool schemas
- Baselines
- Evaluation scripts
- Raw logs
- Metrics
- Example reports

The benchmark should allow other researchers to compare rule-based control, MPC, reinforcement learning, and LLM/code-agent approaches under identical scenarios.

## 6. Experimental Scenarios

Implement at least the following scenarios.

### Scenario A: Baseline Renewable Energy Community

- 5–20 buildings
- Rooftop PV
- Community or building-level batteries
- EV charging
- Flexible loads
- Time-of-use grid tariff
- No major failures

Goal: establish baseline performance and verify the simulation pipeline.

### Scenario B: High EV Penetration

- Increase EV penetration to 30–60%.
- Include morning and evening departure deadlines.
- Evaluate whether coordinated charging reduces peak demand without missing service deadlines.

### Scenario C: PV Export and Grid Constraints

- Increase PV capacity.
- Apply feeder-level or nodal export/import limits.
- Evaluate voltage rise, reverse power flow, and curtailment.
- Test whether local storage and demand shifting reduce grid violations.

### Scenario D: Local Energy Sharing and Settlement

- Enable community market / local energy sharing.
- Compare:
  - No sharing
  - Uniform price sharing
  - Weighted importer/exporter settlement
  - Carbon-aware or fairness-aware settlement
- Report both community savings and distribution of savings among members.

### Scenario E: Failures and Robustness

- Inject:
  - PV inverter failure
  - Battery unavailability
  - EV-charger failure
  - Sensor/observation failure
  - Temporary grid-service limit reduction
- Measure how quickly agents detect the issue, repair their policy, and restore service.

## 7. Agent Tasks

The code agent should support the following natural-language tasks.

### Task 1: Scenario Construction

Input:

```text
Create a renewable energy community with 10 buildings, rooftop PV,
building batteries, and EV charging. Each EV must reach at least 80% SOC
before 07:00. Limit total community grid import to 200 kW. Compare
rule-based charging with a coordinated agent-based policy.
```

Expected output:

- Valid CityLearn scenario configuration
- pandapower grid mapping
- Baseline controller
- Agent-based controller
- Experiment runner
- Evaluation report

### Task 2: Constraint Diagnosis

Input:

```text
The last experiment shows that two EVs missed their morning charging
deadlines and one feeder is overloaded during the evening peak. Identify
the causes and propose a minimal policy change.
```

Expected output:

- Structured diagnosis
- Relevant time windows and affected assets
- Candidate interventions
- Patched controller code
- Re-run results

### Task 3: Policy Improvement

Input:

```text
Improve the current policy to reduce evening peak demand by at least 15%
without increasing missed EV deadlines or comfort violations.
```

Expected output:

- Baseline metrics
- Candidate policy code
- Ablation results
- Constraint-compliance evidence
- Final report

### Task 4: Market / Settlement Analysis

Input:

```text
Evaluate whether local energy sharing improves fairness. Compare no-sharing,
uniform-price sharing, and weighted settlement. Report per-member savings,
service outcomes, and grid impacts.
```

Expected output:

- Per-member and community-level metrics
- Fairness indicators
- Statistical comparison
- Reproducible plots and tables

## 8. Evaluation Metrics

### Energy and Cost

- Total electricity cost
- Grid import/export energy
- Peak demand
- Load factor
- PV self-consumption
- PV curtailment
- Battery throughput and cycling proxy
- Carbon emissions or carbon-intensity-weighted emissions

### Service and Fairness

- EV charging completion rate
- Average and worst-case EV SOC at departure
- Comfort violation degree-hours
- Flexible-load completion rate and delay
- Demand-response requested vs. delivered vs. credited response
- Per-member settlement cost/savings
- Gini coefficient or another distributional-fairness metric
- Worst-member outcome, not only mean outcome

### Grid Feasibility

- Power-flow convergence rate
- Number and duration of voltage violations
- Maximum/min voltage
- Line and transformer loading
- Number of constraint violations after agent repair
- Requested vs. limited vs. applied power

### Agent Performance

- Task success rate
- First-attempt code validity
- Simulation execution success rate
- Repair success rate
- Number of repair iterations
- Token consumption
- Wall-clock runtime
- Constraint-violation rate
- Report evidence completeness

## 9. Baselines

Implement and compare:

1. **Rule-based control**
   - Fixed EV charging schedules
   - Threshold-based battery control
   - Simple PV-following load shifting

2. **Model predictive control (MPC)**
   - Deterministic or scenario-based MPC
   - Use forecasted load, PV, tariff, and weather where available

3. **Single-agent reinforcement learning**
   - One centralized agent controlling all assets

4. **Multi-agent reinforcement learning**
   - Independent learners or a standard MARL baseline

5. **LLM code agent without physics verification**
   - Generates and executes code but does not receive structured verifier feedback

6. **LLM code agent with physics/service verification**
   - Full proposed system

The most important comparison is between baselines 5 and 6. This isolates the value of structured physical/service feedback.

## 10. Deliverables

### Repository Structure

```text
service-aware-energy-agents/
├── README.md
├── pyproject.toml
├── environment.yml
├── configs/
│   ├── scenario_a.yaml
│   ├── scenario_b.yaml
│   ├── scenario_c.yaml
│   ├── scenario_d.yaml
│   └── scenario_e.yaml
├── src/
│   ├── agents/
│   │   ├── planner.py
│   │   ├── coder.py
│   │   ├── executor.py
│   │   ├── verifier.py
│   │   ├── repairer.py
│   │   └── reporter.py
│   ├── simulation/
│   │   ├── citylearn_adapter.py
│   │   ├── pandapower_adapter.py
│   │   └── coupling.py
│   ├── controllers/
│   │   ├── rule_based.py
│   │   ├── mpc.py
│   │   ├── rl_baseline.py
│   │   └── agent_policy.py
│   ├── evaluation/
│   │   ├── metrics.py
│   │   ├── fairness.py
│   │   └── plots.py
│   └── schemas/
│       ├── task.py
│       ├── scenario.py
│       ├── action.py
│       ├── diagnostics.py
│       └── report.py
├── experiments/
│   ├── run_experiment.py
│   ├── run_all.sh
│   └── results/
├── tests/
│   ├── test_citylearn_adapter.py
│   ├── test_pandapower_adapter.py
│   ├── test_metrics.py
│   └── test_agent_repair.py
└── reports/
    └── example_report.md
```

## 11. Implementation Plan

### Phase 1: Reproducible simulation core

- Install and validate CityLearn v3.
- Create a minimal renewable-energy-community scenario.
- Implement a deterministic rule-based controller.
- Log requested, limited, and applied actions.
- Compute energy, cost, service, and fairness metrics.
- Add unit tests.

### Phase 2: Building-grid coupling

- Select an IEEE or SimBench distribution-network model.
- Map building/community demand to grid buses.
- Run pandapower power flow at each step or selected intervals.
- Add voltage and loading checks.
- Return structured diagnostics on failure.

### Phase 3: Code-agent workflow

- Implement planner, coder, executor, verifier, repairer, and reporter.
- Define strict JSON schemas for:
  - Task specification
  - Scenario configuration
  - Controller interface
  - Simulation result
  - Constraint diagnostic
  - Repair patch
  - Final report
- Add sandboxed code execution.
- Require tests before accepting a generated controller.

### Phase 4: Multi-agent coordination

- Implement building, battery, EV, and community-aggregator agents.
- Add negotiation or hierarchical coordination:
  - Local proposal
  - Aggregator reconciliation
  - Grid-constraint validation
  - Final allocation
- Compare against centralized and rule-based approaches.

### Phase 5: Benchmark and paper experiments

- Run all scenarios with fixed random seeds.
- Run each configuration at least 3–5 times.
- Produce confidence intervals or statistical tests.
- Generate publication-quality plots and tables.
- Write an experiment report and paper draft.

## 12. Engineering Requirements

### Reproducibility

- Pin all dependency versions.
- Store random seeds.
- Save every configuration hash.
- Log model name, prompt version, tool calls, code diffs, and simulation outputs.
- Make every figure and table regenerable from saved results.

### Safety and Validation

- Never execute unreviewed generated code with network access.
- Use a sandbox or restricted subprocess environment.
- Enforce timeout and memory limits.
- Validate all generated Python with static checks and unit tests.
- Treat simulation output—not LLM self-assessment—as the source of truth.

### Code Quality

- Use type hints.
- Use Pydantic models for all structured data.
- Keep agent prompts in version-controlled files.
- Separate:
  - Environment logic
  - Agent logic
  - Controller logic
  - Evaluation logic
  - Reporting logic
- Add tests for every critical interface.

## 13. First Milestone

Build a minimum viable demonstration:

1. Create a CityLearn v3 community with:
   - 5 buildings
   - PV
   - Batteries
   - EVs
   - Flexible loads
2. Run a rule-based baseline for one week.
3. Let a code agent generate a coordinated scheduling policy.
4. Run the policy in CityLearn.
5. Validate grid impact using a small pandapower feeder.
6. Detect at least one service or electrical violation.
7. Let the repair agent fix the policy.
8. Produce a Markdown report comparing baseline and repaired agent policy.

The first milestone is successful if the agent can complete this loop **without manual code editing** and all reported metrics are reproducible from saved logs.

## 14. Paper positioning

Target venues:

- Applied Energy
- Energy and AI
- IEEE Transactions on Smart Grid
- IEEE Transactions on Sustainable Energy
- ACM e-Energy
- AAAI / IJCAI workshops on AI for social good, sustainability, or agents
- NeurIPS datasets and benchmarks track, if the benchmark contribution is strong

Working title:

> **Service-Aware Multi-Agent Energy Communities: Physics-Grounded Code Agents for Coordination, Settlement, and Grid-Constraint Compliance**

Key claim to test:

> Code agents with explicit service, settlement, and power-flow verification can produce more reliable and fair community-energy coordination than aggregate-cost-optimal or purely learned baselines.

## 15. Important Design Warning

Do not build a system where LLM agents merely discuss energy policy in natural language.

Every claimed improvement must be supported by:

- Executed simulation code
- Saved trajectories
- Recomputed KPIs
- Power-flow or constraint checks
- Requested versus applied action logs
- Reproducible random seeds
- A final machine-readable result file

The scientific value comes from the closed loop:

```text
natural-language task
  -> executable policy code
  -> simulated energy community
  -> grid/service verification
  -> structured failure diagnosis
  -> targeted repair
  -> reproducible evidence
```