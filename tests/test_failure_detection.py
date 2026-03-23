"""Tests for the failure detection system.

Tests orphan detection, circular reference detection, and clean
hierarchy validation.
"""

import pytest

from adobe_mcp.apps.illustrator.failure_detection import (
    check_hierarchy,
    check_connections,
)


# ---------------------------------------------------------------------------
# check_hierarchy — orphan detected
# ---------------------------------------------------------------------------


def test_orphan_detected():
    """Part referencing a non-existent parent is flagged as orphan."""
    hierarchy = {
        "body": {"parent": None, "area": 1000, "children": ["head"]},
        "head": {"parent": "body", "area": 200, "children": []},
        "floating_part": {"parent": "nonexistent_parent", "area": 50, "children": []},
    }

    result = check_hierarchy(hierarchy)
    assert len(result["issues"]) >= 1

    orphan_issues = [i for i in result["issues"] if i["type"] == "orphan"]
    assert len(orphan_issues) == 1
    assert orphan_issues[0]["part"] == "floating_part"
    assert orphan_issues[0]["severity"] == "warning"


# ---------------------------------------------------------------------------
# check_hierarchy — circular reference detected
# ---------------------------------------------------------------------------


def test_cycle_detected():
    """Circular parent chain (A->B->A) is detected."""
    hierarchy = {
        "part_a": {"parent": "part_b", "area": 100, "children": ["part_b"]},
        "part_b": {"parent": "part_a", "area": 100, "children": ["part_a"]},
    }

    result = check_hierarchy(hierarchy)
    cycle_issues = [i for i in result["issues"] if i["type"] == "circular_reference"]
    assert len(cycle_issues) >= 1
    assert cycle_issues[0]["severity"] == "error"
    assert "Circular reference" in cycle_issues[0]["message"]


# ---------------------------------------------------------------------------
# check_hierarchy — clean hierarchy
# ---------------------------------------------------------------------------


def test_clean_hierarchy_no_issues():
    """Well-formed hierarchy produces no issues."""
    hierarchy = {
        "body": {"parent": None, "area": 1000, "children": ["head", "arm_left", "arm_right"]},
        "head": {"parent": "body", "area": 200, "children": ["eye_left", "eye_right"]},
        "arm_left": {"parent": "body", "area": 150, "children": []},
        "arm_right": {"parent": "body", "area": 150, "children": []},
        "eye_left": {"parent": "head", "area": 20, "children": []},
        "eye_right": {"parent": "head", "area": 20, "children": []},
    }

    result = check_hierarchy(hierarchy)
    assert len(result["issues"]) == 0
