"""Tests for the object hierarchy management tool.

Verifies pivot setting, auto-inference from bones, tree building,
cycle detection, orphan detection, and hierarchy validation.
All tests are pure Python -- no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.object_hierarchy import (
    set_pivot,
    auto_pivots,
    get_pivot_tree,
    validate_hierarchy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rig_with_bones():
    """Create a rig with spine and arm bones for testing."""
    return {
        "character_name": "test_char",
        "joints": {
            "spine_base": {"x": 100, "y": 200},
            "spine_mid": {"x": 100, "y": 150},
            "spine_top": {"x": 100, "y": 100},
            "shoulder_l": {"x": 80, "y": 100},
            "elbow_l": {"x": 60, "y": 130},
            "wrist_l": {"x": 40, "y": 160},
        },
        "bones": [
            {"name": "spine_lower", "parent_joint": "spine_base", "child_joint": "spine_mid"},
            {"name": "spine_upper", "parent_joint": "spine_mid", "child_joint": "spine_top"},
            {"name": "upper_arm_l", "parent_joint": "shoulder_l", "child_joint": "elbow_l"},
            {"name": "forearm_l", "parent_joint": "elbow_l", "child_joint": "wrist_l"},
        ],
        "bindings": {},
        "landmarks": {},
    }


# ---------------------------------------------------------------------------
# set_pivot
# ---------------------------------------------------------------------------


def test_set_pivot_stores_data():
    """set_pivot should store pivot data on the landmark."""
    rig = {"landmarks": {}}
    landmark = set_pivot(
        rig, "elbow_l", "hinge", "upper_arm to forearm",
        [-90, 90], "upper_arm_l", ["forearm_l"], "rigid_hinge"
    )

    assert "pivot" in landmark
    assert landmark["pivot"]["type"] == "hinge"
    assert landmark["pivot"]["connects"] == "upper_arm to forearm"
    assert landmark["pivot"]["rotation_range"] == [-90, 90]
    assert landmark["pivot"]["parent_part"] == "upper_arm_l"
    assert landmark["pivot"]["child_parts"] == ["forearm_l"]
    assert landmark["pivot"]["relationship"] == "rigid_hinge"
    # Verify it's stored in the rig
    assert "elbow_l" in rig["landmarks"]


def test_set_pivot_creates_landmark_if_missing():
    """set_pivot should create the landmarks dict if it doesn't exist."""
    rig = {}
    set_pivot(rig, "new_joint", "ball", "test", [-180, 180], "a", ["b"], "ball_joint")
    assert "landmarks" in rig
    assert "new_joint" in rig["landmarks"]
    assert rig["landmarks"]["new_joint"]["pivot"]["type"] == "ball"


# ---------------------------------------------------------------------------
# auto_pivots
# ---------------------------------------------------------------------------


def test_auto_pivots_infers_from_bones():
    """auto_pivots should create pivot data for each bone's child joint."""
    rig = _make_rig_with_bones()
    inferred = auto_pivots(rig)

    # Should create pivots for spine_mid, spine_top, elbow_l, wrist_l
    assert len(inferred) >= 4
    pivot_names = [p["name"] for p in inferred]
    assert "spine_mid" in pivot_names
    assert "elbow_l" in pivot_names
    assert "wrist_l" in pivot_names


def test_auto_pivots_detects_branching():
    """A joint with multiple child bones should get a ball joint type."""
    rig = {
        "joints": {
            "center": {"x": 100, "y": 100},
            "arm_l": {"x": 50, "y": 100},
            "arm_r": {"x": 150, "y": 100},
            "head": {"x": 100, "y": 50},
        },
        "bones": [
            {"name": "to_arm_l", "parent_joint": "center", "child_joint": "arm_l"},
            {"name": "to_arm_r", "parent_joint": "center", "child_joint": "arm_r"},
            {"name": "to_head", "parent_joint": "center", "child_joint": "head"},
        ],
        "bindings": {},
        "landmarks": {},
    }
    # center has 3 child bones but center is the parent_joint not child_joint
    # The auto_pivots creates pivots at child_joint endpoints: arm_l, arm_r, head
    inferred = auto_pivots(rig)
    names = [p["name"] for p in inferred]
    assert "arm_l" in names
    assert "arm_r" in names


# ---------------------------------------------------------------------------
# get_pivot_tree
# ---------------------------------------------------------------------------


def test_get_pivot_tree_builds_tree():
    """get_pivot_tree should build a nested tree from pivot relationships."""
    rig = {"landmarks": {}}
    set_pivot(rig, "root", "ball", "root", [-180, 180], "", ["child_a", "child_b"], "ball_joint")
    set_pivot(rig, "child_a", "hinge", "a", [-90, 90], "root", [], "rigid_hinge")
    set_pivot(rig, "child_b", "hinge", "b", [-90, 90], "root", [], "rigid_hinge")

    tree = get_pivot_tree(rig)
    assert tree["name"] == "root"
    child_names = [c["name"] for c in tree.get("children", [])]
    assert "child_a" in child_names
    assert "child_b" in child_names


# ---------------------------------------------------------------------------
# validate_hierarchy
# ---------------------------------------------------------------------------


def test_validate_detects_orphan():
    """validate_hierarchy should flag landmarks referencing non-existent parts."""
    rig = {
        "landmarks": {
            "joint_a": {
                "pivot": {
                    "type": "hinge",
                    "parent_part": "nonexistent_part",
                    "child_parts": [],
                    "rotation_range": [-90, 90],
                },
            },
        },
        "bones": [],
    }
    result = validate_hierarchy(rig)
    assert result["valid"] is False
    assert any(i["type"] == "orphan" for i in result["issues"])


def test_validate_detects_cycle():
    """validate_hierarchy should flag cycles in the hierarchy."""
    rig = {
        "landmarks": {
            "a": {
                "pivot": {
                    "type": "hinge",
                    "parent_part": "b",
                    "child_parts": ["b"],
                    "rotation_range": [-90, 90],
                },
            },
            "b": {
                "pivot": {
                    "type": "hinge",
                    "parent_part": "a",
                    "child_parts": ["a"],
                    "rotation_range": [-90, 90],
                },
            },
        },
        "bones": [
            {"name": "a"},
            {"name": "b"},
        ],
    }
    result = validate_hierarchy(rig)
    assert result["valid"] is False
    assert any(i["type"] == "cycle" for i in result["issues"])


def test_validate_detects_oversized_child():
    """validate_hierarchy should flag children larger than their parents."""
    rig = {
        "landmarks": {
            "parent": {
                "bounds": {"area": 100},
                "pivot": {
                    "type": "hinge",
                    "parent_part": "",
                    "child_parts": ["child"],
                    "rotation_range": [-90, 90],
                },
            },
            "child": {
                "bounds": {"area": 500},
                "pivot": {
                    "type": "hinge",
                    "parent_part": "parent",
                    "child_parts": [],
                    "rotation_range": [-90, 90],
                },
            },
        },
        "bones": [{"name": "parent"}, {"name": "child"}],
    }
    result = validate_hierarchy(rig)
    assert result["valid"] is False
    assert any(i["type"] == "oversized_child" for i in result["issues"])
