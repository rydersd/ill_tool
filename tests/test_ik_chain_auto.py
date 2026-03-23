"""Tests for automatic IK chain detection from hierarchy.

Verifies chain detection for linear, branching, single-joint,
and cyclic hierarchies.
All tests are pure Python — no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.ik_chain_auto import (
    detect_ik_chains,
    label_chains,
    _has_cycle,
    _build_adjacency,
)


# ---------------------------------------------------------------------------
# Linear chain detection
# ---------------------------------------------------------------------------


def test_linear_chain_detected():
    """A simple linear hierarchy produces one chain with all joints."""
    hierarchy = {
        "shoulder": {"children": ["elbow"]},
        "elbow": {"children": ["wrist"]},
        "wrist": {"children": []},
    }
    result = detect_ik_chains(hierarchy)
    chains = result["chains"]

    # Should find one chain: shoulder -> elbow -> wrist
    assert len(chains) == 1
    assert chains[0]["joints"] == ["shoulder", "elbow", "wrist"]
    assert chains[0]["length"] == 3
    assert chains[0]["type"] == "linear"


# ---------------------------------------------------------------------------
# Branching hierarchy -> multiple chains
# ---------------------------------------------------------------------------


def test_branching_produces_multiple_chains():
    """A branching hierarchy produces one chain per root-to-leaf path."""
    hierarchy = {
        "spine": {"children": ["shoulder_l", "shoulder_r"]},
        "shoulder_l": {"children": ["elbow_l"]},
        "shoulder_r": {"children": ["elbow_r"]},
        "elbow_l": {"children": []},
        "elbow_r": {"children": []},
    }
    result = detect_ik_chains(hierarchy)
    chains = result["chains"]

    # Should find 2 chains: spine->shoulder_l->elbow_l, spine->shoulder_r->elbow_r
    assert len(chains) == 2

    joint_sets = [tuple(c["joints"]) for c in chains]
    assert ("spine", "shoulder_l", "elbow_l") in joint_sets
    assert ("spine", "shoulder_r", "elbow_r") in joint_sets


# ---------------------------------------------------------------------------
# Single joint is not a chain
# ---------------------------------------------------------------------------


def test_single_joint_not_a_chain():
    """A hierarchy with only one joint produces no chains (need 2+)."""
    hierarchy = {
        "root": {"children": []},
    }
    result = detect_ik_chains(hierarchy)
    assert len(result["chains"]) == 0


# ---------------------------------------------------------------------------
# Loop / cycle detection
# ---------------------------------------------------------------------------


def test_cycle_detected_and_handled():
    """A cyclic hierarchy is detected and doesn't cause infinite recursion."""
    hierarchy = {
        "a": {"children": ["b"]},
        "b": {"children": ["c"]},
        "c": {"children": ["a"]},  # cycle back to a
    }
    result = detect_ik_chains(hierarchy)

    # Should detect the cycle
    assert result["has_cycle"] is True
    # Should still find chains (paths that don't loop)
    # a->b->c is a valid path (cycle detection stops revisiting 'a')
    assert len(result["chains"]) >= 1

    # Verify no chain contains duplicate joints
    for chain in result["chains"]:
        assert len(chain["joints"]) == len(set(chain["joints"]))


# ---------------------------------------------------------------------------
# Label chains with template
# ---------------------------------------------------------------------------


def test_label_chains_with_template():
    """Template-based labelling matches chains by joint count."""
    hierarchy = {
        "spine": {"children": ["shoulder_l", "hip_l"]},
        "shoulder_l": {"children": ["elbow_l"]},
        "elbow_l": {"children": ["wrist_l"]},
        "hip_l": {"children": ["knee_l"]},
        "knee_l": {"children": []},
        "wrist_l": {"children": []},
    }
    result = detect_ik_chains(hierarchy)

    # Template: 4-joint chain = "left_arm", 3-joint chain = "left_leg"
    template = {"left_arm": 4, "left_leg": 3}
    labelled = label_chains(result["chains"], template)

    label_map = {c["label"]: c["length"] for c in labelled}
    assert "left_arm" in label_map
    assert label_map["left_arm"] == 4
    assert "left_leg" in label_map
    assert label_map["left_leg"] == 3
