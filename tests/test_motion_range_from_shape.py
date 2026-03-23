"""Tests for motion range estimation from part geometry.

Verifies that overlap, gap, and aspect ratio produce correct
rotation range estimates.
All tests are pure Python — no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.motion_range_from_shape import (
    estimate_range,
    _overlap_fraction,
    _gap_distance,
    _aspect_ratio,
)


# ---------------------------------------------------------------------------
# Overlapping parts -> small range
# ---------------------------------------------------------------------------


def test_overlapping_parts_small_range():
    """Parts with heavy overlap should produce limited range (around +-30 deg)."""
    # Part A and B overlap significantly
    part_a = [0, 0, 100, 50]   # x=0, y=0, w=100, h=50
    part_b = [20, 10, 100, 50]  # overlaps heavily with A
    connection = [50, 25]

    result = estimate_range(part_a, part_b, connection)

    assert result["overlap_fraction"] > 0.3
    # Should be limited range
    assert result["max_deg"] <= 60.0
    assert result["min_deg"] >= -60.0
    assert result["confidence"] > 0.5


# ---------------------------------------------------------------------------
# Gap between parts -> large range
# ---------------------------------------------------------------------------


def test_gap_produces_large_range():
    """Parts with a large gap should produce wide range (up to +-180 deg)."""
    part_a = [0, 0, 50, 50]
    part_b = [200, 0, 50, 50]  # 150pt gap
    connection = [100, 25]

    result = estimate_range(part_a, part_b, connection)

    assert result["gap"] > 100.0
    assert result["max_deg"] >= 120.0
    assert result["min_deg"] <= -120.0


# ---------------------------------------------------------------------------
# Thin parts -> wider range
# ---------------------------------------------------------------------------


def test_thin_parts_wider_range():
    """Long thin parts should get wider range from aspect ratio bonus."""
    # Thin part (high aspect ratio)
    part_a = [0, 0, 200, 20]   # AR = 10
    part_b = [0, 25, 200, 20]  # also thin, touching
    connection = [100, 22]

    result = estimate_range(part_a, part_b, connection)

    assert result["aspect_bonus"] > 0.0
    # Aspect ratio bonus should increase the range
    assert result["max_deg"] > 30.0


# ---------------------------------------------------------------------------
# Touching parts (no gap, no overlap) -> moderate range
# ---------------------------------------------------------------------------


def test_touching_parts_moderate_range():
    """Parts that barely touch should produce moderate range (~+-90 deg)."""
    part_a = [0, 0, 50, 50]
    part_b = [50, 0, 50, 50]  # touching edge-to-edge
    connection = [50, 25]

    result = estimate_range(part_a, part_b, connection)

    # Should be moderate range (overlap is edge-only)
    assert 30.0 <= result["max_deg"] <= 120.0


# ---------------------------------------------------------------------------
# Symmetric range (min == -max)
# ---------------------------------------------------------------------------


def test_range_is_symmetric():
    """The range should always be symmetric around 0."""
    part_a = [0, 0, 80, 40]
    part_b = [30, 30, 80, 40]
    connection = [50, 40]

    result = estimate_range(part_a, part_b, connection)

    assert result["min_deg"] == -result["max_deg"]
    assert result["confidence"] > 0.0
    assert result["confidence"] <= 1.0
