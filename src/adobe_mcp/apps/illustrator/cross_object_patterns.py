"""Cross-object pattern recognition for labeling parts.

Extracts shape features from parts, builds a pattern database of
labeled features, and matches new parts against the database to
suggest labels based on feature similarity.

Pattern database is stored at:
    ~/.claude/memory/illustration/patterns.json
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


class AiCrossObjectPatternsInput(BaseModel):
    """Pattern recognition across objects for labeling."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ...,
        description="Action: extract_features, record_labeled_part, match_pattern",
    )
    part: Optional[dict] = Field(
        default=None,
        description="Part dict with area, bbox (x,y,w,h), symmetry_score, contour_area",
    )
    features: Optional[dict] = Field(
        default=None,
        description="Pre-computed features dict for recording or matching",
    )
    label: Optional[str] = Field(
        default=None, description="Label for recording a part"
    )
    storage_path: Optional[str] = Field(
        default=None, description="Custom storage path for patterns file"
    )


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _default_patterns_path() -> str:
    """Return the default patterns file path."""
    home = os.path.expanduser("~")
    return os.path.join(home, ".claude", "memory", "illustration", "patterns.json")


def _load_patterns(storage_path: str | None = None) -> list[dict]:
    """Load patterns from disk."""
    path = storage_path or _default_patterns_path()
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def _save_patterns(patterns: list[dict], storage_path: str | None = None) -> None:
    """Save patterns to disk."""
    path = storage_path or _default_patterns_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(patterns, f, indent=2)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def extract_features(part: dict) -> dict:
    """Compute shape features from a part definition.

    Computes:
    - aspect_ratio: bbox width / bbox height
    - relative_area: part area / bbox area
    - symmetry_score: direct from part if available, else 0
    - position_quadrant: which quadrant the center falls in (1-4)
    - compactness: contour area / bbox area (how filled the bbox is)

    Args:
        part: dict with 'area', 'bbox' (dict with x,y,w,h or list [x,y,w,h]),
              optional 'symmetry_score', optional 'contour_area'

    Returns:
        Feature dict with computed values.
    """
    # Parse bbox — support both dict and list formats
    bbox = part.get("bbox", {})
    if isinstance(bbox, list) and len(bbox) == 4:
        bx, by, bw, bh = bbox
    elif isinstance(bbox, dict):
        bx = bbox.get("x", 0)
        by = bbox.get("y", 0)
        bw = bbox.get("w", bbox.get("width", 1))
        bh = bbox.get("h", bbox.get("height", 1))
    else:
        bw, bh = 1, 1
        bx, by = 0, 0

    # Avoid division by zero
    bw = max(bw, 0.001)
    bh = max(bh, 0.001)
    bbox_area = bw * bh

    area = part.get("area", 0)
    contour_area = part.get("contour_area", area)

    aspect_ratio = bw / bh
    relative_area = area / bbox_area if bbox_area > 0 else 0
    symmetry_score = part.get("symmetry_score", 0.0)

    # Position quadrant based on bbox center
    cx = bx + bw / 2
    cy = by + bh / 2
    # Quadrant: 1=top-right, 2=top-left, 3=bottom-left, 4=bottom-right
    # Using image coordinates (0,0 at top-left)
    if cx >= 0 and cy < 0:
        quadrant = 1
    elif cx < 0 and cy < 0:
        quadrant = 2
    elif cx < 0 and cy >= 0:
        quadrant = 3
    else:
        quadrant = 4

    compactness = contour_area / bbox_area if bbox_area > 0 else 0

    return {
        "aspect_ratio": round(aspect_ratio, 4),
        "relative_area": round(relative_area, 4),
        "symmetry_score": round(symmetry_score, 4),
        "position_quadrant": quadrant,
        "compactness": round(compactness, 4),
    }


def record_labeled_part(
    features: dict,
    label: str,
    storage_path: str | None = None,
) -> dict:
    """Add a labeled feature set to the pattern database.

    Args:
        features: pre-computed feature dict
        label: the label for this part (e.g. "arm", "head", "leg")
        storage_path: optional custom path

    Returns:
        The stored pattern entry.
    """
    entry = {
        "features": features,
        "label": label,
    }

    patterns = _load_patterns(storage_path)
    patterns.append(entry)
    _save_patterns(patterns, storage_path)

    return entry


def _feature_distance(a: dict, b: dict) -> float:
    """Compute distance between two feature dicts.

    Uses weighted Euclidean distance across continuous features.
    Quadrant mismatch adds a penalty.
    """
    continuous_keys = ["aspect_ratio", "relative_area", "symmetry_score", "compactness"]
    sum_sq = 0.0
    for key in continuous_keys:
        va = a.get(key, 0.0)
        vb = b.get(key, 0.0)
        sum_sq += (va - vb) ** 2

    # Quadrant mismatch penalty
    if a.get("position_quadrant") != b.get("position_quadrant"):
        sum_sq += 0.25  # Add 0.5^2 penalty for quadrant mismatch

    return math.sqrt(sum_sq)


def match_pattern(
    features: dict,
    storage_path: str | None = None,
    max_distance: float = 0.5,
) -> dict | None:
    """Find the best matching label from the pattern database.

    Args:
        features: feature dict of the part to classify
        storage_path: optional custom path
        max_distance: maximum feature distance to accept a match

    Returns:
        {"label": str, "distance": float, "confidence": float} or None
    """
    patterns = _load_patterns(storage_path)
    if not patterns:
        return None

    best_match = None
    best_distance = float("inf")

    for entry in patterns:
        dist = _feature_distance(features, entry["features"])
        if dist < best_distance:
            best_distance = dist
            best_match = entry

    if best_match is None or best_distance > max_distance:
        return None

    # Convert distance to confidence (closer = higher confidence)
    confidence = max(0.0, 1.0 - best_distance / max_distance)

    return {
        "label": best_match["label"],
        "distance": round(best_distance, 4),
        "confidence": round(confidence, 4),
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_cross_object_patterns tool."""

    @mcp.tool(
        name="adobe_ai_cross_object_patterns",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_cross_object_patterns(
        params: AiCrossObjectPatternsInput,
    ) -> str:
        """Pattern recognition across objects for labeling.

        Actions:
        - extract_features: compute shape features from a part
        - record_labeled_part: add labeled features to database
        - match_pattern: find best matching label for new features
        """
        action = params.action.lower().strip()

        if action == "extract_features":
            if params.part is None:
                return json.dumps({
                    "error": "extract_features requires part"
                })
            features = extract_features(params.part)
            return json.dumps({"action": "extract_features", "features": features})

        elif action == "record_labeled_part":
            if params.features is None or params.label is None:
                return json.dumps({
                    "error": "record_labeled_part requires features and label"
                })
            entry = record_labeled_part(
                params.features, params.label, params.storage_path
            )
            return json.dumps({"action": "record_labeled_part", "entry": entry})

        elif action == "match_pattern":
            if params.features is None:
                return json.dumps({
                    "error": "match_pattern requires features"
                })
            result = match_pattern(params.features, params.storage_path)
            if result is None:
                return json.dumps({
                    "action": "match_pattern",
                    "match": None,
                    "message": "No matching pattern found",
                })
            return json.dumps({"action": "match_pattern", "match": result})

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": [
                    "extract_features",
                    "record_labeled_part",
                    "match_pattern",
                ],
            })
