"""Detect connection points between segmented parts.

Uses OpenCV morphological operations to find boundary regions between
adjacent parts, then classifies connections as joints, containment,
adjacent, or separate based on boundary geometry.

Pure Python implementation using OpenCV and numpy.
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


class AiConnectionDetectorInput(BaseModel):
    """Detect connections between segmented parts."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        default="detect", description="Action: detect"
    )
    image_path: str = Field(
        ..., description="Path to the image to analyze"
    )
    parts: list[dict] = Field(
        ..., description="List of part dicts from segmenter"
    )
    dilation_pixels: int = Field(
        default=5, description="Dilation kernel size for boundary detection", ge=1, le=20
    )


# ---------------------------------------------------------------------------
# Pure Python helpers
# ---------------------------------------------------------------------------


def _create_part_mask(
    part: dict,
    image_shape: tuple[int, int],
) -> np.ndarray:
    """Create a binary mask for a part from its bounds.

    Uses bounds [x, y, w, h] to create a filled rectangle mask.
    """
    mask = np.zeros(image_shape[:2], dtype=np.uint8)
    bounds = part.get("bounds", [0, 0, 0, 0])
    x, y, w, h = bounds
    mask[y:y+h, x:x+w] = 255
    return mask


def classify_connection(
    boundary_width: float,
    part_a_area: int,
    part_b_area: int,
) -> str:
    """Classify the connection type between two parts.

    Args:
        boundary_width: width of the shared boundary in pixels
        part_a_area: area of part A
        part_b_area: area of part B

    Returns:
        "joint" - narrow connection (< 10% of smaller part width)
        "containment" - wide connection where one part is inside another
        "adjacent" - moderate boundary suggesting side-by-side
        "separate" - no meaningful boundary
    """
    if boundary_width <= 0:
        return "separate"

    smaller_area = min(part_a_area, part_b_area)
    if smaller_area <= 0:
        return "separate"

    # Estimate the smaller part's characteristic width (sqrt of area)
    smaller_width = math.sqrt(smaller_area)

    # Ratio of boundary width to smaller part width
    ratio = boundary_width / smaller_width

    if ratio < 0.10:
        return "joint"
    elif ratio > 0.80:
        # Check if one part is much larger (containment)
        larger_area = max(part_a_area, part_b_area)
        if larger_area > smaller_area * 2:
            return "containment"
        return "adjacent"
    else:
        return "adjacent"


def detect_connections(
    parts: list[dict],
    image_path: str,
    dilation_pixels: int = 5,
) -> dict:
    """Detect connections between all pairs of adjacent parts.

    For each pair, dilates their masks and finds overlap to measure
    boundary width. Returns connection metadata including type,
    position, and confidence.

    Args:
        parts: list of part dicts with bounds, area
        image_path: path to the source image (for dimensions)
        dilation_pixels: kernel size for dilation

    Returns:
        {"connections": [{"part_a", "part_b", "type", "position", "confidence"}]}
    """
    img = cv2.imread(image_path)
    if img is None:
        return {"error": f"Could not read image: {image_path}", "connections": []}

    h, w = img.shape[:2]
    image_shape = (h, w)
    kernel = np.ones((dilation_pixels, dilation_pixels), np.uint8)

    connections = []

    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            part_a = parts[i]
            part_b = parts[j]

            mask_a = _create_part_mask(part_a, image_shape)
            mask_b = _create_part_mask(part_b, image_shape)

            # Dilate both masks and find overlap
            dilated_a = cv2.dilate(mask_a, kernel, iterations=1)
            dilated_b = cv2.dilate(mask_b, kernel, iterations=1)
            overlap = cv2.bitwise_and(dilated_a, dilated_b)

            overlap_pixels = np.count_nonzero(overlap)
            if overlap_pixels == 0:
                continue

            # Measure boundary width: approximate as sqrt of overlap area
            boundary_width = math.sqrt(overlap_pixels)

            area_a = part_a.get("area", 0)
            area_b = part_b.get("area", 0)

            conn_type = classify_connection(boundary_width, area_a, area_b)

            # Compute connection centroid from overlap region
            overlap_coords = np.column_stack(np.where(overlap > 0))
            if len(overlap_coords) > 0:
                conn_cy = float(overlap_coords[:, 0].mean())
                conn_cx = float(overlap_coords[:, 1].mean())
            else:
                # Midpoint between centroids
                conn_cx = (part_a["centroid"][0] + part_b["centroid"][0]) / 2
                conn_cy = (part_a["centroid"][1] + part_b["centroid"][1]) / 2

            # Confidence based on overlap clarity
            max_possible_overlap = min(area_a, area_b) * 0.5
            if max_possible_overlap > 0:
                confidence = min(1.0, overlap_pixels / max_possible_overlap)
            else:
                confidence = 0.5

            connections.append({
                "part_a": part_a["name"],
                "part_b": part_b["name"],
                "type": conn_type,
                "position": [round(conn_cx, 1), round(conn_cy, 1)],
                "confidence": round(confidence, 2),
                "boundary_width": round(boundary_width, 1),
            })

    return {"connections": connections}


# ---------------------------------------------------------------------------
# MCP Registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_connection_detector tool."""

    @mcp.tool(
        name="adobe_ai_connection_detector",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_connection_detector(params: AiConnectionDetectorInput) -> str:
        """Detect connection points between segmented parts.

        Analyzes part boundaries to classify connections as joints,
        containment, adjacent, or separate. Returns connection positions
        and confidence scores.
        """
        result = detect_connections(
            params.parts,
            params.image_path,
            params.dilation_pixels,
        )
        return json.dumps(result, indent=2)
