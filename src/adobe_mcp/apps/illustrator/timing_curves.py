"""Joint-specific easing curves.

Returns easing function name + parameters based on joint type and
motion type.  Also generates After Effects keyframe interpolation
values (bezier control points for speed graphs).

Pure Python — no JSX or Adobe required.
"""

import json
import math
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from adobe_mcp.apps.illustrator.rig_data import _load_rig, _save_rig


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiTimingCurvesInput(BaseModel):
    """Joint-specific easing curves."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ..., description="Action: get_timing | generate_ae_easing"
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    joint_type: Optional[str] = Field(
        default=None,
        description="Joint category: large, medium, small, secondary",
    )
    joint_name: Optional[str] = Field(
        default=None,
        description="Specific joint name (will auto-classify type)",
    )
    motion_type: Optional[str] = Field(
        default="rotation",
        description="Motion type: rotation, translation",
    )
    curve_name: Optional[str] = Field(
        default=None,
        description="Curve name for generate_ae_easing",
    )
    curve_params: Optional[dict] = Field(
        default=None,
        description="Curve parameters for generate_ae_easing",
    )


# ---------------------------------------------------------------------------
# Joint classification
# ---------------------------------------------------------------------------


# Joint name -> type classification
JOINT_CLASSIFICATION: dict[str, str] = {
    # Large joints (hip, shoulder) → slow, weighty motion
    "hip": "large", "hip_l": "large", "hip_r": "large",
    "shoulder": "large", "shoulder_l": "large", "shoulder_r": "large",
    "spine": "large", "chest": "large",
    # Medium joints (elbow, knee) → moderate motion
    "elbow": "medium", "elbow_l": "medium", "elbow_r": "medium",
    "knee": "medium", "knee_l": "medium", "knee_r": "medium",
    "neck": "medium",
    # Small joints (wrist, ankle) → snappy motion
    "wrist": "small", "wrist_l": "small", "wrist_r": "small",
    "ankle": "small", "ankle_l": "small", "ankle_r": "small",
    "head": "small",
    # Secondary (hair, tail) → spring/overshoot
    "tail": "secondary", "tail_tip": "secondary",
    "hair": "secondary", "antenna": "secondary",
    "ear": "secondary", "fin": "secondary",
}


# ---------------------------------------------------------------------------
# Timing curve presets
# ---------------------------------------------------------------------------


# Easing curves indexed by (joint_type, motion_type)
TIMING_CURVES: dict[tuple[str, str], dict] = {
    # Large joints → cubic ease in/out, slow start & stop
    ("large", "rotation"): {
        "curve_name": "ease_in_out_cubic",
        "description": "Slow start and stop, weighty feel",
        "bezier": {"in_x": 0.42, "in_y": 0.0, "out_x": 0.58, "out_y": 1.0},
        "influence_in": 75.0,
        "influence_out": 75.0,
    },
    ("large", "translation"): {
        "curve_name": "ease_in_out_cubic",
        "description": "Slow start and stop, weighty translation",
        "bezier": {"in_x": 0.42, "in_y": 0.0, "out_x": 0.58, "out_y": 1.0},
        "influence_in": 75.0,
        "influence_out": 75.0,
    },
    # Medium joints → quadratic ease in/out, moderate
    ("medium", "rotation"): {
        "curve_name": "ease_in_out_quad",
        "description": "Moderate acceleration, natural feel",
        "bezier": {"in_x": 0.45, "in_y": 0.0, "out_x": 0.55, "out_y": 1.0},
        "influence_in": 55.0,
        "influence_out": 55.0,
    },
    ("medium", "translation"): {
        "curve_name": "ease_in_out_quad",
        "description": "Moderate translation easing",
        "bezier": {"in_x": 0.45, "in_y": 0.0, "out_x": 0.55, "out_y": 1.0},
        "influence_in": 55.0,
        "influence_out": 55.0,
    },
    # Small joints → ease out quad, snappy
    ("small", "rotation"): {
        "curve_name": "ease_out_quad",
        "description": "Snappy start, smooth stop",
        "bezier": {"in_x": 0.25, "in_y": 0.46, "out_x": 0.45, "out_y": 0.94},
        "influence_in": 30.0,
        "influence_out": 70.0,
    },
    ("small", "translation"): {
        "curve_name": "ease_out_quad",
        "description": "Snappy translation",
        "bezier": {"in_x": 0.25, "in_y": 0.46, "out_x": 0.45, "out_y": 0.94},
        "influence_in": 30.0,
        "influence_out": 70.0,
    },
    # Secondary → spring, overshoot and settle
    ("secondary", "rotation"): {
        "curve_name": "spring",
        "description": "Overshoot and settle, follow-through feel",
        "bezier": {"in_x": 0.2, "in_y": 1.3, "out_x": 0.7, "out_y": 0.9},
        "influence_in": 20.0,
        "influence_out": 90.0,
        "overshoot": 0.15,
        "oscillations": 2,
    },
    ("secondary", "translation"): {
        "curve_name": "spring",
        "description": "Springy translation with overshoot",
        "bezier": {"in_x": 0.2, "in_y": 1.3, "out_x": 0.7, "out_y": 0.9},
        "influence_in": 20.0,
        "influence_out": 90.0,
        "overshoot": 0.15,
        "oscillations": 2,
    },
}


def _classify_joint(joint_name: str) -> str:
    """Classify a joint name into large/medium/small/secondary."""
    name_lower = joint_name.lower()

    # Direct match
    if name_lower in JOINT_CLASSIFICATION:
        return JOINT_CLASSIFICATION[name_lower]

    # Keyword-based classification
    for keyword in ("hair", "tail", "antenna", "ear", "fin", "ribbon"):
        if keyword in name_lower:
            return "secondary"
    for keyword in ("hip", "shoulder", "spine", "chest", "pelvis"):
        if keyword in name_lower:
            return "large"
    for keyword in ("elbow", "knee", "neck"):
        if keyword in name_lower:
            return "medium"
    for keyword in ("wrist", "ankle", "hand", "foot", "finger", "toe", "head"):
        if keyword in name_lower:
            return "small"

    # Default to medium
    return "medium"


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def get_timing_curve(
    joint_type: str,
    motion_type: str = "rotation",
) -> dict:
    """Get timing curve for a joint type and motion type.

    Args:
        joint_type: "large", "medium", "small", "secondary"
        motion_type: "rotation" or "translation"

    Returns:
        Curve definition with name, bezier params, and AE influence values
    """
    key = (joint_type.lower(), motion_type.lower())
    curve = TIMING_CURVES.get(key)

    if curve is None:
        # Fall back to medium rotation
        curve = TIMING_CURVES[("medium", "rotation")]

    return {
        "joint_type": joint_type,
        "motion_type": motion_type,
        **curve,
    }


def generate_ae_easing(
    curve_name: str,
    params: Optional[dict] = None,
) -> dict:
    """Generate After Effects keyframe interpolation values.

    Produces bezier speed graph control points suitable for AE expressions
    or keyframe interpolation.

    Args:
        curve_name: name of the easing curve
        params: optional override parameters

    Returns:
        {"curve_name": str, "keyframe_interpolation": {...},
         "ae_expression": str}
    """
    # Find matching curve by name
    matching_curve = None
    for key, curve in TIMING_CURVES.items():
        if curve["curve_name"] == curve_name:
            matching_curve = dict(curve)
            break

    if matching_curve is None:
        # Provide a reasonable default
        matching_curve = {
            "curve_name": curve_name,
            "bezier": {"in_x": 0.42, "in_y": 0.0, "out_x": 0.58, "out_y": 1.0},
            "influence_in": 50.0,
            "influence_out": 50.0,
        }

    # Apply parameter overrides
    if params:
        if "influence_in" in params:
            matching_curve["influence_in"] = params["influence_in"]
        if "influence_out" in params:
            matching_curve["influence_out"] = params["influence_out"]
        if "bezier" in params:
            matching_curve["bezier"].update(params["bezier"])

    bezier = matching_curve["bezier"]

    # AE keyframe interpolation format
    keyframe_interp = {
        "inType": "BEZIER",
        "outType": "BEZIER",
        "inTemporalEase": [{
            "speed": 0.0,
            "influence": matching_curve.get("influence_in", 50.0),
        }],
        "outTemporalEase": [{
            "speed": 0.0,
            "influence": matching_curve.get("influence_out", 50.0),
        }],
        "spatialTangent": {
            "inTangent": [bezier["in_x"], bezier["in_y"]],
            "outTangent": [bezier["out_x"], bezier["out_y"]],
        },
    }

    # AE expression for custom easing
    ae_expression = (
        f"// {matching_curve['curve_name']} easing\n"
        f"var t = (time - thisComp.layer(index).inPoint) / "
        f"(thisComp.layer(index).outPoint - thisComp.layer(index).inPoint);\n"
        f"var p1 = [{bezier['in_x']}, {bezier['in_y']}];\n"
        f"var p2 = [{bezier['out_x']}, {bezier['out_y']}];\n"
        f"linear(t, 0, 1, value, value);"
    )

    return {
        "curve_name": matching_curve["curve_name"],
        "bezier": bezier,
        "keyframe_interpolation": keyframe_interp,
        "ae_expression": ae_expression,
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_timing_curves tool."""

    @mcp.tool(
        name="adobe_ai_timing_curves",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_timing_curves(params: AiTimingCurvesInput) -> str:
        """Joint-specific easing curves.

        Actions:
        - get_timing: get easing curve for a joint type
        - generate_ae_easing: produce AE keyframe interpolation values
        """
        action = params.action.lower().strip()

        # ── get_timing ───────────────────────────────────────────────
        if action == "get_timing":
            # Resolve joint type from joint_name if needed
            joint_type = params.joint_type
            if joint_type is None and params.joint_name:
                joint_type = _classify_joint(params.joint_name)
            if joint_type is None:
                return json.dumps({
                    "error": "Requires joint_type or joint_name"
                })

            motion_type = params.motion_type or "rotation"
            result = get_timing_curve(joint_type, motion_type)

            return json.dumps({"action": "get_timing", **result}, indent=2)

        # ── generate_ae_easing ───────────────────────────────────────
        elif action == "generate_ae_easing":
            if not params.curve_name:
                return json.dumps({
                    "error": "generate_ae_easing requires curve_name"
                })

            result = generate_ae_easing(params.curve_name, params.curve_params)
            return json.dumps({"action": "generate_ae_easing", **result}, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["get_timing", "generate_ae_easing"],
            })
