"""CV-based part segmentation for illustration analysis.

Segments an image into distinct color regions using k-means clustering,
then extracts connected components for each region. Outline regions
(near-black) are filtered out to isolate actual character parts.

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


class AiPartSegmenterInput(BaseModel):
    """Segment an image into distinct color parts."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        default="segment", description="Action: segment"
    )
    image_path: str = Field(
        ..., description="Path to the image to segment"
    )
    n_clusters: int = Field(
        default=5, description="Number of color clusters for k-means", ge=2, le=20
    )
    min_area: int = Field(
        default=50, description="Minimum pixel area for a part to be included", ge=1
    )
    outline_threshold: int = Field(
        default=40, description="Max brightness (0-255) to consider a region an outline", ge=0, le=255
    )


# ---------------------------------------------------------------------------
# Pure Python helpers
# ---------------------------------------------------------------------------


def segment_by_color(image_path: str, n_clusters: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """K-means clustering on pixel colors.

    Args:
        image_path: path to the image file
        n_clusters: number of color clusters

    Returns:
        (labeled_image, cluster_centers) where labeled_image has the same
        shape as the input (h, w) with cluster indices, and cluster_centers
        is (n_clusters, 3) BGR values.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    h, w = img.shape[:2]
    # Reshape to (n_pixels, 3) for k-means
    pixels = img.reshape(-1, 3).astype(np.float32)

    # K-means clustering
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    _, labels, centers = cv2.kmeans(
        pixels, n_clusters, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
    )

    labeled_image = labels.reshape(h, w).astype(np.int32)
    return labeled_image, centers


def extract_parts(
    labeled_image: np.ndarray,
    original_image: np.ndarray,
    min_area: int = 50,
) -> list[dict]:
    """Extract part information from each labeled region.

    For each cluster label, finds connected components and computes
    bounding box, centroid, area, and dominant color.

    Args:
        labeled_image: (h, w) array of cluster indices
        original_image: (h, w, 3) BGR image
        min_area: minimum pixel area to include a part

    Returns:
        List of part dicts with name, bounds, centroid, area, color_hex.
    """
    unique_labels = np.unique(labeled_image)
    parts = []
    part_idx = 0

    for label in unique_labels:
        # Create binary mask for this label
        mask = (labeled_image == label).astype(np.uint8) * 255

        # Find connected components within this label
        num_components, comp_labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask, connectivity=8
        )

        # Skip background component (index 0)
        for comp_id in range(1, num_components):
            area = stats[comp_id, cv2.CC_STAT_AREA]
            if area < min_area:
                continue

            x = stats[comp_id, cv2.CC_STAT_LEFT]
            y = stats[comp_id, cv2.CC_STAT_TOP]
            w = stats[comp_id, cv2.CC_STAT_WIDTH]
            h_val = stats[comp_id, cv2.CC_STAT_HEIGHT]
            cx = float(centroids[comp_id][0])
            cy = float(centroids[comp_id][1])

            # Compute dominant color from original image within this component
            comp_mask = (comp_labels == comp_id)
            region_pixels = original_image[comp_mask]
            if len(region_pixels) > 0:
                mean_color = region_pixels.mean(axis=0).astype(int)
                # BGR to hex
                color_hex = "#{:02x}{:02x}{:02x}".format(
                    int(mean_color[2]), int(mean_color[1]), int(mean_color[0])
                )
            else:
                color_hex = "#000000"

            parts.append({
                "name": f"part_{part_idx}",
                "bounds": [int(x), int(y), int(w), int(h_val)],
                "centroid": [round(cx, 1), round(cy, 1)],
                "area": int(area),
                "color_hex": color_hex,
                "label": int(label),
            })
            part_idx += 1

    return parts


def filter_outline_regions(parts: list[dict], outline_threshold: int = 40) -> list[dict]:
    """Remove near-black regions that are outlines, not actual parts.

    A part is considered an outline if its dominant color has all RGB
    channels below the outline_threshold.

    Args:
        parts: list of part dicts from extract_parts
        outline_threshold: max brightness per channel to count as outline

    Returns:
        Filtered list with outline parts removed.
    """
    filtered = []
    for part in parts:
        hex_color = part.get("color_hex", "#000000")
        # Parse hex color
        hex_str = hex_color.lstrip("#")
        if len(hex_str) == 6:
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
        else:
            r, g, b = 0, 0, 0

        # Keep the part if any channel is above the threshold
        if r > outline_threshold or g > outline_threshold or b > outline_threshold:
            filtered.append(part)

    return filtered


def segment_image(
    image_path: str,
    n_clusters: int = 5,
    min_area: int = 50,
    outline_threshold: int = 40,
) -> dict:
    """Full segmentation pipeline: cluster, extract, filter.

    Returns:
        {"parts": [...], "image_size": [w, h]}
    """
    img = cv2.imread(image_path)
    if img is None:
        return {"error": f"Could not read image: {image_path}", "parts": [], "image_size": [0, 0]}

    h, w = img.shape[:2]
    labeled, centers = segment_by_color(image_path, n_clusters)
    parts = extract_parts(labeled, img, min_area)
    parts = filter_outline_regions(parts, outline_threshold)

    # Re-number parts after filtering
    for i, part in enumerate(parts):
        part["name"] = f"part_{i}"

    return {
        "parts": parts,
        "image_size": [int(w), int(h)],
    }


# ---------------------------------------------------------------------------
# MCP Registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_part_segmenter tool."""

    @mcp.tool(
        name="adobe_ai_part_segmenter",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_part_segmenter(params: AiPartSegmenterInput) -> str:
        """Segment an image into distinct color parts using k-means clustering.

        Returns a list of detected parts with bounds, centroids, areas,
        and dominant colors. Outline regions (near-black) are filtered out.
        """
        result = segment_image(
            params.image_path,
            n_clusters=params.n_clusters,
            min_area=params.min_area,
            outline_threshold=params.outline_threshold,
        )
        return json.dumps(result, indent=2)
