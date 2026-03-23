"""Rank detected parts by area to inform rig hierarchy.

Sorts parts by area, assigns hierarchy roles (root, major, minor, detail),
computes size ratios relative to the largest part, and suggests functional
roles based on size distribution.

Pure Python implementation — no image processing, operates on part metadata.
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


class AiPartSizeRankerInput(BaseModel):
    """Rank parts by area to inform rig hierarchy."""
    model_config = ConfigDict(str_strip_whitespace=True)
    parts: str = Field(
        ...,
        description='JSON array of parts: [{"name": "part_0", "area": 5000, ...}, ...]',
    )
    major_threshold: float = Field(
        default=0.10,
        description="Ratio threshold (vs root) above which a part is 'major'",
        ge=0.0, le=1.0,
    )
    detail_threshold: float = Field(
        default=0.01,
        description="Ratio threshold below which a part is 'detail'",
        ge=0.0, le=1.0,
    )


# ---------------------------------------------------------------------------
# Core ranking functions
# ---------------------------------------------------------------------------


def rank_parts(
    parts: list[dict],
    major_threshold: float = 0.10,
    detail_threshold: float = 0.01,
) -> list[dict]:
    """Sort parts by area descending and assign hierarchy roles.

    Roles:
        - root: the single largest part
        - major: area > major_threshold * root_area
        - minor: area between detail_threshold and major_threshold * root_area
        - detail: area < detail_threshold * root_area

    Args:
        parts: list of part dicts, each must have 'area' key
        major_threshold: ratio vs root for 'major' classification
        detail_threshold: ratio vs root for 'detail' classification

    Returns:
        sorted list of part dicts with role and ratio fields added.
    """
    if not parts:
        return []

    # Sort by area descending
    sorted_parts = sorted(parts, key=lambda p: p.get("area", 0), reverse=True)

    root_area = sorted_parts[0].get("area", 1)
    if root_area <= 0:
        root_area = 1

    result = []
    for i, part in enumerate(sorted_parts):
        area = part.get("area", 0)
        ratio = area / root_area

        if i == 0:
            role = "root"
        elif ratio >= major_threshold:
            role = "major"
        elif ratio >= detail_threshold:
            role = "minor"
        else:
            role = "detail"

        ranked = {**part, "role": role, "ratio": round(ratio, 4)}
        result.append(ranked)

    return result


def compute_size_ratios(parts: list[dict]) -> list[dict]:
    """Compute ratio of each part's area to the largest part.

    Args:
        parts: list of part dicts with 'area' key

    Returns:
        list of dicts with name, area, and ratio_to_root.
    """
    if not parts:
        return []

    sorted_parts = sorted(parts, key=lambda p: p.get("area", 0), reverse=True)
    root_area = sorted_parts[0].get("area", 1)
    if root_area <= 0:
        root_area = 1

    return [
        {
            "name": p.get("name", f"part_{i}"),
            "area": p.get("area", 0),
            "ratio_to_root": round(p.get("area", 0) / root_area, 4),
        }
        for i, p in enumerate(sorted_parts)
    ]


def suggest_hierarchy_roles(parts: list[dict]) -> list[dict]:
    """Suggest functional roles based on size distribution.

    Largest = body/torso, medium = limbs/appendages, small = details/accessories.

    Args:
        parts: list of part dicts with area

    Returns:
        list of dicts with name, area, and suggested_role.
    """
    if not parts:
        return []

    sorted_parts = sorted(parts, key=lambda p: p.get("area", 0), reverse=True)
    total = len(sorted_parts)
    root_area = sorted_parts[0].get("area", 1)
    if root_area <= 0:
        root_area = 1

    result = []
    for i, p in enumerate(sorted_parts):
        area = p.get("area", 0)
        ratio = area / root_area

        if i == 0:
            suggested = "body"
        elif ratio >= 0.3:
            suggested = "major_limb"
        elif ratio >= 0.1:
            suggested = "limb"
        elif ratio >= 0.03:
            suggested = "appendage"
        else:
            suggested = "detail"

        result.append({
            "name": p.get("name", f"part_{i}"),
            "area": area,
            "ratio": round(ratio, 4),
            "suggested_role": suggested,
        })

    return result


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_part_size_ranker tool."""

    @mcp.tool(
        name="adobe_ai_part_size_ranker",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_part_size_ranker(params: AiPartSizeRankerInput) -> str:
        """Rank parts by area and assign hierarchy roles.

        Takes a JSON array of parts with area values, sorts by size, assigns
        roles (root/major/minor/detail), and suggests functional hierarchy.
        """
        try:
            parts = json.loads(params.parts)
        except (json.JSONDecodeError, TypeError) as exc:
            return json.dumps({"error": f"Invalid parts JSON: {exc}"})

        if not isinstance(parts, list):
            return json.dumps({"error": "parts must be a JSON array"})

        ranked = rank_parts(
            parts,
            major_threshold=params.major_threshold,
            detail_threshold=params.detail_threshold,
        )
        ratios = compute_size_ratios(parts)
        roles = suggest_hierarchy_roles(parts)

        return json.dumps({
            "ranked": ranked,
            "size_ratios": ratios,
            "suggested_roles": roles,
            "part_count": len(parts),
        }, indent=2)
