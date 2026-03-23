"""Template inheritance: modify rig templates with add/remove/merge operations.

Supports "Like X but with Y" workflows — add parts, remove parts, merge
templates at a connection point, or derive a new template from a base
with modifications.

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


class AiTemplateInheritanceInput(BaseModel):
    """Modify rig templates: add/remove parts, merge templates."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ...,
        description="Action: add_parts, remove_parts, merge_templates, derive_template",
    )
    template: str = Field(
        default="{}",
        description="JSON object of the base template",
    )
    template_b: str = Field(
        default="{}",
        description="JSON object of second template (for merge)",
    )
    parts_json: str = Field(
        default="[]",
        description="JSON array of parts to add or part names to remove",
    )
    merge_point: str = Field(
        default="",
        description="Part name to attach template_b to (for merge)",
    )
    modifications: str = Field(
        default="{}",
        description='JSON modifications: {"add": [...], "remove": [...]}',
    )


# ---------------------------------------------------------------------------
# Template manipulation functions
# ---------------------------------------------------------------------------


def _ensure_template_structure(template: dict) -> dict:
    """Ensure a template dict has all required fields with defaults."""
    return {
        "name": template.get("name", "unnamed"),
        "parts": template.get("parts", []),
        "connections": template.get("connections", []),
        "constraints": template.get("constraints", []),
        "poses": template.get("poses", {}),
        "metadata": template.get("metadata", {}),
    }


def add_parts(template: dict, new_parts: list[dict]) -> dict:
    """Add parts and their connections to an existing template.

    Each new part can include a 'connects_to' field specifying which
    existing part it connects to.

    Args:
        template: the base template dict
        new_parts: list of part dicts to add

    Returns:
        modified template with new parts and connections.
    """
    result = _ensure_template_structure(template)
    existing_names = {p.get("name") for p in result["parts"]}

    for part in new_parts:
        name = part.get("name", f"new_part_{len(result['parts'])}")
        if name in existing_names:
            # Rename to avoid collision
            name = f"{name}_{len(result['parts'])}"

        new_part = {**part, "name": name}
        # Extract connection info before adding to parts
        connects_to = new_part.pop("connects_to", None)
        result["parts"].append(new_part)
        existing_names.add(name)

        # Add connection if specified
        if connects_to and connects_to in existing_names:
            result["connections"].append({
                "from": connects_to,
                "to": name,
                "type": part.get("connection_type", "hinge"),
            })

    return result


def remove_parts(template: dict, part_names: list[str]) -> dict:
    """Remove parts and their connections from a template.

    Args:
        template: the base template dict
        part_names: list of part names to remove

    Returns:
        modified template without the specified parts.
    """
    result = _ensure_template_structure(template)
    names_to_remove = set(part_names)

    # Remove parts
    result["parts"] = [
        p for p in result["parts"]
        if p.get("name") not in names_to_remove
    ]

    # Remove connections involving removed parts
    result["connections"] = [
        c for c in result["connections"]
        if c.get("from") not in names_to_remove and c.get("to") not in names_to_remove
    ]

    # Remove constraints involving removed parts
    result["constraints"] = [
        c for c in result["constraints"]
        if c.get("part") not in names_to_remove
        and c.get("part_a") not in names_to_remove
        and c.get("part_b") not in names_to_remove
    ]

    return result


def merge_templates(
    template_a: dict,
    template_b: dict,
    merge_point: str,
) -> dict:
    """Attach template_b to template_a at the specified merge point.

    The merge point must be a part name in template_a. All parts from
    template_b are added, with the root part of template_b connected
    to the merge point.

    Args:
        template_a: the primary template
        template_b: the template to attach
        merge_point: part name in template_a to connect to

    Returns:
        merged template.
    """
    result = _ensure_template_structure(template_a)
    b = _ensure_template_structure(template_b)

    existing_names = {p.get("name") for p in result["parts"]}

    if merge_point not in existing_names:
        return {
            **result,
            "error": f"Merge point '{merge_point}' not found in template_a",
        }

    # Prefix template_b part names to avoid collisions
    prefix = b.get("name", "b") + "_"
    name_map = {}

    for part in b["parts"]:
        old_name = part.get("name", "")
        new_name = prefix + old_name if old_name in existing_names else old_name
        name_map[old_name] = new_name
        result["parts"].append({**part, "name": new_name})

    # Remap and add connections from template_b
    for conn in b["connections"]:
        result["connections"].append({
            "from": name_map.get(conn.get("from", ""), conn.get("from", "")),
            "to": name_map.get(conn.get("to", ""), conn.get("to", "")),
            "type": conn.get("type", "hinge"),
        })

    # Connect the first part of template_b to the merge point
    if b["parts"]:
        first_b_name = name_map.get(
            b["parts"][0].get("name", ""),
            b["parts"][0].get("name", ""),
        )
        result["connections"].append({
            "from": merge_point,
            "to": first_b_name,
            "type": "hinge",
        })

    # Add constraints from template_b with remapped names
    for constraint in b["constraints"]:
        remapped = dict(constraint)
        for key in ("part", "part_a", "part_b"):
            if key in remapped:
                remapped[key] = name_map.get(remapped[key], remapped[key])
        result["constraints"].append(remapped)

    result["name"] = f"{result['name']}+{b['name']}"
    return result


