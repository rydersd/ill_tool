"""Tests for secondary motion detection.

Verifies that small leaf parts are flagged for follow-through,
large leaves are not, and motion parameters match expected ranges.
All tests are pure Python — no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.secondary_motion import (
    detect_secondary_parts,
    assign_motion_params,
    SECONDARY_MOTION_PRESETS,
)


# ---------------------------------------------------------------------------
# Small leaf part detected as secondary
# ---------------------------------------------------------------------------


def test_small_leaf_detected():
    """A leaf node with small area relative to parent should be flagged."""
    hierarchy = {
        "body": {"children": ["tail"], "area": 1000.0},
        "tail": {"children": ["tail_tip"], "area": 200.0},
        "tail_tip": {"children": [], "area": 30.0},  # 30/200 = 0.15 < 0.3
    }
    result = detect_secondary_parts(hierarchy, area_ratio_threshold=0.3)

    parts = result["secondary_parts"]
    part_names = [p["name"] for p in parts]

    assert "tail_tip" in part_names

    tail_tip = next(p for p in parts if p["name"] == "tail_tip")
    assert tail_tip["area_ratio"] < 0.3
    assert tail_tip["parent"] == "tail"


# ---------------------------------------------------------------------------
# Large leaf not flagged
# ---------------------------------------------------------------------------


def test_large_leaf_not_flagged():
    """A leaf node with large area relative to parent should not be flagged."""
    hierarchy = {
        "torso": {"children": ["arm"], "area": 500.0},
        "arm": {"children": [], "area": 400.0},  # 400/500 = 0.8 > 0.3
    }
    result = detect_secondary_parts(hierarchy, area_ratio_threshold=0.3)

    parts = result["secondary_parts"]
    part_names = [p["name"] for p in parts]

    assert "arm" not in part_names


# ---------------------------------------------------------------------------
# Motion params match expected ranges
# ---------------------------------------------------------------------------


def test_motion_params_match_presets():
    """Assigned params should match the preset for each known type."""
    # Hair preset
    hair_params = assign_motion_params("hair_strand", "hair")
    assert hair_params["spring_freq"] == SECONDARY_MOTION_PRESETS["hair"]["spring_freq"]
    assert hair_params["amplitude"] == SECONDARY_MOTION_PRESETS["hair"]["amplitude"]
    assert hair_params["damping"] == SECONDARY_MOTION_PRESETS["hair"]["damping"]

    # Tail preset
    tail_params = assign_motion_params("tail_tip", "tail")
    assert tail_params["spring_freq"] == SECONDARY_MOTION_PRESETS["tail"]["spring_freq"]
    assert tail_params["amplitude"] == SECONDARY_MOTION_PRESETS["tail"]["amplitude"]
    assert tail_params["damping"] == SECONDARY_MOTION_PRESETS["tail"]["damping"]

    # Antenna preset
    ant_params = assign_motion_params("left_antenna", "antenna")
    assert ant_params["spring_freq"] == SECONDARY_MOTION_PRESETS["antenna"]["spring_freq"]
    assert ant_params["amplitude"] == SECONDARY_MOTION_PRESETS["antenna"]["amplitude"]
    assert ant_params["damping"] == SECONDARY_MOTION_PRESETS["antenna"]["damping"]

    # Unknown type falls back to default
    unknown = assign_motion_params("mystery", "unknown_type")
    assert unknown["spring_freq"] == SECONDARY_MOTION_PRESETS["default"]["spring_freq"]
