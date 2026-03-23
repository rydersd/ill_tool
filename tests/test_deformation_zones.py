"""Tests for deformation zone identification.

Verifies that zone bounds contain the joint position and that
zone size is proportional to connected part sizes.
All tests are pure Python — no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.deformation_zones import (
    find_deformation_zones,
    find_deformation_zones_with_factor,
)


def _make_rig(joints, bones, bindings=None):
    """Helper to build a minimal rig dict."""
    return {
        "joints": joints,
        "bones": bones,
        "bindings": bindings or {},
    }


# ---------------------------------------------------------------------------
# Zone bounds contain the joint position
# ---------------------------------------------------------------------------


def test_zone_contains_joint_position():
    """The zone bounding box must contain the joint's position."""
    rig = _make_rig(
        joints={
            "shoulder": {"x": 100.0, "y": -200.0},
            "elbow": {"x": 150.0, "y": -250.0},
            "wrist": {"x": 200.0, "y": -230.0},
        },
        bones=[
            {"name": "upper_arm", "parent_joint": "shoulder", "child_joint": "elbow"},
            {"name": "forearm", "parent_joint": "elbow", "child_joint": "wrist"},
        ],
    )
    result = find_deformation_zones(rig, joint_name="elbow")
    zones = result["zones"]

    assert len(zones) == 1
    zone = zones[0]

    # Zone bounds [x, y, w, h] must contain the joint position
    zx, zy, zw, zh = zone["bounds"]
    jx, jy = 150.0, -250.0

    assert zx <= jx <= zx + zw
    assert zy <= jy <= zy + zh
    assert zone["center"] == [150.0, -250.0]


# ---------------------------------------------------------------------------
# Zone size proportional to part sizes
# ---------------------------------------------------------------------------


def test_zone_size_proportional_to_parts():
    """Larger connected parts should produce larger deformation zones."""
    # Small bones
    rig_small = _make_rig(
        joints={
            "a": {"x": 0.0, "y": 0.0},
            "b": {"x": 10.0, "y": 0.0},
            "c": {"x": 20.0, "y": 0.0},
        },
        bones=[
            {"name": "b1", "parent_joint": "a", "child_joint": "b"},
            {"name": "b2", "parent_joint": "b", "child_joint": "c"},
        ],
    )

    # Large bones
    rig_large = _make_rig(
        joints={
            "a": {"x": 0.0, "y": 0.0},
            "b": {"x": 100.0, "y": 0.0},
            "c": {"x": 200.0, "y": 0.0},
        },
        bones=[
            {"name": "b1", "parent_joint": "a", "child_joint": "b"},
            {"name": "b2", "parent_joint": "b", "child_joint": "c"},
        ],
    )

    result_small = find_deformation_zones(rig_small, joint_name="b")
    result_large = find_deformation_zones(rig_large, joint_name="b")

    zone_small = result_small["zones"][0]
    zone_large = result_large["zones"][0]

    # Larger parts should produce a larger zone radius
    assert zone_large["radius"] > zone_small["radius"]


# ---------------------------------------------------------------------------
# Custom radius factor
# ---------------------------------------------------------------------------


def test_custom_radius_factor():
    """The radius_factor parameter scales zone size accordingly."""
    rig = _make_rig(
        joints={
            "a": {"x": 0.0, "y": 0.0},
            "b": {"x": 100.0, "y": 0.0},
        },
        bones=[
            {"name": "b1", "parent_joint": "a", "child_joint": "b"},
        ],
    )

    result_small = find_deformation_zones_with_factor(rig, joint_name="b", radius_factor=0.1)
    result_large = find_deformation_zones_with_factor(rig, joint_name="b", radius_factor=0.5)

    zone_small = result_small["zones"][0]
    zone_large = result_large["zones"][0]

    # 0.5 factor should give 5x the radius of 0.1 factor
    assert zone_large["radius"] == pytest.approx(zone_small["radius"] * 5.0, rel=0.01)
