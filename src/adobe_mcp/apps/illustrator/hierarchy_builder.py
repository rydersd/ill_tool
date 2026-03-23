"""Build a tree hierarchy from parts and connections.

Takes segmented parts and their detected connections, then builds a
parent-child hierarchy tree. The largest part becomes root (unless
specified), joints determine parent-child edges, and containment
means the container is the parent. Unconnected parts are attached
to their nearest connected neighbor.

Pure Python implementation.
"""

import json
import math
from collections import deque
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiHierarchyBuilderInput(BaseModel):
    """Build a tree hierarchy from parts and connections."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        default="build", description="Action: build"
    )
    parts: list[dict] = Field(
        ..., description="List of part dicts from segmenter"
    )
    connections: list[dict] = Field(
        ..., description="List of connection dicts from connection_detector"
    )
    root_name: Optional[str] = Field(
        default=None, description="Force a specific part as root (default: largest)"
    )


# ---------------------------------------------------------------------------
# Internal tree node
# ---------------------------------------------------------------------------


class _TreeNode:
    """Internal node for hierarchy building."""
    __slots__ = ("name", "parent", "children", "pivot_position", "area")

    def __init__(self, name: str, area: int = 0):
        self.name = name
        self.parent: Optional["_TreeNode"] = None
        self.children: list["_TreeNode"] = []
        self.pivot_position: Optional[list[float]] = None
        self.area = area


# ---------------------------------------------------------------------------
# Pure Python helpers
# ---------------------------------------------------------------------------


def build_hierarchy(
    parts: list[dict],
    connections: list[dict],
    root_name: Optional[str] = None,
) -> dict:
    """Build a tree from parts and connections.

    Algorithm:
    1. If no root specified, use the largest part by area.
    2. BFS from root through "joint" connections to assign parent-child.
    3. "containment" connections make the container the parent.
    4. Unconnected parts become children of their nearest connected part.

    Args:
        parts: list of part dicts with name, area, centroid
        connections: list of connection dicts with part_a, part_b, type, position

    Returns:
        Dict with root name and flat node list.
    """
    if not parts:
        return {"root": None, "nodes": []}

    # Create nodes
    nodes = {}
    for part in parts:
        name = part["name"]
        nodes[name] = _TreeNode(name, area=part.get("area", 0))

    # Determine root
    if root_name and root_name in nodes:
        root = nodes[root_name]
    else:
        # Largest part by area
        root = max(nodes.values(), key=lambda n: n.area)

    # Build adjacency from connections
    adjacency = {}  # name -> [(neighbor_name, connection)]
    for conn in connections:
        a = conn.get("part_a", "")
        b = conn.get("part_b", "")
        if a not in nodes or b not in nodes:
            continue
        adjacency.setdefault(a, []).append((b, conn))
        adjacency.setdefault(b, []).append((a, conn))

    # Process containment first: container is always parent
    assigned = {root.name}
    for conn in connections:
        if conn.get("type") != "containment":
            continue
        a = conn.get("part_a", "")
        b = conn.get("part_b", "")
        if a not in nodes or b not in nodes:
            continue
        # Larger part is container (parent)
        if nodes[a].area >= nodes[b].area:
            parent_node, child_node = nodes[a], nodes[b]
        else:
            parent_node, child_node = nodes[b], nodes[a]

        if child_node.parent is None and child_node.name != root.name:
            child_node.parent = parent_node
            parent_node.children.append(child_node)
            child_node.pivot_position = conn.get("position")
            assigned.add(child_node.name)

    # BFS from root through joint/adjacent connections
    queue = deque([root.name])
    while queue:
        current_name = queue.popleft()
        for neighbor_name, conn in adjacency.get(current_name, []):
            if neighbor_name in assigned:
                continue
            conn_type = conn.get("type", "")
            if conn_type in ("joint", "adjacent"):
                child_node = nodes[neighbor_name]
                parent_node = nodes[current_name]
                child_node.parent = parent_node
                parent_node.children.append(child_node)
                child_node.pivot_position = conn.get("position")
                assigned.add(neighbor_name)
                queue.append(neighbor_name)

    # Attach unconnected parts to their nearest connected part
    unconnected = [name for name in nodes if name not in assigned]
    if unconnected and assigned:
        # Build centroid lookup
        centroid_map = {}
        for part in parts:
            centroid_map[part["name"]] = part.get("centroid", [0, 0])

        for orphan_name in unconnected:
            orphan_centroid = centroid_map.get(orphan_name, [0, 0])
            best_dist = float("inf")
            best_parent = root.name

            for assigned_name in assigned:
                ac = centroid_map.get(assigned_name, [0, 0])
                dist = math.sqrt(
                    (ac[0] - orphan_centroid[0]) ** 2 +
                    (ac[1] - orphan_centroid[1]) ** 2
                )
                if dist < best_dist:
                    best_dist = dist
                    best_parent = assigned_name

            orphan_node = nodes[orphan_name]
            parent_node = nodes[best_parent]
            orphan_node.parent = parent_node
            parent_node.children.append(orphan_node)
            assigned.add(orphan_name)

    return _serialize_hierarchy(root, nodes)


def _serialize_hierarchy(root: _TreeNode, nodes: dict) -> dict:
    """Convert internal tree to serializable dict."""
    flat_nodes = []

    def walk(node: _TreeNode):
        flat_nodes.append({
            "name": node.name,
            "parent": node.parent.name if node.parent else None,
            "children": [c.name for c in node.children],
            "pivot_position": node.pivot_position,
        })
        for child in node.children:
            walk(child)

    walk(root)
    return {
        "root": root.name,
        "nodes": flat_nodes,
    }


def hierarchy_to_dict(hierarchy: dict) -> dict:
    """Convert flat hierarchy to nested dict for serialization.

    Returns: {"name": root, "children": [{"name": ..., "children": [...]}]}
    """
    nodes_by_name = {}
    for node in hierarchy.get("nodes", []):
        nodes_by_name[node["name"]] = {
            "name": node["name"],
            "pivot_position": node.get("pivot_position"),
            "children": [],
        }

    # Wire up children
    for node in hierarchy.get("nodes", []):
        for child_name in node.get("children", []):
            if child_name in nodes_by_name:
                nodes_by_name[node["name"]]["children"].append(
                    nodes_by_name[child_name]
                )

    root_name = hierarchy.get("root")
    if root_name and root_name in nodes_by_name:
        return nodes_by_name[root_name]
    return {"name": None, "children": []}


def hierarchy_to_flat(hierarchy: dict) -> list[dict]:
    """Convert hierarchy to flat list with parent references.

    Returns: [{"name": ..., "parent": ..., "pivot_position": ...}]
    """
    return [
        {
            "name": node["name"],
            "parent": node.get("parent"),
            "pivot_position": node.get("pivot_position"),
        }
        for node in hierarchy.get("nodes", [])
    ]


# ---------------------------------------------------------------------------
# MCP Registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_hierarchy_builder tool."""

    @mcp.tool(
        name="adobe_ai_hierarchy_builder",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_hierarchy_builder(params: AiHierarchyBuilderInput) -> str:
        """Build a parent-child tree hierarchy from parts and connections.

        Uses the largest part as root (or a specified root), then BFS
        through connections to assign parents. Containment connections
        make the container the parent. Orphan parts attach to nearest.
        """
        hierarchy = build_hierarchy(
            params.parts,
            params.connections,
            params.root_name,
        )
        nested = hierarchy_to_dict(hierarchy)
        flat = hierarchy_to_flat(hierarchy)

        return json.dumps({
            "action": "build",
            "hierarchy": hierarchy,
            "nested": nested,
            "flat": flat,
        }, indent=2)
