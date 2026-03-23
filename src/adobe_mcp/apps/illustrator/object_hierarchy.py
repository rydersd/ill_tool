"""Object hierarchy management for character rigs.

Extends rig landmarks with pivot fields (rotation ranges, parent/child
relationships). Provides tools to set pivots manually, auto-infer pivots
from bone data, build a tree representation of the hierarchy, and validate
the hierarchy for common problems (orphans, cycles, oversized children).

No hardcoded joint names -- all operations work with whatever bones and
landmarks the rig contains.
"""

import json
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from adobe_mcp.apps.illustrator.rig_data import _load_rig, _save_rig


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiObjectHierarchyInput(BaseModel):
    """Manage object hierarchy and pivot relationships in a character rig."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ..., description="Action: set_pivot, auto_pivots, get_tree, validate"
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    # -- set_pivot fields --
    landmark_name: Optional[str] = Field(
        default=None, description="Landmark to set pivot on"
    )
    pivot_type: Optional[str] = Field(
        default=None, description="Pivot type: hinge, ball, fixed, slide"
    )
    connects: Optional[str] = Field(
        default=None, description="What this pivot connects (e.g. 'upper_arm to forearm')"
    )
    rotation_range: Optional[list[float]] = Field(
        default=None, description="[min_degrees, max_degrees] rotation range"
    )
    parent_part: Optional[str] = Field(
        default=None, description="Parent part name"
    )
    child_parts: Optional[list[str]] = Field(
        default=None, description="Child part names"
    )
    relationship: Optional[str] = Field(
        default=None, description="Relationship type: rigid_hinge, ball_joint, flex, etc."
    )


# ---------------------------------------------------------------------------
# Pure Python helpers
# ---------------------------------------------------------------------------


def set_pivot(
    rig: dict,
    landmark_name: str,
    pivot_type: str,
    connects: str,
    rotation_range: list[float],
    parent_part: str,
    child_parts: list[str],
    relationship: str,
) -> dict:
    """Update a landmark with pivot data.

    Adds pivot fields to the landmark entry in the rig. If the landmark
    doesn't exist yet, it is created with the pivot data.

    Returns the updated landmark dict.
    """
    if "landmarks" not in rig:
        rig["landmarks"] = {}

    landmark = rig["landmarks"].get(landmark_name, {})
    landmark["pivot"] = {
        "type": pivot_type,
        "connects": connects,
        "rotation_range": rotation_range,
        "parent_part": parent_part,
        "child_parts": child_parts,
        "relationship": relationship,
    }
    rig["landmarks"][landmark_name] = landmark
    return landmark


def auto_pivots(rig: dict) -> list[dict]:
    """Scan rig bones and bindings to auto-infer pivot data for each bone endpoint.

    For each bone, the child_joint end becomes a pivot point. The parent bone
    (if any) is determined by finding another bone whose child_joint matches
    this bone's parent_joint.

    Returns a list of inferred pivot entries that were added to the rig.
    """
    bones = rig.get("bones", [])
    bindings = rig.get("bindings", {})
    if "landmarks" not in rig:
        rig["landmarks"] = {}

    # Build lookup: joint_name -> list of bones that start/end there
    joint_to_parent_bones = {}  # bones whose child_joint is this joint
    joint_to_child_bones = {}   # bones whose parent_joint is this joint
    for bone in bones:
        pj = bone.get("parent_joint", "")
        cj = bone.get("child_joint", "")
        joint_to_child_bones.setdefault(pj, []).append(bone)
        joint_to_parent_bones.setdefault(cj, []).append(bone)

    inferred = []
    for bone in bones:
        child_joint = bone.get("child_joint", "")
        parent_joint = bone.get("parent_joint", "")

        # The child_joint of this bone is a pivot point
        pivot_name = child_joint
        if not pivot_name:
            continue

        # Determine parent part from the bone itself
        parent_part = bone.get("name", "")

        # Determine child parts: bones whose parent_joint == this child_joint
        child_bones = joint_to_child_bones.get(child_joint, [])
        child_parts = [b.get("name", "") for b in child_bones]

        # Determine pivot type based on structure
        # If multiple children branch out, it's a ball joint; otherwise hinge
        if len(child_parts) > 1:
            pivot_type = "ball"
            default_range = [-180.0, 180.0]
        else:
            pivot_type = "hinge"
            default_range = [-90.0, 90.0]

        # Check if binding info gives us more context
        bound_parts = []
        for part_name, binding in bindings.items():
            bound_joints = binding if isinstance(binding, list) else [binding]
            for bj in bound_joints:
                joint_ref = bj.get("joint", bj) if isinstance(bj, dict) else bj
                if joint_ref == child_joint:
                    bound_parts.append(part_name)

        connects = f"{parent_part} to {', '.join(child_parts)}" if child_parts else parent_part

        pivot_data = {
            "type": pivot_type,
            "connects": connects,
            "rotation_range": default_range,
            "parent_part": parent_part,
            "child_parts": child_parts,
            "relationship": "ball_joint" if pivot_type == "ball" else "rigid_hinge",
        }

        landmark = rig["landmarks"].get(pivot_name, {})
        landmark["pivot"] = pivot_data

        # Copy joint position to landmark if available
        joints = rig.get("joints", {})
        if child_joint in joints:
            landmark["x"] = joints[child_joint].get("x", 0)
            landmark["y"] = joints[child_joint].get("y", 0)

        rig["landmarks"][pivot_name] = landmark
        inferred.append({"name": pivot_name, **pivot_data})

    return inferred


def get_pivot_tree(rig: dict) -> dict:
    """Return the hierarchy as a nested tree dict.

    Format: {root: {name, pivot, children: [{name, pivot, children: [...]}]}}

    Builds the tree from landmark pivot parent/child relationships.
    The root is the landmark with no parent, or the first one found
    if multiple roots exist.
    """
    landmarks = rig.get("landmarks", {})

    # Build adjacency from pivot parent/child relationships
    all_names = set(landmarks.keys())
    children_of = {}  # parent -> [child_names]
    has_parent = set()

    for name, lm in landmarks.items():
        pivot = lm.get("pivot")
        if not pivot:
            continue
        child_parts = pivot.get("child_parts", [])
        for child in child_parts:
            if child in all_names or child in [
                lm2.get("pivot", {}).get("parent_part") for lm2 in landmarks.values()
            ]:
                children_of.setdefault(name, []).append(child)
                has_parent.add(child)

    # Find roots (no parent)
    roots = [n for n in all_names if n not in has_parent and landmarks[n].get("pivot")]
    if not roots:
        # If no clear root, use all landmarks with pivots
        roots = [n for n in all_names if landmarks[n].get("pivot")]

    def build_node(name: str, visited: set) -> dict:
        if name in visited:
            return {"name": name, "pivot": None, "children": [], "cycle": True}
        visited = visited | {name}
        lm = landmarks.get(name, {})
        pivot_data = lm.get("pivot")
        child_names = children_of.get(name, [])
        return {
            "name": name,
            "pivot": pivot_data,
            "children": [build_node(c, visited) for c in child_names],
        }

    if len(roots) == 1:
        return build_node(roots[0], set())
    elif roots:
        return {
            "name": "__multi_root__",
            "pivot": None,
            "children": [build_node(r, set()) for r in roots],
        }
    else:
        return {"name": "__empty__", "pivot": None, "children": []}


def validate_hierarchy(rig: dict) -> dict:
    """Validate the hierarchy for common problems.

    Checks for:
    - Orphans: landmarks with pivots that reference non-existent parts
    - Cycles: circular parent/child references
    - Oversized children: child parts larger than their parents (using bounds if available)

    Returns: {"valid": bool, "issues": [{"type": str, "detail": str}]}
    """
    landmarks = rig.get("landmarks", {})
    issues = []

    all_landmark_names = set(landmarks.keys())
    all_bone_names = {b.get("name", "") for b in rig.get("bones", [])}
    all_known_names = all_landmark_names | all_bone_names

    # Check orphans: child_parts or parent_part referencing unknown names
    for name, lm in landmarks.items():
        pivot = lm.get("pivot")
        if not pivot:
            continue

        parent_part = pivot.get("parent_part", "")
        if parent_part and parent_part not in all_known_names:
            issues.append({
                "type": "orphan",
                "detail": f"Landmark '{name}' references unknown parent_part '{parent_part}'",
            })

        for child in pivot.get("child_parts", []):
            if child and child not in all_known_names:
                issues.append({
                    "type": "orphan",
                    "detail": f"Landmark '{name}' references unknown child_part '{child}'",
                })

    # Check cycles using DFS
    children_of = {}
    for name, lm in landmarks.items():
        pivot = lm.get("pivot")
        if not pivot:
            continue
        children_of[name] = pivot.get("child_parts", [])

    def has_cycle(start: str) -> bool:
        visited = set()
        stack = [start]
        while stack:
            current = stack.pop()
            if current in visited:
                return True
            visited.add(current)
            for child in children_of.get(current, []):
                if child in visited:
                    return True
                stack.append(child)
        return False

    checked_for_cycles = set()
    for name in landmarks:
        if name not in checked_for_cycles:
            if has_cycle(name):
                issues.append({
                    "type": "cycle",
                    "detail": f"Cycle detected involving landmark '{name}'",
                })
            checked_for_cycles.add(name)

    # Check oversized children (compare areas/bounds if available)
    for name, lm in landmarks.items():
        pivot = lm.get("pivot")
        if not pivot:
            continue
        parent_bounds = lm.get("bounds")
        if not parent_bounds:
            continue
        parent_area = parent_bounds.get("area", 0)
        for child_name in pivot.get("child_parts", []):
            child_lm = landmarks.get(child_name, {})
            child_bounds = child_lm.get("bounds")
            if child_bounds:
                child_area = child_bounds.get("area", 0)
                if child_area > parent_area > 0:
                    issues.append({
                        "type": "oversized_child",
                        "detail": f"Child '{child_name}' (area={child_area}) is larger "
                                  f"than parent '{name}' (area={parent_area})",
                    })

    return {
        "valid": len(issues) == 0,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# MCP Registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_object_hierarchy tool."""

    @mcp.tool(
        name="adobe_ai_object_hierarchy",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_object_hierarchy(params: AiObjectHierarchyInput) -> str:
        """Manage object hierarchy and pivot relationships in a character rig.

        Actions:
        - set_pivot: Set pivot data on a specific landmark
        - auto_pivots: Auto-infer pivots from bone/binding data
        - get_tree: Return the hierarchy as a nested tree
        - validate: Check for orphans, cycles, and oversized children
        """
        rig = _load_rig(params.character_name)
        action = params.action.lower().strip()

        if action == "set_pivot":
            if not params.landmark_name:
                return json.dumps({"error": "landmark_name is required for set_pivot"})
            landmark = set_pivot(
                rig,
                params.landmark_name,
                params.pivot_type or "hinge",
                params.connects or "",
                params.rotation_range or [-90.0, 90.0],
                params.parent_part or "",
                params.child_parts or [],
                params.relationship or "rigid_hinge",
            )
            _save_rig(params.character_name, rig)
            return json.dumps({
                "action": "set_pivot",
                "landmark": params.landmark_name,
                "pivot": landmark.get("pivot"),
            }, indent=2)

        elif action == "auto_pivots":
            inferred = auto_pivots(rig)
            _save_rig(params.character_name, rig)
            return json.dumps({
                "action": "auto_pivots",
                "inferred_count": len(inferred),
                "pivots": inferred,
            }, indent=2)

        elif action == "get_tree":
            tree = get_pivot_tree(rig)
            return json.dumps({
                "action": "get_tree",
                "tree": tree,
            }, indent=2)

        elif action == "validate":
            result = validate_hierarchy(rig)
            return json.dumps({
                "action": "validate",
                **result,
            }, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["set_pivot", "auto_pivots", "get_tree", "validate"],
            })
