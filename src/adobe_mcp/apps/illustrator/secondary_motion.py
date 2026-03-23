"""Detect parts needing follow-through / secondary motion.

Leaf nodes in the hierarchy with small area relative to their parent
are candidates for secondary motion (hair, tail tips, antennae,
accessories).  Assigns spring/wiggle parameters per part type.

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


class AiSecondaryMotionInput(BaseModel):
    """Detect parts needing follow-through / secondary motion."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ..., description="Action: detect_secondary | assign_params"
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    hierarchy: Optional[dict] = Field(
        default=None,
        description="Joint hierarchy: {joint: {children: [...], area: float}}",
    )
    area_ratio_threshold: float = Field(
        default=0.3,
        description="Max area ratio (child/parent) to be considered secondary",
        ge=0.01, le=1.0,
    )
    part_name: Optional[str] = Field(
        default=None, description="Part name for assign_params action"
    )
    part_type: Optional[str] = Field(
        default=None,
        description="Part type for assign_params: hair, tail, antenna, accessory",
    )


# ---------------------------------------------------------------------------
# Motion parameter presets
# ---------------------------------------------------------------------------


SECONDARY_MOTION_PRESETS: dict[str, dict[str, float]] = {
    "hair": {"spring_freq": 2.0, "amplitude": 5.0, "damping": 0.8},
    "tail": {"spring_freq": 1.0, "amplitude": 15.0, "damping": 0.6},
    "antenna": {"spring_freq": 3.0, "amplitude": 10.0, "damping": 0.9},
    "accessory": {"spring_freq": 1.5, "amplitude": 8.0, "damping": 0.7},
    "ear": {"spring_freq": 2.5, "amplitude": 6.0, "damping": 0.85},
    "fin": {"spring_freq": 1.8, "amplitude": 12.0, "damping": 0.65},
    "ribbon": {"spring_freq": 1.2, "amplitude": 20.0, "damping": 0.5},
    "default": {"spring_freq": 2.0, "amplitude": 8.0, "damping": 0.7},
}


# ---------------------------------------------------------------------------
# Core detection
# ---------------------------------------------------------------------------


def _infer_part_type(name: str) -> str:
    """Infer part type from its name using keyword matching."""
    name_lower = name.lower()
    for keyword in ("hair", "strand", "bang", "lock"):
        if keyword in name_lower:
            return "hair"
    for keyword in ("tail", "tail_tip"):
        if keyword in name_lower:
            return "tail"
    for keyword in ("antenna", "antennae", "feeler"):
        if keyword in name_lower:
            return "antenna"
    for keyword in ("ear", "ear_tip"):
        if keyword in name_lower:
            return "ear"
    for keyword in ("fin",):
        if keyword in name_lower:
            return "fin"
    for keyword in ("ribbon", "scarf", "cape"):
        if keyword in name_lower:
            return "ribbon"
    return "accessory"


