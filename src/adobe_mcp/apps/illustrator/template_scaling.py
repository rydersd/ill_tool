"""Scale template positions to fit a new target bounding box.

Proportionally scales all part positions, adjusts translation constraints
(but not rotation), and can match template parts to actual detected part
centroids while maintaining relative proportions.

Pure Python implementation — operates on template dict structures.
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


class AiTemplateScalingInput(BaseModel):
    """Scale template positions to fit a target bounding box."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        default="scale_template",
        description="Action: scale_template, maintain_proportions, adjust_constraints",
    )
    template: str = Field(
        ..., description="JSON object of the template to scale"
    )
    target_bounds: str = Field(
        default="",
        description='JSON bounding box: {"x": 0, "y": 0, "width": 800, "height": 600}',
    )
    target_parts: str = Field(
        default="[]",
        description="JSON array of detected part centroids for proportion matching",
    )
    scale_factor: float = Field(
        default=1.0,
        description="Uniform scale factor (used by adjust_constraints)",
        gt=0.0,
    )


# ---------------------------------------------------------------------------
# Scaling functions
# ---------------------------------------------------------------------------


def _get_template_bounds(parts: list[dict]) -> dict:
    """Compute bounding box of all part positions in a template.

    Returns dict with min_x, min_y, max_x, max_y, width, height.
    """
    if not parts:
        return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0}

    positions = []
    for p in parts:
        pos = p.get("position", p.get("centroid", [0, 0]))
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            positions.append(pos)

    if not positions:
        return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0}

    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    return {
        "min_x": min_x, "min_y": min_y,
        "max_x": max_x, "max_y": max_y,
        "width": max_x - min_x,
        "height": max_y - min_y,
    }


def scale_template(template: dict, target_bounds: dict) -> dict:
    """Scale all part positions proportionally to fit within target bounding box.

    Args:
        template: template dict with parts that have position/centroid fields
        target_bounds: dict with x, y, width, height

    Returns:
        template with scaled positions.
    """
    result = {**template}
    parts = [dict(p) for p in result.get("parts", [])]

    if not parts:
        result["parts"] = parts
        return result

    src_bounds = _get_template_bounds(parts)
    src_w = src_bounds["width"] or 1.0
    src_h = src_bounds["height"] or 1.0

    tgt_x = target_bounds.get("x", 0)
    tgt_y = target_bounds.get("y", 0)
    tgt_w = target_bounds.get("width", src_w)
    tgt_h = target_bounds.get("height", src_h)

    scale_x = tgt_w / src_w
    scale_y = tgt_h / src_h

    for part in parts:
        pos_key = "position" if "position" in part else "centroid"
        pos = part.get(pos_key, [0, 0])

        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            # Scale relative to source origin, then translate to target origin
            new_x = (pos[0] - src_bounds["min_x"]) * scale_x + tgt_x
            new_y = (pos[1] - src_bounds["min_y"]) * scale_y + tgt_y
            part[pos_key] = [round(new_x, 2), round(new_y, 2)]

    result["parts"] = parts
    result["_scaling"] = {
        "scale_x": round(scale_x, 4),
        "scale_y": round(scale_y, 4),
        "source_bounds": src_bounds,
        "target_bounds": target_bounds,
    }

    return result


