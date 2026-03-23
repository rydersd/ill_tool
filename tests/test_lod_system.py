"""Tests for the LOD (level of detail) system.

Tests wide shot -> 1 part, medium -> major parts only, close -> all parts.
"""

import pytest

from adobe_mcp.apps.illustrator.lod_system import (
    compute_lod,
    simplify_to_lod,
)


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SAMPLE_PARTS = [
    {"name": "body", "area": 1000},       # root — largest
    {"name": "head", "area": 200},         # 20% of root — major
    {"name": "arm_left", "area": 150},     # 15% of root — major
    {"name": "arm_right", "area": 150},    # 15% of root — major
    {"name": "eye_left", "area": 20},      # 2% of root — minor detail
    {"name": "eye_right", "area": 20},     # 2% of root — minor detail
    {"name": "button", "area": 5},         # 0.5% of root — minor detail
]


# ---------------------------------------------------------------------------
# Wide shot — LOD 1 — silhouette only
# ---------------------------------------------------------------------------


def test_wide_shot_single_part():
    """Wide shot (LOD 1) returns only the root part."""
    result = simplify_to_lod(SAMPLE_PARTS, lod_level=1)

    assert len(result) == 1
    assert result[0]["name"] == "body"


# ---------------------------------------------------------------------------
# Medium shot — LOD 2 — major parts
# ---------------------------------------------------------------------------


def test_medium_shot_major_parts():
    """Medium shot (LOD 2) returns root + parts with area > 10% of root."""
    result = simplify_to_lod(SAMPLE_PARTS, lod_level=2)

    names = [p["name"] for p in result]
    # body (root) + head (20%) + arm_left (15%) + arm_right (15%)
    assert "body" in names
    assert "head" in names
    assert "arm_left" in names
    assert "arm_right" in names
    # Small parts excluded
    assert "eye_left" not in names
    assert "button" not in names
    assert len(result) == 4


# ---------------------------------------------------------------------------
# Close-up — LOD 3 — all parts
# ---------------------------------------------------------------------------


def test_close_up_all_parts():
    """Close-up (LOD 3) returns all parts."""
    result = simplify_to_lod(SAMPLE_PARTS, lod_level=3)

    assert len(result) == len(SAMPLE_PARTS)
    names = [p["name"] for p in result]
    assert "eye_left" in names
    assert "button" in names
