"""Analyze a reference image for geometric forms using OpenCV.

Returns measured shapes (vertices, edges, angles, proportions) — not guesses.
Pure Python analysis: no JSX, no Illustrator interaction.
"""

import json
import os

import cv2
import numpy as np

from adobe_mcp.apps.illustrator.models import AiAnalyzeReferenceInput


def _classify_shape(vertex_count: int, width: float, height: float) -> str:
    """Classify a shape by its approximate polygon vertex count and dimensions."""
    if vertex_count == 3:
        return "triangle"
    elif vertex_count == 4:
        # Distinguish square, rectangle, and trapezoid by aspect ratio
        aspect = min(width, height) / max(width, height) if max(width, height) > 0 else 1.0
        if aspect > 0.9:
            return "square"
        elif aspect > 0.4:
            return "rectangle"
        else:
            return "trapezoid"
    elif vertex_count == 5:
        return "pentagon"
    elif vertex_count == 6:
        return "hexagon"
    elif vertex_count == 7:
        return "heptagon"
    elif vertex_count == 8:
        return "octagon"
    else:
        # >8 vertices — likely a circle or ellipse
        return "circle/ellipse"


def _edge_lengths(approx_points: np.ndarray) -> list[float]:
    """Compute edge lengths between consecutive vertices of an approximate polygon."""
    pts = approx_points.reshape(-1, 2)
    n = len(pts)
    lengths = []
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        length = float(np.linalg.norm(p2 - p1))
        lengths.append(round(length, 1))
    return lengths


def _edge_ratios(lengths: list[float]) -> list[float]:
    """Compute ratio of each edge length to the longest edge."""
    max_len = max(lengths) if lengths else 1.0
    if max_len == 0:
        return [0.0] * len(lengths)
    return [round(l / max_len, 2) for l in lengths]


def _analyze_image(params: AiAnalyzeReferenceInput) -> dict:
    """Run the full OpenCV analysis pipeline on the reference image."""
    # Step 1: Load image
    img = cv2.imread(params.image_path)
    if img is None:
        return {"error": f"Could not read image at {params.image_path}"}

    img_h, img_w = img.shape[:2]
    total_area = img_h * img_w
    min_area = (params.min_area_pct / 100.0) * total_area

    # Step 2: Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Step 3: Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Step 4: Canny edge detection
    edges = cv2.Canny(blurred, params.canny_low, params.canny_high)

    # Step 5: Find external contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    total_found = len(contours)

    # Step 6: Filter by minimum area
    filtered = [c for c in contours if cv2.contourArea(c) >= min_area]

    # Step 7: Sort by area descending, cap at max_contours
    filtered.sort(key=lambda c: cv2.contourArea(c), reverse=True)
    filtered = filtered[: params.max_contours]

    # Step 8: Analyze each contour
    shapes = []
    for idx, contour in enumerate(filtered):
        # Approximate polygon
        arc_len = cv2.arcLength(contour, True)
        epsilon = 0.02 * arc_len
        approx = cv2.approxPolyDP(contour, epsilon, True)
        vertex_count = len(approx)

        # Minimum area bounding rectangle
        rect = cv2.minAreaRect(contour)
        center, (w, h), rotation = rect

        # Classify shape
        shape_type = _classify_shape(vertex_count, w, h)

        # Area and perimeter
        area = cv2.contourArea(contour)
        perimeter = arc_len

        # Centroid from moments
        moments = cv2.moments(contour)
        if moments["m00"] != 0:
            cx = moments["m10"] / moments["m00"]
            cy = moments["m01"] / moments["m00"]
        else:
            cx, cy = float(center[0]), float(center[1])

        # Edge lengths and ratios from approximate polygon vertices
        edges_list = _edge_lengths(approx)
        ratios = _edge_ratios(edges_list)

        # Axis-aligned bounding rect for convenience
        bx, by, bw, bh = cv2.boundingRect(contour)

        # Approximate polygon points as plain list
        approx_pts = approx.reshape(-1, 2).tolist()

        shapes.append({
            "index": idx,
            "type": shape_type,
            "vertices": vertex_count,
            "center": [round(cx, 1), round(cy, 1)],
            "width": round(float(w), 1),
            "height": round(float(h), 1),
            "rotation_deg": round(float(rotation), 1),
            "area": int(area),
            "perimeter": round(perimeter, 1),
            "edge_lengths": edges_list,
            "edge_ratios": ratios,
            "bounding_rect": [bx, by, bw, bh],
            "approx_points": approx_pts,
        })

    return {
        "image_size": [img_w, img_h],
        "total_contours_found": total_found,
        "shapes_returned": len(shapes),
        "shapes": shapes,
    }


def register(mcp):
    """Register the adobe_ai_analyze_reference tool."""

    @mcp.tool(
        name="adobe_ai_analyze_reference",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_analyze_reference(params: AiAnalyzeReferenceInput) -> str:
        """Analyze a reference image with OpenCV to extract measured geometric forms.

        Returns a JSON manifest of detected shapes with vertices, edge lengths,
        proportions, rotation angles, and centroids. Use this to understand the
        precise geometry of a reference before recreating it in Illustrator.
        """
        # Validate image path exists before processing
        if not os.path.isfile(params.image_path):
            return f"Error: Could not read image at {params.image_path}"

        result = _analyze_image(params)

        if "error" in result:
            return f"Error: {result['error']}"

        return json.dumps(result, indent=2)
