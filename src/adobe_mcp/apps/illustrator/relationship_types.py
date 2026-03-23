"""Define and infer relationship types between connected parts.

Provides a catalog of biomechanical/mechanical relationship types
(hinge, ball joint, slide, flex, etc.) with their properties and
default ranges. Includes inference from connection geometry and
After Effects expression generation for each type.

Pure Python implementation.
"""

import json
import math
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiRelationshipTypesInput(BaseModel):
    """Infer or query relationship types between parts."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ..., description="Action: list_types, infer, get_ae_expression"
    )
    connection_type: Optional[str] = Field(
        default=None, description="Connection type from connection_detector (for 'infer')"
    )
    part_shapes: Optional[dict] = Field(
        default=None,
        description="Shape info for the two parts: {part_a: {aspect_ratio, area}, part_b: {...}}"
    )
    relationship_type: Optional[str] = Field(
        default=None, description="Relationship type name (for 'get_ae_expression')"
    )


# ---------------------------------------------------------------------------
# Relationship type catalog
# ---------------------------------------------------------------------------


RELATIONSHIP_TYPES = {
    "rigid_hinge": {
        "rotation": True,
        "translation": False,
        "default_range": [-90, 90],
        "description": "Single-axis rotation like an elbow or door hinge",
    },
    "ball_joint": {
        "rotation": True,
        "translation": False,
        "default_range": [-180, 180],
        "description": "Multi-axis rotation like a shoulder or hip",
    },
    "slide": {
        "rotation": False,
        "translation": True,
        "default_range": [0, 100],
        "description": "Linear translation along one axis",
    },
    "flex": {
        "rotation": True,
        "translation": False,
        "default_range": [-30, 30],
        "multi_joint": True,
        "description": "Distributed rotation across multiple joints (spine, tail)",
    },
    "telescoping": {
        "rotation": False,
        "translation": True,
        "default_range": [0, 200],
        "description": "Extension/retraction along axis (telescoping arm, piston)",
    },
    "fixed": {
        "rotation": False,
        "translation": False,
        "default_range": [0, 0],
        "description": "No movement -- rigidly attached",
    },
}


# ---------------------------------------------------------------------------
# Pure Python helpers
# ---------------------------------------------------------------------------


def infer_relationship(
    connection_type: str,
    part_shapes: Optional[dict] = None,
) -> dict:
    """Infer the most likely relationship type from connection geometry.

    Args:
        connection_type: "joint", "containment", "adjacent", or "separate"
        part_shapes: optional shape info {part_a: {aspect_ratio, area}, ...}

    Returns:
        {"type": str, "confidence": float, "properties": dict}
    """
    if connection_type == "joint":
        # Joints are typically hinges, but elongated parts suggest flex
        if part_shapes:
            # Check if either part is very elongated (aspect ratio > 3)
            for key in ("part_a", "part_b"):
                shape = part_shapes.get(key, {})
                ar = shape.get("aspect_ratio", 1.0)
                if ar > 3.0:
                    return {
                        "type": "flex",
                        "confidence": 0.7,
                        "properties": RELATIONSHIP_TYPES["flex"],
                    }

            # Check if parts are very different in size (ball joint)
            area_a = part_shapes.get("part_a", {}).get("area", 1)
            area_b = part_shapes.get("part_b", {}).get("area", 1)
            if max(area_a, area_b) > min(area_a, area_b) * 3:
                return {
                    "type": "ball_joint",
                    "confidence": 0.6,
                    "properties": RELATIONSHIP_TYPES["ball_joint"],
                }

        return {
            "type": "rigid_hinge",
            "confidence": 0.8,
            "properties": RELATIONSHIP_TYPES["rigid_hinge"],
        }

    elif connection_type == "containment":
        return {
            "type": "fixed",
            "confidence": 0.9,
            "properties": RELATIONSHIP_TYPES["fixed"],
        }

    elif connection_type == "adjacent":
        # Adjacent could be slide or hinge depending on shape
        if part_shapes:
            for key in ("part_a", "part_b"):
                shape = part_shapes.get(key, {})
                ar = shape.get("aspect_ratio", 1.0)
                if ar > 2.0:
                    return {
                        "type": "slide",
                        "confidence": 0.5,
                        "properties": RELATIONSHIP_TYPES["slide"],
                    }

        return {
            "type": "rigid_hinge",
            "confidence": 0.4,
            "properties": RELATIONSHIP_TYPES["rigid_hinge"],
        }

    else:  # "separate" or unknown
        return {
            "type": "fixed",
            "confidence": 0.3,
            "properties": RELATIONSHIP_TYPES["fixed"],
        }


def get_ae_expression(relationship_type: str) -> dict:
    """Return the After Effects expression pattern for a relationship type.

    Args:
        relationship_type: one of the RELATIONSHIP_TYPES keys

    Returns:
        {"type": str, "expression": str, "description": str}
    """
    props = RELATIONSHIP_TYPES.get(relationship_type)
    if not props:
        return {
            "type": relationship_type,
            "expression": "// Unknown relationship type",
            "description": f"No expression defined for '{relationship_type}'",
        }

    rng = props.get("default_range", [0, 0])

    if relationship_type == "rigid_hinge":
        expression = (
            "// Rigid hinge: single-axis rotation\n"
            f"var minRot = {rng[0]};\n"
            f"var maxRot = {rng[1]};\n"
            "var ctrl = thisComp.layer(\"Controls\").effect(\"Rotation\")(\"Slider\");\n"
            "var angle = clamp(ctrl, minRot, maxRot);\n"
            "var pivot = thisLayer.anchorPoint;\n"
            "[transform.position[0] + Math.cos(degreesToRadians(angle)) * (value[0] - pivot[0]),\n"
            " transform.position[1] + Math.sin(degreesToRadians(angle)) * (value[1] - pivot[1])]"
        )
    elif relationship_type == "ball_joint":
        expression = (
            "// Ball joint: multi-axis rotation\n"
            f"var range = {rng[1]};\n"
            "var ctrlX = thisComp.layer(\"Controls\").effect(\"RotationX\")(\"Slider\");\n"
            "var ctrlY = thisComp.layer(\"Controls\").effect(\"RotationY\")(\"Slider\");\n"
            "var angleX = clamp(ctrlX, -range, range);\n"
            "var angleY = clamp(ctrlY, -range, range);\n"
            "transform.rotation + angleX + angleY"
        )
    elif relationship_type == "slide":
        expression = (
            "// Slide: linear translation\n"
            f"var minSlide = {rng[0]};\n"
            f"var maxSlide = {rng[1]};\n"
            "var ctrl = thisComp.layer(\"Controls\").effect(\"Slide\")(\"Slider\");\n"
            "var offset = clamp(ctrl, minSlide, maxSlide);\n"
            "[value[0] + offset, value[1]]"
        )
    elif relationship_type == "flex":
        expression = (
            "// Flex: distributed rotation across chain\n"
            f"var maxFlex = {rng[1]};\n"
            "var ctrl = thisComp.layer(\"Controls\").effect(\"Flex\")(\"Slider\");\n"
            "var jointIndex = parseInt(thisLayer.name.split(\"_\").pop());\n"
            "var totalJoints = 5;  // adjust per chain\n"
            "var perJoint = clamp(ctrl, -maxFlex, maxFlex) / totalJoints;\n"
            "transform.rotation + perJoint * jointIndex"
        )
    elif relationship_type == "telescoping":
        expression = (
            "// Telescoping: extension along axis\n"
            f"var minExt = {rng[0]};\n"
            f"var maxExt = {rng[1]};\n"
            "var ctrl = thisComp.layer(\"Controls\").effect(\"Extend\")(\"Slider\");\n"
            "var ext = clamp(ctrl, minExt, maxExt);\n"
            "[value[0], value[1] - ext]"
        )
    elif relationship_type == "fixed":
        expression = (
            "// Fixed: no movement\n"
            "value"
        )
    else:
        expression = "// Unknown type\nvalue"

    return {
        "type": relationship_type,
        "expression": expression,
        "description": props.get("description", ""),
    }


# ---------------------------------------------------------------------------
# MCP Registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_relationship_types tool."""

    @mcp.tool(
        name="adobe_ai_relationship_types",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_relationship_types(params: AiRelationshipTypesInput) -> str:
        """Query, infer, or get AE expressions for relationship types.

        Actions:
        - list_types: Return all available relationship types
        - infer: Infer relationship type from connection geometry
        - get_ae_expression: Get After Effects expression for a type
        """
        action = params.action.lower().strip()

        if action == "list_types":
            return json.dumps({
                "action": "list_types",
                "types": {
                    name: {
                        "rotation": props["rotation"],
                        "translation": props["translation"],
                        "default_range": props["default_range"],
                        "description": props.get("description", ""),
                    }
                    for name, props in RELATIONSHIP_TYPES.items()
                },
            }, indent=2)

        elif action == "infer":
            if not params.connection_type:
                return json.dumps({"error": "connection_type is required for infer"})
            result = infer_relationship(params.connection_type, params.part_shapes)
            return json.dumps({
                "action": "infer",
                **result,
            }, indent=2)

        elif action == "get_ae_expression":
            if not params.relationship_type:
                return json.dumps({"error": "relationship_type is required"})
            result = get_ae_expression(params.relationship_type)
            return json.dumps({
                "action": "get_ae_expression",
                **result,
            }, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["list_types", "infer", "get_ae_expression"],
            })
