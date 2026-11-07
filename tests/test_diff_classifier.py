"""Unit tests for diff classification (behavior-changing vs cosmetic patches)."""

import pytest
from src.agents.diff_classifier import (
    classify_diff,
    is_behavior_changing,
    DiffClassification,
)

# Test code snippets
SIMPLE_CONTROLLER = '''class RuleBasedController:
    def __init__(self, scenario_config):
        self.config = scenario_config

    def get_actions(self, observations, timestep):
        """Get actions for this timestep."""
        actions = []
        # Simple control logic
        for building_id, obs in observations.items():
            actions.append({"asset_id": f"{building_id}_battery", "value_kw": 0.0})
        return actions
'''

CONTROLLER_WITH_COMMENT_ONLY = '''class RuleBasedController:
    def __init__(self, scenario_config):
        self.config = scenario_config

    def get_actions(self, observations, timestep):
        """Get actions for this timestep."""
        # PATCHED: Add voltage monitoring
        actions = []
        # Simple control logic
        for building_id, obs in observations.items():
            actions.append({"asset_id": f"{building_id}_battery", "value_kw": 0.0})
        return actions
'''

CONTROLLER_WITH_DOCSTRING_ONLY = '''class RuleBasedController:
    def __init__(self, scenario_config):
        self.config = scenario_config

    def get_actions(self, observations, timestep):
        """Get actions for this timestep.
        
        This function now includes voltage monitoring.
        """
        actions = []
        # Simple control logic
        for building_id, obs in observations.items():
            actions.append({"asset_id": f"{building_id}_battery", "value_kw": 0.0})
        return actions
'''

CONTROLLER_WITH_BEHAVIOR_CHANGE = '''class RuleBasedController:
    def __init__(self, scenario_config):
        self.config = scenario_config

    def get_actions(self, observations, timestep):
        """Get actions for this timestep."""
        actions = []
        # Simple control logic
        for building_id, obs in observations.items():
            # PATCHED: Add voltage check
            voltage = obs.get("voltage", 1.0)
            if voltage > 1.05:
                actions.append({"asset_id": f"{building_id}_battery", "value_kw": -5.0})
            else:
                actions.append({"asset_id": f"{building_id}_battery", "value_kw": 0.0})
        return actions
'''

CONTROLLER_WITH_CONSTANT_CHANGE = '''class RuleBasedController:
    def __init__(self, scenario_config):
        self.config = scenario_config

    def get_actions(self, observations, timestep):
        """Get actions for this timestep."""
        actions = []
        # PATCHED: Changed default battery power from 0.0 to 2.0
        DEFAULT_BATTERY_POWER = 2.0  # Was 0.0
        for building_id, obs in observations.items():
            actions.append({"asset_id": f"{building_id}_battery", "value_kw": DEFAULT_BATTERY_POWER})
        return actions
'''

CONTROLLER_WITH_OPERATOR_CHANGE = '''class RuleBasedController:
    def __init__(self, scenario_config):
        self.config = scenario_config

    def get_actions(self, observations, timestep):
        """Get actions for this timestep."""
        actions = []
        for building_id, obs in observations.items():
            voltage = obs.get("voltage", 1.0)
            # PATCHED: Changed > to >= for voltage threshold
            if voltage >= 1.05:  # Was >
                actions.append({"asset_id": f"{building_id}_battery", "value_kw": -5.0})
            else:
                actions.append({"asset_id": f"{building_id}_battery", "value_kw": 0.0})
        return actions
'''

CONTROLLER_WITH_WHITESPACE_ONLY = '''class RuleBasedController:
    def __init__(self, scenario_config):
        self.config = scenario_config

    def get_actions(self, observations, timestep):
        """Get actions for this timestep."""
        actions = []
        
        
        # Simple control logic
        for building_id, obs in observations.items():
            actions.append({"asset_id": f"{building_id}_battery", "value_kw": 0.0})
        return actions
'''

CONTROLLER_WITH_MULTILINE_COMMENT = '''class RuleBasedController:
    def __init__(self, scenario_config):
        self.config = scenario_config

    def get_actions(self, observations, timestep):
        """Get actions for this timestep."""
        # PATCHED: 
        # This is a multi-line comment
        # explaining the voltage fix
        actions = []
        # Simple control logic
        for building_id, obs in observations.items():
            actions.append({"asset_id": f"{building_id}_battery", "value_kw": 0.0})
        return actions
'''


