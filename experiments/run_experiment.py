"""Experiment runner for service-aware energy agents."""
import os
import json
import yaml
import argparse
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import numpy as np

from src.schemas.scenario import ScenarioConfig
from src.schemas.action import RequestedActions, Action, ActionType
from src.schemas.report import (
    ExperimentResult, ExperimentStatus, ControllerType, KPIResult,
    EnergyMetrics, ServiceMetrics, GridMetrics, AgentMetrics
)
from src.simulation import SimulationCoupler
from src.controllers import RuleBasedController, BaseController, MultiAgentController, CentralizedController
from src.evaluation import compute_all_metrics, generate_report_plots, compute_per_member_metrics


class ExperimentRunner:
    """Runs experiments with given scenario and controller."""
    
    def __init__(self, scenario_config: ScenarioConfig, output_dir: str = "experiments/results", run_id: Optional[str] = None):
        self.scenario_config = scenario_config
        self.output_dir = Path(output_dir) / scenario_config.scenario_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if run_id is None:
            seed = scenario_config.random_seed
            self.run_id = f"{scenario_config.scenario_id}_{seed}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        else:
            self.run_id = run_id
        self.run_dir = self.output_dir / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        
        self.coupler: Optional[SimulationCoupler] = None
        self.controller: Optional[BaseController] = None
        self.history: List = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def setup(self, controller_type: str = "rule_based"):
        """Setup simulator and controller."""
        # Create coupler
        self.coupler = SimulationCoupler(self.scenario_config, data_dir="data")
        
        # Create controller
        if controller_type == "rule_based":
            self.controller = RuleBasedController(self.scenario_config)
        elif controller_type == "multi_agent":
            self.controller = MultiAgentController(self.scenario_config)
        elif controller_type == "centralized":
            self.controller = CentralizedController(self.scenario_config)
        else:
            raise ValueError(f"Unknown controller type: {controller_type}")
    
    def run(self, max_steps: Optional[int] = None) -> ExperimentResult:
        """Run the experiment."""
        if not self.coupler or not self.controller:
            self.setup()
        
        self.start_time = time.time()
        print(f"Starting experiment: {self.run_id}")
        
        # Reset
        observations = self.coupler.reset(random_seed=self.scenario_config.random_seed)
        
        # Generate dummy data if needed
        data_dir = Path("data") / self.scenario_config.scenario_id
        if not data_dir.exists():
            print("Generating dummy data...")
            self.coupler.citylearn.generate_dummy_data(str(data_dir))
            # Re-reset with data
            observations = self.coupler.reset(random_seed=self.scenario_config.random_seed)
        
        self.controller.reset()
        step = 0
        
        while True:
            # Get actions from controller
            requested_actions = self.controller.get_actions(observations, step)
            
            # Step co-simulation
            cosim_result = self.coupler.step(requested_actions)
            self.history.append(cosim_result)
            
            # Update observations
            observations = cosim_result.citylearn_result.observations
            step += 1
            
            # Progress
            if step % 100 == 0:
                print(f"  Step {step}...")
            
            # Check termination from CityLearn
            if cosim_result.terminated or cosim_result.truncated:
                print(f"Episode terminated at step {step}")
                break
            
            # Check termination
            if max_steps and step >= max_steps:
                print(f"Reached max steps: {max_steps}")
                break
            
            # Check if all buildings terminated (simplified)
            # In reality, CityLearn would have proper termination
            if step >= self._calculate_max_steps():
                print(f"Completed full episode: {step} steps")
                break
        
        self.end_time = time.time()
        self.coupler.close()
        
        # Compute metrics and generate results
        result = self._create_result()
        
        # Save results
        self._save_results(result)
        
        print(f"Experiment completed in {self.end_time - self.start_time:.1f}s")
        return result
    
    def _calculate_max_steps(self) -> int:
        """Calculate max steps from simulation period."""
        start = self.scenario_config.buildings[0].simulation_start
        end = self.scenario_config.buildings[0].simulation_end
        # Approximate
        days = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days
        return days * 24 * 60 // self.scenario_config.timestep_minutes
    
    def _create_result(self) -> ExperimentResult:
        """Create ExperimentResult from history."""
        # Convert history to dict format for metrics
        history_dicts = []
        for h in self.history:
            history_dicts.append({
                'timestep': h.timestep,
                'requested_actions': [a.model_dump() for a in h.citylearn_result.requested_actions.actions],
                'limited_actions': [a.model_dump() for a in h.citylearn_result.limited_actions.actions],
                'applied_actions': [a.model_dump() for a in h.citylearn_result.applied_actions.actions],
                'observations': h.citylearn_result.observations,
                'rewards': h.citylearn_result.rewards,
                'costs': h.citylearn_result.costs,
                'constraint_violations': h.citylearn_result.constraint_violations,
                'grid_diagnostics': h.citylearn_result.grid_diagnostics
            })
        
        # Scenario config as dict
        scenario_dict = self.scenario_config.model_dump()
        
        # Extract CityLearn results for metrics computation
        cl_history = [h.citylearn_result for h in self.history]
        
        # Compute metrics
        all_metrics = compute_all_metrics(
            history=cl_history,
            scenario_config=scenario_dict,
            repair_history=[],
            token_usage=0,
            wall_clock_seconds=self.end_time - self.start_time if self.end_time and self.start_time else 0
        )
        
        # Per-member metrics
        per_member = compute_per_member_metrics(cl_history, self.scenario_config)
        per_member_dicts = [m.model_dump() for m in per_member]
        
        # Create KPI results
        kpi_results = []
        energy = all_metrics['energy']
        service = all_metrics['service']
        grid = all_metrics['grid']
        
        kpi_defs = [
            ('total_cost', 'Total Cost', '$', energy.total_cost, 'minimize'),
            ('grid_import_kwh', 'Grid Import', 'kWh', energy.grid_import_kwh, 'minimize'),
            ('peak_demand_kw', 'Peak Demand', 'kW', energy.peak_demand_kw, 'minimize'),
            ('pv_self_consumption_kwh', 'PV Self-Consumption', 'kWh', energy.pv_self_consumption_kwh, 'maximize'),
            ('load_factor', 'Load Factor', '-', energy.load_factor, 'maximize'),
            ('ev_completion_rate', 'EV Completion Rate', '-', service.ev_completion_rate, 'maximize'),
            ('comfort_violations', 'Comfort Violations', 'degree-hours', service.comfort_violation_degree_hours, 'minimize'),
            ('pf_convergence', 'PF Convergence Rate', '-', grid.power_flow_convergence_rate, 'maximize'),
            ('voltage_violations', 'Voltage Violations', 'count', grid.voltage_violations_count, 'minimize'),
        ]
        
        for kpi_id, name, unit, value, direction in kpi_defs:
            kpi_results.append(KPIResult(
                kpi_id=kpi_id,
                name=name,
                value=value,
                unit=unit,
                target=None,
                direction=direction
            ))
        
        # Determine controller type from the actual controller instance
        if isinstance(self.controller, MultiAgentController):
            controller_type_enum = ControllerType.LLM_AGENT
            controller_config = {"type": "multi_agent", "workflow": "planner_coder_executor_verifier_reporter"}
        elif isinstance(self.controller, CentralizedController):
            controller_type_enum = ControllerType.RULE_BASED
            controller_config = {"type": "centralized", "approach": "joint_optimization"}
        else:
            # Default to rule_based for backward compatibility
            controller_type_enum = ControllerType.RULE_BASED
            controller_config = {"type": "rule_based"}
        
        # Create result
        result = ExperimentResult(
            run_id=self.run_id,
            scenario_id=self.scenario_config.scenario_id,
            controller_type=controller_type_enum,
            controller_config=controller_config,
            status=ExperimentStatus.COMPLETED,
            start_time=datetime.fromtimestamp(self.start_time) if self.start_time else datetime.now(),
            end_time=datetime.fromtimestamp(self.end_time) if self.end_time else datetime.now(),
            random_seed=self.scenario_config.random_seed,
            energy=energy,
            service=service,
            grid=grid,
            agent=all_metrics['agent'],
            kpis=kpi_results,
            per_member=per_member,
            diagnostic_reports=[h.grid_diagnostics.model_dump() for h in self.history if h.grid_diagnostics],
            trajectories_file=str(self.run_dir / "trajectories.jsonl"),
            logs_file=str(self.run_dir / "experiment.log")
        )
        
        return result
    
    def _save_results(self, result: ExperimentResult):
        """Save experiment results."""
        # Export trajectories and diagnostics
        self.coupler.export_results(str(self.run_dir))
        
        # Save result summary
        result_dict = result.model_dump()
        # Convert datetime to string
        result_dict['start_time'] = result.start_time.isoformat()
        result_dict['end_time'] = result.end_time.isoformat()
        
        with open(self.run_dir / "result.json", "w") as f:
            json.dump(result_dict, f, indent=2, default=str)
        
        # Generate plots
        plots_dir = self.run_dir / "plots"
        plots_dir.mkdir(exist_ok=True)
        
        # Load history for plotting
        history_dicts = []
        for h in self.history:
            history_dicts.append({
                'timestep': h.timestep,
                'observations': h.citylearn_result.observations,
                'applied_actions': [a.model_dump() for a in h.citylearn_result.applied_actions.actions],
                'grid_diagnostics': h.citylearn_result.grid_diagnostics
            })
        
        kpis_dict = {kpi.kpi_id: kpi.value for kpi in result.kpis}
        
        generate_report_plots(
            history=history_dicts,
            kpis=kpis_dict,
            per_member=[m.model_dump() for m in result.per_member],
            output_dir=str(plots_dir),
            scenario_config=self.scenario_config.model_dump()
        )
        
        print(f"Results saved to {self.run_dir}")


