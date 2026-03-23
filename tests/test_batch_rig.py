"""Tests for the batch rig system.

Tests batch template application, status reporting, and template-not-found error.
"""

import json
import os

import pytest

from adobe_mcp.apps.illustrator.batch_rig import (
    batch_apply_template,
    batch_status,
)
from adobe_mcp.apps.illustrator.rig_data import _load_rig, _save_rig


# ---------------------------------------------------------------------------
# batch_apply_template — apply to multiple characters
# ---------------------------------------------------------------------------


def test_batch_apply_to_two_characters(tmp_rig_dir, tmp_path):
    """Template is applied to both characters successfully."""
    # Create a template file
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template = {
        "template_name": "biped",
        "character_name": "template_char",
        "rig": {
            "character_name": "template_char",
            "joints": {
                "head": {"x": 0, "y": -50},
                "hip": {"x": 0, "y": -200},
            },
            "bones": [{"from": "hip", "to": "head"}],
            "poses": {"idle": {"head": {"x": 0, "y": -50}}},
        },
        "paths": {},
    }
    template_path = template_dir / "biped.json"
    with open(template_path, "w") as f:
        json.dump(template, f)

    result = batch_apply_template(
        "biped", ["gir", "zim"], template_dir=str(template_dir)
    )

    assert len(result["results"]) == 2
    for r in result["results"]:
        assert r["status"] == "success"

    # Verify rigs were actually saved with template data
    gir_rig = _load_rig("gir")
    assert "head" in gir_rig["joints"]
    assert gir_rig["character_name"] == "gir"
    assert gir_rig["template_source"] == "biped"

    zim_rig = _load_rig("zim")
    assert "head" in zim_rig["joints"]
    assert zim_rig["character_name"] == "zim"


# ---------------------------------------------------------------------------
# batch_status — report rig status
# ---------------------------------------------------------------------------


def test_batch_status_reports_correctly(tmp_rig_dir):
    """Status correctly reports hierarchy, constraints, and poses."""
    # Create a rig with joints and bones
    rig = _load_rig("hero")
    rig["joints"] = {"head": {"x": 0, "y": 0}}
    rig["bones"] = [{"from": "hip", "to": "head"}]
    rig["poses"] = {"idle": {}}
    _save_rig("hero", rig)

    # Create an empty rig
    empty = _load_rig("npc")
    _save_rig("npc", empty)

    result = batch_status(["hero", "npc"])

    hero_status = next(r for r in result["results"] if r["character"] == "hero")
    assert hero_status["has_hierarchy"] is True
    assert hero_status["has_constraints"] is True
    assert hero_status["has_poses"] is True

    npc_status = next(r for r in result["results"] if r["character"] == "npc")
    assert npc_status["has_hierarchy"] is False
    assert npc_status["has_constraints"] is False
    assert npc_status["has_poses"] is False


# ---------------------------------------------------------------------------
# batch_apply_template — template not found
# ---------------------------------------------------------------------------


def test_template_not_found_returns_error(tmp_rig_dir, tmp_path):
    """Missing template returns error status for all characters."""
    template_dir = tmp_path / "empty_templates"
    template_dir.mkdir()

    result = batch_apply_template(
        "nonexistent", ["char_a", "char_b"],
        template_dir=str(template_dir),
    )

    for r in result["results"]:
        assert r["status"] == "error"
        assert "not found" in r["error"]
