"""Tests for motion path generation from pose sequences.

Verifies root straight paths, child arcs relative to parent,
and frame count matching.
All tests are pure Python — no JSX or Adobe required.
"""

import math

import pytest

from adobe_mcp.apps.illustrator.motion_path_from_hierarchy import (
    compute_joint_paths,
    generate_path_curves,
)


# ---------------------------------------------------------------------------
# Straight path for root joint
# ---------------------------------------------------------------------------


def test_root_straight_path():
    """Root joint with no parent should follow a straight line interpolation."""
    hierarchy = {
        "root": {"children": []},
    }
    start_pose = {"root": {"x": 0.0, "y": 0.0, "rotation": 0.0}}
    end_pose = {"root": {"x": 100.0, "y": 0.0, "rotation": 0.0}}

    result = compute_joint_paths(hierarchy, start_pose, end_pose, frames=5)
    path = result["joint_paths"]["root"]

    # 5 frames: 0, 1, 2, 3, 4
    assert len(path) == 5

    # First frame at start
    assert path[0] == (0, pytest.approx(0.0), pytest.approx(0.0))

    # Last frame at end
    assert path[4] == (4, pytest.approx(100.0), pytest.approx(0.0))

    # Middle frame at midpoint
    assert path[2] == (2, pytest.approx(50.0), pytest.approx(0.0))


# ---------------------------------------------------------------------------
# Child arcs relative to parent
# ---------------------------------------------------------------------------


def test_child_arcs_relative_to_parent():
    """Child joint should move as parent translates, maintaining local offset."""
    hierarchy = {
        "parent": {"children": ["child"]},
        "child": {"children": []},
    }
    start_pose = {
        "parent": {"x": 0.0, "y": 0.0, "rotation": 0.0},
        "child": {"x": 50.0, "y": 0.0, "rotation": 0.0},
    }
    end_pose = {
        "parent": {"x": 100.0, "y": 0.0, "rotation": 0.0},
        "child": {"x": 150.0, "y": 0.0, "rotation": 0.0},
    }

    result = compute_joint_paths(hierarchy, start_pose, end_pose, frames=3)
    parent_path = result["joint_paths"]["parent"]
    child_path = result["joint_paths"]["child"]

    assert len(child_path) == 3

    # Child should maintain offset of ~50 from parent at each frame
    for i in range(3):
        _, px, py = parent_path[i]
        _, cx, cy = child_path[i]
        offset = math.sqrt((cx - px) ** 2 + (cy - py) ** 2)
        assert offset == pytest.approx(50.0, abs=1.0)


# ---------------------------------------------------------------------------
# Frame count matches
# ---------------------------------------------------------------------------


def test_frame_count_matches():
    """Output should have exactly the requested number of frames per joint."""
    hierarchy = {
        "a": {"children": ["b"]},
        "b": {"children": ["c"]},
        "c": {"children": []},
    }
    start_pose = {
        "a": {"x": 0.0, "y": 0.0, "rotation": 0.0},
        "b": {"x": 30.0, "y": 0.0, "rotation": 0.0},
        "c": {"x": 60.0, "y": 0.0, "rotation": 0.0},
    }
    end_pose = {
        "a": {"x": 10.0, "y": 10.0, "rotation": 15.0},
        "b": {"x": 40.0, "y": 10.0, "rotation": 10.0},
        "c": {"x": 70.0, "y": 10.0, "rotation": 5.0},
    }

    for frame_count in (2, 6, 12, 24):
        result = compute_joint_paths(hierarchy, start_pose, end_pose, frames=frame_count)
        assert result["frame_count"] == frame_count
        for joint, path in result["joint_paths"].items():
            assert len(path) == frame_count, f"{joint} has {len(path)} frames, expected {frame_count}"


# ---------------------------------------------------------------------------
# Bezier curve generation
# ---------------------------------------------------------------------------


def test_generate_path_curves():
    """generate_path_curves should produce tangent data for each keyframe."""
    hierarchy = {"root": {"children": []}}
    start = {"root": {"x": 0.0, "y": 0.0, "rotation": 0.0}}
    end = {"root": {"x": 100.0, "y": 50.0, "rotation": 0.0}}

    paths_result = compute_joint_paths(hierarchy, start, end, frames=5)
    curves = generate_path_curves(paths_result["joint_paths"])

    root_curve = curves["curves"]["root"]
    assert len(root_curve) == 5

    # Each point should have tangent data
    for point in root_curve:
        assert "frame" in point
        assert "x" in point
        assert "y" in point
        assert "in_tangent" in point
        assert "out_tangent" in point
        assert len(point["in_tangent"]) == 2
        assert len(point["out_tangent"]) == 2
