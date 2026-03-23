"""Auto-detect IK chains from joint hierarchy.

Walks the hierarchy tree finding all root-to-leaf paths with 2+ joints,
labels them, and optionally matches against a character template for
semantic naming (e.g. "left_arm", "right_leg").

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


class AiIKChainAutoInput(BaseModel):
    """Auto-detect IK chains from joint hierarchy."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ..., description="Action: detect_chains | label_chains"
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    hierarchy: Optional[dict] = Field(
        default=None,
        description="Joint hierarchy dict: {joint: {children: [...]}}. "
                    "If None, loaded from rig.",
    )
    template: Optional[dict] = Field(
        default=None,
        description="Optional template for semantic labelling. "
                    "Maps label to expected joint count or structure.",
    )


# ---------------------------------------------------------------------------
# Hierarchy helpers
# ---------------------------------------------------------------------------


def _build_adjacency(hierarchy: dict) -> dict[str, list[str]]:
    """Build parent->children adjacency from hierarchy dict.

    Supports two formats:
      1) {joint: {"children": [child_names]}}  — nested dict
      2) {joint: [child_names]}                — flat list
    """
    adj: dict[str, list[str]] = {}
    for joint, value in hierarchy.items():
        if isinstance(value, dict):
            children = value.get("children", [])
        elif isinstance(value, list):
            children = value
        else:
            children = []
        adj[joint] = list(children)
    return adj


def _find_roots(adj: dict[str, list[str]]) -> list[str]:
    """Find root joints — those that are never listed as a child."""
    all_children: set[str] = set()
    for children in adj.values():
        all_children.update(children)
    roots = [j for j in adj if j not in all_children]
    return roots if roots else list(adj.keys())[:1]


def _find_all_paths(
    adj: dict[str, list[str]],
    start: str,
    visited: Optional[set[str]] = None,
) -> list[list[str]]:
    """DFS to find all root-to-leaf paths from *start*.

    Tracks visited nodes to avoid infinite loops in cyclic graphs.
    """
    if visited is None:
        visited = set()

    # Cycle detection: if we've visited this node, stop recursion
    if start in visited:
        return []

    visited = visited | {start}
    children = adj.get(start, [])
    # Filter children that would create a cycle
    valid_children = [c for c in children if c not in visited]

    if not valid_children:
        # Leaf node — path is just this joint
        return [[start]]

    paths: list[list[str]] = []
    for child in valid_children:
        sub_paths = _find_all_paths(adj, child, visited)
        for sp in sub_paths:
            paths.append([start] + sp)
    return paths


