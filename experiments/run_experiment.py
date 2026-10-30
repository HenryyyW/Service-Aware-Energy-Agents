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
    EnergyMetrics, ServiceMetrics, GridMetrics, AgentMetrics,
    EnergySharingMetrics, MemberSettlementMetrics
)
from src.simulation import SimulationCoupler
from src.controllers import (
    RuleBasedController, BaseController, MultiAgentController, CentralizedController,
    MPCController, QLearningController, LLMAgentController, LLMVerifiedController,
)
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
    
    def setup(self, controller_type: str = "rule_based", rl_policy: Optional[str] = None, 
              llm_backend: Optional[str] = None, llm_model: Optional[str] = None,
              llm_prompt_template: Optional[str] = None, llm_max_usd: Optional[float] = None,
              llm_max_latency_ms: Optional[int] = None, llm_max_tokens: Optional[int] = None):
        """Setup simulator and controller."""
        # Create coupler
        self.coupler = SimulationCoupler(self.scenario_config, data_dir="data")
        
        # Create LLM config if using LLM controllers
        llm_config = None
        if controller_type in ("llm_agent", "llm_agent_verified"):
            from src.agents.backend.config import LLMConfig
            llm_config = LLMConfig()
            if llm_backend:
                llm_config._backend_raw = llm_backend
            if llm_model:
                llm_config.model = llm_model
            if llm_prompt_template:
                llm_config.prompt_template_id = llm_prompt_template
            if llm_max_usd is not None:
                llm_config.max_usd = llm_max_usd
            if llm_max_latency_ms is not None:
                llm_config.max_latency_ms = llm_max_latency_ms
            if llm_max_tokens is not None:
                llm_config.max_tokens = llm_max_tokens
        
        # Create controller
        if controller_type == "rule_based":
            self.controller = RuleBasedController(self.scenario_config)
        elif controller_type == "multi_agent":
            self.controller = MultiAgentController(self.scenario_config)
        elif controller_type == "centralized":
            self.controller = CentralizedController(self.scenario_config)
        elif controller_type == "mpc":
            self.controller = MPCController(
                self.scenario_config,
                device_metadata=self.coupler.citylearn.get_device_metadata(),
            )
        elif controller_type in ("rl", "rl_single"):
            if not rl_policy:
                raise ValueError("--rl-policy is required for the rl controller")
            self.controller = QLearningController(
                self.scenario_config,
                policy_path=rl_policy,
                device_metadata=self.coupler.citylearn.get_device_metadata(),
            )
        elif controller_type in ("llm_agent", "llm_agent_verified"):
            controller_cls = LLMVerifiedController if controller_type == "llm_agent_verified" else LLMAgentController
            self.controller = controller_cls(
                self.scenario_config,
                device_metadata=self.coupler.citylearn.get_device_metadata(),
                llm_config=llm_config,
            )
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
        last_grid_diagnostics = None
        
        while True:
            # Get actions from controller (pass grid diagnostics from previous step)
            requested_actions = self.controller.get_actions(observations, step)
            
            # Step co-simulation
            cosim_result = self.coupler.step(requested_actions)
            self.history.append(cosim_result)
            
            # Extract grid diagnostics for next step's controller
            last_grid_diagnostics = cosim_result.citylearn_result.grid_diagnostics
            
            # Update controller with grid diagnostics from this step for next step's action selection
            if hasattr(self.controller, 'update_grid_diagnostics'):
                self.controller.update_grid_diagnostics(last_grid_diagnostics)
            
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
        energy = all_metrics['energy']
        service = all_metrics['service']
        grid = all_metrics['grid']
        
        # Per-member metrics
        per_member = compute_per_member_metrics(cl_history, self.scenario_config)
        energy_sharing = None
        settlement_result = self.coupler.get_settlement_result() if self.coupler else None
        if settlement_result:
            settlement_members = {}
            settlement_savings = {}
            for building_id, settlement in settlement_result.building_settlements.items():
                savings = float(settlement.metadata.get("savings_vs_baseline", 0.0))
                settlement_savings[building_id] = savings
                settlement_members[building_id] = MemberSettlementMetrics(
                    baseline_grid_bill=float(settlement.metadata.get("baseline_grid_bill", 0.0)),
                    actual_grid_bill=float(settlement.metadata.get("actual_grid_bill", 0.0)),
                    actual_total_bill=float(settlement.metadata.get("actual_total_bill", 0.0)),
                    settlement_savings=savings,
                    baseline_grid_import_kwh=settlement.baseline_grid_import_kwh,
                    baseline_grid_export_kwh=settlement.baseline_grid_export_kwh,
                    grid_import_kwh=settlement.total_grid_import_kwh,
                    grid_export_kwh=settlement.total_grid_export_kwh,
                    grid_import_cost=settlement.total_grid_import_cost,
                    grid_export_revenue=settlement.total_grid_export_revenue,
                    demand_charge=settlement.actual_demand_charge,
                    community_import_cost=settlement.total_community_import_cost,
                    community_export_revenue=settlement.total_community_export_revenue,
                    net_settlement=settlement.net_settlement,
                )
            per_member_by_id = {member.building_id: member for member in per_member}
            for building_id, savings in settlement_savings.items():
                if building_id in per_member_by_id:
                    per_member_by_id[building_id].settlement_savings = savings
            service.per_member_savings = settlement_savings
            energy_sharing = EnergySharingMetrics(
                market_type=settlement_result.metadata.get("market_type", "uniform_price"),
                settlement_interval_timesteps=settlement_result.metadata.get("settlement_interval_timesteps", 0),
                timestep_minutes=settlement_result.metadata.get("timestep_minutes", 0),
                total_community_volume_kwh=settlement_result.total_community_volume_kwh,
                total_community_revenue=settlement_result.total_community_revenue,
                baseline_grid_bill=sum(m.baseline_grid_bill for m in settlement_members.values()),
                actual_grid_bill=sum(m.actual_grid_bill for m in settlement_members.values()),
                actual_total_bill=sum(m.actual_total_bill for m in settlement_members.values()),
                total_savings_vs_baseline=sum(settlement_savings.values()),
                per_member=settlement_members,
            )
        
        # Create KPI results
        kpi_results = []
        
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
        if energy_sharing:
            kpi_defs.extend([
                ('community_savings', 'Community Savings', '$', energy_sharing.total_savings_vs_baseline, 'maximize'),
                ('community_settlement_volume', 'Community Settlement Volume', 'kWh', energy_sharing.total_community_volume_kwh, 'maximize'),
                ('community_actual_bill', 'Community Actual Bill', '$', energy_sharing.actual_total_bill, 'minimize'),
            ])
        
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
        if isinstance(self.controller, LLMVerifiedController):
            controller_type_enum = ControllerType.LLM_AGENT_VERIFIED
            controller_config = {"type": "llm_agent_verified", **self.controller.agent_stats()}
        elif isinstance(self.controller, LLMAgentController):
            controller_type_enum = ControllerType.LLM_AGENT
            controller_config = {"type": "llm_agent", **self.controller.agent_stats()}
        elif isinstance(self.controller, MultiAgentController):
            controller_type_enum = ControllerType.LLM_AGENT
            controller_config = {"type": "multi_agent", "workflow": "planner_coder_executor_verifier_reporter"}
        elif isinstance(self.controller, MPCController):
            controller_type_enum = ControllerType.MPC
            controller_config = {
                "type": "mpc",
                "approach": "deterministic_receding_horizon_lp",
                "horizon_steps": self.controller.horizon_steps,
                "fallback_steps": self.controller.fallback_steps,
            }
        elif isinstance(self.controller, QLearningController):
            controller_type_enum = ControllerType.RL_SINGLE
            controller_config = {
                "type": "rl_single",
                "algorithm": "tabular_q_learning",
                "policy_path": str(self.controller.policy_path),
                "unseen_states": self.controller.unseen_states,
            }
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
            energy_sharing=energy_sharing,
            kpis=kpi_results,
            per_member=per_member,
            diagnostic_reports=[h.grid_diagnostics.model_dump() for h in self.history if h.grid_diagnostics],
            trajectories_file=str(self.run_dir / "trajectories.jsonl"),
            logs_file=str(self.run_dir / "experiment.log")
        )
        
        return result
    
    def _write_manifest(self, result: ExperimentResult):
        """Write the reproducibility manifest for this run.

        Records the semantic scenario-config hash, seed, git commit and library
        versions so a published number can be traced back to its inputs.
        """
        import platform
        import subprocess

        config_payload = json.dumps(
            self.scenario_config.model_dump(), sort_keys=True, default=str
        ).encode("utf-8")
        try:
            git_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip() or None
            git_dirty = bool(subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip())
        except Exception:
            git_commit, git_dirty = None, None

        versions: Dict[str, str] = {}
        for package in ("citylearn", "pandapower", "numpy", "pandas"):
            try:
                versions[package] = getattr(__import__(package), "__version__", "unknown")
            except Exception:
                versions[package] = "missing"

        manifest = {
            "run_id": result.run_id,
            "scenario_id": result.scenario_id,
            "controller": result.controller_config,
            "random_seed": result.random_seed,
            "scenario_config_sha256": hashlib.sha256(config_payload).hexdigest(),
            "git_commit": git_commit,
            "git_dirty": git_dirty,
            "python": platform.python_version(),
            "packages": versions,
            "timestep_minutes": self.scenario_config.timestep_minutes,
            "history_steps": len(self.history),
        }
        with open(self.run_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2, default=str)

        # Agent traceability for the verified-vs-unverified ablation
        # (ABLATION_DESIGN.md section 4): backend, prompt hash and sampling
        # parameters must be present in manifest.json AND result.json.
        agent_stats = getattr(self.controller, "agent_stats", None)
        if callable(agent_stats):
            manifest["agent"] = agent_stats()
            with open(self.run_dir / "manifest.json", "w") as f:
                json.dump(manifest, f, indent=2, default=str)

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

        self._write_manifest(result)
        
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
                       choices=["rule_based", "multi_agent", "centralized", "mpc", "rl", "rl_single",
                                "llm_agent", "llm_agent_verified"],
                       help="Controller type")
    parser.add_argument("--rl-policy", type=str, default=None,
                       help="Path to a trained RL policy JSON (required for --controller rl)")
    parser.add_argument("--max-steps", type=int, default=None, help="Maximum steps to run")
    parser.add_argument("--output-dir", type=str, default="experiments/results", help="Output directory")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (overrides scenario config)")
    parser.add_argument("--run-id", type=str, default=None, help="Custom run ID (optional)")
    
    # LLM arguments
    parser.add_argument("--llm-backend", type=str, default=None,
                       help="LLM backend for llm_agent/llm_agent_verified: "
                            "fallback | ollama[:<model>] (e.g. ollama:qwen2.5-coder:7b) | "
                            "openai_gpt4 | anthropic_claude")
    parser.add_argument("--llm-model", type=str, default=None,
                       help="Model name (e.g., qwen2.5-coder:7b for ollama, gpt-4-turbo for openai)")
    parser.add_argument("--llm-prompt-template", type=str, default=None,
                       help="Prompt template ID (e.g., llm_agent_v1)")
    parser.add_argument("--llm-max-usd", type=float, default=None,
                       help="Maximum USD budget per run")
    parser.add_argument("--llm-max-latency-ms", type=int, default=None,
                       help="Maximum latency budget per step in milliseconds")
    parser.add_argument("--llm-max-tokens", type=int, default=None,
                       help="Maximum token budget per run")
    
    args = parser.parse_args()
    
    # Load scenario
    scenario = load_scenario(args.config)
    
    # Override seed if provided
    if args.seed is not None:
        scenario.random_seed = args.seed
    
    # Run experiment
    runner = ExperimentRunner(scenario, args.output_dir, run_id=args.run_id)
    runner.setup(args.controller, rl_policy=args.rl_policy,
                 llm_backend=args.llm_backend, llm_model=args.llm_model,
                 llm_prompt_template=args.llm_prompt_template,
                 llm_max_usd=args.llm_max_usd, llm_max_latency_ms=args.llm_max_latency_ms,
                 llm_max_tokens=args.llm_max_tokens)
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
    elif expected_controller == "mpc":
        expected_enum = ControllerType.MPC
    elif expected_controller in ("rl", "rl_single"):
        expected_enum = ControllerType.RL_SINGLE
    elif expected_controller == "llm_agent":
        expected_enum = ControllerType.LLM_AGENT
    elif expected_controller == "llm_agent_verified":
        expected_enum = ControllerType.LLM_AGENT_VERIFIED
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