def derive_template(base_template: dict, modifications: dict) -> dict:
    """Apply modifications to a base template to derive a new one.

    Modifications dict can contain:
        - add: list of parts to add
        - remove: list of part names to remove
        - rename: dict of {old_name: new_name}

    Args:
        base_template: the starting template
        modifications: dict describing changes

    Returns:
        new derived template.
    """
    result = _ensure_template_structure(base_template)

    # Remove parts first
    to_remove = modifications.get("remove", [])
    if to_remove:
        result = remove_parts(result, to_remove)

    # Rename parts
    rename_map = modifications.get("rename", {})
    if rename_map:
        for part in result["parts"]:
            old_name = part.get("name", "")
            if old_name in rename_map:
                part["name"] = rename_map[old_name]
        for conn in result["connections"]:
            if conn.get("from") in rename_map:
                conn["from"] = rename_map[conn["from"]]
            if conn.get("to") in rename_map:
                conn["to"] = rename_map[conn["to"]]

    # Add new parts
    to_add = modifications.get("add", [])
    if to_add:
        result = add_parts(result, to_add)

    # Update name to indicate derivation
    result["name"] = f"{result['name']}_derived"
    result["metadata"]["derived_from"] = base_template.get("name", "unknown")
    result["metadata"]["modifications_applied"] = list(modifications.keys())

    return result


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_template_inheritance tool."""

    @mcp.tool(
        name="adobe_ai_template_inheritance",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_template_inheritance(params: AiTemplateInheritanceInput) -> str:
        """Modify rig templates: add/remove parts, merge, or derive new templates.

        Supports 'Like X but with Y' workflows for template customization.
        """
        action = params.action.lower().strip()

        try:
            template = json.loads(params.template)
        except (json.JSONDecodeError, TypeError) as exc:
            return json.dumps({"error": f"Invalid template JSON: {exc}"})

        # ── add_parts ─────────────────────────────────────────────────
        if action == "add_parts":
            try:
                new_parts = json.loads(params.parts_json)
            except (json.JSONDecodeError, TypeError) as exc:
                return json.dumps({"error": f"Invalid parts_json: {exc}"})

            result = add_parts(template, new_parts)
            return json.dumps({
                "action": "add_parts",
                "parts_added": len(new_parts),
                "template": result,
            }, indent=2)

        # ── remove_parts ──────────────────────────────────────────────
        elif action == "remove_parts":
            try:
                part_names = json.loads(params.parts_json)
            except (json.JSONDecodeError, TypeError) as exc:
                return json.dumps({"error": f"Invalid parts_json: {exc}"})

            result = remove_parts(template, part_names)
            return json.dumps({
                "action": "remove_parts",
                "parts_removed": len(part_names),
                "template": result,
            }, indent=2)

        # ── merge_templates ───────────────────────────────────────────
        elif action == "merge_templates":
            try:
                template_b = json.loads(params.template_b)
            except (json.JSONDecodeError, TypeError) as exc:
                return json.dumps({"error": f"Invalid template_b JSON: {exc}"})

            if not params.merge_point:
                return json.dumps({"error": "merge_point is required for merge"})

            result = merge_templates(template, template_b, params.merge_point)
            return json.dumps({
                "action": "merge_templates",
                "merge_point": params.merge_point,
                "template": result,
            }, indent=2)

        # ── derive_template ───────────────────────────────────────────
        elif action == "derive_template":
            try:
                modifications = json.loads(params.modifications)
            except (json.JSONDecodeError, TypeError) as exc:
                return json.dumps({"error": f"Invalid modifications JSON: {exc}"})

            result = derive_template(template, modifications)
            return json.dumps({
                "action": "derive_template",
                "template": result,
            }, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": [
                    "add_parts", "remove_parts", "merge_templates", "derive_template"
                ],
            })
