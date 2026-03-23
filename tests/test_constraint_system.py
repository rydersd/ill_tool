"""Tests for the constraint system.

Verifies constraint creation, pose validation, and clamping.
All tests are pure Python -- no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.constraint_system import (
    create_constraint,
    validate_pose,
    clamp_to_constraints,
)


# ---------------------------------------------------------------------------
# create_constraint
# ---------------------------------------------------------------------------


def test_create_constraint():
    """create_constraint should return a well-formed constraint dict."""
    c = create_constraint("elbow_l", "rotation", -90.0, 0.0)
    assert c["joint_name"] == "elbow_l"
    assert c["type"] == "rotation"
    assert c["min"] == -90.0
    assert c["max"] == 0.0


# ---------------------------------------------------------------------------
# validate_pose
# ---------------------------------------------------------------------------


def test_validate_pose_within_range():
    """A pose within all constraint ranges should be valid."""
    rig = {
        "constraints": {
            "elbow_l": {"type": "rotation", "min": -90.0, "max": 0.0},
            "shoulder_l": {"type": "rotation", "min": -180.0, "max": 180.0},
        }
    }
    pose = {"elbow_l": -45.0, "shoulder_l": 30.0}
    result = validate_pose(rig, pose)
    assert result["valid"] is True
    assert result["violations"] == []


def test_validate_pose_outside_range():
    """A pose outside constraint range should report violations."""
    rig = {
        "constraints": {
            "elbow_l": {"type": "rotation", "min": -90.0, "max": 0.0},
        }
    }
    pose = {"elbow_l": 45.0}  # above max of 0
    result = validate_pose(rig, pose)
    assert result["valid"] is False
    assert len(result["violations"]) == 1
    assert result["violations"][0]["joint"] == "elbow_l"
    assert result["violations"][0]["value"] == 45.0


# ---------------------------------------------------------------------------
# clamp_to_constraints
# ---------------------------------------------------------------------------


def test_clamp_within_range_unchanged():
    """Values within range should not be changed by clamp."""
    rig = {
        "constraints": {
            "elbow_l": {"type": "rotation", "min": -90.0, "max": 0.0},
        }
    }
    pose = {"elbow_l": -45.0}
    clamped = clamp_to_constraints(rig, pose)
    assert clamped["elbow_l"] == -45.0


def test_clamp_outside_range_clamped():
    """Values outside range should be clamped to the nearest bound."""
    rig = {
        "constraints": {
            "elbow_l": {"type": "rotation", "min": -90.0, "max": 0.0},
        }
    }
    pose = {"elbow_l": 45.0, "wrist_l": 30.0}  # elbow above max, wrist unconstrained
    clamped = clamp_to_constraints(rig, pose)
    assert clamped["elbow_l"] == 0.0  # clamped to max
    assert clamped["wrist_l"] == 30.0  # unconstrained, unchanged
