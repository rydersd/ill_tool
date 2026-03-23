"""Tests for joint_geometry — joint type inference from bridge proportions.

Tests classification of narrow bridges as hinges, wide bridges as fixed,
and elongated bridges as slides.
"""

import pytest

from adobe_mcp.apps.illustrator.joint_geometry import (
    infer_joint_type,
    infer_rotation_range,
)


# ---------------------------------------------------------------------------
# Test: narrow bridge -> hinge
# ---------------------------------------------------------------------------


def test_narrow_bridge_hinge():
    """A bridge width < 20% of smaller part should classify as hinge."""
    result = infer_joint_type(
        connection_width=8.0,
        part_a_width=80.0,
        part_b_width=60.0,
    )
    # 8/60 = 0.133 < 0.20 -> hinge
    assert result["type"] == "hinge"
    assert result["confidence"] > 0.0
    assert result["rotation_range"] == [-90, 90]


# ---------------------------------------------------------------------------
# Test: wide bridge -> fixed
# ---------------------------------------------------------------------------


def test_wide_bridge_fixed():
    """A bridge width > 50% of smaller part should classify as fixed."""
    result = infer_joint_type(
        connection_width=40.0,
        part_a_width=60.0,
        part_b_width=50.0,
    )
    # 40/50 = 0.80 > 0.50 -> fixed
    assert result["type"] == "fixed"
    assert result["rotation_range"] == [-5, 5]


# ---------------------------------------------------------------------------
# Test: elongated bridge -> slide
# ---------------------------------------------------------------------------


def test_elongated_bridge_slide():
    """A bridge with aspect ratio > 3 should classify as slide."""
    result = infer_joint_type(
        connection_width=10.0,
        part_a_width=80.0,
        part_b_width=80.0,
        connection_height=50.0,  # aspect ratio 50/10 = 5 > 3
    )
    assert result["type"] == "slide"
    assert result["translation_axis"] == "vertical"


# ---------------------------------------------------------------------------
# Test: medium bridge -> ball_joint
# ---------------------------------------------------------------------------


def test_medium_bridge_ball_joint():
    """A bridge width 20-50% of smaller part should classify as ball_joint."""
    result = infer_joint_type(
        connection_width=20.0,
        part_a_width=80.0,
        part_b_width=60.0,
    )
    # 20/60 = 0.333 -> ball_joint
    assert result["type"] == "ball_joint"
    assert result["rotation_range"] == [-180, 180]


# ---------------------------------------------------------------------------
# Test: rotation range estimation
# ---------------------------------------------------------------------------


def test_rotation_range_hinge():
    """Hinge joint should have +-90 degree range by default."""
    result = infer_rotation_range("hinge")
    assert result["min_angle"] == -90
    assert result["max_angle"] == 90
    assert result["total_range"] == 180


def test_rotation_range_fixed():
    """Fixed joint should have very limited rotation."""
    result = infer_rotation_range("fixed")
    assert result["min_angle"] == -5
    assert result["max_angle"] == 5
    assert result["total_range"] == 10
