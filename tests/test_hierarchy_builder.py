"""Tests for the hierarchy builder.

Verifies tree construction from parts and connections, including
linear chains, branching, orphan attachment, and serialization.
All tests are pure Python -- no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.hierarchy_builder import (
    build_hierarchy,
    hierarchy_to_dict,
    hierarchy_to_flat,
)


# ---------------------------------------------------------------------------
# build_hierarchy
# ---------------------------------------------------------------------------


def test_linear_chain_three_parts():
    """3 parts in a chain should produce a linear hierarchy."""
    parts = [
        {"name": "torso", "area": 5000, "centroid": [100, 100]},
        {"name": "upper_arm", "area": 2000, "centroid": [150, 100]},
        {"name": "forearm", "area": 1500, "centroid": [200, 100]},
    ]
    connections = [
        {"part_a": "torso", "part_b": "upper_arm", "type": "joint", "position": [125, 100]},
        {"part_a": "upper_arm", "part_b": "forearm", "type": "joint", "position": [175, 100]},
    ]

    hierarchy = build_hierarchy(parts, connections)
    assert hierarchy["root"] == "torso"  # largest part

    # Find torso node
    torso_node = next(n for n in hierarchy["nodes"] if n["name"] == "torso")
    assert "upper_arm" in torso_node["children"]

    # Find upper_arm node
    arm_node = next(n for n in hierarchy["nodes"] if n["name"] == "upper_arm")
    assert "forearm" in arm_node["children"]
    assert arm_node["parent"] == "torso"


def test_branching_hierarchy():
    """1 parent with 2 children should produce branching hierarchy."""
    parts = [
        {"name": "body", "area": 8000, "centroid": [100, 100]},
        {"name": "arm_l", "area": 2000, "centroid": [50, 100]},
        {"name": "arm_r", "area": 2000, "centroid": [150, 100]},
    ]
    connections = [
        {"part_a": "body", "part_b": "arm_l", "type": "joint", "position": [75, 100]},
        {"part_a": "body", "part_b": "arm_r", "type": "joint", "position": [125, 100]},
    ]

    hierarchy = build_hierarchy(parts, connections)
    assert hierarchy["root"] == "body"

    body_node = next(n for n in hierarchy["nodes"] if n["name"] == "body")
    assert "arm_l" in body_node["children"]
    assert "arm_r" in body_node["children"]


def test_orphan_attached_to_nearest():
    """An unconnected part should be attached to nearest connected part."""
    parts = [
        {"name": "body", "area": 8000, "centroid": [100, 100]},
        {"name": "arm", "area": 2000, "centroid": [150, 100]},
        {"name": "hat", "area": 500, "centroid": [100, 30]},  # no connection
    ]
    connections = [
        {"part_a": "body", "part_b": "arm", "type": "joint", "position": [125, 100]},
    ]

    hierarchy = build_hierarchy(parts, connections)
    # hat should be attached to body (nearest)
    hat_node = next(n for n in hierarchy["nodes"] if n["name"] == "hat")
    assert hat_node["parent"] == "body"


def test_containment_makes_container_parent():
    """Containment connections should make the larger part the parent."""
    parts = [
        {"name": "outer", "area": 10000, "centroid": [100, 100]},
        {"name": "inner", "area": 2000, "centroid": [100, 100]},
    ]
    connections = [
        {"part_a": "outer", "part_b": "inner", "type": "containment", "position": [100, 100]},
    ]

    hierarchy = build_hierarchy(parts, connections)
    assert hierarchy["root"] == "outer"
    inner_node = next(n for n in hierarchy["nodes"] if n["name"] == "inner")
    assert inner_node["parent"] == "outer"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_hierarchy_to_dict_nested():
    """hierarchy_to_dict should create nested dict structure."""
    hierarchy = {
        "root": "body",
        "nodes": [
            {"name": "body", "parent": None, "children": ["arm"], "pivot_position": None},
            {"name": "arm", "parent": "body", "children": [], "pivot_position": [125, 100]},
        ],
    }
    nested = hierarchy_to_dict(hierarchy)
    assert nested["name"] == "body"
    assert len(nested["children"]) == 1
    assert nested["children"][0]["name"] == "arm"


def test_hierarchy_to_flat():
    """hierarchy_to_flat should produce a flat list with parent refs."""
    hierarchy = {
        "root": "body",
        "nodes": [
            {"name": "body", "parent": None, "children": ["arm"], "pivot_position": None},
            {"name": "arm", "parent": "body", "children": [], "pivot_position": [125, 100]},
        ],
    }
    flat = hierarchy_to_flat(hierarchy)
    assert len(flat) == 2
    body = next(n for n in flat if n["name"] == "body")
    assert body["parent"] is None
    arm = next(n for n in flat if n["name"] == "arm")
    assert arm["parent"] == "body"
    assert arm["pivot_position"] == [125, 100]
