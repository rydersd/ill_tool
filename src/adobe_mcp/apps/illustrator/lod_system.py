"""Level of detail (LOD) system for different shot types.

Determines which parts of a character should be visible at different
camera distances:
- wide shot (LOD 1): silhouette only — single root part
- medium shot (LOD 2): major parts visible — head, body, limbs
- close-up (LOD 3): full detail — all parts, features, expressions

Helps optimize rendering and simplify illustration at different scales.
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


class AiLodSystemInput(BaseModel):
    """Compute level of detail for different shot types."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ...,
        description="Action: compute_lod, simplify_parts",
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    shot_type: Optional[str] = Field(
        default=None,
        description="Shot type: wide, medium, close_up",
    )
    parts: Optional[list[dict]] = Field(
        default=None,
        description="List of part dicts with 'name' and 'area' keys",
    )
    lod_level: Optional[int] = Field(
        default=None,
        description="LOD level to simplify to (1, 2, or 3)",
        ge=1, le=3,
    )


# ---------------------------------------------------------------------------
# Shot type to LOD mapping
# ---------------------------------------------------------------------------

SHOT_LOD_MAP = {
    "wide": 1,
    "medium": 2,
    "close_up": 3,
}


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def compute_lod(rig: dict, shot_type: str) -> dict:
    """Determine detail level based on shot type.

    Args:
        rig: the character rig dict
        shot_type: one of "wide", "medium", "close_up"

    Returns:
        {"lod_level": int, "shot_type": str, "description": str}

    Raises:
        ValueError: if shot_type is invalid.
    """
    if shot_type not in SHOT_LOD_MAP:
        raise ValueError(
            f"Invalid shot type '{shot_type}'. "
            f"Valid types: {sorted(SHOT_LOD_MAP.keys())}"
        )

    lod = SHOT_LOD_MAP[shot_type]

    descriptions = {
        1: "Silhouette only — merge all parts into one outline",
        2: "Major parts visible — head, body, limbs as simple shapes",
        3: "Full detail — all parts, features, expressions",
    }

    return {
        "lod_level": lod,
        "shot_type": shot_type,
        "description": descriptions[lod],
    }


def simplify_to_lod(parts: list[dict], lod_level: int) -> list[dict]:
    """Filter parts list to only include parts appropriate for the LOD.

    Parts must have 'name' and 'area' keys. The first part (index 0)
    is treated as the root part.

    LOD 1: only root part
    LOD 2: root + major parts (area > 10% of root area)
    LOD 3: all parts

    Args:
        parts: list of part dicts with at least 'name' and 'area'
        lod_level: 1, 2, or 3

    Returns:
        Filtered list of parts.
    """
    if not parts:
        return []

    if lod_level < 1 or lod_level > 3:
        raise ValueError(f"LOD level must be 1, 2, or 3 (got {lod_level})")

    # LOD 3: all parts
    if lod_level == 3:
        return list(parts)

    # LOD 1: only root (first part)
    if lod_level == 1:
        return [parts[0]]

    # LOD 2: root + major parts (area > 10% of root area)
    root = parts[0]
    root_area = root.get("area", 0)
    if root_area <= 0:
        # If root has no area, return just the root
        return [root]

    threshold = root_area * 0.10
    result = [root]
    for part in parts[1:]:
        part_area = part.get("area", 0)
        if part_area > threshold:
            result.append(part)

    return result


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_lod_system tool."""

    @mcp.tool(
        name="adobe_ai_lod_system",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_lod_system(params: AiLodSystemInput) -> str:
        """Compute level of detail for different shot types.

        Actions:
        - compute_lod: determine LOD level for a shot type
        - simplify_parts: filter parts to the appropriate LOD
        """
        action = params.action.lower().strip()

        if action == "compute_lod":
            if not params.shot_type:
                return json.dumps({"error": "compute_lod requires shot_type"})
            rig = _load_rig(params.character_name)
            try:
                result = compute_lod(rig, params.shot_type)
            except ValueError as e:
                return json.dumps({"error": str(e)})
            return json.dumps({"action": "compute_lod", **result})

        elif action == "simplify_parts":
            if params.parts is None or params.lod_level is None:
                return json.dumps({
                    "error": "simplify_parts requires parts and lod_level"
                })
            try:
                simplified = simplify_to_lod(params.parts, params.lod_level)
            except ValueError as e:
                return json.dumps({"error": str(e)})
            return json.dumps({
                "action": "simplify_parts",
                "lod_level": params.lod_level,
                "original_count": len(params.parts),
                "simplified_count": len(simplified),
                "parts": simplified,
            })

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["compute_lod", "simplify_parts"],
            })
