"""Generate motion paths from pose sequences.

Computes arc paths for each joint from a start pose to an end pose,
resolving child joint positions relative to their parent's motion.
Smooths the resulting paths into bezier curves for AE motion paths.

Pure Python — no JSX or Adobe required.
"""

import json
import math
from typing import Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from adobe_mcp.apps.illustrator.rig_data import _load_rig, _save_rig


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiMotionPathFromHierarchyInput(BaseModel):
    """Generate motion paths from pose sequences."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ..., description="Action: compute_paths | generate_curves"
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    start_pose: Optional[dict] = Field(
        default=None,
        description="Start pose: {joint_name: {x, y, rotation}}",
    )
    end_pose: Optional[dict] = Field(
        default=None,
        description="End pose: {joint_name: {x, y, rotation}}",
    )
    frames: int = Field(
        default=12,
        description="Number of frames in the motion path",
        ge=2, le=120,
    )
    hierarchy: Optional[dict] = Field(
        default=None,
        description="Joint hierarchy: {joint: {children: [...], parent: str}}",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation from a to b at parameter t."""
    return a + (b - a) * t


def _rotate_point(px: float, py: float, cx: float, cy: float, angle_rad: float) -> tuple[float, float]:
    """Rotate point (px,py) around center (cx,cy) by angle_rad."""
    dx = px - cx
    dy = py - cy
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    nx = cx + dx * cos_a - dy * sin_a
    ny = cy + dx * sin_a + dy * cos_a
    return (nx, ny)


def _build_parent_map(hierarchy: dict) -> dict[str, Optional[str]]:
    """Build child -> parent mapping from hierarchy."""
    parent_map: dict[str, Optional[str]] = {}
    for joint, value in hierarchy.items():
        if joint not in parent_map:
            parent_map[joint] = None  # root by default
        if isinstance(value, dict):
            children = value.get("children", [])
            explicit_parent = value.get("parent")
            if explicit_parent:
                parent_map[joint] = explicit_parent
        elif isinstance(value, list):
            children = value
        else:
            children = []
        for child in children:
            parent_map[child] = joint
    return parent_map


def _find_roots(parent_map: dict[str, Optional[str]]) -> list[str]:
    """Find joints with no parent (roots)."""
    return [j for j, p in parent_map.items() if p is None]


# ---------------------------------------------------------------------------
# Core motion path computation
# ---------------------------------------------------------------------------


def compute_joint_paths(
    hierarchy: dict,
    start_pose: dict,
    end_pose: dict,
    frames: int = 12,
) -> dict:
    """Compute arc paths from start to end pose for each joint.

    For root joints: interpolate position directly (straight line or
    slight arc based on rotation).
    For child joints: position is derived from parent motion + local
    rotation change.

    Args:
        hierarchy: joint hierarchy
        start_pose: {joint: {x, y, rotation}} start positions
        end_pose: {joint: {x, y, rotation}} end positions
        frames: number of frames

    Returns:
        {"joint_paths": {joint: [(frame, x, y), ...]}}
    """
    parent_map = _build_parent_map(hierarchy)
    roots = _find_roots(parent_map)

    # All joints we need to compute paths for
    all_joints = set(start_pose.keys()) & set(end_pose.keys())
    joint_paths: dict[str, list[tuple[int, float, float]]] = {}

    # Process in BFS order from roots so parents are computed before children
    processed: set[str] = set()
    queue: list[str] = [j for j in roots if j in all_joints]
    # Also add joints whose parents aren't in our set (treat as roots)
    for j in all_joints:
        parent = parent_map.get(j)
        if parent is None or parent not in all_joints:
            if j not in queue:
                queue.append(j)

    while queue:
        joint = queue.pop(0)
        if joint in processed:
            continue
        processed.add(joint)

        start = start_pose[joint]
        end = end_pose[joint]

        sx, sy = start.get("x", 0.0), start.get("y", 0.0)
        ex, ey = end.get("x", 0.0), end.get("y", 0.0)
        s_rot = math.radians(start.get("rotation", 0.0))
        e_rot = math.radians(end.get("rotation", 0.0))

        parent = parent_map.get(joint)

        if parent is None or parent not in all_joints:
            # Root joint: interpolate directly
            path: list[tuple[int, float, float]] = []
            for f in range(frames):
                t = f / max(frames - 1, 1)
                x = round(_lerp(sx, ex, t), 4)
                y = round(_lerp(sy, ey, t), 4)
                path.append((f, x, y))
            joint_paths[joint] = path
        else:
            # Child joint: position relative to parent
            parent_start = start_pose[parent]
            psx, psy = parent_start.get("x", 0.0), parent_start.get("y", 0.0)

            # Local offset from parent at start
            local_x = sx - psx
            local_y = sy - psy
            local_dist = math.sqrt(local_x ** 2 + local_y ** 2)
            local_angle = math.atan2(local_y, local_x) if local_dist > 0.001 else 0.0

            path = []
            parent_path = joint_paths.get(parent, [])

            for f in range(frames):
                t = f / max(frames - 1, 1)

                # Parent position at this frame
                if parent_path and f < len(parent_path):
                    _, ppx, ppy = parent_path[f]
                else:
                    ppx = _lerp(psx, end_pose[parent].get("x", 0.0), t)
                    ppy = _lerp(psy, end_pose[parent].get("y", 0.0), t)

                # Interpolate parent rotation
                ps_rot = math.radians(start_pose[parent].get("rotation", 0.0))
                pe_rot = math.radians(end_pose[parent].get("rotation", 0.0))
                parent_rot = _lerp(ps_rot, pe_rot, t)

                # Apply parent rotation to local offset
                rot_delta = parent_rot - math.radians(start_pose[parent].get("rotation", 0.0))
                current_angle = local_angle + rot_delta

                # Also interpolate this joint's own rotation influence on position
                own_rot = _lerp(s_rot, e_rot, t)

                # Compute child position from parent + rotated local offset
                x = round(ppx + local_dist * math.cos(current_angle), 4)
                y = round(ppy + local_dist * math.sin(current_angle), 4)

                path.append((f, x, y))

            joint_paths[joint] = path

        # Enqueue children
        for j in all_joints:
            if parent_map.get(j) == joint and j not in processed:
                queue.append(j)

    return {"joint_paths": joint_paths, "frame_count": frames}


