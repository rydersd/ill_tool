"""Export and import hierarchy templates as JSON files.

Provides round-trip serialization for rig templates, with validation
on import and sensible defaults for missing fields. Templates are
stored in a configurable directory.

Pure Python implementation.
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

_DEFAULT_TEMPLATE_DIR = os.path.expanduser(
    "~/.claude/memory/illustration/templates"
)


class AiTemplateExportInput(BaseModel):
    """Export or import a hierarchy template as JSON."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ..., description="Action: export_template, import_template"
    )
    template: str = Field(
        default="{}",
        description="JSON object of the template to export",
    )
    path: str = Field(
        default="",
        description="File path for export/import (defaults to templates dir)",
    )
    template_name: str = Field(
        default="",
        description="Template name (used to derive path if path is empty)",
    )


# ---------------------------------------------------------------------------
# Required template fields with defaults
# ---------------------------------------------------------------------------

_TEMPLATE_DEFAULTS = {
    "name": "unnamed",
    "parts": [],
    "connections": [],
    "constraints": [],
    "poses": {},
    "metadata": {},
    "tags": [],
}


# ---------------------------------------------------------------------------
# Export/import functions
# ---------------------------------------------------------------------------


def export_template(template: dict, path: str) -> dict:
    """Write a template dict as a JSON file.

    Ensures all required fields are present (fills defaults for missing ones).

    Args:
        template: the template dict to export
        path: file path to write to

    Returns:
        dict with success status and path.
    """
    # Ensure required fields
    output = {}
    for key, default in _TEMPLATE_DEFAULTS.items():
        output[key] = template.get(key, default)

    # Preserve any extra fields from the template
    for key, val in template.items():
        if key not in output:
            output[key] = val

    # Ensure directory exists
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return {
        "success": True,
        "path": path,
        "template_name": output.get("name", "unnamed"),
        "part_count": len(output.get("parts", [])),
        "connection_count": len(output.get("connections", [])),
    }


def import_template(path: str) -> dict:
    """Load and validate a template from a JSON file.

    Fills missing fields with defaults. Returns error dict if file is
    invalid or missing.

    Args:
        path: file path to read from

    Returns:
        the loaded template dict, or error dict.
    """
    if not os.path.isfile(path):
        return {"error": f"Template file not found: {path}"}

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid JSON in template file: {exc}"}
    except OSError as exc:
        return {"error": f"Could not read template file: {exc}"}

    if not isinstance(raw, dict):
        return {"error": "Template file must contain a JSON object (not array)"}

    # Fill defaults for missing fields
    for key, default in _TEMPLATE_DEFAULTS.items():
        if key not in raw:
            raw[key] = default

    # Validate parts is a list
    if not isinstance(raw.get("parts"), list):
        raw["parts"] = []

    # Validate connections is a list
    if not isinstance(raw.get("connections"), list):
        raw["connections"] = []

    return raw


def _resolve_path(path: str, template_name: str) -> str:
    """Resolve a template file path from explicit path or template name.

    If path is given, use it. Otherwise derive from template_name and
    default directory.
    """
    if path:
        return os.path.expanduser(path)

    if template_name:
        safe_name = template_name.replace(" ", "_").replace("/", "_")
        return os.path.join(_DEFAULT_TEMPLATE_DIR, f"{safe_name}.json")

    return os.path.join(_DEFAULT_TEMPLATE_DIR, "unnamed.json")


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_template_export tool."""

    @mcp.tool(
        name="adobe_ai_template_export",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_template_export(params: AiTemplateExportInput) -> str:
        """Export or import hierarchy templates as JSON.

        Actions:
        - export_template: write template to a JSON file
        - import_template: load and validate a template from file
        """
        action = params.action.lower().strip()
        resolved_path = _resolve_path(params.path, params.template_name)

        # ── export_template ───────────────────────────────────────────
        if action == "export_template":
            try:
                template = json.loads(params.template)
            except (json.JSONDecodeError, TypeError) as exc:
                return json.dumps({"error": f"Invalid template JSON: {exc}"})

            result = export_template(template, resolved_path)
            return json.dumps(result, indent=2)

        # ── import_template ───────────────────────────────────────────
        elif action == "import_template":
            result = import_template(resolved_path)
            if "error" in result:
                return json.dumps(result)

            return json.dumps({
                "action": "import_template",
                "path": resolved_path,
                "template": result,
            }, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["export_template", "import_template"],
            })
