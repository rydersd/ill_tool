"""Tests for weight zone computation.

Verifies influence weights based on distance from joints.
All tests are pure Python — no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.weight_zones import (
    get_weights_for_path,
    compute_weight_zones,
)


def _make_rig(joints, bones=None, bindings=None):
    """Helper to build a minimal rig dict."""
    return {
        "joints": joints,
        "bones": bones or [],
        "bindings": bindings or {},
    }


# ---------------------------------------------------------------------------
# Path at joint -> weight 1.0
# ---------------------------------------------------------------------------


def test_path_at_joint_full_weight():
    """A path centered exactly on the joint should have weight 1.0."""
    rig = _make_rig(joints={"elbow": {"x": 100.0, "y": -200.0}})

    # Path bounds centered on the joint
    path_bounds = [90.0, -210.0, 20.0, 20.0]  # center = (100, -200)
    weight = get_weights_for_path(rig, path_bounds, "elbow", influence_radius=100.0)

    assert weight == 1.0


# ---------------------------------------------------------------------------
# Path far away -> weight 0.0
# ---------------------------------------------------------------------------


def test_path_far_away_zero_weight():
    """A path far from the joint should have weight 0.0."""
    rig = _make_rig(joints={"elbow": {"x": 100.0, "y": -200.0}})

    # Path bounds very far from joint
    path_bounds = [900.0, 900.0, 20.0, 20.0]  # center = (910, 910)
    weight = get_weights_for_path(rig, path_bounds, "elbow", influence_radius=100.0)

    assert weight == 0.0


# ---------------------------------------------------------------------------
# Path at 50% distance -> approximately 0.5
# ---------------------------------------------------------------------------


def test_path_at_midpoint_approximate_half():
    """A path at 50% of the influence radius should have ~0.5 weight.

    With inner=25% and outer=75%, at 50% distance:
      t = (50 - 25) / (75 - 25) = 25/50 = 0.5
      weight = 1.0 - 0.5 = 0.5
    """
    rig = _make_rig(joints={"elbow": {"x": 0.0, "y": 0.0}})

    # Path at 50% of influence radius (100)
    # So center should be 50 points from joint
    path_bounds = [40.0, -10.0, 20.0, 20.0]  # center = (50, 0), distance = 50
    weight = get_weights_for_path(rig, path_bounds, "elbow", influence_radius=100.0)

    assert weight == pytest.approx(0.5, abs=0.01)
