"""Identify areas that deform during joint motion.

For each joint, finds the region between two connected parts that would
stretch or compress during rotation.  The zone is the area within a
configurable radius of the joint, spanning both parts.

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


class AiDeformationZonesInput(BaseModel):
    """Identify deformation zones around joints."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        default="find_zones",
        description="Action: find_zones",
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    joint_name: Optional[str] = Field(
        default=None,
        description="Specific joint to analyze. If None, all joints.",
    )
    radius_factor: float = Field(
        default=0.3,
        description="Zone radius as fraction of average connected part size",
        ge=0.05, le=2.0,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bounds_size(bounds: list[float]) -> float:
    """Average dimension of a bounding box [x, y, w, h]."""
    return (bounds[2] + bounds[3]) / 2.0


def _bounds_contains_point(bounds: list[float], px: float, py: float) -> bool:
    """Check if a point is inside a bounding box."""
    return (bounds[0] <= px <= bounds[0] + bounds[2] and
            bounds[1] <= py <= bounds[1] + bounds[3])


# ---------------------------------------------------------------------------
# Core deformation zone detection
# ---------------------------------------------------------------------------


def find_deformation_zones(rig: dict, joint_name: Optional[str] = None) -> dict:
    """Find deformation zones for joints.

    For each joint, the zone is a circular region centered on the joint
    whose radius is proportional to the average size of the connected
    parts.  The zone represents the area that would stretch/compress
    during rotation.

    Args:
        rig: character rig dict with joints, bones, bindings
        joint_name: optional specific joint; if None, processes all

    Returns:
        {"zones": [{joint, center, radius, bounds, connected_parts, ...}]}
    """
    joints = rig.get("joints", {})
    bones = rig.get("bones", [])
    bindings = rig.get("bindings", {})

    # Build adjacency: which bones connect to which joints
    joint_bones: dict[str, list[dict]] = {}
    for bone in bones:
        pj = bone.get("parent_joint", "")
        cj = bone.get("child_joint", "")
        for j in (pj, cj):
            if j:
                joint_bones.setdefault(j, []).append(bone)

    target_joints = [joint_name] if joint_name else list(joints.keys())
    zones: list[dict] = []

    for jname in target_joints:
        if jname not in joints:
            continue

        jx = joints[jname]["x"]
        jy = joints[jname]["y"]

        # Collect connected parts and their sizes
        connected_bones = joint_bones.get(jname, [])
        connected_part_names: list[str] = []
        part_sizes: list[float] = []

        for bone in connected_bones:
            bone_name = bone.get("name", "")
            bound_parts = bindings.get(bone_name, [])
            if isinstance(bound_parts, str):
                bound_parts = [bound_parts]
            connected_part_names.extend(bound_parts)

            # Estimate part size from bone length
            pj = bone.get("parent_joint", "")
            cj = bone.get("child_joint", "")
            if pj in joints and cj in joints:
                dx = joints[cj]["x"] - joints[pj]["x"]
                dy = joints[cj]["y"] - joints[pj]["y"]
                bone_len = math.sqrt(dx * dx + dy * dy)
                part_sizes.append(bone_len)

        # Zone radius is proportional to average part size
        if part_sizes:
            avg_size = sum(part_sizes) / len(part_sizes)
        else:
            # Fallback: use a default radius based on joint position
            avg_size = 50.0

        # Use the rig's radius_factor (passed via the caller)
        # Default: zone radius = 30% of average connected part size
        radius = avg_size * 0.3  # default; caller can override

        # Zone bounds as a bounding box centered on the joint
        zone_bounds = [
            round(jx - radius, 2),
            round(jy - radius, 2),
            round(radius * 2, 2),
            round(radius * 2, 2),
        ]

        zones.append({
            "joint": jname,
            "center": [round(jx, 2), round(jy, 2)],
            "radius": round(radius, 2),
            "bounds": zone_bounds,
            "connected_parts": list(set(connected_part_names)),
            "connected_bone_count": len(connected_bones),
            "avg_part_size": round(avg_size, 2),
        })

    return {"zones": zones}


def find_deformation_zones_with_factor(
    rig: dict,
    joint_name: Optional[str] = None,
    radius_factor: float = 0.3,
) -> dict:
    """Find deformation zones with a custom radius factor.

    The radius_factor controls zone radius as a fraction of
    the average connected part size.
    """
    joints = rig.get("joints", {})
    bones = rig.get("bones", [])
    bindings = rig.get("bindings", {})

    # Build adjacency
    joint_bones: dict[str, list[dict]] = {}
    for bone in bones:
        pj = bone.get("parent_joint", "")
        cj = bone.get("child_joint", "")
        for j in (pj, cj):
            if j:
                joint_bones.setdefault(j, []).append(bone)

    target_joints = [joint_name] if joint_name else list(joints.keys())
    zones: list[dict] = []

    for jname in target_joints:
        if jname not in joints:
            continue

        jx = joints[jname]["x"]
        jy = joints[jname]["y"]

        connected_bones = joint_bones.get(jname, [])
        connected_part_names: list[str] = []
        part_sizes: list[float] = []

        for bone in connected_bones:
            bone_name = bone.get("name", "")
            bound_parts = bindings.get(bone_name, [])
            if isinstance(bound_parts, str):
                bound_parts = [bound_parts]
            connected_part_names.extend(bound_parts)

            pj = bone.get("parent_joint", "")
            cj = bone.get("child_joint", "")
            if pj in joints and cj in joints:
                dx = joints[cj]["x"] - joints[pj]["x"]
                dy = joints[cj]["y"] - joints[pj]["y"]
                bone_len = math.sqrt(dx * dx + dy * dy)
                part_sizes.append(bone_len)

        avg_size = sum(part_sizes) / len(part_sizes) if part_sizes else 50.0
        radius = avg_size * radius_factor

        zone_bounds = [
            round(jx - radius, 2),
            round(jy - radius, 2),
            round(radius * 2, 2),
            round(radius * 2, 2),
        ]

        zones.append({
            "joint": jname,
            "center": [round(jx, 2), round(jy, 2)],
            "radius": round(radius, 2),
            "bounds": zone_bounds,
            "connected_parts": list(set(connected_part_names)),
            "connected_bone_count": len(connected_bones),
            "avg_part_size": round(avg_size, 2),
        })

    return {"zones": zones}


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_deformation_zones tool."""

    @mcp.tool(
        name="adobe_ai_deformation_zones",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_deformation_zones(params: AiDeformationZonesInput) -> str:
        """Identify areas that deform during joint motion.

        For each joint, finds the region between connected parts that
        would stretch/compress during rotation.
        """
        rig = _load_rig(params.character_name)

        if not rig.get("joints"):
            return json.dumps({"error": "No joints found in rig"})

        result = find_deformation_zones_with_factor(
            rig,
            joint_name=params.joint_name,
            radius_factor=params.radius_factor,
        )

        # Store in rig
        rig.setdefault("deformation_zones", {})
        for zone in result["zones"]:
            rig["deformation_zones"][zone["joint"]] = zone
        _save_rig(params.character_name, rig)

        return json.dumps({
            "action": "find_zones",
            **result,
        }, indent=2)
