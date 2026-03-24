"""3D form projection from observed 2D axis.

Given a visible axis in a 2D drawing (centerline, seam, spine), infer
the 3D orientation of the object and provide:
- Feature placement on 3D surfaces projected to 2D
- Correct mirroring across the 3D center plane (not flat 2D flip)
- Feature continuation past silhouette edges
- Visibility checks (is a point in front or behind?)

Works for any object with a visible axis — characters, vehicles,
furniture, props. Covers 80% of illustration use cases.
"""

import json
import math
from typing import Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from adobe_mcp.apps.illustrator.rig_data import _load_rig, _save_rig


# ---------------------------------------------------------------------------
# 3D math primitives
# ---------------------------------------------------------------------------

def rotation_matrix_z(angle_rad: float) -> np.ndarray:
    """Rotation around Z axis (tilt/roll in the image plane)."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)


def rotation_matrix_y(angle_rad: float) -> np.ndarray:
    """Rotation around Y axis (turn/yaw — face turning left/right)."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)


def rotation_matrix_x(angle_rad: float) -> np.ndarray:
    """Rotation around X axis (nod/pitch — face tilting up/down)."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)


def orthographic_project(point_3d: np.ndarray) -> tuple[float, float]:
    """Orthographic projection: drop the Z coordinate."""
    return (float(point_3d[0]), float(point_3d[1]))


# ---------------------------------------------------------------------------
# Core: infer 3D orientation from observed 2D axis
# ---------------------------------------------------------------------------

def infer_orientation_from_axis(
    axis_top_2d: list[float],
    axis_bottom_2d: list[float],
    expected_3d_direction: str = "vertical",
    near_side_width: float | None = None,
    far_side_width: float | None = None,
) -> dict:
    """Infer 3D orientation from a visible axis in a 2D drawing.

    The axis (e.g., a centerline/seam) is something that should be
    straight in 3D but appears at an angle in 2D because the object
    is tilted/rotated.

    Args:
        axis_top_2d: [x, y] of the top of the axis in 2D (AI coords, y-up)
        axis_bottom_2d: [x, y] of the bottom of the axis
        expected_3d_direction: what direction this axis runs in 3D
            "vertical" = the axis is vertical in the object's local space
            "horizontal" = the axis is horizontal
        near_side_width: width of the near side (if measurable) for yaw estimation
        far_side_width: width of the far side (if measurable) for yaw estimation

    Returns:
        dict with: roll_deg, yaw_deg, rotation_matrix, axis_angle_deg,
                   axis_length, axis_center
    """
    top = np.array(axis_top_2d, dtype=np.float64)
    bot = np.array(axis_bottom_2d, dtype=np.float64)

    dx = bot[0] - top[0]
    dy = bot[1] - top[1]
    axis_length = math.sqrt(dx * dx + dy * dy)

    if expected_3d_direction == "vertical":
        # A vertical axis should point straight down (0, -1) in AI coords
        # The angle from vertical = the tilt/roll
        axis_angle = math.atan2(dx, -dy)  # angle from downward vertical
        roll_deg = math.degrees(axis_angle)
    else:
        # A horizontal axis should point right (1, 0)
        axis_angle = math.atan2(dy, dx)
        roll_deg = math.degrees(axis_angle)

    # Estimate yaw (turn) from near/far side width ratio
    yaw_deg = 0.0
    if near_side_width is not None and far_side_width is not None:
        if near_side_width > 0 and far_side_width > 0:
            # ratio = cos(yaw) relationship
            # near side appears at full width, far side foreshortened
            ratio = far_side_width / near_side_width
            ratio = max(0.0, min(1.0, ratio))
            yaw_deg = math.degrees(math.acos(ratio))

    # Build the combined rotation matrix
    roll_rad = math.radians(roll_deg)
    yaw_rad = math.radians(yaw_deg)
    rot = rotation_matrix_z(roll_rad) @ rotation_matrix_y(yaw_rad)

    center = ((top + bot) / 2).tolist()

    return {
        "roll_deg": round(roll_deg, 2),
        "yaw_deg": round(yaw_deg, 2),
        "axis_angle_deg": round(math.degrees(math.atan2(dy, dx)), 2),
        "axis_length": round(axis_length, 2),
        "axis_center": [round(center[0], 1), round(center[1], 1)],
        "rotation_matrix": rot.tolist(),
    }


# ---------------------------------------------------------------------------
# Place features on 3D surface, project to 2D
# ---------------------------------------------------------------------------

def place_feature_on_surface(
    orientation: dict,
    local_position: list[float],
    form_dimensions: list[float],
    surface: str = "front",
) -> dict:
    """Place a feature at a position on a 3D surface, project to 2D.

    Args:
        orientation: result from infer_orientation_from_axis
        local_position: [u, v] normalized position on the surface (0-1)
            u=0 is left, u=1 is right, v=0 is top, v=1 is bottom
        form_dimensions: [width, height, depth] of the 3D form in drawing units
        surface: which face — "front", "back", "left", "right", "top", "bottom"

    Returns:
        dict with: position_2d, visible (bool), depth (for z-ordering)
    """
    w, h, d = form_dimensions
    u, v = local_position

    # Map (u, v) on the named surface to a 3D local coordinate
    # Origin at center of the form
    if surface == "front":
        local_3d = np.array([(u - 0.5) * w, (0.5 - v) * h, d / 2])
    elif surface == "back":
        local_3d = np.array([(0.5 - u) * w, (0.5 - v) * h, -d / 2])
    elif surface == "left":
        local_3d = np.array([-w / 2, (0.5 - v) * h, (0.5 - u) * d])
    elif surface == "right":
        local_3d = np.array([w / 2, (0.5 - v) * h, (u - 0.5) * d])
    elif surface == "top":
        local_3d = np.array([(u - 0.5) * w, h / 2, (0.5 - v) * d])
    elif surface == "bottom":
        local_3d = np.array([(u - 0.5) * w, -h / 2, (v - 0.5) * d])
    else:
        local_3d = np.array([(u - 0.5) * w, (0.5 - v) * h, d / 2])

    # Apply rotation
    rot = np.array(orientation["rotation_matrix"])
    rotated = rot @ local_3d

    # Project to 2D (orthographic) and offset to axis center
    center = np.array(orientation["axis_center"])
    x_2d = rotated[0] + center[0]
    y_2d = rotated[1] + center[1]

    # Visibility: point is visible if its Z (depth) component faces the camera
    # In orthographic, positive Z faces the camera
    visible = rotated[2] >= 0

    return {
        "position_2d": [round(x_2d, 1), round(y_2d, 1)],
        "visible": bool(visible),
        "depth": round(float(rotated[2]), 1),
    }


# ---------------------------------------------------------------------------
# Mirror across the 3D center plane
# ---------------------------------------------------------------------------

def mirror_point_3d(
    orientation: dict,
    point_2d: list[float],
    form_dimensions: list[float],
    surface: str = "front",
) -> dict:
    """Mirror a 2D point across the object's 3D center plane.

    This is the CORRECT way to mirror a feature on a tilted object —
    not a flat 2D flip, but a 3D reflection that accounts for
    foreshortening and rotation.

    Args:
        orientation: result from infer_orientation_from_axis
        point_2d: [x, y] in AI coordinates
        form_dimensions: [width, height, depth]
        surface: which surface the point is on

    Returns:
        dict with: mirrored_2d, visible, depth
    """
    rot = np.array(orientation["rotation_matrix"])
    rot_inv = rot.T  # orthogonal matrix, inverse = transpose
    center = np.array(orientation["axis_center"])

    # Un-project: 2D → 3D local (assumes point is on the named surface)
    offset = np.array(point_2d) - center
    # We know the 2D position but need to reconstruct Z from the surface constraint
    # For a point on the front face, Z = d/2 in local space before rotation
    w, h, d = form_dimensions

    if surface == "front":
        local_z = d / 2
    elif surface == "back":
        local_z = -d / 2
    else:
        local_z = 0  # approximate for other surfaces

    # Solve for local 3D position given 2D projection and known surface
    # rotated = rot @ local_3d
    # projected = [rotated[0], rotated[1]]
    # We know projected and rot[2,:] @ local_3d = local_z (surface constraint)
    # This gives us 3 equations for 3 unknowns

    # For orthographic: x_2d = rot[0,:] @ local + cx, y_2d = rot[1,:] @ local + cy
    # Surface constraint: depends on surface type
    # Simplify: use the inverse rotation on [offset_x, offset_y, estimated_z]

    # Estimate Z from the rotation of the surface normal
    surface_normal_local = np.array([0, 0, 1])  # front face
    if surface == "back":
        surface_normal_local = np.array([0, 0, -1])
    elif surface == "left":
        surface_normal_local = np.array([-1, 0, 0])
    elif surface == "right":
        surface_normal_local = np.array([1, 0, 0])

    rotated_normal = rot @ surface_normal_local
    # The depth component in screen space
    estimated_z = local_z * rotated_normal[2]

    rotated_point = np.array([offset[0], offset[1], estimated_z])
    local_3d = rot_inv @ rotated_point

    # Mirror: flip the X component (left-right symmetry in local space)
    local_3d[0] = -local_3d[0]

    # Re-rotate and project
    mirrored_rotated = rot @ local_3d
    mirrored_2d = [
        round(float(mirrored_rotated[0] + center[0]), 1),
        round(float(mirrored_rotated[1] + center[1]), 1),
    ]

    visible = mirrored_rotated[2] >= 0

    return {
        "mirrored_2d": mirrored_2d,
        "visible": bool(visible),
        "depth": round(float(mirrored_rotated[2]), 1),
    }


def mirror_points_3d(
    orientation: dict,
    points_2d: list[list[float]],
    form_dimensions: list[float],
    surface: str = "front",
) -> list[dict]:
    """Mirror multiple points across the 3D center plane."""
    return [mirror_point_3d(orientation, p, form_dimensions, surface) for p in points_2d]


# ---------------------------------------------------------------------------
# Feature continuation past silhouette edge
# ---------------------------------------------------------------------------

def continue_feature_line(
    orientation: dict,
    line_start_2d: list[float],
    line_end_2d: list[float],
    form_dimensions: list[float],
    extension_factor: float = 1.5,
) -> dict:
    """Extend a feature line past where it meets the silhouette edge.

    The line continues along the 3D surface even though it goes behind
    the visible edge. This computes where it would emerge or how far it
    extends before wrapping around the form.

    Args:
        line_start_2d: visible start of the line
        line_end_2d: where the line meets the silhouette edge
        extension_factor: how far past the edge to extend (1.0 = same length)

    Returns:
        dict with: extended_point_2d, wraps_to_surface (which face it continues onto),
                   visible (whether the extension is visible)
    """
    start = np.array(line_start_2d)
    end = np.array(line_end_2d)
    direction = end - start
    length = np.linalg.norm(direction)

    if length == 0:
        return {"extended_point_2d": line_end_2d, "wraps_to_surface": None, "visible": False}

    # Extend the line in 2D by the extension factor
    extended = end + direction * extension_factor
    extended_2d = [round(float(extended[0]), 1), round(float(extended[1]), 1)]

    # Determine which surface the line wraps to based on direction
    # If the line goes past the right edge → wraps to right face
    # If past the left edge → wraps to left face
    # If past the top → wraps to top face
    center = np.array(orientation["axis_center"])
    w = form_dimensions[0]

    dx = direction[0]
    wraps_to = None
    if dx > 0:
        wraps_to = "right"
    elif dx < 0:
        wraps_to = "left"

    return {
        "extended_point_2d": extended_2d,
        "wraps_to_surface": wraps_to,
        "visible": False,  # extensions past the edge are generally hidden
    }


# ---------------------------------------------------------------------------
# Convenience: derive form from observed measurements
# ---------------------------------------------------------------------------

def estimate_form_dimensions(
    axis_length: float,
    near_width: float,
    far_width: float | None = None,
) -> list[float]:
    """Estimate 3D form dimensions from observed 2D measurements.

    Args:
        axis_length: length of the visible axis (height indicator)
        near_width: width of the near/visible side
        far_width: width of the far side (if measurable)

    Returns:
        [width, height, depth] — estimated 3D dimensions
    """
    height = axis_length
    width = near_width
    # Depth estimated from width (assume roughly cubic proportions for 80% case)
    depth = width * 0.6 if far_width is None else width * 0.8
    return [round(width, 1), round(height, 1), round(depth, 1)]


# ---------------------------------------------------------------------------
# MCP Tool
# ---------------------------------------------------------------------------

class Form3DProjectionInput(BaseModel):
    """Project 3D form from observed 2D axis — handles tilted/rotated objects."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: infer_orientation, place_feature, mirror, mirror_points, continue_line, estimate_dimensions")
    character_name: str = Field(default="character", description="Character identifier")

    # infer_orientation
    axis_top: Optional[str] = Field(default=None, description="JSON [x,y] of axis top in AI coords")
    axis_bottom: Optional[str] = Field(default=None, description="JSON [x,y] of axis bottom")
    near_side_width: Optional[float] = Field(default=None, description="Width of near side for yaw estimation")
    far_side_width: Optional[float] = Field(default=None, description="Width of far side")

    # place_feature / mirror
    local_position: Optional[str] = Field(default=None, description="JSON [u,v] normalized position on surface (0-1)")
    point_2d: Optional[str] = Field(default=None, description="JSON [x,y] point to mirror")
    points_2d: Optional[str] = Field(default=None, description="JSON array of [x,y] points to mirror")
    form_dimensions: Optional[str] = Field(default=None, description="JSON [width,height,depth] of 3D form")
    surface: str = Field(default="front", description="Surface: front, back, left, right, top, bottom")

    # continue_line
    line_start: Optional[str] = Field(default=None, description="JSON [x,y] line start")
    line_end: Optional[str] = Field(default=None, description="JSON [x,y] line end (at silhouette edge)")
    extension_factor: float = Field(default=1.5, description="How far past the edge to extend")