def _has_cycle(adj: dict[str, list[str]]) -> bool:
    """Detect cycles using DFS coloring (WHITE/GRAY/BLACK)."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in adj}

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for child in adj.get(node, []):
            if child not in color:
                continue
            if color[child] == GRAY:
                return True  # back-edge → cycle
            if color[child] == WHITE and dfs(child):
                return True
        color[node] = BLACK
        return False

    for node in adj:
        if color[node] == WHITE:
            if dfs(node):
                return True
    return False


# ---------------------------------------------------------------------------
# Core detection
# ---------------------------------------------------------------------------


def detect_ik_chains(hierarchy: dict) -> dict:
    """Find all root-to-leaf paths with 2+ joints — each is an IK chain candidate.

    Args:
        hierarchy: joint hierarchy dict

    Returns:
        {"chains": [...], "has_cycle": bool, "total_joints": int}
    """
    adj = _build_adjacency(hierarchy)
    has_cycle = _has_cycle(adj)
    roots = _find_roots(adj)

    all_chains: list[dict] = []
    seen_paths: set[tuple[str, ...]] = set()

    for root in roots:
        paths = _find_all_paths(adj, root)
        for path in paths:
            # Only keep paths with 2+ joints (minimum for an IK chain)
            if len(path) < 2:
                continue
            path_key = tuple(path)
            if path_key in seen_paths:
                continue
            seen_paths.add(path_key)

            # Classify chain topology
            chain_type = "linear"
            if len(path) == 2:
                chain_type = "single_bone"
            elif len(path) >= 4:
                chain_type = "multi_bone"

            all_chains.append({
                "joints": path,
                "type": chain_type,
                "label": f"chain_{len(all_chains)}",
                "length": len(path),
            })

    return {
        "chains": all_chains,
        "has_cycle": has_cycle,
        "total_joints": len(adj),
    }


def label_chains(chains: list[dict], template: Optional[dict] = None) -> list[dict]:
    """Auto-name chains, optionally matching against a template.

    If template is provided, attempts to match chains by length/position:
        template = {"left_arm": 3, "right_arm": 3, "spine": 4}
    Each value is the expected joint count for that label.

    Args:
        chains: list of chain dicts from detect_ik_chains
        template: optional mapping of label -> expected joint count

    Returns:
        Updated chain list with semantic labels where matched.
    """
    labelled = [dict(c) for c in chains]  # shallow copies

    if template is None:
        # Just use positional naming
        for i, chain in enumerate(labelled):
            chain["label"] = f"chain_{i}"
        return labelled

    # Group chains by length for template matching
    length_buckets: dict[int, list[int]] = {}
    for idx, chain in enumerate(labelled):
        length_buckets.setdefault(chain["length"], []).append(idx)

    # Match template entries by length, consuming chains greedily
    used_indices: set[int] = set()
    for label, expected_length in template.items():
        candidates = length_buckets.get(expected_length, [])
        for idx in candidates:
            if idx not in used_indices:
                labelled[idx]["label"] = label
                used_indices.add(idx)
                break

    # Any unmatched chains keep their positional names
    unnamed_counter = 0
    for idx, chain in enumerate(labelled):
        if idx not in used_indices:
            chain["label"] = f"chain_{unnamed_counter}"
            unnamed_counter += 1

    return labelled


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_ik_chain_auto tool."""

    @mcp.tool(
        name="adobe_ai_ik_chain_auto",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_ik_chain_auto(params: AiIKChainAutoInput) -> str:
        """Auto-detect IK chains from joint hierarchy.

        Actions:
        - detect_chains: find all root-to-leaf paths with 2+ joints
        - label_chains: auto-name detected chains, optionally matching a template
        """
        action = params.action.lower().strip()

        # Resolve hierarchy
        hierarchy = params.hierarchy
        if hierarchy is None:
            rig = _load_rig(params.character_name)
            # Build hierarchy from rig joints + bones
            joints = rig.get("joints", {})
            bones = rig.get("bones", [])
            hierarchy = {}
            for j_name in joints:
                hierarchy[j_name] = {"children": []}
            for bone in bones:
                parent = bone.get("parent_joint")
                child = bone.get("child_joint")
                if parent and child and parent in hierarchy:
                    hierarchy[parent]["children"].append(child)

        if not hierarchy:
            return json.dumps({"error": "No hierarchy provided or found in rig"})

        # ── detect_chains ────────────────────────────────────────────
        if action == "detect_chains":
            result = detect_ik_chains(hierarchy)

            # Store detected chains in rig
            rig = _load_rig(params.character_name)
            rig["ik_chains"] = result["chains"]
            _save_rig(params.character_name, rig)

            return json.dumps({
                "action": "detect_chains",
                **result,
            }, indent=2)

        # ── label_chains ─────────────────────────────────────────────
        elif action == "label_chains":
            detection = detect_ik_chains(hierarchy)
            labelled = label_chains(detection["chains"], params.template)

            rig = _load_rig(params.character_name)
            rig["ik_chains"] = labelled
            _save_rig(params.character_name, rig)

            return json.dumps({
                "action": "label_chains",
                "chains": labelled,
                "template_used": params.template is not None,
            }, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["detect_chains", "label_chains"],
            })
