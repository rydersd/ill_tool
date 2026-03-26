"""Axis-guided contour scanner for extracting vector paths from reference images.

Given a reference image and an axis (center + angle), this module:
1. Walks along the main axis in incremental steps
2. At each step, scans perpendicular (cross-axis) for color transitions
3. Collects edge transition points (background->feature and feature->background)
4. Separates into left_edges and right_edges contour lists
5. Fits efficient bezier paths through each edge set via curve_fit
6. Returns contour data ready for AI path placement

Tier 1 (top): Pure Python scanning, edge detection, and path fitting.
Tier 2 (bottom): MCP tool registration for scan_feature and place_contour actions.
"""

import json
import math
import os
from typing import Optional

import cv2
import numpy as np

from adobe_mcp.apps.illustrator.curve_fit import fit_bezier_path
from adobe_mcp.apps.illustrator.landmark_axis import compute_transform, pixel_to_ai
from adobe_mcp.apps.illustrator.models import AiContourScannerInput
from adobe_mcp.apps.illustrator.rig_data import _load_rig
from adobe_mcp.engine import _async_run_jsx
from adobe_mcp.jsx.templates import escape_jsx_string


# ── Tier 1: Pure Python Edge Scanning ────────────────────────────────────


def _load_grayscale(image_path: str) -> Optional[np.ndarray]:
    """Load an image and convert to single-channel grayscale.

    Returns the grayscale image as a 2D numpy array (uint8), or None on failure.
    """
    img = cv2.imread(image_path)
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _pixel_in_bounds(x: int, y: int, width: int, height: int) -> bool:
    """Check whether a pixel coordinate is within image bounds."""
    return 0 <= x < width and 0 <= y < height


def scan_edges_along_axis(
    gray: np.ndarray,
    axis_center: tuple[float, float],
    axis_angle_deg: float,
    scan_start: float,
    scan_end: float,
    scan_step: float,
    cross_range: float,
    sample_step: float,
    bright_threshold: int = 80,
    dark_threshold: int = 30,
) -> dict:
    """Walk along the main axis and scan perpendicular for edge transitions.

    At each position along the main axis, we scan along the cross-axis direction
    from -cross_range to +cross_range looking for brightness transitions that
    indicate feature boundaries.

    Args:
        gray: Grayscale image as 2D numpy array.
        axis_center: (x, y) center of the axis in pixel coordinates.
        axis_angle_deg: Angle of the main axis in degrees. 0=right, 90=down
                        (standard image coordinates where Y increases downward).
        scan_start: Start distance along axis from center (can be negative).
        scan_end: End distance along axis from center.
        scan_step: Increment along the main axis per scan line.
        cross_range: Half-width of the perpendicular scan.
        sample_step: Increment along the cross-axis per sample.
        bright_threshold: Brightness above this = background (not feature).
        dark_threshold: Brightness below this = feature (dark region).

    Returns:
        Dict with keys:
            left_edges: list of [x, y] pixel positions (first transition per scan line)
            right_edges: list of [x, y] pixel positions (last transition per scan line)
            all_transitions: list of all transition points for debugging
            scan_line_count: number of scan lines processed
    """
    img_h, img_w = gray.shape[:2]

    # Main axis direction (in image coordinates, Y increases downward)
    angle_rad = math.radians(axis_angle_deg)
    dir_x = math.cos(angle_rad)
    dir_y = math.sin(angle_rad)

    # Cross-axis direction (perpendicular, 90 degrees clockwise in image coords)
    cross_x = -dir_y
    cross_y = dir_x

    left_edges = []
    right_edges = []
    all_transitions = []
    scan_line_count = 0

    # Walk along the main axis from scan_start to scan_end
    t = scan_start
    while t <= scan_end:
        # Compute the scan origin for this axis position
        origin_x = axis_center[0] + t * dir_x
        origin_y = axis_center[1] + t * dir_y

        # Scan along the cross-axis at this position
        line_transitions = []
        s = -cross_range
        prev_brightness = None

        while s <= cross_range:
            # Compute the sample point
            px = origin_x + s * cross_x
            py = origin_y + s * cross_y
            ix, iy = int(round(px)), int(round(py))

            if _pixel_in_bounds(ix, iy, img_w, img_h):
                brightness = int(gray[iy, ix])

                if prev_brightness is not None:
                    # Detect entering dark feature: background -> feature
                    if prev_brightness > bright_threshold and brightness < dark_threshold:
                        line_transitions.append({
                            "type": "enter",
                            "pos": [round(px, 2), round(py, 2)],
                            "axis_t": round(t, 2),
                            "cross_s": round(s, 2),
                        })
                    # Detect leaving dark feature: feature -> background
                    elif prev_brightness < dark_threshold and brightness > bright_threshold:
                        line_transitions.append({
                            "type": "exit",
                            "pos": [round(px, 2), round(py, 2)],
                            "axis_t": round(t, 2),
                            "cross_s": round(s, 2),
                        })

                prev_brightness = brightness

            s += sample_step

        # Separate first "enter" as left edge and last "exit" as right edge
        # This handles the common case of a single feature region per scan line
        enters = [tr for tr in line_transitions if tr["type"] == "enter"]
        exits = [tr for tr in line_transitions if tr["type"] == "exit"]

        if enters:
            left_edges.append(enters[0]["pos"])
        if exits:
            right_edges.append(exits[-1]["pos"])

        all_transitions.extend(line_transitions)
        scan_line_count += 1
        t += scan_step

    return {
        "left_edges": left_edges,
        "right_edges": right_edges,
        "all_transitions": all_transitions,
        "scan_line_count": scan_line_count,
    }


