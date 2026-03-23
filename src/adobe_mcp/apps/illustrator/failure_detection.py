"""Failure detection for analysis results.

Detects common errors in hierarchy and connection analysis:
- Orphaned parts (no parent, not root)
- Circular references (A->B->A)
- Child larger than parent
- Too many children (>10)
- Duplicate connections
- Self-connections

Returns structured issue reports with severity levels.
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


class AiFailureDetectionInput(BaseModel):
    """Detect analysis errors in hierarchy and connections."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ...,
        description="Action: check_hierarchy, check_connections",
    )
    hierarchy: Optional[dict] = Field(
        default=None,
        description="Hierarchy dict: {part_name: {parent: str|null, area: float, children: [str]}}",
    )
    connections: Optional[list[dict]] = Field(
        default=None,
        description="List of connection dicts with 'from' and 'to' keys",
    )


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def check_hierarchy(hierarchy: dict) -> dict:
    """Detect issues in a part hierarchy.

    Checks for:
    - Orphaned parts: no parent and not the root
    - Circular references: A->B->C->A
    - Child larger than parent: unusual, flagged for review
    - Too many children: >10 children suggests over-segmentation

    Args:
        hierarchy: dict mapping part names to {parent, area, children}

    Returns:
        {"issues": [{"type": str, "part": str, "severity": str, "message": str}]}
    """
    issues = []

    if not hierarchy:
        return {"issues": []}

    # Find the root(s) — parts with no parent
    roots = []
    for part_name, info in hierarchy.items():
        parent = info.get("parent")
        if parent is None or parent == "":
            roots.append(part_name)

    # Check for orphans: parts whose parent doesn't exist in hierarchy
    for part_name, info in hierarchy.items():
        parent = info.get("parent")
        if parent and parent not in hierarchy:
            issues.append({
                "type": "orphan",
                "part": part_name,
                "severity": "warning",
                "message": f"Part '{part_name}' references parent '{parent}' which doesn't exist",
            })

    # Check for circular references by following parent chains
    for part_name in hierarchy:
        visited = set()
        current = part_name
        while current and current in hierarchy:
            if current in visited:
                issues.append({
                    "type": "circular_reference",
                    "part": part_name,
                    "severity": "error",
                    "message": f"Circular reference detected: chain from '{part_name}' loops back to '{current}'",
                })
                break
            visited.add(current)
            current = hierarchy[current].get("parent")

    # Check for child larger than parent
    for part_name, info in hierarchy.items():
        parent_name = info.get("parent")
        if parent_name and parent_name in hierarchy:
            child_area = info.get("area", 0)
            parent_area = hierarchy[parent_name].get("area", 0)
            if child_area > 0 and parent_area > 0 and child_area > parent_area:
                issues.append({
                    "type": "child_larger_than_parent",
                    "part": part_name,
                    "severity": "info",
                    "message": (
                        f"Part '{part_name}' (area={child_area}) is larger than "
                        f"parent '{parent_name}' (area={parent_area})"
                    ),
                })

    # Check for too many children
    for part_name, info in hierarchy.items():
        children = info.get("children", [])
        if len(children) > 10:
            issues.append({
                "type": "too_many_children",
                "part": part_name,
                "severity": "warning",
                "message": (
                    f"Part '{part_name}' has {len(children)} children — "
                    "possibly over-segmented"
                ),
            })

    return {"issues": issues}


def check_connections(connections: list[dict]) -> dict:
    """Detect issues in connection data.

    Checks for:
    - Duplicate connections (A<->B listed more than once)
    - Self-connections (A<->A)

    Args:
        connections: list of dicts with 'from' and 'to' keys

    Returns:
        {"issues": [{"type": str, "connection": dict, "severity": str, "message": str}]}
    """
    issues = []

    if not connections:
        return {"issues": []}

    # Track seen connections (normalize order for undirected comparison)
    seen_pairs = set()

    for conn in connections:
        from_part = conn.get("from", "")
        to_part = conn.get("to", "")

        # Self-connection check
        if from_part == to_part:
            issues.append({
                "type": "self_connection",
                "connection": conn,
                "severity": "error",
                "message": f"Self-connection detected: '{from_part}' connects to itself",
            })
            continue

        # Duplicate check (normalize pair order)
        pair = tuple(sorted([from_part, to_part]))
        if pair in seen_pairs:
            issues.append({
                "type": "duplicate_connection",
                "connection": conn,
                "severity": "warning",
                "message": f"Duplicate connection between '{from_part}' and '{to_part}'",
            })
        else:
            seen_pairs.add(pair)

    return {"issues": issues}


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_failure_detection tool."""

    @mcp.tool(
        name="adobe_ai_failure_detection",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_failure_detection(params: AiFailureDetectionInput) -> str:
        """Detect analysis errors in hierarchy and connections.

        Actions:
        - check_hierarchy: detect orphans, cycles, size anomalies
        - check_connections: detect duplicates and self-connections
        """
        action = params.action.lower().strip()

        if action == "check_hierarchy":
            if params.hierarchy is None:
                return json.dumps({
                    "error": "check_hierarchy requires hierarchy"
                })
            result = check_hierarchy(params.hierarchy)
            return json.dumps({
                "action": "check_hierarchy",
                **result,
                "issue_count": len(result["issues"]),
            })

        elif action == "check_connections":
            if params.connections is None:
                return json.dumps({
                    "error": "check_connections requires connections"
                })
            result = check_connections(params.connections)
            return json.dumps({
                "action": "check_connections",
                **result,
                "issue_count": len(result["issues"]),
            })

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["check_hierarchy", "check_connections"],
            })
