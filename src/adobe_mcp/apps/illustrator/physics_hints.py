"""Estimate mass and center of gravity from parts.

Computes relative mass (proportional to area), center of gravity
(weighted centroid), and moment of inertia around a pivot for a set
of parts.

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


class AiPhysicsHintsInput(BaseModel):
    """Estimate mass and center of gravity from parts."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ..., description="Action: estimate_mass | compute_cog | compute_inertia"
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    parts: Optional[list[dict]] = Field(
        default=None,
        description="List of parts, each with 'name' and 'bounds' [x,y,w,h]",
    )
    pivot: Optional[list[float]] = Field(
        default=None,
        description="Pivot point [x, y] for moment of inertia calculation",
    )


# ---------------------------------------------------------------------------
# Part helpers
# ---------------------------------------------------------------------------


def _part_area(part: dict) -> float:
    """Compute area from part bounds [x, y, w, h]."""
    bounds = part.get("bounds", [0, 0, 0, 0])
    return bounds[2] * bounds[3]


def _part_centroid(part: dict) -> tuple[float, float]:
    """Compute centroid from part bounds [x, y, w, h]."""
    bounds = part.get("bounds", [0, 0, 0, 0])
    return (bounds[0] + bounds[2] / 2.0, bounds[1] + bounds[3] / 2.0)


# ---------------------------------------------------------------------------
# Core physics computation
# ---------------------------------------------------------------------------


def estimate_mass(parts: list[dict]) -> dict:
    """Estimate relative mass for each part based on area.

    mass_i = area_i / total_area

    Args:
        parts: list of dicts with "name" and "bounds" [x, y, w, h]

    Returns:
        {"masses": {name: relative_mass}, "total_area": float}
    """
    total_area = sum(_part_area(p) for p in parts)
    if total_area < 0.001:
        return {
            "masses": {p.get("name", f"part_{i}"): 0.0 for i, p in enumerate(parts)},
            "total_area": 0.0,
        }

    masses: dict[str, float] = {}
    for i, part in enumerate(parts):
        name = part.get("name", f"part_{i}")
        area = _part_area(part)
        masses[name] = round(area / total_area, 6)

    return {"masses": masses, "total_area": round(total_area, 2)}


def compute_center_of_gravity(parts: list[dict]) -> dict:
    """Compute weighted centroid (center of gravity).

    cog = sum(centroid_i * mass_i) / sum(mass_i)

    Args:
        parts: list of dicts with "name" and "bounds" [x, y, w, h]

    Returns:
        {"cog": [x, y], "per_part": [{name, centroid, mass}]}
    """
    total_area = sum(_part_area(p) for p in parts)
    if total_area < 0.001:
        return {"cog": [0.0, 0.0], "per_part": []}

    weighted_x = 0.0
    weighted_y = 0.0
    per_part: list[dict] = []

    for i, part in enumerate(parts):
        name = part.get("name", f"part_{i}")
        area = _part_area(part)
        mass = area / total_area
        cx, cy = _part_centroid(part)

        weighted_x += cx * mass
        weighted_y += cy * mass

        per_part.append({
            "name": name,
            "centroid": [round(cx, 2), round(cy, 2)],
            "mass": round(mass, 6),
        })

    return {
        "cog": [round(weighted_x, 4), round(weighted_y, 4)],
        "per_part": per_part,
    }


def compute_moment_of_inertia(parts: list[dict], pivot: list[float]) -> dict:
    """Compute moment of inertia for rotation around a pivot.

    I = sum(mass_i * dist_i^2)

    where dist_i is the distance from the part centroid to the pivot.

    Args:
        parts: list of dicts with "name" and "bounds" [x, y, w, h]
        pivot: [x, y] pivot point

    Returns:
        {"moment_of_inertia": float, "pivot": [x,y],
         "per_part": [{name, distance, contribution}]}
    """
    total_area = sum(_part_area(p) for p in parts)
    if total_area < 0.001:
        return {
            "moment_of_inertia": 0.0,
            "pivot": pivot,
            "per_part": [],
        }

    total_inertia = 0.0
    per_part: list[dict] = []

    for i, part in enumerate(parts):
        name = part.get("name", f"part_{i}")
        area = _part_area(part)
        mass = area / total_area
        cx, cy = _part_centroid(part)

        dx = cx - pivot[0]
        dy = cy - pivot[1]
        dist_sq = dx * dx + dy * dy
        dist = math.sqrt(dist_sq)

        contribution = mass * dist_sq
        total_inertia += contribution

        per_part.append({
            "name": name,
            "distance": round(dist, 4),
            "mass": round(mass, 6),
            "contribution": round(contribution, 6),
        })

    return {
        "moment_of_inertia": round(total_inertia, 6),
        "pivot": pivot,
        "per_part": per_part,
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_physics_hints tool."""

    @mcp.tool(
        name="adobe_ai_physics_hints",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_physics_hints(params: AiPhysicsHintsInput) -> str:
        """Estimate mass and center of gravity from parts.

        Actions:
        - estimate_mass: relative mass proportional to area
        - compute_cog: weighted centroid (center of gravity)
        - compute_inertia: moment of inertia around a pivot
        """
        action = params.action.lower().strip()

        parts = params.parts
        if parts is None:
            return json.dumps({"error": "Requires 'parts' list"})

        if not parts:
            return json.dumps({"error": "Parts list is empty"})

        # ── estimate_mass ────────────────────────────────────────────
        if action == "estimate_mass":
            result = estimate_mass(parts)

            rig = _load_rig(params.character_name)
            rig["physics"] = rig.get("physics", {})
            rig["physics"]["masses"] = result["masses"]
            _save_rig(params.character_name, rig)

            return json.dumps({"action": "estimate_mass", **result}, indent=2)

        # ── compute_cog ─────────────────────────────────────────────
        elif action == "compute_cog":
            result = compute_center_of_gravity(parts)

            rig = _load_rig(params.character_name)
            rig["physics"] = rig.get("physics", {})
            rig["physics"]["cog"] = result["cog"]
            _save_rig(params.character_name, rig)

            return json.dumps({"action": "compute_cog", **result}, indent=2)

        # ── compute_inertia ──────────────────────────────────────────
        elif action == "compute_inertia":
            if not params.pivot:
                return json.dumps({
                    "error": "compute_inertia requires 'pivot' [x, y]"
                })

            result = compute_moment_of_inertia(parts, params.pivot)

            rig = _load_rig(params.character_name)
            rig["physics"] = rig.get("physics", {})
            rig["physics"]["moment_of_inertia"] = result["moment_of_inertia"]
            _save_rig(params.character_name, rig)

            return json.dumps({"action": "compute_inertia", **result}, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["estimate_mass", "compute_cog", "compute_inertia"],
            })
