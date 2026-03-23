"""Tests for template_export — JSON file round-trip for templates.

Tests export/import roundtrip, invalid JSON handling, and default field population.
"""

import json
import os

import pytest

from adobe_mcp.apps.illustrator.template_export import (
    export_template,
    import_template,
)


# ---------------------------------------------------------------------------
# Test: export/import roundtrip preserves data
# ---------------------------------------------------------------------------


def test_export_import_roundtrip(tmp_path):
    """Exported template should be identical when re-imported."""
    template = {
        "name": "biped_basic",
        "parts": [
            {"name": "torso", "area": 5000},
            {"name": "leg_l", "area": 2000},
        ],
        "connections": [
            {"from": "torso", "to": "leg_l", "type": "hinge"},
        ],
        "constraints": [
            {"type": "rotation", "part": "leg_l", "min_angle": -90, "max_angle": 90},
        ],
        "poses": {"default": {"leg_l": {"angle": 0}}},
        "metadata": {"author": "test"},
        "tags": ["biped", "basic"],
    }

    path = str(tmp_path / "biped_basic.json")

    # Export
    export_result = export_template(template, path)
    assert export_result["success"] is True
    assert os.path.isfile(path)

    # Import
    imported = import_template(path)
    assert "error" not in imported

    # Verify key fields preserved
    assert imported["name"] == "biped_basic"
    assert len(imported["parts"]) == 2
    assert len(imported["connections"]) == 1
    assert imported["poses"]["default"]["leg_l"]["angle"] == 0
    assert "biped" in imported["tags"]


# ---------------------------------------------------------------------------
# Test: invalid JSON -> error
# ---------------------------------------------------------------------------


def test_import_invalid_json(tmp_path):
    """Importing a file with invalid JSON should return an error."""
    path = str(tmp_path / "bad.json")
    with open(path, "w") as f:
        f.write("{not valid json!!!")

    result = import_template(path)
    assert "error" in result
    assert "Invalid JSON" in result["error"]


# ---------------------------------------------------------------------------
# Test: missing fields -> defaults applied
# ---------------------------------------------------------------------------


def test_import_missing_fields_defaults(tmp_path):
    """Template with missing fields should get defaults on import."""
    path = str(tmp_path / "minimal.json")
    with open(path, "w") as f:
        json.dump({"name": "minimal_template"}, f)

    result = import_template(path)
    assert "error" not in result
    assert result["name"] == "minimal_template"
    # Missing fields should have defaults
    assert result["parts"] == []
    assert result["connections"] == []
    assert result["constraints"] == []
    assert result["poses"] == {}
    assert result["metadata"] == {}
    assert result["tags"] == []
