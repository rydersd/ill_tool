"""K-means color clustering to identify distinct color regions in an image.

Reshapes image pixels, runs k-means clustering, filters outline/background
colors, and returns labeled cluster data with centroid colors and pixel counts.

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


class AiColorRegionClusterInput(BaseModel):
    """K-means color clustering for distinct part identification."""
    model_config = ConfigDict(str_strip_whitespace=True)
    image_path: str = Field(..., description="Path to the image to cluster")
    n_clusters: int = Field(
        default=5, description="Number of k-means clusters", ge=2, le=20
    )
    ignore_black: bool = Field(
        default=True,
        description="Filter near-black pixels (outlines) before clustering",
    )
    ignore_white: bool = Field(
        default=True,
        description="Filter near-white pixels (background) before clustering",
    )
    black_threshold: int = Field(
        default=30,
        description="RGB magnitude below this is considered black",
        ge=0, le=128,
    )
    white_threshold: int = Field(
        default=225,
        description="RGB value above this (all channels) is considered white",
        ge=128, le=255,
    )
    merge_threshold: float = Field(
        default=0.0,
        description="If > 0, merge clusters within this RGB Euclidean distance",
        ge=0.0,
    )


# ---------------------------------------------------------------------------
# Core clustering functions
# ---------------------------------------------------------------------------


def cluster_colors(
    image_path: str,
    n_clusters: int = 5,
    ignore_black: bool = True,
    ignore_white: bool = True,
    black_threshold: int = 30,
    white_threshold: int = 225,
) -> dict:
    """Run k-means color clustering on an image.

    Args:
        image_path: path to the input image
        n_clusters: number of clusters for k-means
        ignore_black: whether to filter near-black pixels before clustering
        ignore_white: whether to filter near-white pixels before clustering
        black_threshold: max RGB magnitude to count as black
        white_threshold: min per-channel value to count as white

    Returns:
        dict with clusters list, labeled_image_path, and filtered pixel counts.
    """
    img = cv2.imread(image_path)
    if img is None:
        return {"error": f"Could not read image: {image_path}"}

    h, w = img.shape[:2]
    # Convert BGR -> RGB for consistent color reporting
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Flatten to (N, 3)
    pixels = img_rgb.reshape(-1, 3).astype(np.float32)
    total_pixels = len(pixels)

    # Build a mask of pixels to keep for clustering
    keep_mask = np.ones(total_pixels, dtype=bool)
    filtered_info = {}

    if ignore_black:
        # Magnitude of RGB vector; near-black has low magnitude
        magnitudes = np.sqrt(np.sum(pixels ** 2, axis=1))
        black_mask = magnitudes < (black_threshold * math.sqrt(3))
        filtered_info["black_pixels_filtered"] = int(np.sum(black_mask))
        keep_mask &= ~black_mask

    if ignore_white:
        white_mask = np.all(pixels > white_threshold, axis=1)
        filtered_info["white_pixels_filtered"] = int(np.sum(white_mask))
        keep_mask &= ~white_mask

    kept_pixels = pixels[keep_mask]

    if len(kept_pixels) == 0:
        return {
            "error": "All pixels filtered out — image may be pure black/white",
            "total_pixels": total_pixels,
            **filtered_info,
        }

    # Adjust n_clusters if we have fewer unique colors
    unique_colors = np.unique(kept_pixels, axis=0)
    effective_k = min(n_clusters, len(unique_colors))

    # Run k-means
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    _, labels, centers = cv2.kmeans(
        kept_pixels, effective_k, None, criteria, 10, cv2.KMEANS_PP_CENTERS
    )
    labels = labels.flatten()
    centers = centers.astype(int)

    # Build cluster info
    clusters = []
    for i in range(effective_k):
        mask_i = labels == i
        count = int(np.sum(mask_i))
        color = centers[i].tolist()
        clusters.append({
            "id": i,
            "color_rgb": color,
            "pixel_count": count,
            "percentage": round(count / len(kept_pixels) * 100, 2),
        })

    # Sort by pixel count descending
    clusters.sort(key=lambda c: c["pixel_count"], reverse=True)
    # Reassign IDs after sorting
    for idx, c in enumerate(clusters):
        c["id"] = idx

    # Build labeled image: assign each pixel a cluster color (or black/white for filtered)
    labeled_flat = np.zeros((total_pixels, 3), dtype=np.uint8)
    kept_indices = np.where(keep_mask)[0]
    for i, idx in enumerate(kept_indices):
        labeled_flat[idx] = centers[labels[i]]

    # Write labeled image
    labeled_img = labeled_flat.reshape(h, w, 3)
    labeled_img_bgr = cv2.cvtColor(labeled_img, cv2.COLOR_RGB2BGR)
    labeled_path = os.path.splitext(image_path)[0] + "_clustered.png"
    cv2.imwrite(labeled_path, labeled_img_bgr)

    return {
        "clusters": clusters,
        "n_clusters_requested": n_clusters,
        "n_clusters_found": effective_k,
        "labeled_image_path": labeled_path,
        "image_size": [w, h],
        "total_pixels": total_pixels,
        "pixels_clustered": int(np.sum(keep_mask)),
        **filtered_info,
    }


def merge_similar_clusters(clusters: list[dict], threshold: float = 30.0) -> list[dict]:
    """Merge clusters whose RGB centroids are within a Euclidean distance threshold.

    Args:
        clusters: list of cluster dicts with color_rgb and pixel_count
        threshold: max Euclidean RGB distance to consider clusters similar

    Returns:
        merged list of clusters with updated pixel counts and averaged colors.
    """
    if not clusters:
        return []

    merged = []
    used = set()

    for i, ca in enumerate(clusters):
        if i in used:
            continue

        # Start a merge group with this cluster
        group_colors = [np.array(ca["color_rgb"], dtype=np.float64)]
        group_counts = [ca["pixel_count"]]
        used.add(i)

        for j, cb in enumerate(clusters):
            if j in used:
                continue
            dist = np.linalg.norm(
                np.array(ca["color_rgb"], dtype=np.float64)
                - np.array(cb["color_rgb"], dtype=np.float64)
            )
            if dist <= threshold:
                group_colors.append(np.array(cb["color_rgb"], dtype=np.float64))
                group_counts.append(cb["pixel_count"])
                used.add(j)

        # Compute weighted average color
        total_count = sum(group_counts)
        weighted_color = np.zeros(3, dtype=np.float64)
        for color, count in zip(group_colors, group_counts):
            weighted_color += color * count
        weighted_color /= total_count

        merged.append({
            "id": len(merged),
            "color_rgb": [int(round(c)) for c in weighted_color.tolist()],
            "pixel_count": total_count,
            "percentage": 0.0,  # recalculated below
        })

    # Recalculate percentages
    grand_total = sum(c["pixel_count"] for c in merged)
    if grand_total > 0:
        for c in merged:
            c["percentage"] = round(c["pixel_count"] / grand_total * 100, 2)

    return merged


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_color_region_cluster tool."""

    @mcp.tool(
        name="adobe_ai_color_region_cluster",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_color_region_cluster(params: AiColorRegionClusterInput) -> str:
        """K-means color clustering to identify distinct color regions.

        Clusters image pixels by color, filters outlines (black) and background
        (white), and returns cluster centroids with pixel counts and a labeled image.
        Optionally merges similar clusters by RGB distance.
        """
        if not os.path.isfile(params.image_path):
            return json.dumps({"error": f"Image not found: {params.image_path}"})

        result = cluster_colors(
            params.image_path,
            n_clusters=params.n_clusters,
            ignore_black=params.ignore_black,
            ignore_white=params.ignore_white,
            black_threshold=params.black_threshold,
            white_threshold=params.white_threshold,
        )

        if "error" in result:
            return json.dumps(result)

        # Optionally merge similar clusters
        if params.merge_threshold > 0 and result.get("clusters"):
            result["clusters_before_merge"] = len(result["clusters"])
            result["clusters"] = merge_similar_clusters(
                result["clusters"], params.merge_threshold
            )
            result["clusters_after_merge"] = len(result["clusters"])

        return json.dumps(result, indent=2)
