"""Tests for joint-specific timing/easing curves.

Verifies that joint types get the correct easing curves and
AE interpolation values are generated.
All tests are pure Python — no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.timing_curves import (
    get_timing_curve,
    generate_ae_easing,
    _classify_joint,
)


# ---------------------------------------------------------------------------
# Hip -> cubic (large joint)
# ---------------------------------------------------------------------------


def test_hip_gets_cubic():
    """Large joints like hip should get ease_in_out_cubic."""
    result = get_timing_curve("large", "rotation")

    assert result["curve_name"] == "ease_in_out_cubic"
    assert result["joint_type"] == "large"
    assert "bezier" in result
    assert result["influence_in"] == 75.0
    assert result["influence_out"] == 75.0


# ---------------------------------------------------------------------------
# Wrist -> snappy (small joint)
# ---------------------------------------------------------------------------


def test_wrist_gets_snappy():
    """Small joints like wrist should get ease_out_quad (snappy)."""
    result = get_timing_curve("small", "rotation")

    assert result["curve_name"] == "ease_out_quad"
    assert result["joint_type"] == "small"
    # Snappy = strong out influence, weak in
    assert result["influence_in"] < result["influence_out"]


# ---------------------------------------------------------------------------
# Secondary -> spring
# ---------------------------------------------------------------------------


def test_secondary_gets_spring():
    """Secondary parts should get spring easing with overshoot."""
    result = get_timing_curve("secondary", "rotation")

    assert result["curve_name"] == "spring"
    assert "overshoot" in result
    assert result["overshoot"] > 0.0
    assert "oscillations" in result


# ---------------------------------------------------------------------------
# Joint name auto-classification
# ---------------------------------------------------------------------------


def test_joint_name_classification():
    """Joint names should auto-classify to the correct type."""
    assert _classify_joint("hip_l") == "large"
    assert _classify_joint("shoulder_r") == "large"
    assert _classify_joint("elbow_l") == "medium"
    assert _classify_joint("knee_r") == "medium"
    assert _classify_joint("wrist_l") == "small"
    assert _classify_joint("ankle_r") == "small"
    assert _classify_joint("tail_tip") == "secondary"
    assert _classify_joint("hair_strand") == "secondary"


# ---------------------------------------------------------------------------
# AE easing generation
# ---------------------------------------------------------------------------


def test_ae_easing_generation():
    """generate_ae_easing should return valid AE keyframe interpolation data."""
    result = generate_ae_easing("ease_in_out_cubic")

    assert result["curve_name"] == "ease_in_out_cubic"
    assert "keyframe_interpolation" in result
    assert "ae_expression" in result

    ki = result["keyframe_interpolation"]
    assert ki["inType"] == "BEZIER"
    assert ki["outType"] == "BEZIER"
    assert "inTemporalEase" in ki
    assert "outTemporalEase" in ki
