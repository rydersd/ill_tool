"""Search templates by characteristics: tags, part count, symmetry type.

Provides tag management and multi-criteria filtering across a collection
of templates. Supports searching by tags, minimum/maximum part counts,
and symmetry type.

Pure Python implementation — operates on template dict collections.
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


class AiTemplateLibrarySearchInput(BaseModel):
    """Search templates by tags, part count, and symmetry."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ..., description="Action: search_templates, tag_template"
    )
    query: str = Field(
        default="{}",
        description=(
            'JSON search query: {"tags": ["wings"], "min_parts": 5, '
            '"max_parts": 20, "symmetry": "bilateral"}'
        ),
    )
    templates: str = Field(
        default="[]",
        description="JSON array of templates to search within",
    )
    template: str = Field(
        default="{}",
        description="JSON template to tag (for tag_template action)",
    )
    tags: str = Field(
        default="[]",
        description="JSON array of tags to add (for tag_template action)",
    )


# ---------------------------------------------------------------------------
# Search and tagging functions
# ---------------------------------------------------------------------------


def search_templates(query: dict, templates: list[dict]) -> list[dict]:
    """Search templates by multiple criteria.

    Query fields (all optional):
        - tags: list of strings — template must have ALL listed tags
        - min_parts: minimum part count
        - max_parts: maximum part count
        - symmetry: symmetry type string to match in metadata
        - name_contains: substring match on template name

    Args:
        query: dict of search criteria
        templates: list of template dicts to search

    Returns:
        list of matching templates with match scores.
    """
    if not templates:
        return []

    required_tags = set(query.get("tags", []))
    min_parts = query.get("min_parts", 0)
    max_parts = query.get("max_parts", float("inf"))
    symmetry = query.get("symmetry", "").lower()
    name_contains = query.get("name_contains", "").lower()

    results = []

    for tmpl in templates:
        score = 0.0
        match = True

        # Tag matching
        tmpl_tags = set(tmpl.get("tags", []))
        if required_tags:
            if required_tags.issubset(tmpl_tags):
                score += 0.4
            else:
                match = False

        # Part count matching
        part_count = len(tmpl.get("parts", []))
        if part_count < min_parts or part_count > max_parts:
            match = False
        else:
            score += 0.2

        # Symmetry matching
        if symmetry:
            tmpl_symmetry = tmpl.get("metadata", {}).get("symmetry", "").lower()
            tmpl_tags_lower = {t.lower() for t in tmpl_tags}
            if symmetry in tmpl_symmetry or symmetry in tmpl_tags_lower:
                score += 0.2
            else:
                match = False

        # Name matching
        if name_contains:
            tmpl_name = tmpl.get("name", "").lower()
            if name_contains in tmpl_name:
                score += 0.2
            else:
                match = False

        if match:
            results.append({
                "template": tmpl,
                "match_score": round(score, 3),
                "name": tmpl.get("name", "unnamed"),
                "part_count": part_count,
                "tags": list(tmpl_tags),
            })

    # Sort by match score descending
    results.sort(key=lambda r: r["match_score"], reverse=True)
    return results


def tag_template(template: dict, tags: list[str]) -> dict:
    """Add searchable tags to a template.

    Args:
        template: the template dict to tag
        tags: list of tag strings to add

    Returns:
        template with updated tags list (no duplicates).
    """
    result = {**template}
    existing_tags = set(result.get("tags", []))
    existing_tags.update(tags)
    result["tags"] = sorted(existing_tags)
    return result


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_template_library_search tool."""

    @mcp.tool(
        name="adobe_ai_template_library_search",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_template_library_search(
        params: AiTemplateLibrarySearchInput,
    ) -> str:
        """Search templates by tags, part count, and symmetry.

        Actions:
        - search_templates: find templates matching query criteria
        - tag_template: add searchable tags to a template
        """
        action = params.action.lower().strip()

        # ── search_templates ──────────────────────────────────────────
        if action == "search_templates":
            try:
                query = json.loads(params.query)
            except (json.JSONDecodeError, TypeError) as exc:
                return json.dumps({"error": f"Invalid query JSON: {exc}"})

            try:
                templates = json.loads(params.templates)
            except (json.JSONDecodeError, TypeError) as exc:
                return json.dumps({"error": f"Invalid templates JSON: {exc}"})

            if not isinstance(templates, list):
                return json.dumps({"error": "templates must be a JSON array"})

            results = search_templates(query, templates)
            return json.dumps({
                "action": "search_templates",
                "query": query,
                "matches": len(results),
                "results": results,
            }, indent=2)

        # ── tag_template ──────────────────────────────────────────────
        elif action == "tag_template":
            try:
                template = json.loads(params.template)
            except (json.JSONDecodeError, TypeError) as exc:
                return json.dumps({"error": f"Invalid template JSON: {exc}"})

            try:
                tags = json.loads(params.tags)
            except (json.JSONDecodeError, TypeError) as exc:
                return json.dumps({"error": f"Invalid tags JSON: {exc}"})

            if not isinstance(tags, list):
                return json.dumps({"error": "tags must be a JSON array"})

            result = tag_template(template, tags)
            return json.dumps({
                "action": "tag_template",
                "tags_added": tags,
                "template": result,
            }, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["search_templates", "tag_template"],
            })
