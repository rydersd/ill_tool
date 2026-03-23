"""Object-type-specific pose presets stored as relative joint angles.

Provides pre-built poses for biped, quadruped, and vehicle rigs.
Poses are stored as relative percentages of each joint's range
(0% = min, 100% = max, 50% = neutral).

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


class AiPoseLibraryGenericInput(BaseModel):
    """Object-type-specific pose presets."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ..., description="Action: get_poses | apply_pose"
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    object_type: Optional[str] = Field(
        default=None, description="Object type: biped, quadruped, vehicle"
    )
    preset_name: Optional[str] = Field(
        default=None, description="Pose preset name to apply"
    )


# ---------------------------------------------------------------------------
# Pose presets
# ---------------------------------------------------------------------------


# Values are relative percentages: 0% = min range, 50% = neutral, 100% = max
POSE_PRESETS: dict[str, dict[str, dict[str, float]]] = {
    "biped": {
        "idle": {
            "hip": 50.0, "spine": 50.0, "chest": 50.0, "neck": 50.0, "head": 50.0,
            "shoulder_l": 45.0, "elbow_l": 40.0, "wrist_l": 50.0,
            "shoulder_r": 45.0, "elbow_r": 40.0, "wrist_r": 50.0,
            "hip_l": 48.0, "knee_l": 45.0, "ankle_l": 50.0,
            "hip_r": 48.0, "knee_r": 45.0, "ankle_r": 50.0,
        },
        "walk_contact": {
            "hip": 50.0, "spine": 52.0, "chest": 48.0, "neck": 50.0, "head": 50.0,
            "shoulder_l": 30.0, "elbow_l": 35.0, "wrist_l": 45.0,
            "shoulder_r": 70.0, "elbow_r": 65.0, "wrist_r": 55.0,
            "hip_l": 70.0, "knee_l": 30.0, "ankle_l": 60.0,
            "hip_r": 30.0, "knee_r": 70.0, "ankle_r": 40.0,
        },
        "walk_passing": {
            "hip": 50.0, "spine": 48.0, "chest": 52.0, "neck": 50.0, "head": 50.0,
            "shoulder_l": 50.0, "elbow_l": 50.0, "wrist_l": 50.0,
            "shoulder_r": 50.0, "elbow_r": 50.0, "wrist_r": 50.0,
            "hip_l": 50.0, "knee_l": 50.0, "ankle_l": 50.0,
            "hip_r": 50.0, "knee_r": 50.0, "ankle_r": 50.0,
        },
        "jump": {
            "hip": 45.0, "spine": 40.0, "chest": 35.0, "neck": 55.0, "head": 55.0,
            "shoulder_l": 80.0, "elbow_l": 70.0, "wrist_l": 60.0,
            "shoulder_r": 80.0, "elbow_r": 70.0, "wrist_r": 60.0,
            "hip_l": 35.0, "knee_l": 65.0, "ankle_l": 70.0,
            "hip_r": 35.0, "knee_r": 65.0, "ankle_r": 70.0,
        },
    },
    "quadruped": {
        "stand": {
            "spine": 50.0, "chest": 50.0, "neck": 50.0, "head": 50.0,
            "shoulder_fl": 48.0, "elbow_fl": 45.0, "wrist_fl": 50.0,
            "shoulder_fr": 48.0, "elbow_fr": 45.0, "wrist_fr": 50.0,
            "hip_bl": 48.0, "knee_bl": 45.0, "ankle_bl": 50.0,
            "hip_br": 48.0, "knee_br": 45.0, "ankle_br": 50.0,
            "tail": 50.0,
        },
        "walk": {
            "spine": 52.0, "chest": 48.0, "neck": 50.0, "head": 50.0,
            "shoulder_fl": 65.0, "elbow_fl": 35.0, "wrist_fl": 55.0,
            "shoulder_fr": 35.0, "elbow_fr": 65.0, "wrist_fr": 45.0,
            "hip_bl": 35.0, "knee_bl": 65.0, "ankle_bl": 45.0,
            "hip_br": 65.0, "knee_br": 35.0, "ankle_br": 55.0,
            "tail": 55.0,
        },
        "sit": {
            "spine": 40.0, "chest": 45.0, "neck": 55.0, "head": 55.0,
            "shoulder_fl": 50.0, "elbow_fl": 40.0, "wrist_fl": 50.0,
            "shoulder_fr": 50.0, "elbow_fr": 40.0, "wrist_fr": 50.0,
            "hip_bl": 20.0, "knee_bl": 80.0, "ankle_bl": 70.0,
            "hip_br": 20.0, "knee_br": 80.0, "ankle_br": 70.0,
            "tail": 30.0,
        },
    },
    "vehicle": {
        "parked": {
            "wheel_fl": 50.0, "wheel_fr": 50.0,
            "wheel_bl": 50.0, "wheel_br": 50.0,
            "steering": 50.0, "suspension_f": 50.0, "suspension_r": 50.0,
            "body": 50.0,
        },
        "moving": {
            "wheel_fl": 75.0, "wheel_fr": 75.0,
            "wheel_bl": 75.0, "wheel_br": 75.0,
            "steering": 50.0, "suspension_f": 55.0, "suspension_r": 45.0,
            "body": 52.0,
        },
        "turning": {
            "wheel_fl": 70.0, "wheel_fr": 70.0,
            "wheel_bl": 70.0, "wheel_br": 70.0,
            "steering": 75.0, "suspension_f": 60.0, "suspension_r": 40.0,
            "body": 55.0,
        },
    },
}


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def get_poses_for_type(object_type: str) -> dict:
    """Return available poses for an object type.

    Args:
        object_type: "biped", "quadruped", "vehicle"

    Returns:
        {"type": str, "poses": {name: {joint: pct}}} or empty if unknown
    """
    presets = POSE_PRESETS.get(object_type)
    if presets is None:
        return {
            "type": object_type,
            "poses": {},
            "available_types": list(POSE_PRESETS.keys()),
        }

    return {
        "type": object_type,
        "poses": presets,
        "pose_names": list(presets.keys()),
    }


