"""Tests for physics hints (mass, COG, moment of inertia).

Verifies center of gravity shifts toward heavier parts and
equal parts produce a centered COG.
All tests are pure Python — no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.physics_hints import (
    estimate_mass,
    compute_center_of_gravity,
    compute_moment_of_inertia,
)


# ---------------------------------------------------------------------------
# Equal parts -> COG at centroid of centroids
# ---------------------------------------------------------------------------


def test_equal_parts_cog_at_center():
    """Two equal-area parts should have COG at the midpoint of their centroids."""
    parts = [
        {"name": "left", "bounds": [0.0, 0.0, 100.0, 100.0]},   # center=(50,50), area=10000
        {"name": "right", "bounds": [200.0, 0.0, 100.0, 100.0]}, # center=(250,50), area=10000
    ]

    result = compute_center_of_gravity(parts)
    cog = result["cog"]

    # Midpoint of (50,50) and (250,50) = (150, 50)
    assert cog[0] == pytest.approx(150.0, abs=0.1)
    assert cog[1] == pytest.approx(50.0, abs=0.1)

    # Each part should have mass = 0.5
    for pp in result["per_part"]:
        assert pp["mass"] == pytest.approx(0.5, abs=0.001)


# ---------------------------------------------------------------------------
# One heavy part -> COG shifts toward it
# ---------------------------------------------------------------------------


def test_heavy_part_shifts_cog():
    """A heavier (larger area) part should pull COG toward its centroid."""
    parts = [
        {"name": "small", "bounds": [0.0, 0.0, 50.0, 50.0]},     # center=(25,25), area=2500
        {"name": "large", "bounds": [200.0, 0.0, 200.0, 200.0]},  # center=(300,100), area=40000
    ]

    result = compute_center_of_gravity(parts)
    cog = result["cog"]

    # COG should be much closer to the large part (300, 100) than to (25, 25)
    assert cog[0] > 150.0  # shifted well past midpoint toward large part
    assert cog[0] < 300.0  # but not all the way to large centroid


# ---------------------------------------------------------------------------
# Moment of inertia
# ---------------------------------------------------------------------------


def test_moment_of_inertia_increases_with_distance():
    """Parts farther from the pivot should contribute more to moment of inertia."""
    # Two equal parts, one close to pivot, one far
    parts = [
        {"name": "near", "bounds": [0.0, 0.0, 50.0, 50.0]},     # center=(25,25)
        {"name": "far", "bounds": [0.0, 0.0, 50.0, 50.0]},      # same area
    ]
    # Adjust far part position
    parts[1]["bounds"] = [500.0, 0.0, 50.0, 50.0]  # center=(525,25)

    pivot = [0.0, 0.0]

    result = compute_moment_of_inertia(parts, pivot)

    # Find per-part contributions
    near_contrib = next(p for p in result["per_part"] if p["name"] == "near")
    far_contrib = next(p for p in result["per_part"] if p["name"] == "far")

    # Far part should have much larger contribution (distance^2)
    assert far_contrib["contribution"] > near_contrib["contribution"]
    assert result["moment_of_inertia"] > 0.0
