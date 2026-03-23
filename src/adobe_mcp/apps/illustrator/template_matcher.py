"""Match new objects against known hierarchy templates.

Compares detected parts from a segmented image against saved templates
to suggest the best-matching object type (biped, quadruped, vehicle, etc.).
Scores are computed from part count, symmetry, and aspect ratio similarity.

Pure Python implementation.
"""

import json
import math
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from adobe_mcp.apps.illustrator.hierarchy_templates import (
    list_templates,
    load_template,
)


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiTemplateMatcherInput(BaseModel):
    """Match parts against known templates."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        default="match", description="Action: match, suggest"
    )
    parts: list[dict] = Field(
        ..., description="List of part dicts from segmenter"
    )
    template_dir: Optional[str] = Field(
        default=None, description="Override template directory"
    )
    top_n: int = Field(
        default=3, description="Number of top matches to return", ge=1, le=10
    )


# ---------------------------------------------------------------------------
# Symmetry detection
# ---------------------------------------------------------------------------


def _detect_symmetry(parts: list[dict]) -> str:
    """Detect symmetry type from part positions.

    Returns: "bilateral", "radial", or "none"
    """
    if not parts:
        return "none"

    centroids = [p.get("centroid", [0, 0]) for p in parts]
    if not centroids:
        return "none"

    # Compute center of mass
    cx = sum(c[0] for c in centroids) / len(centroids)
    cy = sum(c[1] for c in centroids) / len(centroids)

    # Check bilateral symmetry (left-right mirror)
    # For each part on the left, check if there's a corresponding part on the right
    left_parts = [c for c in centroids if c[0] < cx - 5]
    right_parts = [c for c in centroids if c[0] > cx + 5]

    if left_parts and right_parts and abs(len(left_parts) - len(right_parts)) <= 1:
        # Check if distances from center are similar
        left_dists = sorted([abs(c[0] - cx) for c in left_parts])
        right_dists = sorted([abs(c[0] - cx) for c in right_parts])
        min_len = min(len(left_dists), len(right_dists))
        if min_len > 0:
            avg_diff = sum(
                abs(left_dists[i] - right_dists[i])
                for i in range(min_len)
            ) / min_len
            # If average position difference is small relative to spread
            spread = max(1, max(c[0] for c in centroids) - min(c[0] for c in centroids))
            if avg_diff / spread < 0.2:
                return "bilateral"

    # Check radial symmetry (parts evenly distributed around center)
    if len(parts) >= 3:
        angles = []
        for c in centroids:
            angle = math.atan2(c[1] - cy, c[0] - cx)
            angles.append(angle)
        angles.sort()
        if len(angles) >= 3:
            diffs = [angles[i+1] - angles[i] for i in range(len(angles)-1)]
            diffs.append((2 * math.pi + angles[0]) - angles[-1])
            if diffs:
                avg_diff = sum(diffs) / len(diffs)
                variance = sum((d - avg_diff) ** 2 for d in diffs) / len(diffs)
                if variance < 0.3:  # relatively even distribution
                    return "radial"

    return "none"


def _compute_aspect_ratio(parts: list[dict]) -> float:
    """Compute overall bounding box aspect ratio from parts."""
    if not parts:
        return 1.0

    all_bounds = [p.get("bounds", [0, 0, 1, 1]) for p in parts]
    min_x = min(b[0] for b in all_bounds)
    min_y = min(b[1] for b in all_bounds)
    max_x = max(b[0] + b[2] for b in all_bounds)
    max_y = max(b[1] + b[3] for b in all_bounds)

    width = max(1, max_x - min_x)
    height = max(1, max_y - min_y)
    return width / height


# ---------------------------------------------------------------------------
# Pure Python helpers
# ---------------------------------------------------------------------------


def match_templates(
    parts: list[dict],
    templates: dict,
) -> list[dict]:
    """Score each template against the detected parts.

    Scoring factors:
    - Part count match: score based on closeness (+-2 = close, +-5 = weak)
    - Symmetry match: bilateral vs radial vs none
    - Aspect ratio similarity

    Args:
        parts: list of part dicts from segmenter
        templates: dict of {name: template_dict}

    Returns:
        List of {"template": name, "score": float, "breakdown": dict}
        sorted by score descending.
    """
    part_count = len(parts)
    symmetry = _detect_symmetry(parts)
    aspect_ratio = _compute_aspect_ratio(parts)

    results = []
    for name, template in templates.items():
        # Part count score (0 to 1)
        t_part_count = template.get("part_count", 0)
        count_diff = abs(part_count - t_part_count)
        if count_diff <= 2:
            count_score = 1.0 - count_diff * 0.1
        elif count_diff <= 5:
            count_score = 0.6 - (count_diff - 2) * 0.1
        else:
            count_score = max(0.0, 0.3 - (count_diff - 5) * 0.05)

        # Symmetry score (0 or 1)
        # Infer template symmetry from landmark positions
        t_landmarks = template.get("landmarks", {})
        t_parts_for_sym = [
            {"centroid": [lm.get("x", 0), lm.get("y", 0)]}
            for lm in t_landmarks.values()
            if "x" in lm and "y" in lm
        ]
        t_symmetry = _detect_symmetry(t_parts_for_sym) if t_parts_for_sym else "none"
        symmetry_score = 1.0 if symmetry == t_symmetry else 0.3

        # Aspect ratio score
        t_image_size = template.get("source_image_size")
        if t_image_size and isinstance(t_image_size, (list, tuple)) and len(t_image_size) >= 2:
            t_w, t_h = t_image_size[0], max(1, t_image_size[1])
            t_aspect = t_w / t_h
        else:
            t_aspect = 1.0
        ar_diff = abs(aspect_ratio - t_aspect)
        ar_score = max(0.0, 1.0 - ar_diff * 0.5)

        # Weighted combination
        total_score = (
            count_score * 0.4 +
            symmetry_score * 0.3 +
            ar_score * 0.3
        )

        results.append({
            "template": name,
            "score": round(total_score, 3),
            "breakdown": {
                "count_score": round(count_score, 3),
                "symmetry_score": round(symmetry_score, 3),
                "ar_score": round(ar_score, 3),
                "detected_symmetry": symmetry,
                "template_symmetry": t_symmetry,
                "part_count": part_count,
                "template_part_count": t_part_count,
            },
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def suggest_template(
    parts: list[dict],
    template_dir: Optional[str] = None,
    top_n: int = 3,
) -> list[dict]:
    """Load all templates and return the top N matches.

    Args:
        parts: list of part dicts from segmenter
        template_dir: override template directory
        top_n: number of top matches to return

    Returns:
        Top N matching templates with scores.
    """
    names = list_templates(template_dir)
    templates = {}
    for name in names:
        t = load_template(name, template_dir)
        if t:
            templates[name] = t

    if not templates:
        return []

    results = match_templates(parts, templates)
    return results[:top_n]


# ---------------------------------------------------------------------------
# MCP Registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_template_matcher tool."""

    @mcp.tool(
        name="adobe_ai_template_matcher",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_template_matcher(params: AiTemplateMatcherInput) -> str:
        """Match detected parts against known hierarchy templates.

        Scores templates based on part count, symmetry, and aspect ratio
        similarity. Returns top N matches with detailed breakdowns.
        """
        results = suggest_template(
            params.parts,
            params.template_dir,
            params.top_n,
        )
        return json.dumps({
            "action": "match",
            "matches": results,
            "total_matches": len(results),
        }, indent=2)