def load_scenario(config_path: str) -> ScenarioConfig:
    """Load scenario configuration from YAML file."""
    with open(config_path, 'r') as f:
        config_dict = yaml.safe_load(f)
    return ScenarioConfig(**config_dict)


def main():
    parser = argparse.ArgumentParser(description="Run energy community experiment")
    parser.add_argument("--config", type=str, required=True, help="Path to scenario YAML config")
    parser.add_argument("--controller", type=str, default="rule_based", 
                       choices=["rule_based", "multi_agent", "centralized"], help="Controller type")
    parser.add_argument("--max-steps", type=int, default=None, help="Maximum steps to run")
    parser.add_argument("--output-dir", type=str, default="experiments/results", help="Output directory")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (overrides scenario config)")
    parser.add_argument("--run-id", type=str, default=None, help="Custom run ID (optional)")
    
    args = parser.parse_args()
    
    # Load scenario
    scenario = load_scenario(args.config)
    
    # Override seed if provided
    if args.seed is not None:
        scenario.random_seed = args.seed
    
    # Run experiment
    runner = ExperimentRunner(scenario, args.output_dir, run_id=args.run_id)
    runner.setup(args.controller)
    result = runner.run(args.max_steps)
    
    # Verify result matches command line
    assert result.scenario_id == scenario.scenario_id, f"Scenario mismatch: {result.scenario_id} vs {scenario.scenario_id}"
    assert result.random_seed == scenario.random_seed, f"Seed mismatch: {result.random_seed} vs {scenario.random_seed}"
    # controller_type is enum, compare value
    expected_controller = args.controller
    if expected_controller == "rule_based":
        expected_enum = ControllerType.RULE_BASED
    elif expected_controller == "multi_agent":
        expected_enum = ControllerType.LLM_AGENT
    elif expected_controller == "centralized":
        expected_enum = ControllerType.RULE_BASED  # centralized maps to RULE_BASED in _create_result
    else:
        expected_enum = ControllerType.RULE_BASED
    assert result.controller_type == expected_enum, f"Controller mismatch: {result.controller_type} vs {expected_enum}"
    print(f"Verification passed: scenario={result.scenario_id}, controller={result.controller_type.value}, seed={result.random_seed}")
    print(f"Result file: {runner.run_dir / 'result.json'}")
    
    print(f"\nExperiment Summary:")
    print(f"  Run ID: {result.run_id}")
    print(f"  Total Cost: ${result.energy.total_cost:.2f}")
    print(f"  Grid Import: {result.energy.grid_import_kwh:.1f} kWh")
    print(f"  Peak Demand: {result.energy.peak_demand_kw:.1f} kW")
    print(f"  PV Self-Consumption: {result.energy.pv_self_consumption_kwh:.1f} kWh")
    print(f"  PF Convergence: {result.grid.power_flow_convergence_rate:.1%}")
    print(f"  Voltage Violations: {result.grid.voltage_violations_count}")
    print(f"  Line Violations: {result.grid.line_loading_violations}")


if __name__ == "__main__":
    main()