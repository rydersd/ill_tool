"""Tests for hierarchy template save/load/apply.

Verifies roundtrip serialization, template listing, and position scaling.
All tests are pure Python -- no JSX or Adobe required.
"""

import os
import json

import pytest

from adobe_mcp.apps.illustrator.hierarchy_templates import (
    save_template,
    load_template,
    list_templates,
    apply_template,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_template_dir(tmp_path):
    """Provide a temporary directory for templates."""
    tdir = tmp_path / "templates"
    tdir.mkdir()
    return str(tdir)


def _biped_rig():
    """Create a minimal biped rig for template testing."""
    return {
        "character_name": "biped_test",
        "landmarks": {
            "shoulder_l": {"x": 80, "y": 100, "pivot": {"type": "ball"}},
            "elbow_l": {"x": 60, "y": 150, "pivot": {"type": "hinge"}},
            "hip_l": {"x": 90, "y": 200, "pivot": {"type": "ball"}},
        },
        "constraints": {
            "elbow_l": {"type": "rotation", "min": -90, "max": 0},
        },
        "bones": [
            {"name": "upper_arm_l", "parent_joint": "shoulder_l", "child_joint": "elbow_l"},
        ],
        "body_part_labels": {
            "part_0": "torso",
            "part_1": "left arm",
        },
        "image_size": [400, 600],
    }


# ---------------------------------------------------------------------------
# save / load roundtrip
# ---------------------------------------------------------------------------


def test_save_load_roundtrip(tmp_template_dir):
    """save_template + load_template should roundtrip without data loss."""
    rig = _biped_rig()
    save_template("biped", rig, tmp_template_dir)

    loaded = load_template("biped", tmp_template_dir)
    assert loaded is not None
    assert loaded["name"] == "biped"
    assert "shoulder_l" in loaded["landmarks"]
    assert loaded["constraints"]["elbow_l"]["min"] == -90
    assert len(loaded["bones"]) == 1


def test_load_missing_template(tmp_template_dir):
    """load_template for a non-existent name should return None."""
    result = load_template("nonexistent", tmp_template_dir)
    assert result is None


# ---------------------------------------------------------------------------
# list_templates
# ---------------------------------------------------------------------------


def test_list_templates(tmp_template_dir):
    """list_templates should return saved template names."""
    rig = _biped_rig()
    save_template("biped", rig, tmp_template_dir)
    save_template("quadruped", rig, tmp_template_dir)

    names = list_templates(tmp_template_dir)
    assert "biped" in names
    assert "quadruped" in names
    assert len(names) == 2


# ---------------------------------------------------------------------------
# apply_template
# ---------------------------------------------------------------------------


def test_apply_template_copies_structure(tmp_template_dir):
    """apply_template should copy landmarks, constraints, bones, labels."""
    rig = _biped_rig()
    save_template("biped", rig, tmp_template_dir)
    template = load_template("biped", tmp_template_dir)

    target_rig = {"character_name": "new_char"}
    result = apply_template(template, target_rig)

    assert result["landmarks"] == 3
    assert result["constraints"] == 1
    assert result["bones"] == 1
    assert result["labels"] == 2
    assert "shoulder_l" in target_rig["landmarks"]


def test_apply_template_scales_positions(tmp_template_dir):
    """apply_template should scale normalized positions to target size."""
    rig = _biped_rig()
    save_template("biped", rig, tmp_template_dir)
    template = load_template("biped", tmp_template_dir)

    # Target rig with different image size (double width, same height)
    target_rig = {"character_name": "new_char", "image_size": [800, 600]}
    apply_template(template, target_rig, target_image_size=[800, 600])

    # shoulder_l was at x=80 in 400-wide image -> x_norm=0.2
    # In 800-wide target -> x should be 160
    shoulder = target_rig["landmarks"]["shoulder_l"]
    assert "x" in shoulder
    assert abs(shoulder["x"] - 160.0) < 1.0  # 0.2 * 800 = 160
