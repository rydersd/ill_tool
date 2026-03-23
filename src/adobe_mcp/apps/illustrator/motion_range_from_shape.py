"""Infer rotation limits from part geometry.

Estimates joint rotation range based on the spatial relationship between
two connected parts: overlap, gap distance, and aspect ratios.

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


class AiMotionRangeFromShapeInput(BaseModel):
    """Infer rotation limits from part geometry."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        default="estimate_range",
        description="Action: estimate_range",
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    joint_name: Optional[str] = Field(
        default=None, description="Joint to estimate range for"
    )
    part_a_bounds: Optional[list[float]] = Field(
        default=None,
        description="Bounding box of part A [x, y, width, height]",
    )
    part_b_bounds: Optional[list[float]] = Field(
        default=None,
        description="Bounding box of part B [x, y, width, height]",
    )
    connection_point: Optional[list[float]] = Field(
        default=None,
        description="Connection point between parts [x, y]",
    )


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _bounds_center(bounds: list[float]) -> tuple[float, float]:
    """Compute center of a bounding box [x, y, w, h]."""
    return (bounds[0] + bounds[2] / 2, bounds[1] + bounds[3] / 2)


def _bounds_area(bounds: list[float]) -> float:
    """Compute area of a bounding box [x, y, w, h]."""
    return bounds[2] * bounds[3]


def _aspect_ratio(bounds: list[float]) -> float:
    """Return aspect ratio as max(w,h)/min(w,h). Always >= 1."""
    w, h = bounds[2], bounds[3]
    if min(w, h) < 0.001:
        return 10.0  # very elongated
    return max(w, h) / min(w, h)


def _overlap_fraction(bounds_a: list[float], bounds_b: list[float]) -> float:
    """Compute fraction of the smaller part that overlaps with the larger.

    Returns 0.0 (no overlap) to 1.0 (fully contained).
    """
    ax1, ay1 = bounds_a[0], bounds_a[1]
    ax2, ay2 = ax1 + bounds_a[2], ay1 + bounds_a[3]
    bx1, by1 = bounds_b[0], bounds_b[1]
    bx2, by2 = bx1 + bounds_b[2], by1 + bounds_b[3]

    # Intersection rectangle
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0  # no overlap

    intersection_area = (ix2 - ix1) * (iy2 - iy1)
    smaller_area = min(_bounds_area(bounds_a), _bounds_area(bounds_b))
    if smaller_area < 0.001:
        return 0.0

    return min(intersection_area / smaller_area, 1.0)


def _gap_distance(bounds_a: list[float], bounds_b: list[float]) -> float:
    """Compute the minimum gap between two bounding boxes.

    Returns 0.0 if they overlap or touch.
    """
    ax1, ay1 = bounds_a[0], bounds_a[1]
    ax2, ay2 = ax1 + bounds_a[2], ay1 + bounds_a[3]
    bx1, by1 = bounds_b[0], bounds_b[1]
    bx2, by2 = bx1 + bounds_b[2], by1 + bounds_b[3]

    # Distance along each axis (0 if overlapping on that axis)
    dx = max(0, max(ax1 - bx2, bx1 - ax2))
    dy = max(0, max(ay1 - by2, by1 - ay2))

    return math.sqrt(dx * dx + dy * dy)


# ---------------------------------------------------------------------------
# Core estimation
# ---------------------------------------------------------------------------


def estimate_range(
    part_a_bounds: list[float],
    part_b_bounds: list[float],
    connection_point: list[float],
) -> dict:
    """Estimate rotation range based on overlap, gap, and aspect ratios.

    Logic:
      - Heavy overlap at rest -> limited range (+-30 deg)
      - Touching (small overlap, no gap) -> moderate range (+-90 deg)
      - Gap between parts -> wide range (+-180 deg)
      - Long thin parts get wider range (aspect ratio bonus)

    Returns:
        {"min_deg": float, "max_deg": float, "confidence": float,
         "overlap_fraction": float, "gap": float, "aspect_bonus": float}
    """
    overlap = _overlap_fraction(part_a_bounds, part_b_bounds)
    gap = _gap_distance(part_a_bounds, part_b_bounds)

    # Base range from overlap/gap relationship
    if overlap > 0.3:
        # Heavy overlap -> limited range
        base_range = 30.0
        confidence = 0.8
    elif overlap > 0.05:
        # Moderate overlap -> moderate range
        base_range = 60.0
        confidence = 0.7
    elif gap < 1.0:
        # Touching (no gap, no overlap) -> moderate range
        base_range = 90.0
        confidence = 0.7
    elif gap < 20.0:
        # Small gap -> wider range
        base_range = 120.0
        confidence = 0.6
    else:
        # Large gap -> wide range
        base_range = 180.0
        confidence = 0.5

    # Aspect ratio bonus: long thin parts tend to have wider range
    ar_a = _aspect_ratio(part_a_bounds)
    ar_b = _aspect_ratio(part_b_bounds)
    max_ar = max(ar_a, ar_b)

    # Aspect bonus: narrow parts (high AR) get up to 50% extra range
    aspect_bonus = 0.0
    if max_ar > 2.0:
        aspect_bonus = min((max_ar - 2.0) / 6.0, 0.5)  # 0-50% bonus
        base_range = min(base_range * (1.0 + aspect_bonus), 180.0)

    # Reduce confidence if parts are very different in size
    area_ratio = min(_bounds_area(part_a_bounds), _bounds_area(part_b_bounds)) / \
                 max(_bounds_area(part_a_bounds), _bounds_area(part_b_bounds), 0.001)
    if area_ratio < 0.1:
        confidence *= 0.8

    return {
        "min_deg": round(-base_range, 1),
        "max_deg": round(base_range, 1),
        "confidence": round(confidence, 3),
        "overlap_fraction": round(overlap, 4),
        "gap": round(gap, 2),
        "aspect_bonus": round(aspect_bonus, 4),
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_motion_range_from_shape tool."""

    @mcp.tool(
        name="adobe_ai_motion_range_from_shape",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_motion_range_from_shape(
        params: AiMotionRangeFromShapeInput,
    ) -> str:
        """Infer rotation limits from part geometry.

        Estimates joint rotation range based on overlap, gap, and
        part aspect ratios between two connected parts.
        """
        if params.part_a_bounds and params.part_b_bounds and params.connection_point:
            result = estimate_range(
                params.part_a_bounds,
                params.part_b_bounds,
                params.connection_point,
            )

            # Store in rig if joint_name is given
            if params.joint_name:
                rig = _load_rig(params.character_name)
                rig.setdefault("motion_ranges", {})
                rig["motion_ranges"][params.joint_name] = result
                _save_rig(params.character_name, rig)

            return json.dumps({
                "action": "estimate_range",
                "joint_name": params.joint_name,
                **result,
            }, indent=2)

        return json.dumps({
            "error": "Requires part_a_bounds, part_b_bounds, and connection_point",
        })
