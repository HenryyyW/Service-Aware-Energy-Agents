"""Main pipeline for NL -> Scenario Config."""

from typing import Dict, Any, List
import time
import os
from src.agents.config_roles import (
    ConfigAgentState,
)
from src.agents.config_planner import ConfigPlannerAgent, create_config_planner
from src.agents.config_coder import ConfigCoderAgent
from src.agents.config_executor import ConfigExecutorAgent
from src.agents.config_verifier import ConfigVerifierAgent
from src.agents.config_reporter import ConfigReporterAgent
from src.agents.config_mapping import (
    map_weather_to_climate_zone,
    map_grid_to_pandapower,
    parse_location,
    extract_asset_counts,
)


class NLConfigPipeline:
    """
    Main pipeline for NL -> Scenario Config.

    Orchestrates: Planner -> Coder -> Executor -> Verifier -> Reporter
    """

    def __init__(
        self,
        planner: "ConfigPlannerAgent" = None,
        coder: "ConfigCoderAgent" = None,
        executor: "ConfigExecutorAgent" = None,
        verifier: "ConfigVerifierAgent" = None,
        reporter: "ConfigReporterAgent" = None,
        max_iterations: int = 3,
        project_root: str = None,
    ):
        self.planner = planner or create_config_planner({})
        self.coder = coder or ConfigCoderAgent()
        self.executor = executor or ConfigExecutorAgent(project_root=project_root)
        self.verifier = verifier or ConfigVerifierAgent()
        self.reporter = reporter or ConfigReporterAgent()
        self.max_iterations = max_iterations
        self.project_root = project_root or os.getcwd()
        self.iteration_history: List[Dict[str, Any]] = []

    def run(
        self,
        nl_description: str,
        baseline_config: Dict[str, Any] = None,
        scenario_id: str = None,
    ) -> Dict[str, Any]:
        """
        Run the complete NL -> Scenario Config pipeline.

        Args:
            nl_description: Natural language description of the scenario
            baseline_config: Optional baseline config to modify
            scenario_id: Optional scenario ID

        Returns:
            Dict with final config, manifest, and iteration history
        """
        start_time = time.time()

        # Initialize state
        state = ConfigAgentState()
        state.nl_description = nl_description
        state.original_nl = nl_description
        state.baseline_config = baseline_config
        state.iteration = 0
        state.max_iterations = self.max_iterations

        if scenario_id:
            state.add_manifest_entry("scenario_id", scenario_id)

        state.add_audit({"event": "pipeline_start", "nl_description": nl_description})

        # Try to extract structured info from NL to enhance plan
        self._preprocess_nl(state)

        # Main loop
        for iteration in range(self.max_iterations):
            state.iteration = iteration
            iter_start = time.time()

            print(f"\n{'='*60}")
            print(f"ITERATION {iteration + 1}/{self.max_iterations}")
            print(f"{'='*60}")

            # === PLANNER ===
            print("\n[PLANNER] Analyzing NL description...")
            plan = self.planner.plan(state)
            state.config_plan = plan.model_dump()
            print(f"  Target assets: {plan.target_assets}")
            print(f"  Building count: {plan.building_count}")
            print(f"  Confidence: {plan.confidence:.0%}")

            if plan.primary_issue == "none":
                print("  No configuration needed!")
                break

            # === CODER ===
            print("\n[CODER] Applying configuration plan...")
            coder_output = self.coder.code(
                state, state.config_plan, state.baseline_config
            )
            state.config_changes = coder_output.config_changes
            state.patched_config = coder_output.patched_config
            state.config_diff = coder_output.config_diff
            print(f"  Changes applied: {coder_output.applied_count}")
            print(f"  Failed: {coder_output.failed_count}")

            # === EXECUTOR ===
            print("\n[EXECUTOR] Running simulation validation...")
            scenario_id = f"nl_config_{int(time.time())}_{iteration}"
            executor_output = self.executor.execute(
                state, coder_output.patched_config, scenario_id
            )
            print(f"  Result: {'PASS' if executor_output.success else 'FAIL'}")
            print(f"  Steps: {executor_output.simulation_steps}")
            print(f"  Violations: {executor_output.violation_counts}")
            print(f"  Power flow converged: {executor_output.power_flow_converged}")

            # === VERIFIER ===
            print("\n[VERIFIER] Verifying configuration...")
            verifier_output = self.verifier.verify(coder_output.patched_config)
            state.verification_result = verifier_output.model_dump()
            print(f"  Schema valid: {verifier_output.schema_valid}")
            print(f"  Round-trip: {verifier_output.round_trip_valid}")
            print(f"  Determinism: {verifier_output.determinism_check}")
            print(f"  Confidence: {verifier_output.confidence:.0%}")
            print(f"  Recommendation: {verifier_output.recommendation}")

            # === REPORTER ===
            print("\n[REPORTER] Generating iteration report...")
            reporter_output = self.reporter.report(
                state, state.config_plan, coder_output, executor_output, verifier_output
            )
            print(f"  Summary: {reporter_output.summary}")

            # Record iteration
            iter_duration = time.time() - iter_start
            iteration_record = {
                "iteration": iteration,
                "planner_output": state.config_plan,
                "coder_output": coder_output.model_dump(),
                "executor_output": executor_output.model_dump(),
                "verifier_output": verifier_output.model_dump(),
                "reporter_output": reporter_output.model_dump(),
                "success": executor_output.success,
                "duration": iter_duration,
            }
            self.iteration_history.append(iteration_record)
            state.audit_trail.append(
                {
                    "iteration": iteration,
                    "duration": iter_duration,
                    "success": executor_output.success,
                    "changes": len(coder_output.config_changes),
                }
            )

            # Check if repair successful
            if executor_output.success and verifier_output.recommendation == "accept":
                print(
                    f"\n\u2713 CONFIG GENERATION SUCCESSFUL in iteration {iteration + 1}"
                )
                state.add_manifest_entry("final", True)
                break

            # Check if should continue
            if verifier_output.recommendation in ["retry", "escalate"]:
                if iteration == self.max_iterations - 1:
                    print("\n\u2717 MAX ITERATIONS REACHED")
                    break
                print(
                    f"\n\u2192 Continuing to next iteration (recommendation: {verifier_output.recommendation})"
                )
                # Update state for next iteration
                state.baseline_config = coder_output.patched_config
            else:
                print(
                    f"\n\u2192 Stopping (recommendation: {verifier_output.recommendation})"
                )
                break

        total_time = time.time() - start_time
        success = any(i.get("success", False) for i in self.iteration_history)

        # Generate final report
        final_report = self.reporter.generate_final_report(
            self.iteration_history,
            ConfigAgentState(
                patched_config=state.patched_config,
                manifest=state.manifest,
                audit_trail=state.audit_trail,
            ),
        )

        return {
            "success": success,
            "final_config": state.patched_config,
            "scenario_id": (
                state.manifest.get("scenario_id") if state.manifest else None
            ),
            "iterations": self.iteration_history,
            "total_iterations": len(self.iteration_history),
            "total_time": total_time,
            "final_report": final_report,
            "manifest": state.manifest,
            "audit_trail": state.audit_trail,
        }

    def _preprocess_nl(self, state: ConfigAgentState):
        """Preprocess NL to extract structured hints."""
        nl = state.nl_description

        # Extract hints
        location = parse_location(state.nl_description)
        if location:
            state.add_manifest_entry("extracted_location", location)

        assets = extract_asset_counts(state.nl_description)
        if assets:
            state.add_manifest_entry("extracted_assets", assets)

        climate = map_weather_to_climate_zone(state.nl_description)
        if climate:
            state.add_manifest_entry("mapped_climate_zone", climate)

        grid_type = map_grid_to_pandapower(state.nl_description)
        if grid_type != "ieee_34":  # Not default
            state.add_manifest_entry("mapped_grid_type", grid_type)


def run_nl_to_config(
    nl_description: str,
    baseline_config: Dict[str, Any] = None,
    scenario_id: str = None,
    max_iterations: int = 3,
    project_root: str = None,
) -> Dict[str, Any]:
    """Convenience function to run NL -> Scenario Config pipeline."""
    pipeline = NLConfigPipeline(
        max_iterations=max_iterations,
        project_root=project_root,
    )
    return pipeline.run(nl_description, baseline_config, scenario_id)


def create_nl_config_pipeline(config: Dict[str, Any]):
    """Factory function to create NL config pipeline from config."""
    return NLConfigPipeline(
        planner=create_config_planner(config),
        coder=ConfigCoderAgent(),
        executor=ConfigExecutorAgent(),
        verifier=ConfigVerifierAgent(),
        reporter=ConfigReporterAgent(),
        max_iterations=config.get("max_iterations", 3),
        project_root=config.get("project_root"),
    )
