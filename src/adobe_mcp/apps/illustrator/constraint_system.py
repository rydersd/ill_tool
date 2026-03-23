"""Generic per-joint constraint system for character rigs.

Allows creating rotation/translation constraints on individual joints,
validating poses against those constraints, and clamping pose values
to stay within allowed ranges.

Constraints are stored in rig["constraints"] as a dict keyed by joint name.

Pure Python implementation.
"""

import json
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from adobe_mcp.apps.illustrator.rig_data import _load_rig, _save_rig


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiConstraintSystemInput(BaseModel):
    """Manage per-joint constraints on a character rig."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ..., description="Action: create, validate_pose, clamp, list"
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    joint_name: Optional[str] = Field(
        default=None, description="Joint to constrain (for 'create')"
    )
    constraint_type: Optional[str] = Field(
        default="rotation",
        description="Constraint type: rotation, translation, scale"
    )
    min_val: Optional[float] = Field(
        default=None, description="Minimum allowed value"
    )
    max_val: Optional[float] = Field(
        default=None, description="Maximum allowed value"
    )
    pose: Optional[dict] = Field(
        default=None,
        description="Pose dict to validate/clamp: {joint_name: value, ...}"
    )


# ---------------------------------------------------------------------------
# Pure Python helpers
# ---------------------------------------------------------------------------


def create_constraint(
    joint_name: str,
    constraint_type: str,
    min_val: float,
    max_val: float,
) -> dict:
    """Create a constraint dict for a joint.

    Args:
        joint_name: name of the joint
        constraint_type: "rotation", "translation", or "scale"
        min_val: minimum allowed value
        max_val: maximum allowed value

    Returns:
        Constraint dict ready to store in rig["constraints"].
    """
    return {
        "joint_name": joint_name,
        "type": constraint_type,
        "min": min_val,
        "max": max_val,
    }


def validate_pose(rig: dict, pose: dict) -> dict:
    """Check if all joint values in a pose respect constraints.

    Args:
        rig: the character rig (must have "constraints" key)
        pose: dict of {joint_name: value} representing current pose

    Returns:
        {"valid": bool, "violations": [{"joint": str, "value": float,
         "min": float, "max": float, "type": str}]}
    """
    constraints = rig.get("constraints", {})
    violations = []

    for joint_name, value in pose.items():
        if joint_name not in constraints:
            continue

        constraint = constraints[joint_name]
        min_val = constraint.get("min", float("-inf"))
        max_val = constraint.get("max", float("inf"))

        if value < min_val or value > max_val:
            violations.append({
                "joint": joint_name,
                "value": value,
                "min": min_val,
                "max": max_val,
                "type": constraint.get("type", "unknown"),
            })

    return {
        "valid": len(violations) == 0,
        "violations": violations,
    }


def clamp_to_constraints(rig: dict, pose: dict) -> dict:
    """Clamp pose values to constraint ranges.

    Args:
        rig: the character rig (must have "constraints" key)
        pose: dict of {joint_name: value}

    Returns:
        New pose dict with values clamped to allowed ranges.
    """
    constraints = rig.get("constraints", {})
    clamped = {}

    for joint_name, value in pose.items():
        if joint_name in constraints:
            constraint = constraints[joint_name]
            min_val = constraint.get("min", float("-inf"))
            max_val = constraint.get("max", float("inf"))
            clamped[joint_name] = max(min_val, min(max_val, value))
        else:
            clamped[joint_name] = value

    return clamped


# ---------------------------------------------------------------------------
# MCP Registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_constraint_system tool."""

    @mcp.tool(
        name="adobe_ai_constraint_system",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_constraint_system(params: AiConstraintSystemInput) -> str:
        """Manage per-joint constraints for rotation, translation, and scale.

        Actions:
        - create: Add a constraint to a joint
        - validate_pose: Check if a pose respects all constraints
        - clamp: Clamp a pose to constraint ranges
        - list: List all constraints in the rig
        """
        rig = _load_rig(params.character_name)
        action = params.action.lower().strip()

        if action == "create":
            if not params.joint_name:
                return json.dumps({"error": "joint_name is required for create"})
            if params.min_val is None or params.max_val is None:
                return json.dumps({"error": "min_val and max_val are required"})

            constraint = create_constraint(
                params.joint_name,
                params.constraint_type or "rotation",
                params.min_val,
                params.max_val,
            )

            if "constraints" not in rig:
                rig["constraints"] = {}
            rig["constraints"][params.joint_name] = constraint
            _save_rig(params.character_name, rig)

            return json.dumps({
                "action": "create",
                "constraint": constraint,
            }, indent=2)

        elif action == "validate_pose":
            if not params.pose:
                return json.dumps({"error": "pose is required for validate_pose"})
            result = validate_pose(rig, params.pose)
            return json.dumps({
                "action": "validate_pose",
                **result,
            }, indent=2)

        elif action == "clamp":
            if not params.pose:
                return json.dumps({"error": "pose is required for clamp"})
            clamped = clamp_to_constraints(rig, params.pose)
            return json.dumps({
                "action": "clamp",
                "original": params.pose,
                "clamped": clamped,
            }, indent=2)

        elif action == "list":
            constraints = rig.get("constraints", {})
            return json.dumps({
                "action": "list",
                "constraints": constraints,
                "total": len(constraints),
            }, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["create", "validate_pose", "clamp", "list"],
            })