def fit_contour_from_edges(
    left_edges: list[list[float]],
    right_edges: list[list[float]],
    error_threshold: float = 2.0,
    max_segments: Optional[int] = None,
    closed: bool = True,
) -> dict:
    """Fit bezier paths through left and right edge point sets, then combine.

    For a closed contour, the path goes: left_edges (top to bottom) then
    right_edges reversed (bottom to top), forming a loop around the feature.

    For an open contour, returns separate left and right edge paths.

    Args:
        left_edges: List of [x, y] pixel positions for the left boundary.
        right_edges: List of [x, y] pixel positions for the right boundary.
        error_threshold: Max error for bezier curve fitting.
        max_segments: Optional cap on bezier segments.
        closed: Whether to combine edges into a closed contour.

    Returns:
        Dict with:
            contour_points: combined ordered point list (pixel coords)
            left_segments: bezier segments for left edge
            right_segments: bezier segments for right edge
            anchor_count: total number of anchor points in the fitted path
    """
    result = {
        "contour_points": [],
        "left_segments": [],
        "right_segments": [],
        "left_anchors": [],
        "right_anchors": [],
        "anchor_count": 0,
    }

    if not left_edges and not right_edges:
        return result

    # Fit bezier paths through each edge set
    left_anchors = []
    right_anchors = []

    if len(left_edges) >= 2:
        left_pts = np.array(left_edges, dtype=np.float64)
        left_segs = fit_bezier_path(left_pts, error_threshold, max_segments)
        result["left_segments"] = [
            [[float(v) for v in p] for p in seg] for seg in left_segs
        ]
        # Extract anchor points from segments for the contour
        if left_segs:
            left_anchors.append([float(left_segs[0][0][0]), float(left_segs[0][0][1])])
            for seg in left_segs:
                left_anchors.append([float(seg[3][0]), float(seg[3][1])])
    elif len(left_edges) == 1:
        left_anchors = [list(left_edges[0])]

    if len(right_edges) >= 2:
        right_pts = np.array(right_edges, dtype=np.float64)
        right_segs = fit_bezier_path(right_pts, error_threshold, max_segments)
        result["right_segments"] = [
            [[float(v) for v in p] for p in seg] for seg in right_segs
        ]
        if right_segs:
            right_anchors.append([float(right_segs[0][0][0]), float(right_segs[0][0][1])])
            for seg in right_segs:
                right_anchors.append([float(seg[3][0]), float(seg[3][1])])
    elif len(right_edges) == 1:
        right_anchors = [list(right_edges[0])]

    result["left_anchors"] = left_anchors
    result["right_anchors"] = right_anchors

    # Combine into contour: left top->bottom, then right bottom->top (reversed)
    if closed and left_anchors and right_anchors:
        contour = left_anchors + list(reversed(right_anchors))
    else:
        contour = left_anchors + right_anchors

    result["contour_points"] = contour
    result["anchor_count"] = len(contour)

    return result


