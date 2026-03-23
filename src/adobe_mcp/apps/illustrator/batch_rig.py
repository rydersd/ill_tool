"""Batch rig operations for applying templates to multiple characters.

Provides batch_apply_template to load a template and apply it to multiple
character rigs at once, and batch_status to report rig status for a
list of characters.

Uses character_template storage at:
    ~/.claude/memory/illustration/characters/{template_name}.json
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


class AiBatchRigInput(BaseModel):
    """Apply templates to multiple character rigs."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ...,
        description="Action: batch_apply_template, batch_status",
    )
    template_name: Optional[str] = Field(
        default=None, description="Template name to apply"
    )
    character_names: Optional[list[str]] = Field(
        default=None, description="List of character names"
    )
    template_dir: Optional[str] = Field(
        default=None, description="Custom template directory path"
    )


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _default_template_dir() -> str:
    """Return the default directory for character templates."""
    home = os.path.expanduser("~")
    return os.path.join(home, ".claude", "memory", "illustration", "characters")


def _load_template(template_name: str, template_dir: str | None = None) -> dict | None:
    """Load a template file by name.

    Returns:
        The template dict, or None if not found.
    """
    base_dir = template_dir or _default_template_dir()
    path = os.path.join(base_dir, f"{template_name}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def batch_apply_template(
    template_name: str,
    character_names: list[str],
    template_dir: str | None = None,
) -> dict:
    """Load a template and apply it to each character rig.

    The template's rig data (joints, bones, bindings, poses, etc.) is
    merged into each character's rig, preserving the character name.

    Args:
        template_name: name of the template to load
        character_names: list of character names to apply to
        template_dir: optional custom template directory

    Returns:
        {"results": [{"character": ..., "status": ...}, ...]}
    """
    template = _load_template(template_name, template_dir)
    if template is None:
        return {
            "results": [
                {"character": name, "status": "error", "error": f"Template '{template_name}' not found"}
                for name in character_names
            ]
        }

    template_rig = template.get("rig", {})
    results = []

    for char_name in character_names:
        try:
            rig = _load_rig(char_name)
            # Merge template rig data into character rig
            # Preserve character_name, overlay everything else from template
            for key, value in template_rig.items():
                if key == "character_name":
                    continue  # Keep the target character's name
                rig[key] = json.loads(json.dumps(value))  # Deep copy via JSON

            rig["character_name"] = char_name
            rig["template_source"] = template_name
            _save_rig(char_name, rig)

            results.append({
                "character": char_name,
                "status": "success",
                "joints_applied": len(rig.get("joints", {})),
                "bones_applied": len(rig.get("bones", [])),
            })
        except Exception as e:
            results.append({
                "character": char_name,
                "status": "error",
                "error": str(e),
            })

    return {"results": results}


def batch_status(character_names: list[str]) -> dict:
    """Return rig status for each character.

    Reports whether each character has hierarchy (joints), constraints
    (bones), and poses.

    Args:
        character_names: list of character names to check

    Returns:
        {"results": [{"character": ..., "has_hierarchy": bool, ...}, ...]}
    """
    results = []
    for char_name in character_names:
        rig = _load_rig(char_name)
        results.append({
            "character": char_name,
            "has_hierarchy": len(rig.get("joints", {})) > 0,
            "has_constraints": len(rig.get("bones", [])) > 0,
            "has_poses": len(rig.get("poses", {})) > 0,
            "joint_count": len(rig.get("joints", {})),
            "bone_count": len(rig.get("bones", [])),
            "pose_count": len(rig.get("poses", {})),
        })

    return {"results": results}


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_batch_rig tool."""

    @mcp.tool(
        name="adobe_ai_batch_rig",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_batch_rig(params: AiBatchRigInput) -> str:
        """Apply templates to multiple character rigs.

        Actions:
        - batch_apply_template: load template and apply to each character
        - batch_status: report rig status for each character
        """
        action = params.action.lower().strip()

        if action == "batch_apply_template":
            if not params.template_name or not params.character_names:
                return json.dumps({
                    "error": "batch_apply_template requires template_name and character_names"
                })
            result = batch_apply_template(
                params.template_name,
                params.character_names,
                params.template_dir,
            )
            return json.dumps(result)

        elif action == "batch_status":
            if not params.character_names:
                return json.dumps({
                    "error": "batch_status requires character_names"
                })
            result = batch_status(params.character_names)
            return json.dumps(result)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["batch_apply_template", "batch_status"],
            })