def detect_secondary_parts(
    hierarchy: dict,
    area_ratio_threshold: float = 0.3,
) -> dict:
    """Find leaf nodes with small area relative to parent.

    Args:
        hierarchy: {joint_name: {"children": [...], "area": float}}
                   area is optional; defaults to 100 if missing.
        area_ratio_threshold: max child/parent area ratio to qualify

    Returns:
        {"secondary_parts": [{name, parent, area_ratio, inferred_type, ...}]}
    """
    # Build parent map
    parent_map: dict[str, str] = {}
    areas: dict[str, float] = {}

    for joint, data in hierarchy.items():
        if isinstance(data, dict):
            children = data.get("children", [])
            areas[joint] = data.get("area", 100.0)
        elif isinstance(data, list):
            children = data
            areas[joint] = 100.0
        else:
            children = []
            areas[joint] = 100.0

        for child in children:
            parent_map[child] = joint
            # If child has its own entry, area will be overridden
            if child not in areas:
                areas[child] = 100.0

    # Override areas for children that have their own hierarchy entries
    for joint, data in hierarchy.items():
        if isinstance(data, dict) and "area" in data:
            areas[joint] = data["area"]

    # Find leaf nodes (those with no children)
    all_children: set[str] = set()
    for joint, data in hierarchy.items():
        if isinstance(data, dict):
            all_children.update(data.get("children", []))
        elif isinstance(data, list):
            all_children.update(data)

    # Leaf nodes are in hierarchy but have no children listed, OR
    # are referenced as children but not keys in hierarchy
    leaf_nodes: set[str] = set()
    for joint, data in hierarchy.items():
        if isinstance(data, dict):
            children = data.get("children", [])
        elif isinstance(data, list):
            children = data
        else:
            children = []
        if not children:
            leaf_nodes.add(joint)

    # Also add children that don't appear as keys (implicit leaves)
    for child in all_children:
        if child not in hierarchy:
            leaf_nodes.add(child)

    secondary_parts: list[dict] = []

    for leaf in sorted(leaf_nodes):
        parent = parent_map.get(leaf)
        if parent is None:
            continue

        parent_area = areas.get(parent, 100.0)
        leaf_area = areas.get(leaf, 100.0)

        if parent_area < 0.001:
            continue

        ratio = leaf_area / parent_area

        if ratio <= area_ratio_threshold:
            inferred_type = _infer_part_type(leaf)
            params = dict(SECONDARY_MOTION_PRESETS.get(
                inferred_type, SECONDARY_MOTION_PRESETS["default"]
            ))

            secondary_parts.append({
                "name": leaf,
                "parent": parent,
                "area_ratio": round(ratio, 4),
                "inferred_type": inferred_type,
                **params,
            })

    return {"secondary_parts": secondary_parts}


def assign_motion_params(part_name: str, part_type: str) -> dict:
    """Assign spring/wiggle parameters for a part based on type.

    Args:
        part_name: name of the part
        part_type: one of hair, tail, antenna, accessory, ear, fin, ribbon

    Returns:
        {"name": str, "type": str, "spring_freq": float,
         "amplitude": float, "damping": float}
    """
    preset = SECONDARY_MOTION_PRESETS.get(
        part_type, SECONDARY_MOTION_PRESETS["default"]
    )
    return {
        "name": part_name,
        "type": part_type,
        **preset,
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_secondary_motion tool."""

    @mcp.tool(
        name="adobe_ai_secondary_motion",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_secondary_motion(params: AiSecondaryMotionInput) -> str:
        """Detect parts needing follow-through / secondary motion.

        Actions:
        - detect_secondary: find leaf parts with small area relative to parent
        - assign_params: get spring/wiggle parameters for a specific part type
        """
        action = params.action.lower().strip()

        # ── detect_secondary ─────────────────────────────────────────
        if action == "detect_secondary":
            hierarchy = params.hierarchy
            if hierarchy is None:
                rig = _load_rig(params.character_name)
                # Build from rig joints + bones
                joints = rig.get("joints", {})
                bones = rig.get("bones", [])
                hierarchy = {}
                for j_name in joints:
                    hierarchy[j_name] = {"children": [], "area": 100.0}
                for bone in bones:
                    parent = bone.get("parent_joint")
                    child = bone.get("child_joint")
                    if parent and parent in hierarchy:
                        hierarchy[parent]["children"].append(child)

            if not hierarchy:
                return json.dumps({"error": "No hierarchy provided or in rig"})

            result = detect_secondary_parts(hierarchy, params.area_ratio_threshold)

            # Store in rig
            rig = _load_rig(params.character_name)
            rig["secondary_motion"] = result["secondary_parts"]
            _save_rig(params.character_name, rig)

            return json.dumps({
                "action": "detect_secondary",
                **result,
            }, indent=2)

        # ── assign_params ────────────────────────────────────────────
        elif action == "assign_params":
            if not params.part_name or not params.part_type:
                return json.dumps({
                    "error": "assign_params requires part_name and part_type"
                })

            result = assign_motion_params(params.part_name, params.part_type)
            return json.dumps({
                "action": "assign_params",
                **result,
            }, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["detect_secondary", "assign_params"],
            })
