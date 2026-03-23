"""Confidence scoring for computer vision analysis results.

Provides scoring functions for segmentation quality, connection clarity,
and symmetry accuracy. Each returns a 0.0-1.0 confidence score with
a reasoning string explaining the assessment.
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


class AiCvConfidenceInput(BaseModel):
    """Score confidence of CV analysis results."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ...,
        description="Action: score_segmentation, score_connection, score_symmetry",
    )
    # For score_segmentation
    parts: Optional[list[dict]] = Field(
        default=None,
        description="List of part dicts with area, color info",
    )
    image_stats: Optional[dict] = Field(
        default=None,
        description="Image statistics: total_pixels, non_white_pixels, color_clusters",
    )
    # For score_connection
    connection: Optional[dict] = Field(
        default=None,
        description="Connection dict with boundary_clarity (0-1), width_consistency (0-1)",
    )
    # For score_symmetry
    symmetry_result: Optional[dict] = Field(
        default=None,
        description="Symmetry result dict with ssim_score (0-1)",
    )


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def score_segmentation(parts: list[dict], image_stats: dict) -> dict:
    """Score confidence of part segmentation quality.

    Factors:
    - Color cluster separation: distinct colors = high, gradients = low
    - Part count: 2-10 = normal, >20 = possibly over-segmented
    - Coverage: parts cover >80% of non-white area = good

    Args:
        parts: list of parts with 'area' and optional 'color_variance' keys
        image_stats: dict with 'total_pixels', 'non_white_pixels', 'color_clusters'

    Returns:
        {"score": float, "reasoning": str}
    """
    reasons = []
    score_components = []

    # Factor 1: Part count appropriateness
    part_count = len(parts)
    if part_count == 0:
        return {"score": 0.0, "reasoning": "No parts detected — zero confidence"}

    if 2 <= part_count <= 10:
        count_score = 1.0
        reasons.append(f"Part count ({part_count}) is in ideal range 2-10")
    elif 10 < part_count <= 20:
        count_score = 0.7
        reasons.append(f"Part count ({part_count}) is moderately high")
    elif part_count > 20:
        count_score = 0.3
        reasons.append(f"Part count ({part_count}) suggests over-segmentation")
    else:
        # part_count == 1
        count_score = 0.5
        reasons.append("Only 1 part detected — may be under-segmented")
    score_components.append(count_score)

    # Factor 2: Color cluster separation
    clusters = image_stats.get("color_clusters", 0)
    if clusters >= part_count and clusters <= part_count * 2:
        cluster_score = 1.0
        reasons.append(f"Color clusters ({clusters}) match part count well")
    elif clusters < part_count:
        cluster_score = 0.4
        reasons.append(
            f"Fewer color clusters ({clusters}) than parts ({part_count}) "
            "— possible gradient/noise confusion"
        )
    else:
        cluster_score = 0.6
        reasons.append(f"Many color clusters ({clusters}) — possible over-detection")
    score_components.append(cluster_score)

    # Factor 3: Coverage
    non_white = image_stats.get("non_white_pixels", 0)
    if non_white > 0:
        total_part_area = sum(p.get("area", 0) for p in parts)
        coverage = total_part_area / non_white
        if coverage > 0.8:
            coverage_score = 1.0
            reasons.append(f"Parts cover {coverage:.0%} of content area")
        elif coverage > 0.5:
            coverage_score = 0.7
            reasons.append(f"Parts cover only {coverage:.0%} of content area")
        else:
            coverage_score = 0.3
            reasons.append(f"Parts cover only {coverage:.0%} — significant content missed")
    else:
        coverage_score = 0.5
        reasons.append("No non-white pixels — image may be blank")
    score_components.append(coverage_score)

    # Weighted average
    final_score = sum(score_components) / len(score_components)

    return {
        "score": round(final_score, 3),
        "reasoning": "; ".join(reasons),
    }


def score_connection(connection: dict) -> dict:
    """Score confidence of a detected connection between parts.

    Factors:
    - boundary_clarity: how clearly defined the boundary is (0-1)
    - width_consistency: how uniform the connection width is (0-1)

    Args:
        connection: dict with 'boundary_clarity' and 'width_consistency' keys

    Returns:
        {"score": float, "reasoning": str}
    """
    reasons = []

    clarity = connection.get("boundary_clarity", 0.5)
    consistency = connection.get("width_consistency", 0.5)

    # Boundary clarity contribution
    if clarity >= 0.8:
        reasons.append(f"Clear boundary (clarity={clarity:.2f})")
    elif clarity >= 0.5:
        reasons.append(f"Moderate boundary clarity ({clarity:.2f})")
    else:
        reasons.append(f"Unclear boundary (clarity={clarity:.2f}) — low confidence")

    # Width consistency contribution
    if consistency >= 0.8:
        reasons.append(f"Consistent connection width ({consistency:.2f})")
    elif consistency >= 0.5:
        reasons.append(f"Some width variation ({consistency:.2f})")
    else:
        reasons.append(f"Inconsistent width ({consistency:.2f}) — may not be a real connection")

    # Combined score — weighted toward clarity (60/40)
    score = clarity * 0.6 + consistency * 0.4

    return {
        "score": round(score, 3),
        "reasoning": "; ".join(reasons),
    }


def score_symmetry(symmetry_result: dict) -> dict:
    """Score confidence of symmetry detection from SSIM.

    Uses the SSIM score directly as the confidence measure.

    Args:
        symmetry_result: dict with 'ssim_score' (0.0-1.0)

    Returns:
        {"score": float, "reasoning": str}
    """
    ssim = symmetry_result.get("ssim_score", 0.0)
    ssim = max(0.0, min(1.0, ssim))

    if ssim >= 0.9:
        reasoning = f"Strong symmetry detected (SSIM={ssim:.3f})"
    elif ssim >= 0.7:
        reasoning = f"Moderate symmetry (SSIM={ssim:.3f})"
    elif ssim >= 0.5:
        reasoning = f"Weak symmetry (SSIM={ssim:.3f}) — may be asymmetric"
    else:
        reasoning = f"No meaningful symmetry (SSIM={ssim:.3f})"

    return {
        "score": round(ssim, 3),
        "reasoning": reasoning,
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_cv_confidence tool."""

    @mcp.tool(
        name="adobe_ai_cv_confidence",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_cv_confidence(params: AiCvConfidenceInput) -> str:
        """Score confidence of computer vision analysis results.

        Actions:
        - score_segmentation: confidence based on part count, color separation, coverage
        - score_connection: confidence based on boundary clarity and width consistency
        - score_symmetry: confidence from SSIM score
        """
        action = params.action.lower().strip()

        if action == "score_segmentation":
            if params.parts is None or params.image_stats is None:
                return json.dumps({
                    "error": "score_segmentation requires parts and image_stats"
                })
            result = score_segmentation(params.parts, params.image_stats)
            return json.dumps({"action": "score_segmentation", **result})

        elif action == "score_connection":
            if params.connection is None:
                return json.dumps({
                    "error": "score_connection requires connection"
                })
            result = score_connection(params.connection)
            return json.dumps({"action": "score_connection", **result})

        elif action == "score_symmetry":
            if params.symmetry_result is None:
                return json.dumps({
                    "error": "score_symmetry requires symmetry_result"
                })
            result = score_symmetry(params.symmetry_result)
            return json.dumps({"action": "score_symmetry", **result})

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": [
                    "score_segmentation",
                    "score_connection",
                    "score_symmetry",
                ],
            })
