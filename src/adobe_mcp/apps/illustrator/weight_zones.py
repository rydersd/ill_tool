"""Define influence regions per joint.

Computes weight zones for each joint based on proximity.  Paths near a
joint are heavily influenced by its rotation; paths far away are not.

Influence falloff:
  - Within 25% of joint -> weight 1.0 (fully influenced)
  - 25-75% of radius -> linear falloff
  - Beyond 75% -> weight 0.0

Pure Python — no JSX or Adobe required.
"""

import json
import math
from typing import Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from adobe_mcp.apps.illustrator.rig_data import _load_rig, _save_rig


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiWeightZonesInput(BaseModel):
    """Define influence regions per joint."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        default="compute_zones",
        description="Action: compute_zones | get_weight",
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    joint_name: Optional[str] = Field(
        default=None, description="Joint name for get_weight action"
    )
    path_bounds: Optional[list[float]] = Field(
        default=None, description="Path bounding box [x, y, w, h] for get_weight"
    )
    influence_radius: float = Field(
        default=100.0,
        description="Max influence radius in points",
        gt=0,
    )


# ---------------------------------------------------------------------------
# Core weight computation
# ---------------------------------------------------------------------------


def _distance(ax: float, ay: float, bx: float, by: float) -> float:
    """Euclidean distance between two points."""
    return math.sqrt((bx - ax) ** 2 + (by - ay) ** 2)


def _bounds_center(bounds: list[float]) -> tuple[float, float]:
    """Center of a bounding box [x, y, w, h]."""
    return (bounds[0] + bounds[2] / 2.0, bounds[1] + bounds[3] / 2.0)


def get_weights_for_path(
    rig: dict,
    path_bounds: list[float],
    joint_name: str,
    influence_radius: float = 100.0,
) -> float:
    """Return influence weight (0-1) for a specific path at a specific joint.

    Falloff:
      - Distance <= 25% of influence_radius -> weight 1.0
      - Distance 25%-75% -> linear falloff from 1.0 to 0.0
      - Distance >= 75% -> weight 0.0

    Args:
        rig: character rig dict
        path_bounds: [x, y, w, h] bounding box of the path
        joint_name: name of the joint
        influence_radius: maximum influence distance

    Returns:
        float in [0.0, 1.0]
    """
    joints = rig.get("joints", {})
    if joint_name not in joints:
        return 0.0

    jx = joints[joint_name]["x"]
    jy = joints[joint_name]["y"]

    px, py = _bounds_center(path_bounds)
    dist = _distance(jx, jy, px, py)

    inner_radius = influence_radius * 0.25
    outer_radius = influence_radius * 0.75

    if dist <= inner_radius:
        return 1.0
    elif dist >= outer_radius:
        return 0.0
    else:
        # Linear falloff between inner and outer
        t = (dist - inner_radius) / (outer_radius - inner_radius)
        return round(1.0 - t, 4)


def compute_weight_zones(
    rig: dict,
    influence_radius: float = 100.0,
) -> dict:
    """Compute weight zones for all joints in the rig.

    For each joint, defines the influence zone with inner (full weight)
    and outer (zero weight) radii, plus the joint center.

    Args:
        rig: character rig dict
        influence_radius: max influence radius

    Returns:
        {"weight_zones": [{joint, center, inner_radius, outer_radius, ...}]}
    """
    joints = rig.get("joints", {})
    bones = rig.get("bones", [])
    bindings = rig.get("bindings", {})

    # Build joint -> connected paths mapping
    joint_paths: dict[str, list[str]] = {}
    for bone in bones:
        pj = bone.get("parent_joint", "")
        bone_name = bone.get("name", "")
        bound_parts = bindings.get(bone_name, [])
        if isinstance(bound_parts, str):
            bound_parts = [bound_parts]
        if pj:
            joint_paths.setdefault(pj, []).extend(bound_parts)

    zones: list[dict] = []
    inner_radius = influence_radius * 0.25
    outer_radius = influence_radius * 0.75

    for jname, jdata in joints.items():
        jx = jdata["x"]
        jy = jdata["y"]

        connected = list(set(joint_paths.get(jname, [])))

        zones.append({
            "joint": jname,
            "center": [round(jx, 2), round(jy, 2)],
            "inner_radius": round(inner_radius, 2),
            "outer_radius": round(outer_radius, 2),
            "influence_radius": round(influence_radius, 2),
            "connected_paths": connected,
        })

    return {"weight_zones": zones}


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_weight_zones tool."""

    @mcp.tool(
        name="adobe_ai_weight_zones",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_weight_zones(params: AiWeightZonesInput) -> str:
        """Define influence regions per joint.

        Actions:
        - compute_zones: compute weight zones for all joints
        - get_weight: get influence weight for a specific path at a joint
        """
        action = params.action.lower().strip()
        rig = _load_rig(params.character_name)

        if not rig.get("joints"):
            return json.dumps({"error": "No joints found in rig"})

        # ── compute_zones ────────────────────────────────────────────
        if action == "compute_zones":
            result = compute_weight_zones(rig, params.influence_radius)

            rig["weight_zones"] = result["weight_zones"]
            _save_rig(params.character_name, rig)

            return json.dumps({
                "action": "compute_zones",
                **result,
            }, indent=2)

        # ── get_weight ───────────────────────────────────────────────
        elif action == "get_weight":
            if not params.joint_name or not params.path_bounds:
                return json.dumps({
                    "error": "get_weight requires joint_name and path_bounds"
                })

            weight = get_weights_for_path(
                rig, params.path_bounds, params.joint_name,
                params.influence_radius,
            )

            return json.dumps({
                "action": "get_weight",
                "joint_name": params.joint_name,
                "path_bounds": params.path_bounds,
                "weight": weight,
            }, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["compute_zones", "get_weight"],
            })