def pixels_to_ai_coords(
    points: list[list[float]],
    transform: Optional[dict] = None,
) -> list[list[float]]:
    """Convert a list of pixel coordinate points to AI coordinates.

    If a transform dict is provided (from landmark_axis.compute_transform),
    uses the full scale+offset+flip pipeline. Otherwise falls back to
    simple (x, -y) mapping for a 1:1 reference placed at origin.

    Args:
        points: List of [px_x, px_y] pixel coordinates.
        transform: Optional transform dict with scale, offset_x, offset_y.

    Returns:
        List of [ai_x, ai_y] Illustrator coordinates.
    """
    ai_points = []
    for pt in points:
        if transform:
            ai_x, ai_y = pixel_to_ai(pt[0], pt[1], transform)
        else:
            # Fallback: 1:1 placement at origin, Y-flip only
            ai_x = pt[0]
            ai_y = -pt[1]
        ai_points.append([round(ai_x, 2), round(ai_y, 2)])
    return ai_points


def scan_feature(
    image_path: str,
    axis_center: tuple[float, float],
    axis_angle_deg: float,
    scan_start: float = -100.0,
    scan_end: float = 100.0,
    scan_step: float = 2.0,
    cross_range: float = 80.0,
    sample_step: float = 1.0,
    bright_threshold: int = 80,
    dark_threshold: int = 30,
    error_threshold: float = 2.0,
    max_segments: Optional[int] = None,
    closed: bool = True,
) -> dict:
    """Full pipeline: load image, scan edges, fit contour.

    This is the main entry point for programmatic use (not via MCP).

    Returns a dict with:
        contour_points: List of [x, y] pixel coords forming the contour.
        left_edges: Raw left edge points detected.
        right_edges: Raw right edge points detected.
        anchor_count: Number of anchors after bezier fitting.
        scan_line_count: Number of cross-axis scan lines run.
        error: Optional error message if something failed.
    """
    gray = _load_grayscale(image_path)
    if gray is None:
        return {"error": f"Could not read image: {image_path}"}

    # Scan edges along the axis
    edges = scan_edges_along_axis(
        gray,
        axis_center=axis_center,
        axis_angle_deg=axis_angle_deg,
        scan_start=scan_start,
        scan_end=scan_end,
        scan_step=scan_step,
        cross_range=cross_range,
        sample_step=sample_step,
        bright_threshold=bright_threshold,
        dark_threshold=dark_threshold,
    )

    if not edges["left_edges"] and not edges["right_edges"]:
        return {
            "error": "No edge transitions found in scan region",
            "scan_line_count": edges["scan_line_count"],
            "left_edges": [],
            "right_edges": [],
        }

    # Fit bezier contour through detected edges
    contour = fit_contour_from_edges(
        edges["left_edges"],
        edges["right_edges"],
        error_threshold=error_threshold,
        max_segments=max_segments,
        closed=closed,
    )

    return {
        "contour_points": contour["contour_points"],
        "left_edges": edges["left_edges"],
        "right_edges": edges["right_edges"],
        "left_anchors": contour["left_anchors"],
        "right_anchors": contour["right_anchors"],
        "anchor_count": contour["anchor_count"],
        "scan_line_count": edges["scan_line_count"],
        "all_transitions": edges["all_transitions"],
    }


# ── Tier 2: MCP Tool Registration ───────────────────────────────────────