def generate_path_curves(joint_paths: dict) -> dict:
    """Smooth joint paths into bezier curves for AE motion paths.

    Uses Catmull-Rom to bezier conversion: for each segment, the control
    points are derived from adjacent points.

    Args:
        joint_paths: {joint: [(frame, x, y), ...]} from compute_joint_paths

    Returns:
        {"curves": {joint: [{frame, x, y, in_tangent, out_tangent}, ...]}}
    """
    curves: dict[str, list[dict]] = {}

    for joint_name, path in joint_paths.items():
        if len(path) < 2:
            curves[joint_name] = [{
                "frame": p[0], "x": p[1], "y": p[2],
                "in_tangent": [0.0, 0.0],
                "out_tangent": [0.0, 0.0],
            } for p in path]
            continue

        points = [(p[1], p[2]) for p in path]
        frames = [p[0] for p in path]
        n = len(points)

        curve_points: list[dict] = []
        for i in range(n):
            x, y = points[i]

            # Catmull-Rom tangent estimation
            if i == 0:
                # First point: forward difference
                tx = (points[1][0] - points[0][0]) / 3.0
                ty = (points[1][1] - points[0][1]) / 3.0
            elif i == n - 1:
                # Last point: backward difference
                tx = (points[-1][0] - points[-2][0]) / 3.0
                ty = (points[-1][1] - points[-2][1]) / 3.0
            else:
                # Interior: central difference
                tx = (points[i + 1][0] - points[i - 1][0]) / 6.0
                ty = (points[i + 1][1] - points[i - 1][1]) / 6.0

            curve_points.append({
                "frame": frames[i],
                "x": round(x, 4),
                "y": round(y, 4),
                "in_tangent": [round(-tx, 4), round(-ty, 4)],
                "out_tangent": [round(tx, 4), round(ty, 4)],
            })

        curves[joint_name] = curve_points

    return {"curves": curves}


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_motion_path_from_hierarchy tool."""

    @mcp.tool(
        name="adobe_ai_motion_path_from_hierarchy",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_motion_path_from_hierarchy(
        params: AiMotionPathFromHierarchyInput,
    ) -> str:
        """Generate motion paths from pose sequences.

        Actions:
        - compute_paths: compute arc paths for each joint between two poses
        - generate_curves: smooth paths into bezier curves for AE
        """
        action = params.action.lower().strip()

        # ── compute_paths ────────────────────────────────────────────
        if action == "compute_paths":
            if not params.start_pose or not params.end_pose:
                return json.dumps({
                    "error": "compute_paths requires start_pose and end_pose"
                })

            hierarchy = params.hierarchy or {}
            # If no hierarchy, treat all joints as roots
            if not hierarchy:
                for j in params.start_pose:
                    hierarchy[j] = {"children": []}

            result = compute_joint_paths(
                hierarchy,
                params.start_pose,
                params.end_pose,
                params.frames,
            )

            # Store in rig
            rig = _load_rig(params.character_name)
            # Convert tuples to lists for JSON serialization
            serializable_paths = {}
            for j, path in result["joint_paths"].items():
                serializable_paths[j] = [[f, x, y] for f, x, y in path]
            rig["motion_paths"] = serializable_paths
            _save_rig(params.character_name, rig)

            return json.dumps({
                "action": "compute_paths",
                "joint_paths": serializable_paths,
                "frame_count": result["frame_count"],
            }, indent=2)

        # ── generate_curves ──────────────────────────────────────────
        elif action == "generate_curves":
            if not params.start_pose or not params.end_pose:
                return json.dumps({
                    "error": "generate_curves requires start_pose and end_pose"
                })

            hierarchy = params.hierarchy or {}
            if not hierarchy:
                for j in params.start_pose:
                    hierarchy[j] = {"children": []}

            paths_result = compute_joint_paths(
                hierarchy,
                params.start_pose,
                params.end_pose,
                params.frames,
            )
            curves = generate_path_curves(paths_result["joint_paths"])

            return json.dumps({
                "action": "generate_curves",
                **curves,
                "frame_count": params.frames,
            }, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["compute_paths", "generate_curves"],
            })
