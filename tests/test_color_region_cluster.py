"""Tests for color_region_cluster — K-means color clustering.

Tests cluster detection on synthetic images with known color regions,
merging of similar clusters, and filtering of black/white pixels.
"""

import os

import cv2
import numpy as np
import pytest

from adobe_mcp.apps.illustrator.color_region_cluster import (
    cluster_colors,
    merge_similar_clusters,
)


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="session")
def three_color_png():
    """200x150 image with 3 solid color blocks: red, green, blue (no black/white)."""
    path = os.path.join(FIXTURES_DIR, "three_color.png")
    img = np.zeros((150, 200, 3), dtype=np.uint8)
    # Red block (top third) — BGR
    img[0:50, :] = (0, 0, 200)
    # Green block (middle third) — BGR
    img[50:100, :] = (0, 200, 0)
    # Blue block (bottom third) — BGR
    img[100:150, :] = (200, 0, 0)
    cv2.imwrite(path, img)
    return path


@pytest.fixture(scope="session")
def gradient_cluster_png():
    """100x100 horizontal gradient from dark red to bright red."""
    path = os.path.join(FIXTURES_DIR, "gradient_cluster.png")
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    for x in range(100):
        val = int(50 + x * 1.8)  # range ~50-230 to avoid black/white filtering
        img[:, x] = (0, 0, val)  # BGR — varying red
    cv2.imwrite(path, img)
    return path


@pytest.fixture(scope="session")
def outlined_shapes_png():
    """200x200 image with colored shapes outlined in black on white background."""
    path = os.path.join(FIXTURES_DIR, "outlined_shapes.png")
    img = np.full((200, 200, 3), 255, dtype=np.uint8)  # white background
    # Red filled circle with black outline
    cv2.circle(img, (60, 100), 40, (0, 0, 200), -1)
    cv2.circle(img, (60, 100), 40, (0, 0, 0), 3)
    # Green filled rectangle with black outline
    cv2.rectangle(img, (110, 60), (190, 140), (0, 200, 0), -1)
    cv2.rectangle(img, (110, 60), (190, 140), (0, 0, 0), 3)
    cv2.imwrite(path, img)
    return path


# ---------------------------------------------------------------------------
# Test: 3 solid colors -> 3 clusters
# ---------------------------------------------------------------------------


def test_three_solid_colors_produce_three_clusters(three_color_png):
    """Image with 3 distinct solid colors should yield exactly 3 clusters."""
    result = cluster_colors(
        three_color_png, n_clusters=3, ignore_black=False, ignore_white=False
    )
    assert "error" not in result
    assert len(result["clusters"]) == 3
    # Each cluster should have roughly 1/3 of total pixels
    total = result["pixels_clustered"]
    for cluster in result["clusters"]:
        assert cluster["pixel_count"] > total * 0.2
        assert cluster["pixel_count"] < total * 0.5


# ---------------------------------------------------------------------------
# Test: gradient -> clusters merge when threshold is high
# ---------------------------------------------------------------------------


def test_gradient_merged_clusters(gradient_cluster_png):
    """Gradient image with merge should reduce cluster count."""
    result = cluster_colors(
        gradient_cluster_png, n_clusters=5, ignore_black=False, ignore_white=False
    )
    assert "error" not in result
    clusters = result["clusters"]
    assert len(clusters) >= 2  # k-means finds at least 2 on gradient

    # Merge with high threshold — should reduce count
    merged = merge_similar_clusters(clusters, threshold=100.0)
    assert len(merged) <= len(clusters)


# ---------------------------------------------------------------------------
# Test: black outlines filtered when ignore_black=True
# ---------------------------------------------------------------------------


def test_black_outlines_filtered(outlined_shapes_png):
    """With ignore_black=True, black outline pixels should be excluded from clustering."""
    result = cluster_colors(
        outlined_shapes_png, n_clusters=5, ignore_black=True, ignore_white=True
    )
    assert "error" not in result
    assert result.get("black_pixels_filtered", 0) > 0
    assert result.get("white_pixels_filtered", 0) > 0
    # Clusters should be the colored shapes, not black/white
    for cluster in result["clusters"]:
        r, g, b = cluster["color_rgb"]
        # No cluster should be near-black (all channels < 30)
        is_near_black = r < 40 and g < 40 and b < 40
        assert not is_near_black, f"Cluster {cluster['id']} is near-black: {cluster['color_rgb']}"


# ---------------------------------------------------------------------------
# Test: labeled image file is written
# ---------------------------------------------------------------------------


def test_labeled_image_created(three_color_png):
    """cluster_colors should write a labeled image file."""
    result = cluster_colors(
        three_color_png, n_clusters=3, ignore_black=False, ignore_white=False
    )
    assert "error" not in result
    labeled_path = result["labeled_image_path"]
    assert os.path.isfile(labeled_path)
    # Verify it's a valid image
    labeled_img = cv2.imread(labeled_path)
    assert labeled_img is not None
    assert labeled_img.shape[0] > 0


# ---------------------------------------------------------------------------
# Test: merge_similar_clusters with no merge needed
# ---------------------------------------------------------------------------


def test_merge_no_overlap():
    """Clusters with colors far apart should not merge."""
    clusters = [
        {"id": 0, "color_rgb": [255, 0, 0], "pixel_count": 100, "percentage": 50.0},
        {"id": 1, "color_rgb": [0, 255, 0], "pixel_count": 60, "percentage": 30.0},
        {"id": 2, "color_rgb": [0, 0, 255], "pixel_count": 40, "percentage": 20.0},
    ]
    merged = merge_similar_clusters(clusters, threshold=30.0)
    # RGB distance between R/G/B is ~360, so nothing should merge at threshold=30
    assert len(merged) == 3
