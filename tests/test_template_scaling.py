"""Tests for template_scaling — proportional position scaling.

Tests 2x scaling, rotation constraint preservation, translation constraint
scaling, and proportion-maintaining matching to target parts.
"""

import pytest

from adobe_mcp.apps.illustrator.template_scaling import (
    scale_template,
    maintain_proportions,
    adjust_constraints,
)


def _make_template_with_positions():
    """Helper: template with parts at known positions."""
    return {
        "name": "test_template",
        "parts": [
            {"name": "head", "position": [100, 50]},
            {"name": "torso", "position": [100, 150]},
            {"name": "foot_l", "position": [80, 300]},
            {"name": "foot_r", "position": [120, 300]},
        ],
        "connections": [],
        "constraints": [
            {"type": "rotation", "part": "head", "min_angle": -30, "max_angle": 30},
            {"type": "translation", "part": "torso", "min_x": -50, "max_x": 50,
             "min_y": -20, "max_y": 20},
        ],
        "metadata": {},
    }


# ---------------------------------------------------------------------------
# Test: 2x scale -> positions doubled
# ---------------------------------------------------------------------------


def test_2x_scale_positions_doubled():
    """Scaling to a 2x target should roughly double relative positions."""
    template = _make_template_with_positions()
    # Original spans: x=[80,120]=40 wide, y=[50,300]=250 tall
    # Target is 2x: 80 wide, 500 tall
    target_bounds = {"x": 0, "y": 0, "width": 80, "height": 500}

    result = scale_template(template, target_bounds)
    parts = {p["name"]: p for p in result["parts"]}

    # Verify scale factors recorded
    assert result["_scaling"]["scale_x"] == 2.0
    assert result["_scaling"]["scale_y"] == 2.0

    # Head was at relative (20, 0) from min -> should be at (40, 0) in target
    assert parts["head"]["position"][0] == pytest.approx(40.0, abs=1)
    assert parts["head"]["position"][1] == pytest.approx(0.0, abs=1)


# ---------------------------------------------------------------------------
# Test: rotation constraints unchanged after adjust_constraints
# ---------------------------------------------------------------------------


def test_rotation_constraints_preserved():
    """adjust_constraints should not modify rotation constraints."""
    template = _make_template_with_positions()
    result = adjust_constraints(template, scale_factor=2.0)

    for constraint in result["constraints"]:
        if constraint["type"] == "rotation":
            assert constraint["min_angle"] == -30
            assert constraint["max_angle"] == 30


# ---------------------------------------------------------------------------
# Test: translation constraints scaled
# ---------------------------------------------------------------------------


def test_translation_constraints_scaled():
    """adjust_constraints should scale translation limits by scale_factor."""
    template = _make_template_with_positions()
    result = adjust_constraints(template, scale_factor=2.0)

    for constraint in result["constraints"]:
        if constraint["type"] == "translation":
            assert constraint["min_x"] == -100.0  # -50 * 2
            assert constraint["max_x"] == 100.0
            assert constraint["min_y"] == -40.0  # -20 * 2
            assert constraint["max_y"] == 40.0


# ---------------------------------------------------------------------------
# Test: maintain_proportions with matching target parts
# ---------------------------------------------------------------------------


def test_maintain_proportions_matching():
    """When target parts match template names, positions should adjust."""
    template = _make_template_with_positions()
    target_parts = [
        {"name": "head", "centroid": [200, 100]},
        {"name": "torso", "centroid": [200, 300]},
        {"name": "foot_l", "centroid": [160, 600]},
        {"name": "foot_r", "centroid": [240, 600]},
    ]

    result = maintain_proportions(template, target_parts)
    assert "_proportion_match" in result
    assert result["_proportion_match"]["matched_parts"] == 4
    # Scale should be ~2x since target is 2x source
    assert result["_proportion_match"]["scale_applied"] > 1.5


# ---------------------------------------------------------------------------
# Test: scale with empty parts -> no crash
# ---------------------------------------------------------------------------


def test_scale_empty_parts():
    """Scaling a template with no parts should not raise."""
    template = {"name": "empty", "parts": []}
    target_bounds = {"x": 0, "y": 0, "width": 100, "height": 100}

    result = scale_template(template, target_bounds)
    assert result["parts"] == []
