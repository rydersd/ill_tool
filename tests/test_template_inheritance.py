"""Tests for template_inheritance — add/remove/merge template operations.

Tests adding wings to a biped, removing a tail from a quadruped,
merging two templates, deriving templates, and name collision handling.
"""

import pytest

from adobe_mcp.apps.illustrator.template_inheritance import (
    add_parts,
    remove_parts,
    merge_templates,
    derive_template,
)


def _make_biped_template():
    """Helper: create a minimal biped template."""
    return {
        "name": "biped",
        "parts": [
            {"name": "torso", "area": 5000},
            {"name": "leg_l", "area": 2000},
            {"name": "leg_r", "area": 2000},
        ],
        "connections": [
            {"from": "torso", "to": "leg_l", "type": "hinge"},
            {"from": "torso", "to": "leg_r", "type": "hinge"},
        ],
        "constraints": [],
        "poses": {},
        "metadata": {},
    }


def _make_quadruped_template():
    """Helper: create a minimal quadruped template with tail."""
    return {
        "name": "quadruped",
        "parts": [
            {"name": "body", "area": 8000},
            {"name": "leg_fl", "area": 1500},
            {"name": "leg_fr", "area": 1500},
            {"name": "leg_bl", "area": 1500},
            {"name": "leg_br", "area": 1500},
            {"name": "tail", "area": 500},
        ],
        "connections": [
            {"from": "body", "to": "leg_fl", "type": "hinge"},
            {"from": "body", "to": "leg_fr", "type": "hinge"},
            {"from": "body", "to": "leg_bl", "type": "hinge"},
            {"from": "body", "to": "leg_br", "type": "hinge"},
            {"from": "body", "to": "tail", "type": "ball_joint"},
        ],
        "constraints": [],
        "poses": {},
        "metadata": {},
    }


# ---------------------------------------------------------------------------
# Test: add wings to biped
# ---------------------------------------------------------------------------


def test_add_wings_to_biped():
    """Adding wings should increase part and connection count."""
    template = _make_biped_template()
    wings = [
        {"name": "wing_l", "area": 1000, "connects_to": "torso"},
        {"name": "wing_r", "area": 1000, "connects_to": "torso"},
    ]

    result = add_parts(template, wings)
    part_names = [p["name"] for p in result["parts"]]

    assert "wing_l" in part_names
    assert "wing_r" in part_names
    assert len(result["parts"]) == 5  # 3 original + 2 wings
    # Should have 2 new connections
    wing_connections = [
        c for c in result["connections"]
        if c["to"] in ("wing_l", "wing_r")
    ]
    assert len(wing_connections) == 2


# ---------------------------------------------------------------------------
# Test: remove tail from quadruped
# ---------------------------------------------------------------------------


def test_remove_tail_from_quadruped():
    """Removing tail should remove the part and its connection."""
    template = _make_quadruped_template()
    result = remove_parts(template, ["tail"])

    part_names = [p["name"] for p in result["parts"]]
    assert "tail" not in part_names
    assert len(result["parts"]) == 5  # 6 - 1

    # No connection should reference tail
    for conn in result["connections"]:
        assert conn["from"] != "tail"
        assert conn["to"] != "tail"


# ---------------------------------------------------------------------------
# Test: merge two templates
# ---------------------------------------------------------------------------


def test_merge_templates():
    """Merging template_b onto template_a should combine parts and connections."""
    template_a = _make_biped_template()
    template_b = {
        "name": "wings",
        "parts": [
            {"name": "wing_base", "area": 800},
            {"name": "wing_tip", "area": 400},
        ],
        "connections": [
            {"from": "wing_base", "to": "wing_tip", "type": "hinge"},
        ],
        "constraints": [],
        "poses": {},
        "metadata": {},
    }

    result = merge_templates(template_a, template_b, merge_point="torso")
    assert "error" not in result

    # Should have all parts from both templates
    assert len(result["parts"]) == 5  # 3 + 2

    # Should have a connection from torso to the first part of template_b
    merge_connections = [
        c for c in result["connections"]
        if c["from"] == "torso" and "wing_base" in c["to"]
    ]
    assert len(merge_connections) == 1


# ---------------------------------------------------------------------------
# Test: derive template with modifications
# ---------------------------------------------------------------------------


def test_derive_template():
    """derive_template should apply add/remove modifications."""
    base = _make_biped_template()
    modifications = {
        "add": [{"name": "tail", "area": 300, "connects_to": "torso"}],
        "remove": ["leg_r"],
    }

    result = derive_template(base, modifications)
    part_names = [p["name"] for p in result["parts"]]

    assert "tail" in part_names
    assert "leg_r" not in part_names
    assert result["name"].endswith("_derived")
    assert result["metadata"]["derived_from"] == "biped"


# ---------------------------------------------------------------------------
# Test: merge with invalid merge point -> error
# ---------------------------------------------------------------------------


def test_merge_invalid_merge_point():
    """Merging with a non-existent merge point should return error."""
    template_a = _make_biped_template()
    template_b = {
        "name": "wings",
        "parts": [{"name": "wing", "area": 500}],
        "connections": [],
        "constraints": [],
        "poses": {},
        "metadata": {},
    }

    result = merge_templates(template_a, template_b, merge_point="nonexistent")
    assert "error" in result
