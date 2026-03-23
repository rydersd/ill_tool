"""Mark joints for anticipation and follow-through timing.

Assigns frame offsets based on hierarchy depth from the leading joint.
Deeper joints start their motion later, creating natural anticipation
and follow-through cascades.

Pure Python — no JSX or Adobe required.
"""

import json
import math
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from adobe_mcp.apps.illustrator.rig_data import _load_rig, _save_rig


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiAnticipationMarkersInput(BaseModel):
    """Mark joints for anticipation and follow-through timing."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        default="assign_offsets",
        description="Action: assign_offsets",
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    hierarchy: Optional[dict] = Field(
        default=None,
        description="Joint hierarchy: {joint: {children: [...]}}",
    )
    lead_joint: str = Field(
        ..., description="Joint that leads the motion (0 offset)"
    )
    frame_step: int = Field(
        default=2,
        description="Frame delay per hierarchy level",
        ge=1, le=10,
    )
    secondary_extra: int = Field(
        default=2,
        description="Additional frame delay for secondary motion parts",
        ge=0, le=10,
    )
    secondary_parts: Optional[list[str]] = Field(
        default=None,
        description="List of joint names considered secondary motion",
    )


# ---------------------------------------------------------------------------
# Core timing assignment
# ---------------------------------------------------------------------------


def _build_adjacency(hierarchy: dict) -> dict[str, list[str]]:
    """Build parent->children adjacency from hierarchy dict."""
    adj: dict[str, list[str]] = {}
    for joint, value in hierarchy.items():
        if isinstance(value, dict):
            children = value.get("children", [])
        elif isinstance(value, list):
            children = value
        else:
            children = []
        adj[joint] = list(children)
    return adj


def _compute_depth_from_lead(
    adj: dict[str, list[str]],
    lead_joint: str,
) -> dict[str, int]:
    """BFS from lead_joint to compute depth (distance) of every reachable joint.

    Traverses both parent->child and child->parent edges so that joints
    above the lead in the hierarchy also get offsets.
    """
    # Build bidirectional adjacency
    bidir: dict[str, set[str]] = {}
    for parent, children in adj.items():
        bidir.setdefault(parent, set())
        for child in children:
            bidir[parent].add(child)
            bidir.setdefault(child, set()).add(parent)

    # BFS
    depths: dict[str, int] = {lead_joint: 0}
    queue: list[str] = [lead_joint]
    while queue:
        current = queue.pop(0)
        current_depth = depths[current]
        for neighbor in bidir.get(current, []):
            if neighbor not in depths:
                depths[neighbor] = current_depth + 1
                queue.append(neighbor)

    return depths


def assign_timing_offsets(
    hierarchy: dict,
    lead_joint: str,
    frame_step: int = 2,
    secondary_extra: int = 2,
    secondary_parts: Optional[list[str]] = None,
) -> dict:
    """Assign frame offsets based on hierarchy depth from lead joint.

    - Lead joint: 0 frame offset
    - Direct neighbors: +frame_step frames
    - 2 steps away: +2*frame_step frames
    - Secondary parts: additional +secondary_extra frames on top

    Args:
        hierarchy: {joint: {"children": [...]}} or {joint: [...]}
        lead_joint: joint that initiates the motion
        frame_step: frames of delay per hierarchy level
        secondary_extra: extra delay for secondary motion parts
        secondary_parts: names of secondary motion joints

    Returns:
        {"offsets": {joint_name: frame_offset}, "lead_joint": str,
         "max_offset": int}
    """
    adj = _build_adjacency(hierarchy)

    # Ensure lead_joint exists in the hierarchy
    # If not in adj keys, still proceed (it might be a child-only node)
    all_joints = set(adj.keys())
    for children in adj.values():
        all_joints.update(children)

    if lead_joint not in all_joints:
        return {
            "error": f"Lead joint '{lead_joint}' not found in hierarchy",
            "available_joints": sorted(all_joints),
        }

    # Compute depths from lead
    depths = _compute_depth_from_lead(adj, lead_joint)

    # Convert depths to frame offsets
    secondary_set = set(secondary_parts) if secondary_parts else set()
    offsets: dict[str, int] = {}
    max_offset = 0

    for joint_name, depth in depths.items():
        offset = depth * frame_step

        # Add extra delay for secondary parts
        if joint_name in secondary_set:
            offset += secondary_extra

        offsets[joint_name] = offset
        max_offset = max(max_offset, offset)

    return {
        "offsets": offsets,
        "lead_joint": lead_joint,
        "frame_step": frame_step,
        "max_offset": max_offset,
        "joint_count": len(offsets),
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_anticipation_markers tool."""

    @mcp.tool(
        name="adobe_ai_anticipation_markers",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_anticipation_markers(
        params: AiAnticipationMarkersInput,
    ) -> str:
        """Mark joints for anticipation and follow-through timing.

        Assigns frame offsets based on hierarchy depth from a lead joint.
        Deeper joints in the hierarchy move later, creating cascading
        anticipation and follow-through.
        """
        hierarchy = params.hierarchy
        if hierarchy is None:
            rig = _load_rig(params.character_name)
            joints = rig.get("joints", {})
            bones = rig.get("bones", [])
            hierarchy = {}
            for j_name in joints:
                hierarchy[j_name] = {"children": []}
            for bone in bones:
                parent = bone.get("parent_joint")
                child = bone.get("child_joint")
                if parent and parent in hierarchy:
                    hierarchy[parent]["children"].append(child)

        if not hierarchy:
            return json.dumps({"error": "No hierarchy provided or in rig"})

        result = assign_timing_offsets(
            hierarchy,
            params.lead_joint,
            frame_step=params.frame_step,
            secondary_extra=params.secondary_extra,
            secondary_parts=params.secondary_parts,
        )

        if "error" in result:
            return json.dumps(result)

        # Store in rig
        rig = _load_rig(params.character_name)
        rig["timing_offsets"] = result
        _save_rig(params.character_name, rig)

        return json.dumps({
            "action": "assign_offsets",
            **result,
        }, indent=2)
