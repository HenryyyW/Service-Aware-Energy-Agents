"""Config Reporter agent - generates reports and manifests."""

from typing import Dict, Any, List
from src.agents.config_roles import (
    ConfigReporterOutput,
    ConfigAgentState,
    ConfigCoderOutput,
    ConfigExecutorOutput,
    ConfigVerifierOutput,
)


class ConfigReporterAgent:
    """Reporter agent for config pipeline."""

    def __init__(self):
        pass

    def report(
        self,
        state: "ConfigAgentState",
        plan: Dict[str, Any],
        coder_output: "ConfigCoderOutput",
        executor_output: "ConfigExecutorOutput",
        verifier_output: "ConfigVerifierOutput",
    ) -> "ConfigReporterOutput":
        """Generate iteration report."""
        # Build summary
        success = executor_output.success
        changes = len(coder_output.config_changes)

        if success:
            summary = f"Config generation successful: {coder_output.applied_count} changes applied, simulation validated"
        else:
            summary = f"Config generation failed: {executor_output.error}"

        # Build detailed report
        detailed = {
            "plan": state.config_plan,
            "changes": coder_output.config_changes,
            "diff": coder_output.config_diff,
            "execution": {
                "success": executor_output.success,
                "steps": executor_output.simulation_steps,
                "violations": executor_output.violation_counts,
                "power_flow_converged": executor_output.power_flow_converged,
                "energy_balance": executor_output.energy_balance_ok,
                "error": executor_output.error,
            },
            "verification": {
                "schema_valid": (
                    state.verification_result.get("schema_valid", False)
                    if state.verification_result
                    else False
                ),
                "round_trip": (
                    state.verification_result.get("round_trip_valid", False)
                    if state.verification_result
                    else False
                ),
                "determinism": (
                    state.verification_result.get("determinism_check", False)
                    if state.verification_result
                    else False
                ),
                "confidence": (
                    state.verification_result.get("confidence", 0)
                    if state.verification_result
                    else 0
                ),
            },
            "mapping_errors": state.mapping_errors,
            "schema_errors": state.schema_errors,
        }

        # Build manifest
        manifest = state.manifest or {}

        # Recommendations
        recommendations = []
        if not state.verification_result.get("schema_valid", True):
            recommendations.append("Fix schema validation errors")
        if state.verification_result and not state.verification_result.get(
            "round_trip_valid", True
        ):
            recommendations.append("Fix round-trip serialization issues")
        if state.mapping_errors:
            recommendations.append("Review mapping errors")

        return ConfigReporterOutput(
            summary=summary,
            detailed_report=detailed,
            artifacts=["scenario_config.json", "manifest.json"],
            recommendations=recommendations,
            manifest=state.manifest or {},
        )

    def generate_final_report(
        self,
        iterations: List[Dict[str, Any]],
        final_state: "ConfigAgentState",
    ) -> Dict[str, Any]:
        """Generate final comprehensive report."""
        total_changes = sum(
            len(i.get("coder_output", {}).get("config_changes", [])) for i in iterations
        )
        successful = sum(
            1 for i in iterations if i.get("executor_output", {}).get("success", False)
        )

        return {
            "total_iterations": len(iterations),
            "successful_iterations": successful,
            "total_changes": total_changes,
            "final_config": final_state.patched_config,
            "final_manifest": final_state.manifest,
            "iterations": iterations,
            "audit_trail": final_state.audit_trail,
        }


def create_config_reporter(config: Dict[str, Any]):
    """Factory function to create config reporter from config."""
    return ConfigReporterAgent()
