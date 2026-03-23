"""Tests for anticipation and follow-through timing markers.

Verifies frame offset assignment based on hierarchy depth.
All tests are pure Python — no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.anticipation_markers import (
    assign_timing_offsets,
)


# ---------------------------------------------------------------------------
# Lead at root -> children delayed
# ---------------------------------------------------------------------------


def test_lead_at_root_children_delayed():
    """The lead joint has offset 0; its children are delayed by frame_step."""
    hierarchy = {
        "hip": {"children": ["spine", "knee_l", "knee_r"]},
        "spine": {"children": ["chest"]},
        "chest": {"children": []},
        "knee_l": {"children": ["ankle_l"]},
        "knee_r": {"children": ["ankle_r"]},
        "ankle_l": {"children": []},
        "ankle_r": {"children": []},
    }

    result = assign_timing_offsets(hierarchy, lead_joint="hip", frame_step=2)
    offsets = result["offsets"]

    assert offsets["hip"] == 0
    # Direct children: +2 frames
    assert offsets["spine"] == 2
    assert offsets["knee_l"] == 2
    assert offsets["knee_r"] == 2
    # Grandchildren: +4 frames
    assert offsets["chest"] == 4
    assert offsets["ankle_l"] == 4
    assert offsets["ankle_r"] == 4


# ---------------------------------------------------------------------------
# Deep hierarchy -> increasing offsets
# ---------------------------------------------------------------------------


def test_deep_hierarchy_increasing_offsets():
    """Each level deeper in the hierarchy adds another frame_step delay."""
    hierarchy = {
        "a": {"children": ["b"]},
        "b": {"children": ["c"]},
        "c": {"children": ["d"]},
        "d": {"children": ["e"]},
        "e": {"children": []},
    }

    result = assign_timing_offsets(hierarchy, lead_joint="a", frame_step=3)
    offsets = result["offsets"]

    assert offsets["a"] == 0
    assert offsets["b"] == 3
    assert offsets["c"] == 6
    assert offsets["d"] == 9
    assert offsets["e"] == 12

    assert result["max_offset"] == 12


# ---------------------------------------------------------------------------
# Secondary parts get extra delay
# ---------------------------------------------------------------------------


def test_secondary_parts_extra_delay():
    """Secondary motion parts receive an additional frame offset."""
    hierarchy = {
        "spine": {"children": ["shoulder", "tail"]},
        "shoulder": {"children": ["elbow"]},
        "elbow": {"children": []},
        "tail": {"children": ["tail_tip"]},
        "tail_tip": {"children": []},
    }

    result = assign_timing_offsets(
        hierarchy,
        lead_joint="spine",
        frame_step=2,
        secondary_extra=2,
        secondary_parts=["tail_tip"],
    )
    offsets = result["offsets"]

    # tail_tip: depth=2 from spine -> 4 frames + 2 extra = 6
    assert offsets["tail_tip"] == 6

    # elbow: depth=2 from spine -> 4 frames (no extra)
    assert offsets["elbow"] == 4

    # tail: depth=1 -> 2 frames (not secondary)
    assert offsets["tail"] == 2
