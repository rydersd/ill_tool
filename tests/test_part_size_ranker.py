"""Tests for part_size_ranker — area-based part hierarchy ranking.

Tests correct role assignment (root/major/minor/detail) based on relative
areas, size ratio calculations, and hierarchy role suggestions.
"""

import pytest

from adobe_mcp.apps.illustrator.part_size_ranker import (
    rank_parts,
    compute_size_ratios,
    suggest_hierarchy_roles,
)


# ---------------------------------------------------------------------------
# Test: 3 parts of different sizes -> correct ranking
# ---------------------------------------------------------------------------


def test_three_parts_correct_ranking():
    """Three parts of clearly different sizes should get root/major/minor roles."""
    parts = [
        {"name": "torso", "area": 5000},
        {"name": "arm", "area": 1200},
        {"name": "hand", "area": 200},
    ]
    ranked = rank_parts(parts)

    assert len(ranked) == 3
    # First should be root (largest)
    assert ranked[0]["name"] == "torso"
    assert ranked[0]["role"] == "root"
    assert ranked[0]["ratio"] == 1.0

    # Second: 1200/5000 = 0.24 > 0.10 -> major
    assert ranked[1]["name"] == "arm"
    assert ranked[1]["role"] == "major"

    # Third: 200/5000 = 0.04 > 0.01 -> minor
    assert ranked[2]["name"] == "hand"
    assert ranked[2]["role"] == "minor"


# ---------------------------------------------------------------------------
# Test: equal sizes -> all major (except root)
# ---------------------------------------------------------------------------


def test_equal_sizes_all_major():
    """Parts of equal area should all be 'major' except the first (root)."""
    parts = [
        {"name": "a", "area": 1000},
        {"name": "b", "area": 1000},
        {"name": "c", "area": 1000},
    ]
    ranked = rank_parts(parts)

    assert ranked[0]["role"] == "root"
    assert ranked[1]["role"] == "major"
    assert ranked[2]["role"] == "major"
    # All ratios should be 1.0
    for r in ranked:
        assert r["ratio"] == 1.0


# ---------------------------------------------------------------------------
# Test: one tiny part -> detail role
# ---------------------------------------------------------------------------


def test_tiny_part_detail():
    """A part with area < 1% of root should be classified as 'detail'."""
    parts = [
        {"name": "body", "area": 10000},
        {"name": "eye", "area": 50},  # 0.5% of root
    ]
    ranked = rank_parts(parts)

    assert ranked[0]["role"] == "root"
    assert ranked[1]["role"] == "detail"
    assert ranked[1]["ratio"] < 0.01


# ---------------------------------------------------------------------------
# Test: size ratios computed correctly
# ---------------------------------------------------------------------------


def test_size_ratios():
    """compute_size_ratios should return correct ratios relative to largest."""
    parts = [
        {"name": "small", "area": 100},
        {"name": "large", "area": 400},
        {"name": "medium", "area": 200},
    ]
    ratios = compute_size_ratios(parts)

    # Should be sorted by area descending
    assert ratios[0]["name"] == "large"
    assert ratios[0]["ratio_to_root"] == 1.0
    assert ratios[1]["name"] == "medium"
    assert ratios[1]["ratio_to_root"] == 0.5
    assert ratios[2]["name"] == "small"
    assert ratios[2]["ratio_to_root"] == 0.25


# ---------------------------------------------------------------------------
# Test: suggest_hierarchy_roles assigns body to largest
# ---------------------------------------------------------------------------


def test_hierarchy_roles_body():
    """The largest part should be suggested as 'body'."""
    parts = [
        {"name": "torso", "area": 8000},
        {"name": "leg_l", "area": 3000},
        {"name": "leg_r", "area": 3000},
        {"name": "finger", "area": 50},
    ]
    roles = suggest_hierarchy_roles(parts)

    assert roles[0]["suggested_role"] == "body"
    assert roles[0]["name"] == "torso"

    # Legs at 3000/8000 = 0.375 -> major_limb
    assert roles[1]["suggested_role"] == "major_limb"

    # Finger at 50/8000 = 0.00625 -> detail
    assert roles[3]["suggested_role"] == "detail"