def register(mcp):
    """Register the adobe_ai_contour_scanner tool."""

    @mcp.tool(
        name="adobe_ai_contour_scanner",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_contour_scanner(params: AiContourScannerInput) -> str:
        """Axis-guided contour scanner for extracting vector paths from reference images.

        Actions:
        - scan_feature: scan a region along an axis and return edge contour points
        - place_contour: place a scanned contour as a path in Illustrator
        """

        if params.action == "scan_feature":
            # ── Scan feature edges from the reference image ──
            if not os.path.exists(params.image_path):
                return json.dumps({"error": f"Image not found: {params.image_path}"})

            result = scan_feature(
                image_path=params.image_path,
                axis_center=(params.axis_center_x, params.axis_center_y),
                axis_angle_deg=params.axis_angle,
                scan_start=params.scan_start,
                scan_end=params.scan_end,
                scan_step=params.scan_step,
                cross_range=params.cross_range,
                sample_step=params.sample_step,
                bright_threshold=params.bright_threshold,
                dark_threshold=params.dark_threshold,
                error_threshold=params.error_threshold,
                max_segments=params.max_segments,
                closed=params.closed,
            )

            if "error" in result and not result.get("contour_points"):
                return json.dumps(result)

            return json.dumps({
                "action": "scan_feature",
                "contour_points": result["contour_points"],
                "anchor_count": result["anchor_count"],
                "left_edge_count": len(result["left_edges"]),
                "right_edge_count": len(result["right_edges"]),
                "scan_line_count": result["scan_line_count"],
                "left_edges": result["left_edges"],
                "right_edges": result["right_edges"],
            })

        elif params.action == "place_contour":
            # ── Place a scanned contour as a path in Illustrator ──
            if not params.contour_json:
                return json.dumps({"error": "place_contour requires contour_json"})

            try:
                contour_data = json.loads(params.contour_json)
            except (json.JSONDecodeError, TypeError) as exc:
                return json.dumps({"error": f"Invalid contour_json: {exc}"})

            # Extract contour points from the scan result
            contour_points = contour_data.get("contour_points", [])
            if not contour_points:
                return json.dumps({"error": "contour_json has no contour_points"})

            # Convert pixel coords to AI coords using rig transform if available
            rig = _load_rig(params.character_name)
            transform = rig.get("transform")
            ai_points = pixels_to_ai_coords(contour_points, transform)

            # Build JSX to create the path
            escaped_layer = escape_jsx_string(params.layer_name)
            escaped_name = escape_jsx_string(params.path_name)
            points_json = json.dumps(ai_points)
            closed_js = "true" if params.closed else "false"

            jsx = f"""
(function() {{
    var doc = app.activeDocument;
    var layer = null;
    for (var i = 0; i < doc.layers.length; i++) {{
        if (doc.layers[i].name === "{escaped_layer}") {{
            layer = doc.layers[i];
            break;
        }}
    }}
    if (!layer) {{
        layer = doc.layers.add();
        layer.name = "{escaped_layer}";
    }}
    doc.activeLayer = layer;

    var path = layer.pathItems.add();
    path.setEntirePath({points_json});
    path.closed = {closed_js};
    path.filled = false;
    path.stroked = true;
    path.strokeWidth = {params.stroke_width};
    path.name = "{escaped_name}";

    var black = new RGBColor();
    black.red = 0;
    black.green = 0;
    black.blue = 0;
    path.strokeColor = black;

    var result = [];
    for (var i = 0; i < path.pathPoints.length; i++) {{
        var a = path.pathPoints[i].anchor;
        result.push([Math.round(a[0] * 100) / 100, Math.round(a[1] * 100) / 100]);
    }}
    return JSON.stringify({{
        name: path.name,
        layer: layer.name,
        pointCount: path.pathPoints.length,
        bounds: path.geometricBounds,
        placed_points: result
    }});
}})();
"""
            jsx_result = await _async_run_jsx("illustrator", jsx)

            if not jsx_result["success"]:
                return json.dumps({
                    "error": f"Path creation failed: {jsx_result['stderr']}",
                    "ai_points": ai_points,
                    "point_count": len(ai_points),
                })

            try:
                placed = json.loads(jsx_result["stdout"])
            except (json.JSONDecodeError, TypeError):
                placed = {"raw": jsx_result["stdout"]}

            return json.dumps({
                "action": "place_contour",
                "name": placed.get("name", params.path_name),
                "layer": placed.get("layer", params.layer_name),
                "point_count": placed.get("pointCount", len(ai_points)),
                "bounds": placed.get("bounds", []),
                "ai_points": ai_points,
                "transform_used": "rig" if transform else "fallback_y_flip",
            })

        else:
            return json.dumps({
                "error": f"Unknown action: {params.action}. Valid: scan_feature, place_contour"
            })
