"""Save and recall object type hierarchy templates.

Templates capture the hierarchy structure, constraints, and relationship
types from a rig so they can be re-applied to new characters of the
same type (e.g. biped, quadruped, vehicle).

Templates are stored as JSON files in ~/.claude/memory/illustration/templates/.

Pure Python implementation.
"""

import json
import os
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from adobe_mcp.apps.illustrator.rig_data import _load_rig, _save_rig


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiHierarchyTemplatesInput(BaseModel):
    """Save, load, list, or apply hierarchy templates."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ..., description="Action: save, load, list, apply"
    )
    character_name: Optional[str] = Field(
        default="character", description="Character identifier (for 'save' and 'apply')"
    )
    template_name: Optional[str] = Field(
        default=None, description="Template name (for save/load/apply)"
    )
    template_dir: Optional[str] = Field(
        default=None,
        description="Override template directory (default: ~/.claude/memory/illustration/templates)"
    )


# ---------------------------------------------------------------------------
# Template directory
# ---------------------------------------------------------------------------


def _default_template_dir() -> str:
    """Return the default template storage directory."""
    return os.path.expanduser("~/.claude/memory/illustration/templates")


def _get_template_dir(override: Optional[str] = None) -> str:
    """Return the template directory, creating it if needed."""
    path = override or _default_template_dir()
    os.makedirs(path, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Pure Python helpers
# ---------------------------------------------------------------------------


def save_template(
    name: str,
    rig: dict,
    template_dir: Optional[str] = None,
) -> dict:
    """Extract hierarchy + constraints + relationships from rig and save as template.

    Captures:
    - landmarks with pivot data (the hierarchy)
    - constraints
    - bones (for structure reference)
    - body_part_labels (for naming)

    Positions are normalized relative to image_size for portability.

    Args:
        name: template name (used as filename)
        rig: the character rig dict
        template_dir: override storage directory

    Returns:
        The saved template dict.
    """
    tdir = _get_template_dir(template_dir)

    # Extract hierarchy data
    landmarks = rig.get("landmarks", {})
    constraints = rig.get("constraints", {})
    bones = rig.get("bones", [])
    labels = rig.get("body_part_labels", {})
    image_size = rig.get("image_size")

    # Normalize positions if image_size is available
    normalized_landmarks = {}
    for lm_name, lm_data in landmarks.items():
        norm = dict(lm_data)  # shallow copy
        if image_size and isinstance(image_size, (list, tuple)) and len(image_size) >= 2:
            w, h = image_size[0], image_size[1]
            if w > 0 and h > 0:
                if "x" in norm:
                    norm["x_norm"] = norm["x"] / w
                if "y" in norm:
                    norm["y_norm"] = norm["y"] / h
        normalized_landmarks[lm_name] = norm

    template = {
        "name": name,
        "landmarks": normalized_landmarks,
        "constraints": constraints,
        "bones": bones,
        "body_part_labels": labels,
        "source_image_size": image_size,
        "part_count": len(labels) if labels else len(landmarks),
    }

    filepath = os.path.join(tdir, f"{name}.json")
    with open(filepath, "w") as f:
        json.dump(template, f, indent=2)

    return template


def load_template(
    name: str,
    template_dir: Optional[str] = None,
) -> Optional[dict]:
    """Load a template from file.

    Args:
        name: template name (filename without .json)
        template_dir: override storage directory

    Returns:
        Template dict, or None if not found.
    """
    tdir = _get_template_dir(template_dir)
    filepath = os.path.join(tdir, f"{name}.json")

    if not os.path.exists(filepath):
        return None

    with open(filepath) as f:
        return json.load(f)


def list_templates(template_dir: Optional[str] = None) -> list[str]:
    """List available template names.

    Returns:
        List of template names (filenames without .json extension).
    """
    tdir = _get_template_dir(template_dir)
    templates = []

    if os.path.isdir(tdir):
        for filename in sorted(os.listdir(tdir)):
            if filename.endswith(".json"):
                templates.append(filename[:-5])  # strip .json

    return templates


def apply_template(
    template: dict,
    rig: dict,
    target_image_size: Optional[list] = None,
) -> dict:
    """Apply a template's hierarchy to a rig, scaling positions.

    If the template has normalized positions (x_norm, y_norm) and a
    target_image_size is provided, positions are scaled to fit.
    Otherwise, raw positions are used.

    Args:
        template: template dict from load_template
        rig: target rig to apply template to
        target_image_size: [w, h] of the target image

    Returns:
        Summary of what was applied.
    """
    applied = {"landmarks": 0, "constraints": 0, "bones": 0, "labels": 0}

    # Apply landmarks
    template_landmarks = template.get("landmarks", {})
    if "landmarks" not in rig:
        rig["landmarks"] = {}

    for lm_name, lm_data in template_landmarks.items():
        new_lm = dict(lm_data)

        # Scale normalized positions to target size
        if target_image_size and len(target_image_size) >= 2:
            tw, th = target_image_size[0], target_image_size[1]
            if "x_norm" in new_lm and tw > 0:
                new_lm["x"] = new_lm["x_norm"] * tw
            if "y_norm" in new_lm and th > 0:
                new_lm["y"] = new_lm["y_norm"] * th

        rig["landmarks"][lm_name] = new_lm
        applied["landmarks"] += 1

    # Apply constraints
    template_constraints = template.get("constraints", {})
    if template_constraints:
        if "constraints" not in rig:
            rig["constraints"] = {}
        rig["constraints"].update(template_constraints)
        applied["constraints"] = len(template_constraints)

    # Apply bones
    template_bones = template.get("bones", [])
    if template_bones:
        rig["bones"] = template_bones
        applied["bones"] = len(template_bones)

    # Apply labels
    template_labels = template.get("body_part_labels", {})
    if template_labels:
        if "body_part_labels" not in rig:
            rig["body_part_labels"] = {}
        rig["body_part_labels"].update(template_labels)
        applied["labels"] = len(template_labels)

    return applied


# ---------------------------------------------------------------------------
# MCP Registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_hierarchy_templates tool."""

    @mcp.tool(
        name="adobe_ai_hierarchy_templates",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_hierarchy_templates(params: AiHierarchyTemplatesInput) -> str:
        """Save, load, list, or apply hierarchy templates.

        Templates capture a rig's hierarchy structure, constraints,
        and relationships for re-use on new characters.
        """
        action = params.action.lower().strip()
        tdir = params.template_dir

        if action == "save":
            if not params.template_name:
                return json.dumps({"error": "template_name is required for save"})
            rig = _load_rig(params.character_name or "character")
            template = save_template(params.template_name, rig, tdir)
            return json.dumps({
                "action": "save",
                "template_name": params.template_name,
                "part_count": template.get("part_count", 0),
                "landmarks": len(template.get("landmarks", {})),
                "constraints": len(template.get("constraints", {})),
            }, indent=2)

        elif action == "load":
            if not params.template_name:
                return json.dumps({"error": "template_name is required for load"})
            template = load_template(params.template_name, tdir)
            if template is None:
                return json.dumps({"error": f"Template '{params.template_name}' not found"})
            return json.dumps({
                "action": "load",
                "template": template,
            }, indent=2)

        elif action == "list":
            templates = list_templates(tdir)
            return json.dumps({
                "action": "list",
                "templates": templates,
                "total": len(templates),
            }, indent=2)

        elif action == "apply":
            if not params.template_name:
                return json.dumps({"error": "template_name is required for apply"})
            template = load_template(params.template_name, tdir)
            if template is None:
                return json.dumps({"error": f"Template '{params.template_name}' not found"})

            rig = _load_rig(params.character_name or "character")
            target_size = rig.get("image_size")
            result = apply_template(template, rig, target_size)
            _save_rig(params.character_name or "character", rig)

            return json.dumps({
                "action": "apply",
                "template_name": params.template_name,
                "applied": result,
            }, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["save", "load", "list", "apply"],
            })