def maintain_proportions(template: dict, target_parts: list[dict]) -> dict:
    """Match template part positions to detected part centroids.

    Finds corresponding parts by name, computes a best-fit scale and
    translation, and applies it to all template parts.

    Args:
        template: template dict with named parts
        target_parts: list of detected parts with name and centroid

    Returns:
        template with adjusted positions maintaining relative proportions.
    """
    result = {**template}
    parts = [dict(p) for p in result.get("parts", [])]

    if not parts or not target_parts:
        result["parts"] = parts
        return result

    # Build name-to-position maps
    template_positions = {}
    for p in parts:
        name = p.get("name", "")
        pos = p.get("position", p.get("centroid", [0, 0]))
        if name and isinstance(pos, (list, tuple)) and len(pos) >= 2:
            template_positions[name] = pos

    target_positions = {}
    for p in target_parts:
        name = p.get("name", "")
        pos = p.get("centroid", p.get("position", [0, 0]))
        if name and isinstance(pos, (list, tuple)) and len(pos) >= 2:
            target_positions[name] = pos

    # Find matching names
    common_names = set(template_positions.keys()) & set(target_positions.keys())

    if len(common_names) < 2:
        # Not enough points to compute a transform — just translate
        if common_names:
            name = list(common_names)[0]
            dx = target_positions[name][0] - template_positions[name][0]
            dy = target_positions[name][1] - template_positions[name][1]
            for part in parts:
                pos_key = "position" if "position" in part else "centroid"
                pos = part.get(pos_key, [0, 0])
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    part[pos_key] = [round(pos[0] + dx, 2), round(pos[1] + dy, 2)]
        result["parts"] = parts
        return result

    # Compute centroid-based scaling
    tmpl_xs = [template_positions[n][0] for n in common_names]
    tmpl_ys = [template_positions[n][1] for n in common_names]
    tgt_xs = [target_positions[n][0] for n in common_names]
    tgt_ys = [target_positions[n][1] for n in common_names]

    tmpl_cx = sum(tmpl_xs) / len(tmpl_xs)
    tmpl_cy = sum(tmpl_ys) / len(tmpl_ys)
    tgt_cx = sum(tgt_xs) / len(tgt_xs)
    tgt_cy = sum(tgt_ys) / len(tgt_ys)

    # Compute scale from average distance to centroid
    tmpl_dists = [
        math.sqrt((x - tmpl_cx) ** 2 + (y - tmpl_cy) ** 2)
        for x, y in zip(tmpl_xs, tmpl_ys)
    ]
    tgt_dists = [
        math.sqrt((x - tgt_cx) ** 2 + (y - tgt_cy) ** 2)
        for x, y in zip(tgt_xs, tgt_ys)
    ]

    avg_tmpl_dist = sum(tmpl_dists) / len(tmpl_dists) if tmpl_dists else 1.0
    avg_tgt_dist = sum(tgt_dists) / len(tgt_dists) if tgt_dists else 1.0

    if avg_tmpl_dist < 0.001:
        scale = 1.0
    else:
        scale = avg_tgt_dist / avg_tmpl_dist

    # Apply scale-from-centroid + translate-to-target-centroid
    for part in parts:
        pos_key = "position" if "position" in part else "centroid"
        pos = part.get(pos_key, [0, 0])
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            new_x = (pos[0] - tmpl_cx) * scale + tgt_cx
            new_y = (pos[1] - tmpl_cy) * scale + tgt_cy
            part[pos_key] = [round(new_x, 2), round(new_y, 2)]

    result["parts"] = parts
    result["_proportion_match"] = {
        "matched_parts": len(common_names),
        "scale_applied": round(scale, 4),
        "source_centroid": [round(tmpl_cx, 2), round(tmpl_cy, 2)],
        "target_centroid": [round(tgt_cx, 2), round(tgt_cy, 2)],
    }

    return result


def adjust_constraints(template: dict, scale_factor: float) -> dict:
    """Scale translation constraints but leave rotation constraints unchanged.

    Args:
        template: template dict with constraints list
        scale_factor: factor to apply to translation values

    Returns:
        template with adjusted constraints.
    """
    result = {**template}
    constraints = [dict(c) for c in result.get("constraints", [])]

    for constraint in constraints:
        ctype = constraint.get("type", "")

        if ctype in ("translation", "translate", "position"):
            # Scale translation limits
            for key in ("min_x", "max_x", "min_y", "max_y", "range_x", "range_y"):
                if key in constraint:
                    constraint[key] = round(constraint[key] * scale_factor, 2)
        # Rotation constraints stay unchanged
        # elif ctype in ("rotation", "rotate"):
        #     pass  # deliberately left alone

    result["constraints"] = constraints
    result["_constraint_scaling"] = {
        "scale_factor": scale_factor,
        "rotation_preserved": True,
        "translation_scaled": True,
    }

    return result


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_template_scaling tool."""

    @mcp.tool(
        name="adobe_ai_template_scaling",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_template_scaling(params: AiTemplateScalingInput) -> str:
        """Scale template positions to fit a target bounding box.

        Actions:
        - scale_template: proportionally scale all positions to target bounds
        - maintain_proportions: match template to detected part centroids
        - adjust_constraints: scale translation constraints by a factor
        """
        action = params.action.lower().strip()

        try:
            template = json.loads(params.template)
        except (json.JSONDecodeError, TypeError) as exc:
            return json.dumps({"error": f"Invalid template JSON: {exc}"})

        # ── scale_template ────────────────────────────────────────────
        if action == "scale_template":
            if not params.target_bounds:
                return json.dumps({"error": "target_bounds required for scale_template"})
            try:
                target_bounds = json.loads(params.target_bounds)
            except (json.JSONDecodeError, TypeError) as exc:
                return json.dumps({"error": f"Invalid target_bounds JSON: {exc}"})

            result = scale_template(template, target_bounds)
            return json.dumps({"action": "scale_template", "template": result}, indent=2)

        # ── maintain_proportions ──────────────────────────────────────
        elif action == "maintain_proportions":
            try:
                target_parts = json.loads(params.target_parts)
            except (json.JSONDecodeError, TypeError) as exc:
                return json.dumps({"error": f"Invalid target_parts JSON: {exc}"})

            result = maintain_proportions(template, target_parts)
            return json.dumps(
                {"action": "maintain_proportions", "template": result}, indent=2
            )

        # ── adjust_constraints ────────────────────────────────────────
        elif action == "adjust_constraints":
            result = adjust_constraints(template, params.scale_factor)
            return json.dumps(
                {"action": "adjust_constraints", "template": result}, indent=2
            )

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": [
                    "scale_template", "maintain_proportions", "adjust_constraints"
                ],
            })
