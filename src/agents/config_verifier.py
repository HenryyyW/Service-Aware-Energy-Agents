"""Config Verifier agent - validates schema, round-trip, determinism, completeness."""

from typing import Dict, Any, List
from pydantic import ValidationError
from src.agents.config_roles import ConfigVerifierOutput
from src.schemas.scenario import ScenarioConfig


class ConfigVerifierAgent:
    """Verifier agent for scenario configuration validation."""

    def __init__(self, determinism_tolerance: float = 1e-6):
        self.determinism_tolerance = determinism_tolerance

    def verify(
        self,
        config: Dict[str, Any],
        scenario_id: str = None,
        round_trip_test: bool = True,
        determinism_test: bool = True,
    ) -> "ConfigVerifierOutput":
        """
        Verify the scenario configuration.

        Args:
            config: The scenario configuration to verify
            scenario_id: Optional scenario ID
            round_trip_test: Whether to test round-trip serialization
            determinism_test: Whether to test determinism

        Returns:
            ConfigVerifierOutput with verification results
        """
        output = ConfigVerifierOutput()

        # 1. Schema validation
        output.schema_valid, schema_errors = self._validate_schema(config)
        output.schema_errors = schema_errors

        if not output.schema_valid:
            output.confidence = 0.0
            output.recommendation = "escalate"
            return output

        # 2. Round-trip validation
        if round_trip_test:
            output.round_trip_valid, rt_errors = self._test_round_trip(config)
            output.round_trip_errors = rt_errors

        # 3. Determinism test
        if determinism_test:
            output.determinism_check, det_errors, seed = self._test_determinism(config)
            output.determinism_errors = det_errors
            output.determinism_seed = seed

        # 4. Schema completeness check
        output.schema_complete, completeness_issues = self._check_completeness(config)
        output.completeness_issues = completeness_issues

        # Collect missing/out-of-range fields
        output.required_fields_missing = self._find_missing_required(config)
        output.out_of_range_fields = self._find_out_of_range(config)
        output.schema_rejections = self._find_schema_rejections(config)

        # Calculate confidence
        output.confidence = self._calculate_confidence(output)

        # Make recommendation
        output.recommendation = self._make_recommendation(output)

        # Build manifest
        output.manifest = self._build_manifest(config)

        return output

    def _validate_schema(self, config: Dict[str, Any]) -> tuple:
        """Validate config against ScenarioConfig schema."""
        errors = []

        try:
            # Parse and validate
            scenario = ScenarioConfig(**config)

            # Additional checks
            if not scenario.buildings:
                errors.append("No buildings configured")

            for i, building in enumerate(scenario.buildings):
                if building.pv and building.pv.capacity_kw <= 0:
                    errors.append(f"Building {i}: PV capacity must be positive")

                if building.battery:
                    if building.battery.capacity_kwh <= 0:
                        errors.append(
                            f"Building {i}: Battery capacity must be positive"
                        )
                    if building.battery.power_kw <= 0:
                        errors.append(f"Building {i}: Battery power must be positive")

            if scenario.timestep_minutes not in [5, 15, 30, 60]:
                # This is a warning, not error
                pass

        except ValidationError as e:
            for error in e.errors():
                field = ".".join(str(x) for x in error["loc"])
                msg = error["msg"]
                errors.append(f"{field}: {msg}")

        return len(errors) == 0, errors

    def _test_round_trip(self, config: Dict[str, Any]) -> tuple:
        """Test config round-trip serialization."""
        errors = []

        try:
            # Parse to model
            scenario = ScenarioConfig(**config)

            # Serialize to dict
            dumped = scenario.model_dump(mode="json")

            # Parse again
            reparsed = ScenarioConfig(**dumped)

            # Compare
            original_dump = config
            reparsed_dump = reparsed.model_dump(mode="json")

            # Compare key fields (ignore non-deterministic fields)
            if original_dump.get("scenario_id") != reparsed_dump.get("scenario_id"):
                errors.append("scenario_id mismatch in round-trip")

            if original_dump.get("name") != reparsed_dump.get("name"):
                errors.append(
                    f"name mismatch: {original_dump.get('name')} vs {reparsed_dump.get('name')}"
                )

            if len(original_dump.get("buildings", [])) != len(
                reparsed_dump.get("buildings", [])
            ):
                errors.append("building count mismatch in round-trip")

        except Exception as e:
            errors.append(f"Round-trip failed: {str(e)}")

        return len(errors) == 0, errors

    def _test_determinism(self, config: Dict[str, Any]) -> tuple:
        """Test determinism by running same config twice."""
        errors = []
        seed = config.get("random_seed", 42)

        try:
            # Parse twice
            scenario1 = ScenarioConfig(**config)
            scenario2 = ScenarioConfig(**config)

            dump1 = scenario1.model_dump(mode="json")
            dump2 = scenario2.model_dump(mode="json")

            # Compare all fields
            for key in set(dump1.keys()) | set(dump2.keys()):
                v1 = dump1.get(key)
                v2 = dump2.get(key)

                if isinstance(v1, float) and isinstance(v2, float):
                    if abs(v1 - v2) > self.determinism_tolerance:
                        errors.append(f"Non-deterministic float at {key}: {v1} vs {v2}")
                elif v1 != v2:
                    errors.append(f"Non-deterministic field at {key}: {v1} vs {v2}")

        except Exception as e:
            errors.append(f"Determinism test failed: {str(e)}")

        return len(errors) == 0, errors, seed

    def _check_completeness(self, config: Dict[str, Any]) -> tuple:
        """Check schema completeness - are all expected fields present?"""
        issues = []

        # Check scenario level
        if not config.get("scenario_id"):
            issues.append("Missing scenario_id")
        if not config.get("name"):
            issues.append("Missing scenario name")
        if not config.get("description"):
            issues.append("Missing description")

        # Check buildings
        buildings = config.get("buildings", [])
        if not buildings:
            issues.append("No buildings configured")
        else:
            for i, b in enumerate(buildings):
                if not b.get("building_id"):
                    issues.append(f"Building {i}: missing building_id")
                if not b.get("building_type"):
                    issues.append(f"Building {i}: missing building_type")

        # Check pandapower
        if not config.get("pandapower"):
            issues.append("No pandapower configuration")

        return len(issues) == 0, issues

    def _find_missing_required(self, config: Dict[str, Any]) -> List[str]:
        """Find missing required fields."""
        missing = []

        required = [
            "scenario_id",
            "name",
            "description",
            "buildings",
            "random_seed",
            "timestep_minutes",
        ]
        for field in required:
            if not config.get(field):
                missing.append(field)

        if config.get("buildings"):
            for i, b in enumerate(config.get("buildings", [])):
                if not b.get("building_id"):
                    missing.append(f"buildings[{i}].building_id")
                if not b.get("building_type"):
                    missing.append(f"buildings[{i}].building_type")

        return missing

    def _find_out_of_range(self, config: Dict[str, Any]) -> List[str]:
        """Find fields with out-of-range values."""
        out_of_range = []

        if config.get("timestep_minutes") not in [5, 15, 30, 60]:
            out_of_range.append(
                f"timestep_minutes: {config.get('timestep_minutes')} not in [5,15,30,60]"
            )

        for i, b in enumerate(config.get("buildings", [])):
            if b.get("pv") and b["pv"].get("capacity_kw", 0) <= 0:
                out_of_range.append(f"buildings[{i}].pv.capacity_kw must be positive")

            if b.get("battery"):
                if b["battery"].get("capacity_kwh", 0) <= 0:
                    out_of_range.append(
                        f"buildings[{i}].battery.capacity_kwh must be positive"
                    )
                if b["battery"].get("power_kw", 0) <= 0:
                    out_of_range.append(
                        f"buildings[{i}].battery.power_kw must be positive"
                    )

        return out_of_range

    def _find_schema_rejections(self, config: Dict[str, Any]) -> List[str]:
        """Find fields that would be rejected by schema."""
        rejections = []

        # Check for unknown fields (extra fields not in schema)
        known_fields = {
            "scenario_id",
            "name",
            "description",
            "buildings",
            "pandapower",
            "energy_sharing",
            "failures",
            "community_import_limit_kw",
            "community_export_limit_kw",
            "carbon_intensity_file",
            "random_seed",
            "timestep_minutes",
        }

        for key in config.keys():
            if key not in known_fields:
                rejections.append(f"Unknown field: {key}")

        return rejections

    def _calculate_confidence(self, output: "ConfigVerifierOutput") -> float:
        """Calculate overall confidence score."""
        score = 1.0

        if not output.schema_valid:
            score -= 0.5
        if not output.round_trip_valid:
            score -= 0.2
        if not output.determinism_check:
            score -= 0.15
        if not output.schema_complete:
            score -= 0.1

        # Penalize for errors
        error_count = (
            len(output.schema_errors)
            + len(output.round_trip_errors)
            + len(output.determinism_errors)
            + len(output.completeness_issues)
        )
        score -= min(0.3, error_count * 0.05)

        return max(0.0, score)

    def _make_recommendation(self, output: "ConfigVerifierOutput") -> str:
        """Make recommendation based on verification results."""
        if not output.schema_valid:
            return "escalate"
        if not output.round_trip_valid:
            return "retry"
        if not output.determinism_check:
            return "retry"
        if not output.schema_complete:
            return "retry"
        if output.confidence > 0.85:
            return "accept"
        elif output.confidence > 0.7:
            return "retry"
        return "escalate"

    def _build_manifest(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Build verification manifest."""
        return {
            "scenario_id": config.get("scenario_id"),
            "name": config.get("name"),
            "building_count": len(config.get("buildings", [])),
            "has_pv": any(b.get("pv") for b in config.get("buildings", [])),
            "has_battery": any(b.get("battery") for b in config.get("buildings", [])),
            "has_ev": any(b.get("evs") for b in config.get("buildings", [])),
            "has_flexible_load": any(
                b.get("flexible_loads") for b in config.get("buildings", [])
            ),
            "has_energy_sharing": bool(config.get("energy_sharing")),
            "has_dynamic_pricing": bool(
                (config.get("energy_sharing") or {}).get("dynamic_pricing", False)
            ),
            "community_import_limit": config.get("community_import_limit_kw"),
            "community_export_limit": config.get("community_export_limit_kw"),
            "timestep_minutes": config.get("timestep_minutes"),
            "random_seed": config.get("random_seed"),
        }


def create_config_verifier(config: Dict[str, Any]):
    """Factory function to create config verifier from config."""
    return ConfigVerifierAgent(
        determinism_tolerance=config.get("determinism_tolerance", 1e-6)
    )
