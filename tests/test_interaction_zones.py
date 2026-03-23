"""Tests for the interaction zones system.

Tests define_interaction_zone, check_interaction overlap detection,
and non-overlapping zone verification.
"""

import math

import pytest

from adobe_mcp.apps.illustrator.interaction_zones import (
    define_interaction_zone,
    check_interaction,
    get_zones,
)


# ---------------------------------------------------------------------------
# define_interaction_zone
# ---------------------------------------------------------------------------


def test_define_zone():
    """Defining a zone stores it in the rig's interaction_zones."""
    rig = {}
    zone = define_interaction_zone(
        rig, "right_hand_grip", [100.0, 200.0], 15.0, "grip"
    )

    assert zone["name"] == "right_hand_grip"
    assert zone["position"] == [100.0, 200.0]
    assert zone["radius"] == 15.0
    assert zone["zone_type"] == "grip"
    assert "right_hand_grip" in rig["interaction_zones"]


# ---------------------------------------------------------------------------
# check_interaction — overlapping zones
# ---------------------------------------------------------------------------


def test_overlap_detection():
    """Two zones close together should be detected as overlapping."""
    rig_a = {}
    rig_b = {}
    define_interaction_zone(rig_a, "hand", [100.0, 100.0], 20.0, "grip")
    define_interaction_zone(rig_b, "handle", [110.0, 100.0], 20.0, "grip")

    # Distance = 10, sum of radii = 40 → overlapping
    result = check_interaction(rig_a, "hand", rig_b, "handle")
    assert result["overlapping"] is True
    assert result["distance"] < result["threshold"]


# ---------------------------------------------------------------------------
# check_interaction — non-overlapping zones
# ---------------------------------------------------------------------------


def test_non_overlapping_zones():
    """Two zones far apart should not be detected as overlapping."""
    rig_a = {}
    rig_b = {}
    define_interaction_zone(rig_a, "hand", [0.0, 0.0], 5.0, "grip")
    define_interaction_zone(rig_b, "foot", [100.0, 100.0], 5.0, "ground_contact")

    # Distance = ~141.4, sum of radii = 10 → not overlapping
    result = check_interaction(rig_a, "hand", rig_b, "foot")
    assert result["overlapping"] is False
    assert result["distance"] > result["threshold"]
