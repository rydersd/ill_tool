"""Classify objects from silhouette characteristics.

Scores an object's part arrangement against known categories (biped,
quadruped, vehicle, insect, plant, furniture, abstract) using part counts,
symmetry information, and spatial relationships.

Pure Python implementation — operates on part metadata and symmetry data.
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


class AiObjectClassifierInput(BaseModel):
    """Classify objects from part arrangement and symmetry."""
    model_config = ConfigDict(str_strip_whitespace=True)
    parts: str = Field(
        ...,
        description=(
            'JSON array of parts: [{"name": "...", "area": N, '
            '"bounding_box": [x,y,w,h], "role": "root|major|minor|detail", '
            '"centroid": [cx,cy]}, ...]'
        ),
    )
    symmetry_info: str = Field(
        default="{}",
        description=(
            'JSON object with symmetry data: '
            '{"bilateral": {"detected": true, "confidence": 0.85}, '
            '"radial": {"detected": false}}'
        ),
    )


# ---------------------------------------------------------------------------
# Classification scoring functions
# ---------------------------------------------------------------------------

# Category scoring templates
_CATEGORIES = {
    "biped": {
        "description": "Two-legged creature (human, bird, etc.)",
        "requires_bilateral": True,
        "appendage_count": [2, 4],  # 2 legs (+ optional 2 arms)
        "has_upper_mass": True,
        "aspect_preference": "tall",
    },
    "quadruped": {
        "description": "Four-legged creature",
        "requires_bilateral": True,
        "appendage_count": [4, 6],  # 4 legs + optional tail/head
        "has_upper_mass": False,
        "aspect_preference": "wide",
    },
    "vehicle": {
        "description": "Vehicle or machine",
        "requires_bilateral": True,
        "appendage_count": [2, 8],  # wheels, wings, etc.
        "has_upper_mass": False,
        "aspect_preference": "wide",
        "has_circular_parts": True,
    },
    "insect": {
        "description": "Six-legged arthropod",
        "requires_bilateral": True,
        "appendage_count": [6, 10],  # 6 legs + wings/antennae
        "has_upper_mass": False,
        "aspect_preference": None,
    },
    "plant": {
        "description": "Plant or tree",
        "requires_bilateral": False,
        "appendage_count": [0, 20],
        "has_upper_mass": False,
        "aspect_preference": "tall",
        "allows_radial": True,
        "allows_asymmetric": True,
    },
    "furniture": {
        "description": "Furniture or rigid object",
        "requires_bilateral": True,
        "appendage_count": [0, 6],
        "has_upper_mass": False,
        "aspect_preference": None,
        "has_rectangular_parts": True,
    },
    "abstract": {
        "description": "Abstract or unclassifiable shape",
        "requires_bilateral": False,
        "appendage_count": [0, 100],
        "has_upper_mass": False,
        "aspect_preference": None,
    },
}


def _count_appendages(parts: list[dict]) -> int:
    """Count parts that look like appendages (non-root, extending from body).

    Appendages are parts with role major/minor that are not the root part.
    """
    return sum(
        1
        for p in parts
        if p.get("role") in ("major", "minor", "limb", "major_limb", "appendage")
    )


def _get_overall_aspect(parts: list[dict]) -> str:
    """Determine overall aspect ratio from bounding boxes.

    Returns 'tall', 'wide', or 'square'.
    """
    if not parts:
        return "square"

    # Find overall bounding box
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    for p in parts:
        bb = p.get("bounding_box", [])
        if len(bb) >= 4:
            x, y, w, h = bb[:4]
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x + w)
            max_y = max(max_y, y + h)
        else:
            # Use centroid and area as approximation
            centroid = p.get("centroid", [0, 0])
            area = p.get("area", 100)
            side = math.sqrt(area) / 2
            min_x = min(min_x, centroid[0] - side)
            min_y = min(min_y, centroid[1] - side)
            max_x = max(max_x, centroid[0] + side)
            max_y = max(max_y, centroid[1] + side)

    total_w = max_x - min_x
    total_h = max_y - min_y

    if total_w <= 0 or total_h <= 0:
        return "square"

    ratio = total_w / total_h
    if ratio > 1.3:
        return "wide"
    elif ratio < 0.77:
        return "tall"
    return "square"


def _has_circular_parts(parts: list[dict]) -> bool:
    """Check if any parts have roughly circular bounding boxes (aspect ratio ~1)."""
    for p in parts:
        bb = p.get("bounding_box", [])
        if len(bb) >= 4:
            w, h = bb[2], bb[3]
            if w > 0 and h > 0:
                ratio = min(w, h) / max(w, h)
                if ratio > 0.8:  # nearly square = roughly circular
                    return True
    return False


def _has_upper_mass(parts: list[dict]) -> bool:
    """Check if the largest part is in the upper half of the overall shape."""
    if not parts:
        return False

    # Find root/largest part
    root = max(parts, key=lambda p: p.get("area", 0))
    root_centroid = root.get("centroid", [0, 0])

    # Find overall vertical extent
    all_centroids_y = [p.get("centroid", [0, 0])[1] for p in parts]
    if not all_centroids_y:
        return False

    mid_y = (min(all_centroids_y) + max(all_centroids_y)) / 2
    return root_centroid[1] < mid_y  # Upper half (lower Y value = higher in image)


def classify_object(
    parts: list[dict],
    symmetry_info: dict,
) -> list[dict]:
    """Score an object against all categories and return top 3.

    Args:
        parts: list of part dicts with area, bounding_box, role, centroid
        symmetry_info: dict with bilateral and radial symmetry data

    Returns:
        list of top 3 classifications with name, confidence, and reasoning.
    """
    bilateral = symmetry_info.get("bilateral", {})
    radial = symmetry_info.get("radial", {})
    is_bilateral = bilateral.get("detected", False)
    is_radial = radial.get("detected", False)
    bilateral_conf = bilateral.get("confidence", 0.0)

    appendage_count = _count_appendages(parts)
    overall_aspect = _get_overall_aspect(parts)
    has_circular = _has_circular_parts(parts)
    has_upper = _has_upper_mass(parts)
    part_count = len(parts)

    scores = []

    for cat_name, cat in _CATEGORIES.items():
        score = 0.0
        reasons = []

        # Symmetry check
        if cat.get("requires_bilateral"):
            if is_bilateral:
                score += 0.25
                reasons.append("bilateral symmetry matches")
            else:
                score -= 0.15
                reasons.append("lacks expected bilateral symmetry")

        if cat.get("allows_radial") and is_radial:
            score += 0.2
            reasons.append("radial symmetry matches")

        if cat.get("allows_asymmetric") and not is_bilateral and not is_radial:
            score += 0.1
            reasons.append("asymmetric nature matches")

        # Appendage count
        a_min, a_max = cat["appendage_count"]
        if a_min <= appendage_count <= a_max:
            # Bonus for being near the expected count
            mid = (a_min + a_max) / 2
            distance = abs(appendage_count - mid) / max(a_max - a_min, 1)
            score += 0.3 * (1.0 - distance)
            reasons.append(f"{appendage_count} appendages in range [{a_min},{a_max}]")
        else:
            score -= 0.2
            reasons.append(f"{appendage_count} appendages outside [{a_min},{a_max}]")

        # Aspect ratio preference
        if cat["aspect_preference"]:
            if overall_aspect == cat["aspect_preference"]:
                score += 0.15
                reasons.append(f"aspect ratio is {overall_aspect} as expected")
            else:
                score -= 0.05

        # Special attributes
        if cat.get("has_circular_parts") and has_circular:
            score += 0.2
            reasons.append("has circular parts (wheels)")
        if cat.get("has_rectangular_parts") and not has_circular:
            score += 0.1
            reasons.append("rectangular parts suggest furniture")

        if cat.get("has_upper_mass") and has_upper:
            score += 0.15
            reasons.append("upper mass detected (head/torso)")

        # Abstract is the fallback — give it a base score
        if cat_name == "abstract":
            score = max(score, 0.1)
            reasons.append("fallback category")

        # Normalize to 0-1
        score = max(0.0, min(1.0, score))

        scores.append({
            "category": cat_name,
            "confidence": round(score, 3),
            "description": cat["description"],
            "reasoning": reasons,
        })

    # Sort by confidence descending
    scores.sort(key=lambda s: s["confidence"], reverse=True)
    return scores[:3]


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_object_classifier tool."""

    @mcp.tool(
        name="adobe_ai_object_classifier",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_object_classifier(params: AiObjectClassifierInput) -> str:
        """Classify object type from part arrangement and symmetry.

        Scores the object against biped, quadruped, vehicle, insect, plant,
        furniture, and abstract categories. Returns top 3 matches.
        """
        try:
            parts = json.loads(params.parts)
        except (json.JSONDecodeError, TypeError) as exc:
            return json.dumps({"error": f"Invalid parts JSON: {exc}"})

        try:
            symmetry_info = json.loads(params.symmetry_info)
        except (json.JSONDecodeError, TypeError) as exc:
            return json.dumps({"error": f"Invalid symmetry_info JSON: {exc}"})

        if not isinstance(parts, list):
            return json.dumps({"error": "parts must be a JSON array"})

        classifications = classify_object(parts, symmetry_info)

        return json.dumps({
            "classifications": classifications,
            "part_count": len(parts),
            "top_match": classifications[0] if classifications else None,
        }, indent=2)
