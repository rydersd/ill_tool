"""Infer joint type from connection geometry between parts.

Classifies joints based on bridge proportions relative to connected parts:
narrow bridges become hinges, wide bridges become fixed joints, and
elongated bridges become slides.

Pure Python implementation — operates on geometry measurements.
"""

import json
import math
import os
from typing import Optional

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiJointGeometryInput(BaseModel):
    """Infer joint type from connection bridge geometry."""
    model_config = ConfigDict(str_strip_whitespace=True)
    connections: str = Field(
        ...,
        description=(
            'JSON array of connections: '
            '[{"connection_width": 10, "connection_height": 15, '
            '"part_a_width": 80, "part_b_width": 60}, ...]'
        ),
    )


# ---------------------------------------------------------------------------
# Joint inference functions
# ---------------------------------------------------------------------------

# Joint type rotation range defaults
_ROTATION_RANGES = {
    "hinge": [-90, 90],
    "ball_joint": [-180, 180],
    "fixed": [-5, 5],
    "slide": [0, 0],  # slides translate, not rotate
}


def infer_joint_type(
    connection_width: float,
    part_a_width: float,
    part_b_width: float,
    connection_height: float = 0.0,
) -> dict:
    """Classify a joint based on bridge proportions.

    Classification rules (bridge = connection_width):
        - bridge < 20% of smaller part -> hinge
        - bridge 20-50% of smaller part -> ball_joint
        - bridge > 50% of smaller part -> fixed
        - bridge aspect ratio > 3 (elongated) -> slide (overrides above)

    Args:
        connection_width: width of the connecting bridge
        part_a_width: width of the first connected part
        part_b_width: width of the second connected part
        connection_height: height of the bridge (for aspect ratio)

    Returns:
        dict with joint type, rotation range, and confidence.
    """
    smaller_part = min(part_a_width, part_b_width)
    if smaller_part <= 0:
        smaller_part = 1.0

    ratio = connection_width / smaller_part

    # Check for elongated bridge (slide joint)
    if connection_height > 0 and connection_width > 0:
        aspect_ratio = max(connection_width, connection_height) / min(
            connection_width, connection_height
        )
        if aspect_ratio > 3.0:
            return {
                "type": "slide",
                "rotation_range": list(_ROTATION_RANGES["slide"]),
                "translation_axis": (
                    "horizontal" if connection_width > connection_height else "vertical"
                ),
                "bridge_ratio": round(ratio, 4),
                "aspect_ratio": round(aspect_ratio, 2),
                "confidence": round(min(aspect_ratio / 5.0, 1.0), 3),
            }

    # Classify by ratio
    if ratio < 0.20:
        joint_type = "hinge"
        # Confidence higher when ratio is clearly in the hinge zone
        confidence = round(1.0 - (ratio / 0.20), 3)
    elif ratio <= 0.50:
        joint_type = "ball_joint"
        # Confidence peaks at 0.35 (middle of range)
        dist_from_center = abs(ratio - 0.35) / 0.15
        confidence = round(max(0.3, 1.0 - dist_from_center), 3)
    else:
        joint_type = "fixed"
        # Confidence higher for wider bridges
        confidence = round(min(ratio, 1.0), 3)

    return {
        "type": joint_type,
        "rotation_range": list(_ROTATION_RANGES[joint_type]),
        "bridge_ratio": round(ratio, 4),
        "confidence": confidence,
    }


def infer_rotation_range(
    joint_type: str,
    part_geometry: Optional[dict] = None,
) -> dict:
    """Estimate rotation range from joint type and optional part geometry.

    Args:
        joint_type: one of hinge, ball_joint, fixed, slide
        part_geometry: optional dict with 'width', 'height' for refined estimates

    Returns:
        dict with min_angle, max_angle, and notes.
    """
    base_range = _ROTATION_RANGES.get(joint_type, [-45, 45])

    # Refine based on part geometry if available
    if part_geometry and joint_type == "hinge":
        # Wider parts have more limited rotation due to collision
        width = part_geometry.get("width", 0)
        height = part_geometry.get("height", 0)
        if width > 0 and height > 0:
            aspect = width / height
            if aspect > 2.0:
                # Wide part: limit rotation
                base_range = [-60, 60]
            elif aspect < 0.5:
                # Tall part: allow more rotation
                base_range = [-120, 120]

    return {
        "joint_type": joint_type,
        "min_angle": base_range[0],
        "max_angle": base_range[1],
        "total_range": base_range[1] - base_range[0],
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_joint_geometry tool."""

    @mcp.tool(
        name="adobe_ai_joint_geometry",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_joint_geometry(params: AiJointGeometryInput) -> str:
        """Infer joint types from connection geometry.

        Classifies each connection bridge as hinge, ball_joint, fixed, or slide
        based on width ratios and aspect ratios.
        """
        try:
            connections = json.loads(params.connections)
        except (json.JSONDecodeError, TypeError) as exc:
            return json.dumps({"error": f"Invalid connections JSON: {exc}"})

        if not isinstance(connections, list):
            return json.dumps({"error": "connections must be a JSON array"})

        results = []
        for conn in connections:
            cw = conn.get("connection_width", 0)
            ch = conn.get("connection_height", 0)
            pa = conn.get("part_a_width", 0)
            pb = conn.get("part_b_width", 0)

            joint = infer_joint_type(cw, pa, pb, ch)
            rotation = infer_rotation_range(joint["type"])
            results.append({**conn, **joint, "rotation_estimate": rotation})

        return json.dumps({"joints": results, "count": len(results)}, indent=2)