def test_comment_only_patch_rejected():
    """Comment-only patch should be rejected as cosmetic."""
    classification = classify_diff(SIMPLE_CONTROLLER, CONTROLLER_WITH_COMMENT_ONLY)

    assert classification.is_behavior_changing is False
    assert (
        "cosmetic" in classification.reason.lower()
        or "comment" in classification.reason.lower()
    )
    assert len(classification.cosmetic_changes) > 0


def test_docstring_only_patch_rejected():
    """Docstring-only patch should be rejected as cosmetic."""
    classification = classify_diff(SIMPLE_CONTROLLER, CONTROLLER_WITH_DOCSTRING_ONLY)

    assert classification.is_behavior_changing is False
    assert (
        "cosmetic" in classification.reason.lower()
        or "docstring" in classification.reason.lower()
    )


def test_whitespace_only_patch_rejected():
    """Whitespace-only patch should be rejected as cosmetic."""
    classification = classify_diff(SIMPLE_CONTROLLER, CONTROLLER_WITH_WHITESPACE_ONLY)

    assert classification.is_behavior_changing is False
    assert (
        "cosmetic" in classification.reason.lower()
        or "whitespace" in classification.reason.lower()
    )


def test_multiline_comment_only_patch_rejected():
    """Multi-line comment-only patch should be rejected as cosmetic."""
    classification = classify_diff(SIMPLE_CONTROLLER, CONTROLLER_WITH_MULTILINE_COMMENT)

    assert classification.is_behavior_changing is False
    assert (
        "cosmetic" in classification.reason.lower()
        or "comment" in classification.reason.lower()
    )


def test_behavior_change_accepted():
    """Real behavior change (new if statement) should be accepted."""
    classification = classify_diff(SIMPLE_CONTROLLER, CONTROLLER_WITH_BEHAVIOR_CHANGE)

    assert classification.is_behavior_changing is True
    assert len(classification.behavior_changes) > 0


def test_constant_change_accepted():
    """New constant assignment should be accepted as behavior change."""
    classification = classify_diff(SIMPLE_CONTROLLER, CONTROLLER_WITH_CONSTANT_CHANGE)

    assert classification.is_behavior_changing is True
    assert len(classification.behavior_changes) > 0


def test_operator_change_accepted():
    """Changed operator (>= vs >) should be accepted as behavior change."""
    classification = classify_diff(SIMPLE_CONTROLLER, CONTROLLER_WITH_OPERATOR_CHANGE)

    assert classification.is_behavior_changing is True
    assert len(classification.behavior_changes) > 0


def test_no_changes_returns_false():
    """Identical code should return is_behavior_changing=False."""
    classification = classify_diff(SIMPLE_CONTROLLER, SIMPLE_CONTROLLER)

    assert classification.is_behavior_changing is False
    assert "no changes" in classification.reason.lower()


def test_is_behavior_changing_helper():
    """Test the helper function."""
    assert (
        is_behavior_changing(SIMPLE_CONTROLLER, CONTROLLER_WITH_BEHAVIOR_CHANGE) is True
    )
    assert (
        is_behavior_changing(SIMPLE_CONTROLLER, CONTROLLER_WITH_COMMENT_ONLY) is False
    )
    assert is_behavior_changing(SIMPLE_CONTROLLER, SIMPLE_CONTROLLER) is False


def test_classification_structure():
    """Test DiffClassification structure has all required fields."""
    classification = classify_diff(SIMPLE_CONTROLLER, CONTROLLER_WITH_BEHAVIOR_CHANGE)

    assert isinstance(classification, DiffClassification)
    assert isinstance(classification.is_behavior_changing, bool)
    assert isinstance(classification.reason, str)
    assert isinstance(classification.changed_lines, list)
    assert isinstance(classification.behavior_changes, list)
    assert isinstance(classification.cosmetic_changes, list)


def test_syntax_error_handling():
    """Test handling of syntax errors in patched code - still detects behavior tokens."""
    bad_code = "def foo(:\n    pass"
    classification = classify_diff(SIMPLE_CONTROLLER, bad_code)

    # Syntax error code still has executable tokens (def, pass), so it's behavior-changing
    # The executor will catch the syntax error separately
    assert classification.is_behavior_changing is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
