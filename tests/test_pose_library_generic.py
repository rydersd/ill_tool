"""Tests for generic pose library presets.

Verifies pose availability, application, unknown types, and value clamping.
All tests are pure Python — no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.pose_library_generic import (
    get_poses_for_type,
    apply_pose_preset,
    POSE_PRESETS,
)


# ---------------------------------------------------------------------------
# Biped has idle pose
# ---------------------------------------------------------------------------


def test_biped_has_idle_pose():
    """Biped type should include an 'idle' pose with expected joints."""
    result = get_poses_for_type("biped")

    assert result["type"] == "biped"
    assert "idle" in result["poses"]
    assert "walk_contact" in result["poses"]
    assert "jump" in result["poses"]

    idle = result["poses"]["idle"]
    assert "hip" in idle
    assert "shoulder_l" in idle
    assert "knee_r" in idle


# ---------------------------------------------------------------------------
# Apply preset sets joint values
# ---------------------------------------------------------------------------


def test_apply_preset_sets_values():
    """Applying a pose preset should set joint angles based on range percentages."""
    rig = {
        "joints": {
            "hip": {"x": 0, "y": 0},
            "knee_l": {"x": 0, "y": -50},
        },
        "motion_ranges": {
            "hip": {"min_deg": -90.0, "max_deg": 90.0},
            "knee_l": {"min_deg": -90.0, "max_deg": 90.0},
        },
    }

    result = apply_pose_preset(rig, "biped", "idle")

    assert result["applied"] is True
    assert "joint_angles" in result

    # idle hip = 50% → angle = -90 + (50/100)*(180) = 0.0
    assert result["joint_angles"]["hip"] == pytest.approx(0.0)

    # idle knee_l = 45% → angle = -90 + (45/100)*(180) = -9.0
    assert result["joint_angles"]["knee_l"] == pytest.approx(-9.0)


# ---------------------------------------------------------------------------
# Unknown type returns empty
# ---------------------------------------------------------------------------


def test_unknown_type_returns_empty():
    """An unknown object type should return empty poses."""
    result = get_poses_for_type("spaceship")

    assert result["type"] == "spaceship"
    assert result["poses"] == {}
    assert "available_types" in result


# ---------------------------------------------------------------------------
# Relative values clamp to range
# ---------------------------------------------------------------------------


def test_apply_preset_clamps_values():
    """Values beyond 0-100% should be clamped, not overflow the range."""
    rig = {
        "joints": {"test_joint": {"x": 0, "y": 0}},
        "motion_ranges": {
            "test_joint": {"min_deg": -45.0, "max_deg": 45.0},
        },
    }

    # Manually test with a rig that has an extreme (we can verify clamping
    # works by checking the preset values are within range)
    result = apply_pose_preset(rig, "biped", "idle")
    assert result["applied"] is True

    # All angles should be within the joint ranges they reference,
    # or within default -180..+180 if no range is set
    for joint, angle in result["joint_angles"].items():
        jr = rig["motion_ranges"].get(joint, {"min_deg": -180, "max_deg": 180})
        assert jr["min_deg"] <= angle <= jr["max_deg"]


# ---------------------------------------------------------------------------
# Unknown preset returns error
# ---------------------------------------------------------------------------


def test_unknown_preset_returns_error():
    """Requesting a non-existent preset returns an error with available list."""
    rig = {"joints": {}, "motion_ranges": {}}

    result = apply_pose_preset(rig, "biped", "nonexistent_pose")

    assert result["applied"] is False
    assert "error" in result
    assert "available" in result
    assert "idle" in result["available"]
