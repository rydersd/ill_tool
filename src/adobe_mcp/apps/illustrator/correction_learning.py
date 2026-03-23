"""Correction learning from user feedback.

Records user corrections to CV analysis results and uses them to
suggest labels for future parts with similar features.

Corrections are stored at:
    ~/.claude/memory/illustration/corrections.json

Each correction captures the original label, corrected label, and
shape context (area ratio, aspect ratio, position) so similar parts
can receive better suggestions in the future.
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


class AiCorrectionLearningInput(BaseModel):
    """Learn from user corrections to improve future analysis."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ...,
        description="Action: record_correction, suggest_from_corrections",
    )
    correction_type: Optional[str] = Field(
        default=None,
        description="Type: part_label, connection, hierarchy, joint_type",
    )
    original: Optional[str] = Field(
        default=None, description="Original label/value"
    )
    corrected: Optional[str] = Field(
        default=None, description="Corrected label/value"
    )
    context: Optional[dict] = Field(
        default=None,
        description="Shape context: area_ratio, aspect_ratio, position_relative_to_root",
    )
    part_features: Optional[dict] = Field(
        default=None,
        description="Features of a new part to get suggestions for",
    )
    storage_path: Optional[str] = Field(
        default=None, description="Custom storage path for corrections file"
    )


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

VALID_CORRECTION_TYPES = {"part_label", "connection", "hierarchy", "joint_type"}


def _default_corrections_path() -> str:
    """Return the default corrections file path."""
    home = os.path.expanduser("~")
    return os.path.join(home, ".claude", "memory", "illustration", "corrections.json")


def _load_corrections(storage_path: str | None = None) -> list[dict]:
    """Load corrections from disk."""
    path = storage_path or _default_corrections_path()
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def _save_corrections(corrections: list[dict], storage_path: str | None = None) -> None:
    """Save corrections to disk."""
    path = storage_path or _default_corrections_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(corrections, f, indent=2)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def record_correction(
    correction_type: str,
    original: str,
    corrected: str,
    context: dict,
    storage_path: str | None = None,
) -> dict:
    """Store a user correction with shape context.

    Args:
        correction_type: one of part_label, connection, hierarchy, joint_type
        original: the original label/value
        corrected: the corrected label/value
        context: shape features dict (area_ratio, aspect_ratio, position_relative_to_root)
        storage_path: optional custom path for the corrections file

    Returns:
        The stored correction dict.

    Raises:
        ValueError: if correction_type is invalid.
    """
    if correction_type not in VALID_CORRECTION_TYPES:
        raise ValueError(
            f"Invalid correction type '{correction_type}'. "
            f"Valid types: {sorted(VALID_CORRECTION_TYPES)}"
        )

    correction = {
        "correction_type": correction_type,
        "original": original,
        "corrected": corrected,
        "context": context,
    }

    corrections = _load_corrections(storage_path)
    corrections.append(correction)
    _save_corrections(corrections, storage_path)

    return correction


def _feature_distance(features_a: dict, features_b: dict) -> float:
    """Compute distance between two feature dicts.

    Compares area_ratio, aspect_ratio, and position_relative_to_root
    with equal weighting. Missing keys contribute 0 distance.

    Returns:
        Euclidean distance across normalized feature dimensions.
    """
    dims = ["area_ratio", "aspect_ratio", "position_relative_to_root"]
    sum_sq = 0.0
    for dim in dims:
        a = features_a.get(dim, 0.0)
        b = features_b.get(dim, 0.0)
        sum_sq += (a - b) ** 2
    return math.sqrt(sum_sq)


def suggest_from_corrections(
    part_features: dict,
    storage_path: str | None = None,
    max_distance: float = 0.3,
) -> dict | None:
    """Suggest a label based on stored corrections with similar features.

    Finds the correction whose context features are closest to the given
    part features (within max_distance).

    Args:
        part_features: shape features of the new part
        storage_path: optional custom corrections file path
        max_distance: maximum feature distance to consider a match

    Returns:
        {"suggested_label": str, "distance": float, "from_correction": dict}
        or None if no match is close enough.
    """
    corrections = _load_corrections(storage_path)
    if not corrections:
        return None

    best_match = None
    best_distance = float("inf")

    for correction in corrections:
        ctx = correction.get("context", {})
        dist = _feature_distance(part_features, ctx)
        if dist < best_distance:
            best_distance = dist
            best_match = correction

    if best_match is None or best_distance > max_distance:
        return None

    return {
        "suggested_label": best_match["corrected"],
        "distance": round(best_distance, 4),
        "from_correction": best_match,
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_correction_learning tool."""

    @mcp.tool(
        name="adobe_ai_correction_learning",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_correction_learning(params: AiCorrectionLearningInput) -> str:
        """Learn from user corrections to improve future analysis.

        Actions:
        - record_correction: store a correction with shape context
        - suggest_from_corrections: get suggestions for a new part
        """
        action = params.action.lower().strip()

        if action == "record_correction":
            if (
                not params.correction_type
                or params.original is None
                or params.corrected is None
                or params.context is None
            ):
                return json.dumps({
                    "error": "record_correction requires correction_type, original, corrected, context"
                })
            try:
                result = record_correction(
                    params.correction_type,
                    params.original,
                    params.corrected,
                    params.context,
                    params.storage_path,
                )
            except ValueError as e:
                return json.dumps({"error": str(e)})
            return json.dumps({"action": "record_correction", "correction": result})

        elif action == "suggest_from_corrections":
            if params.part_features is None:
                return json.dumps({
                    "error": "suggest_from_corrections requires part_features"
                })
            result = suggest_from_corrections(
                params.part_features, params.storage_path
            )
            if result is None:
                return json.dumps({
                    "action": "suggest_from_corrections",
                    "suggestion": None,
                    "message": "No matching corrections found",
                })
            return json.dumps({
                "action": "suggest_from_corrections",
                "suggestion": result,
            })

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["record_correction", "suggest_from_corrections"],
            })
