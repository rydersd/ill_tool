"""Tests for the scene graph relationship system.

Tests add_relationship, get_relationships, and validate_scene for
detecting circular conflicts.
"""

import pytest

from adobe_mcp.apps.illustrator.scene_graph import (
    add_relationship,
    get_relationships,
    validate_scene,
)


# ---------------------------------------------------------------------------
# add_relationship
# ---------------------------------------------------------------------------


def test_add_relationship():
    """Adding a relationship stores it in the scene graph."""
    scene = {"relationships": []}
    rel = add_relationship(scene, "character", "sword", "holds")

    assert rel["obj_a"] == "character"
    assert rel["obj_b"] == "sword"
    assert rel["rel_type"] == "holds"
    assert len(scene["relationships"]) == 1


# ---------------------------------------------------------------------------
# get_relationships
# ---------------------------------------------------------------------------


def test_get_relationships_by_object():
    """Query returns all relationships involving a specific object."""
    scene = {"relationships": []}
    add_relationship(scene, "hero", "sword", "holds")
    add_relationship(scene, "hero", "villain", "faces")
    add_relationship(scene, "horse", "hero", "follows")

    rels = get_relationships(scene, "hero")
    assert len(rels) == 3  # hero appears in all three

    # Check that unrelated queries return fewer results
    rels_sword = get_relationships(scene, "sword")
    assert len(rels_sword) == 1
    assert rels_sword[0]["rel_type"] == "holds"


# ---------------------------------------------------------------------------
# validate_scene — conflict detection
# ---------------------------------------------------------------------------


def test_validate_scene_detects_conflict():
    """Circular conflict (A holds B + B holds A) is detected."""
    scene = {"relationships": []}
    add_relationship(scene, "A", "B", "holds")
    add_relationship(scene, "B", "A", "holds")

    result = validate_scene(scene)
    assert result["valid"] is False
    assert len(result["conflicts"]) >= 1

    conflict = result["conflicts"][0]
    assert conflict["type"] == "circular_conflict"
    assert "A" in conflict["message"]
    assert "B" in conflict["message"]
