"""Detect kinematic chains from hierarchy data.

Scans a part hierarchy to find root-to-leaf paths with 2+ joints,
classifies them as linear, branching, or loop, and auto-labels
them based on template names or sequential numbering.

Pure Python implementation.
"""

import json
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiChainDetectorInput(BaseModel):
    """Detect kinematic chains from a hierarchy."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        default="detect", description="Action: detect"
    )
    hierarchy: dict = Field(
        ..., description="Hierarchy dict from hierarchy_builder (with root and nodes)"
    )
    template_labels: Optional[dict] = Field(
        default=None,
        description="Optional template labels to match chains against: "
                    "{pattern: label} e.g. {'shoulder.*elbow.*wrist': 'arm'}"
    )
    min_joints: int = Field(
        default=2, description="Minimum joints to qualify as a chain", ge=2
    )


# ---------------------------------------------------------------------------
# Pure Python helpers
# ---------------------------------------------------------------------------


def _build_adjacency(hierarchy: dict) -> tuple[dict, str]:
    """Build adjacency list from hierarchy nodes.

    Returns: (children_of: {name: [child_names]}, root_name)
    """
    nodes = hierarchy.get("nodes", [])
    root = hierarchy.get("root")
    children_of = {}

    for node in nodes:
        name = node.get("name", "")
        children = node.get("children", [])
        children_of[name] = children

    return children_of, root


def detect_chains(hierarchy: dict, min_joints: int = 2) -> list[dict]:
    """Find all root-to-leaf paths with min_joints or more joints.

    A chain is a path from any node to a leaf (no children) that
    passes through at least min_joints nodes.

    Args:
        hierarchy: dict with "root" and "nodes" from hierarchy_builder
        min_joints: minimum joints to qualify as a chain

    Returns:
        List of chain dicts with joints list.
    """
    children_of, root = _build_adjacency(hierarchy)
    if not root:
        return []

    chains = []

    def dfs(node_name: str, path: list[str]):
        path = path + [node_name]
        children = children_of.get(node_name, [])

        if not children:
            # Leaf node - path is complete
            if len(path) >= min_joints:
                chains.append(list(path))
        else:
            for child in children:
                dfs(child, path)

    dfs(root, [])
    return [{"joints": chain} for chain in chains]


def classify_chain(chain: dict) -> str:
    """Classify a chain as linear, branching, or loop.

    A simple chain with sequential joints is "linear".
    If the same joint appears more than once, it's a "loop".
    Branching is determined at the hierarchy level, not per-chain
    (each chain is a single path), so single chains are always linear.

    Args:
        chain: dict with "joints" list

    Returns:
        "linear", "branching", or "loop"
    """
    joints = chain.get("joints", [])
    if not joints:
        return "linear"

    # Check for repeated joints (loops)
    if len(joints) != len(set(joints)):
        return "loop"

    # A single root-to-leaf path is always linear
    return "linear"


def label_chain(
    chain: dict,
    template: Optional[dict] = None,
    chain_index: int = 0,
) -> str:
    """Auto-name a chain.

    If a template is provided, try to match joint names against
    template patterns. Otherwise, use sequential numbering.

    Args:
        chain: dict with "joints" list
        template: optional {pattern_keyword: label} mapping
        chain_index: sequential index for auto-naming

    Returns:
        Label string for the chain.
    """
    joints = chain.get("joints", [])
    joints_str = "_".join(joints).lower()

    if template:
        for pattern, label in template.items():
            # Simple keyword matching: check if all keywords appear in joint names
            keywords = pattern.lower().split(".*")
            keywords = [k.strip() for k in keywords if k.strip()]
            if all(kw in joints_str for kw in keywords):
                return label

    return f"chain_{chain_index}"


def detect_and_classify(
    hierarchy: dict,
    template_labels: Optional[dict] = None,
    min_joints: int = 2,
) -> dict:
    """Full chain detection pipeline.

    Returns:
        {"chains": [{"joints": [...], "type": str, "label": str}]}
    """
    raw_chains = detect_chains(hierarchy, min_joints)
    result_chains = []

    for i, chain in enumerate(raw_chains):
        chain_type = classify_chain(chain)
        label = label_chain(chain, template_labels, i)
        result_chains.append({
            "joints": chain["joints"],
            "type": chain_type,
            "label": label,
        })

    return {"chains": result_chains}


# ---------------------------------------------------------------------------
# MCP Registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_chain_detector tool."""

    @mcp.tool(
        name="adobe_ai_chain_detector",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_chain_detector(params: AiChainDetectorInput) -> str:
        """Detect kinematic chains from a part hierarchy.

        Finds all root-to-leaf paths with 2+ joints, classifies them
        as linear/branching/loop, and auto-labels them.
        """
        result = detect_and_classify(
            params.hierarchy,
            params.template_labels,
            params.min_joints,
        )
        return json.dumps({
            "action": "detect",
            **result,
            "total_chains": len(result["chains"]),
        }, indent=2)
