"""Multi-object relationship management for scene graphs.

Tracks relationships between objects in a scene (holds, faces, rides,
follows, avoids) and validates for conflicts like circular dependencies.

Relationships are stored in the rig under 'scene_graph'.
"""

import json
import math
import os
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from adobe_mcp.apps.illustrator.rig_data import _load_rig, _save_rig


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiSceneGraphInput(BaseModel):
    """Manage multi-object relationships in a scene."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ...,
        description="Action: add_relationship, get_relationships, validate_scene",
    )
    character_name: str = Field(
        default="character", description="Character identifier (scene owner)"
    )
    obj_a: Optional[str] = Field(
        default=None, description="First object in the relationship"
    )
    obj_b: Optional[str] = Field(
        default=None, description="Second object in the relationship"
    )
    rel_type: Optional[str] = Field(
        default=None,
        description="Relationship type: holds, faces, rides, follows, avoids",
    )
    obj_name: Optional[str] = Field(
        default=None, description="Object to query relationships for"
    )


# ---------------------------------------------------------------------------
# Relationship types
# ---------------------------------------------------------------------------

VALID_REL_TYPES = {"holds", "faces", "rides", "follows", "avoids"}

# Relationship pairs that conflict when reversed (A holds B & B holds A)
CONFLICT_PAIRS = {"holds", "rides"}


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def add_relationship(scene: dict, obj_a: str, obj_b: str, rel_type: str) -> dict:
    """Add a relationship between two objects in the scene graph.

    Args:
        scene: the scene_graph dict (list of relationship dicts)
        obj_a: source object name
        obj_b: target object name
        rel_type: one of holds, faces, rides, follows, avoids

    Returns:
        The new relationship dict that was added.

    Raises:
        ValueError: if rel_type is invalid or objects are the same.
    """
    if rel_type not in VALID_REL_TYPES:
        raise ValueError(
            f"Invalid relationship type '{rel_type}'. "
            f"Valid types: {sorted(VALID_REL_TYPES)}"
        )
    if obj_a == obj_b:
        raise ValueError("Cannot create a relationship between an object and itself.")

    relationship = {
        "obj_a": obj_a,
        "obj_b": obj_b,
        "rel_type": rel_type,
    }

    if "relationships" not in scene:
        scene["relationships"] = []

    # Avoid exact duplicates
    for existing in scene["relationships"]:
        if (
            existing["obj_a"] == obj_a
            and existing["obj_b"] == obj_b
            and existing["rel_type"] == rel_type
        ):
            return existing

    scene["relationships"].append(relationship)
    return relationship


def get_relationships(scene: dict, obj_name: str) -> list[dict]:
    """Get all relationships involving a specific object.

    Returns relationships where the object appears as either obj_a or obj_b.
    """
    results = []
    for rel in scene.get("relationships", []):
        if rel["obj_a"] == obj_name or rel["obj_b"] == obj_name:
            results.append(rel)
    return results


def validate_scene(scene: dict) -> dict:
    """Validate the scene graph for conflicting relationships.

    Detects:
    - Circular conflicts: A holds B while B holds A
    - Self-references (shouldn't exist but check anyway)

    Returns:
        {"valid": bool, "conflicts": [...]}
    """
    conflicts = []
    relationships = scene.get("relationships", [])

    for i, rel_a in enumerate(relationships):
        # Check self-reference
        if rel_a["obj_a"] == rel_a["obj_b"]:
            conflicts.append({
                "type": "self_reference",
                "relationship": rel_a,
                "message": f"{rel_a['obj_a']} has a relationship with itself",
            })

        # Check for circular conflicts (A->B and B->A with conflicting types)
        if rel_a["rel_type"] in CONFLICT_PAIRS:
            for rel_b in relationships[i + 1:]:
                if rel_b["rel_type"] in CONFLICT_PAIRS:
                    if (
                        rel_a["obj_a"] == rel_b["obj_b"]
                        and rel_a["obj_b"] == rel_b["obj_a"]
                        and rel_a["rel_type"] == rel_b["rel_type"]
                    ):
                        conflicts.append({
                            "type": "circular_conflict",
                            "relationship_a": rel_a,
                            "relationship_b": rel_b,
                            "message": (
                                f"{rel_a['obj_a']} {rel_a['rel_type']} "
                                f"{rel_a['obj_b']} conflicts with "
                                f"{rel_b['obj_a']} {rel_b['rel_type']} "
                                f"{rel_b['obj_b']}"
                            ),
                        })

    return {
        "valid": len(conflicts) == 0,
        "conflicts": conflicts,
        "relationship_count": len(relationships),
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_scene_graph tool."""

    @mcp.tool(
        name="adobe_ai_scene_graph",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_scene_graph(params: AiSceneGraphInput) -> str:
        """Manage multi-object relationships in a scene.

        Actions:
        - add_relationship: link two objects with a relationship type
        - get_relationships: query all relationships for an object
        - validate_scene: check for conflicting relationships
        """
        action = params.action.lower().strip()
        rig = _load_rig(params.character_name)
        rig.setdefault("scene_graph", {"relationships": []})
        scene = rig["scene_graph"]

        if action == "add_relationship":
            if not params.obj_a or not params.obj_b or not params.rel_type:
                return json.dumps({
                    "error": "add_relationship requires obj_a, obj_b, and rel_type"
                })
            try:
                rel = add_relationship(
                    scene, params.obj_a, params.obj_b, params.rel_type
                )
            except ValueError as e:
                return json.dumps({"error": str(e)})

            _save_rig(params.character_name, rig)
            return json.dumps({
                "action": "add_relationship",
                "relationship": rel,
                "total_relationships": len(scene.get("relationships", [])),
            })

        elif action == "get_relationships":
            if not params.obj_name:
                return json.dumps({
                    "error": "get_relationships requires obj_name"
                })
            rels = get_relationships(scene, params.obj_name)
            return json.dumps({
                "action": "get_relationships",
                "object": params.obj_name,
                "relationships": rels,
                "count": len(rels),
            })

        elif action == "validate_scene":
            result = validate_scene(scene)
            return json.dumps({
                "action": "validate_scene",
                **result,
            })

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": [
                    "add_relationship",
                    "get_relationships",
                    "validate_scene",
                ],
            })
