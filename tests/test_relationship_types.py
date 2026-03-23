"""Tests for the relationship types module.

Verifies inference from known geometries and AE expression generation.
All tests are pure Python -- no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.relationship_types import (
    RELATIONSHIP_TYPES,
    infer_relationship,
    get_ae_expression,
)


# ---------------------------------------------------------------------------
# infer_relationship
# ---------------------------------------------------------------------------


def test_infer_joint_defaults_to_hinge():
    """A 'joint' connection with no shape info should default to rigid_hinge."""
    result = infer_relationship("joint")
    assert result["type"] == "rigid_hinge"
    assert result["confidence"] > 0.5
    assert result["properties"]["rotation"] is True


def test_infer_joint_elongated_parts_suggest_flex():
    """Elongated parts at a joint should suggest flex relationship."""
    shapes = {
        "part_a": {"aspect_ratio": 4.0, "area": 2000},
        "part_b": {"aspect_ratio": 1.5, "area": 1000},
    }
    result = infer_relationship("joint", shapes)
    assert result["type"] == "flex"


def test_infer_containment_is_fixed():
    """Containment connections should infer fixed relationship."""
    result = infer_relationship("containment")
    assert result["type"] == "fixed"
    assert result["confidence"] > 0.8


def test_infer_separate_is_fixed():
    """Separate (no connection) should default to fixed with low confidence."""
    result = infer_relationship("separate")
    assert result["type"] == "fixed"
    assert result["confidence"] < 0.5


# ---------------------------------------------------------------------------
# get_ae_expression
# ---------------------------------------------------------------------------


def test_ae_expression_hinge():
    """rigid_hinge should return a rotation-based AE expression."""
    result = get_ae_expression("rigid_hinge")
    assert result["type"] == "rigid_hinge"
    assert "rotation" in result["expression"].lower() or "rot" in result["expression"].lower()
    assert result["description"] != ""


def test_ae_expression_unknown_type():
    """Unknown relationship type should return a comment expression."""
    result = get_ae_expression("nonexistent_type")
    assert "Unknown" in result["expression"] or "unknown" in result["description"].lower()