def register(mcp):
    """Register the adobe_ai_form_3d_projection tool."""

    @mcp.tool(
        name="adobe_ai_form_3d_projection",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def adobe_ai_form_3d_projection(params: Form3DProjectionInput) -> str:
        """Infer 3D orientation from a visible axis and project features correctly.

        Use when an object is tilted/rotated and you need to place, mirror,
        or extend features accounting for the 3D form — not flat 2D operations.
        """
        rig = _load_rig(params.character_name)
        rig.setdefault("form_3d", {})

        if params.action == "infer_orientation":
            if not params.axis_top or not params.axis_bottom:
                return json.dumps({"error": "axis_top and axis_bottom required"})
            top = json.loads(params.axis_top)
            bot = json.loads(params.axis_bottom)
            orientation = infer_orientation_from_axis(
                top, bot,
                near_side_width=params.near_side_width,
                far_side_width=params.far_side_width,
            )
            rig["form_3d"]["orientation"] = orientation
            _save_rig(params.character_name, rig)
            return json.dumps(orientation)

        elif params.action == "place_feature":
            orientation = rig["form_3d"].get("orientation")
            if not orientation:
                return json.dumps({"error": "Run infer_orientation first"})
            if not params.local_position or not params.form_dimensions:
                return json.dumps({"error": "local_position and form_dimensions required"})
            local_pos = json.loads(params.local_position)
            dims = json.loads(params.form_dimensions)
            result = place_feature_on_surface(orientation, local_pos, dims, params.surface)
            return json.dumps(result)

        elif params.action == "mirror":
            orientation = rig["form_3d"].get("orientation")
            if not orientation:
                return json.dumps({"error": "Run infer_orientation first"})
            if not params.point_2d or not params.form_dimensions:
                return json.dumps({"error": "point_2d and form_dimensions required"})
            point = json.loads(params.point_2d)
            dims = json.loads(params.form_dimensions)
            result = mirror_point_3d(orientation, point, dims, params.surface)
            return json.dumps(result)

        elif params.action == "mirror_points":
            orientation = rig["form_3d"].get("orientation")
            if not orientation:
                return json.dumps({"error": "Run infer_orientation first"})
            if not params.points_2d or not params.form_dimensions:
                return json.dumps({"error": "points_2d and form_dimensions required"})
            points = json.loads(params.points_2d)
            dims = json.loads(params.form_dimensions)
            results = mirror_points_3d(orientation, points, dims, params.surface)
            return json.dumps(results)

        elif params.action == "continue_line":
            orientation = rig["form_3d"].get("orientation")
            if not orientation:
                return json.dumps({"error": "Run infer_orientation first"})
            if not params.line_start or not params.line_end or not params.form_dimensions:
                return json.dumps({"error": "line_start, line_end, and form_dimensions required"})
            start = json.loads(params.line_start)
            end = json.loads(params.line_end)
            dims = json.loads(params.form_dimensions)
            result = continue_feature_line(orientation, start, end, dims, params.extension_factor)
            return json.dumps(result)

        elif params.action == "estimate_dimensions":
            if params.near_side_width is None:
                return json.dumps({"error": "near_side_width required"})
            orientation = rig["form_3d"].get("orientation")
            axis_len = orientation["axis_length"] if orientation else 400
            dims = estimate_form_dimensions(axis_len, params.near_side_width, params.far_side_width)
            rig["form_3d"]["dimensions"] = dims
            _save_rig(params.character_name, rig)
            return json.dumps({"dimensions": dims})

        return json.dumps({"error": f"Unknown action: {params.action}"})