def apply_pose_preset(rig: dict, object_type: str, preset_name: str) -> dict:
    """Apply a pose preset to a rig by computing absolute angles from percentages.

    For each joint in the preset:
      absolute_angle = min_deg + (pct / 100) * (max_deg - min_deg)

    If the rig has motion_ranges for a joint, uses those limits.
    Otherwise defaults to -180..+180.

    Args:
        rig: character rig dict
        object_type: "biped", "quadruped", "vehicle"
        preset_name: name of the pose preset

    Returns:
        {"applied": bool, "joint_angles": {joint: angle_deg}}
    """
    presets = POSE_PRESETS.get(object_type)
    if presets is None:
        return {"applied": False, "error": f"Unknown type: {object_type}"}

    pose = presets.get(preset_name)
    if pose is None:
        return {
            "applied": False,
            "error": f"Unknown preset: {preset_name}",
            "available": list(presets.keys()),
        }

    motion_ranges = rig.get("motion_ranges", {})
    joints = rig.get("joints", {})
    applied_angles: dict[str, float] = {}

    for joint_name, pct in pose.items():
        # Clamp percentage to 0-100
        pct = max(0.0, min(100.0, pct))

        # Get range for this joint
        jr = motion_ranges.get(joint_name, {})
        min_deg = jr.get("min_deg", -180.0)
        max_deg = jr.get("max_deg", 180.0)

        # Compute absolute angle from percentage
        angle = min_deg + (pct / 100.0) * (max_deg - min_deg)
        applied_angles[joint_name] = round(angle, 2)

        # Update joint rotation in rig if joint exists
        if joint_name in joints:
            joints[joint_name]["rotation"] = round(angle, 2)

    rig["joints"] = joints
    rig.setdefault("current_pose", {})
    rig["current_pose"] = {
        "type": object_type,
        "preset": preset_name,
        "percentages": pose,
        "angles": applied_angles,
    }

    return {
        "applied": True,
        "type": object_type,
        "preset": preset_name,
        "joint_angles": applied_angles,
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_pose_library_generic tool."""

    @mcp.tool(
        name="adobe_ai_pose_library_generic",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_pose_library_generic(
        params: AiPoseLibraryGenericInput,
    ) -> str:
        """Object-type-specific pose presets.

        Actions:
        - get_poses: list available poses for an object type
        - apply_pose: apply a pose preset to the rig
        """
        action = params.action.lower().strip()

        # ── get_poses ────────────────────────────────────────────────
        if action == "get_poses":
            if not params.object_type:
                return json.dumps({
                    "error": "get_poses requires object_type",
                    "available_types": list(POSE_PRESETS.keys()),
                })

            result = get_poses_for_type(params.object_type)
            return json.dumps({"action": "get_poses", **result}, indent=2)

        # ── apply_pose ───────────────────────────────────────────────
        elif action == "apply_pose":
            if not params.object_type or not params.preset_name:
                return json.dumps({
                    "error": "apply_pose requires object_type and preset_name"
                })

            rig = _load_rig(params.character_name)
            result = apply_pose_preset(rig, params.object_type, params.preset_name)

            if result.get("applied"):
                _save_rig(params.character_name, rig)

            return json.dumps({"action": "apply_pose", **result}, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["get_poses", "apply_pose"],
            })
