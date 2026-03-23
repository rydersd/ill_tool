"""Tests for the chain detector.

Verifies chain detection from hierarchies, classification, and labeling.
All tests are pure Python -- no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.chain_detector import (
    detect_chains,
    classify_chain,
    label_chain,
    detect_and_classify,
)


# ---------------------------------------------------------------------------
# detect_chains
# ---------------------------------------------------------------------------


def test_linear_three_joint_chain():
    """A linear 3-node path should be detected as a chain."""
    hierarchy = {
        "root": "shoulder",
        "nodes": [
            {"name": "shoulder", "parent": None, "children": ["elbow"]},
            {"name": "elbow", "parent": "shoulder", "children": ["wrist"]},
            {"name": "wrist", "parent": "elbow", "children": []},
        ],
    }
    chains = detect_chains(hierarchy, min_joints=2)
    assert len(chains) == 1
    assert chains[0]["joints"] == ["shoulder", "elbow", "wrist"]


def test_branching_produces_multiple_chains():
    """A branching tree should produce one chain per leaf path."""
    hierarchy = {
        "root": "body",
        "nodes": [
            {"name": "body", "parent": None, "children": ["arm_l", "arm_r"]},
            {"name": "arm_l", "parent": "body", "children": []},
            {"name": "arm_r", "parent": "body", "children": []},
        ],
    }
    chains = detect_chains(hierarchy, min_joints=2)
    assert len(chains) == 2
    chain_endpoints = [c["joints"][-1] for c in chains]
    assert "arm_l" in chain_endpoints
    assert "arm_r" in chain_endpoints


def test_single_joint_not_a_chain():
    """A single-node hierarchy should not produce any chains (min_joints=2)."""
    hierarchy = {
        "root": "body",
        "nodes": [
            {"name": "body", "parent": None, "children": []},
        ],
    }
    chains = detect_chains(hierarchy, min_joints=2)
    assert len(chains) == 0


# ---------------------------------------------------------------------------
# classify_chain
# ---------------------------------------------------------------------------


def test_classify_linear():
    """A chain with unique joints is linear."""
    chain = {"joints": ["a", "b", "c"]}
    assert classify_chain(chain) == "linear"


def test_classify_loop():
    """A chain with repeated joints is a loop."""
    chain = {"joints": ["a", "b", "c", "a"]}
    assert classify_chain(chain) == "loop"


# ---------------------------------------------------------------------------
# label_chain / detect_and_classify
# ---------------------------------------------------------------------------


def test_label_chain_with_template():
    """Template matching should apply labels from pattern keywords."""
    chain = {"joints": ["shoulder_r", "elbow_r", "wrist_r"]}
    template = {"shoulder.*elbow.*wrist": "arm_r"}
    label = label_chain(chain, template, 0)
    assert label == "arm_r"


def test_detect_and_classify_full_pipeline():
    """Full pipeline should detect, classify, and label chains."""
    hierarchy = {
        "root": "body",
        "nodes": [
            {"name": "body", "parent": None, "children": ["shoulder_r"]},
            {"name": "shoulder_r", "parent": "body", "children": ["elbow_r"]},
            {"name": "elbow_r", "parent": "shoulder_r", "children": ["wrist_r"]},
            {"name": "wrist_r", "parent": "elbow_r", "children": []},
        ],
    }
    result = detect_and_classify(hierarchy)
    assert len(result["chains"]) == 1
    chain = result["chains"][0]
    assert chain["type"] == "linear"
    assert len(chain["joints"]) == 4
