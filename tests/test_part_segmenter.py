"""Tests for the CV-based part segmenter.

Uses synthetic images with distinct colored rectangles to verify
segmentation, part extraction, and outline filtering.
All tests are pure Python -- no JSX or Adobe required.
"""

import os

import cv2
import numpy as np
import pytest

from adobe_mcp.apps.illustrator.part_segmenter import (
    segment_by_color,
    extract_parts,
    filter_outline_regions,
    segment_image,
)


# ---------------------------------------------------------------------------
# Fixtures: synthetic images with distinct colored regions
# ---------------------------------------------------------------------------


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="session")
def three_color_rects_png():
    """200x200 image with 3 distinct colored rectangles on black background.

    Red rectangle at top-left, green at top-right, blue at bottom-center.
    """
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    path = os.path.join(FIXTURES_DIR, "three_color_rects.png")
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    # Red rectangle (BGR: 0, 0, 255) at top-left
    cv2.rectangle(img, (10, 10), (80, 80), (0, 0, 255), -1)
    # Green rectangle (BGR: 0, 255, 0) at top-right
    cv2.rectangle(img, (120, 10), (190, 80), (0, 255, 0), -1)
    # Blue rectangle (BGR: 255, 0, 0) at bottom-center
    cv2.rectangle(img, (60, 120), (140, 190), (255, 0, 0), -1)
    cv2.imwrite(path, img)
    return path


@pytest.fixture(scope="session")
def outline_image_png():
    """200x200 image with colored shapes and black outlines."""
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    path = os.path.join(FIXTURES_DIR, "outline_shapes.png")
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    # White rectangle with black outline
    cv2.rectangle(img, (40, 40), (160, 160), (255, 255, 255), -1)
    cv2.rectangle(img, (40, 40), (160, 160), (10, 10, 10), 3)
    cv2.imwrite(path, img)
    return path


# ---------------------------------------------------------------------------
# segment_by_color
# ---------------------------------------------------------------------------


def test_segment_by_color_returns_labels(three_color_rects_png):
    """segment_by_color should return labeled image and cluster centers."""
    labeled, centers = segment_by_color(three_color_rects_png, n_clusters=4)
    assert labeled.shape == (200, 200)
    assert centers.shape[0] == 4
    assert centers.shape[1] == 3
    # Should have multiple distinct labels
    unique = np.unique(labeled)
    assert len(unique) >= 2


# ---------------------------------------------------------------------------
# extract_parts
# ---------------------------------------------------------------------------


def test_extract_parts_finds_three_rectangles(three_color_rects_png):
    """extract_parts should find 3 distinct colored regions."""
    labeled, centers = segment_by_color(three_color_rects_png, n_clusters=4)
    img = cv2.imread(three_color_rects_png)
    parts = extract_parts(labeled, img, min_area=100)

    # Filter out black background parts
    non_black = [p for p in parts if p["color_hex"] != "#000000"]
    # Should find at least 3 non-background parts (the colored rectangles)
    assert len(non_black) >= 3


def test_extract_parts_has_correct_fields(three_color_rects_png):
    """Each extracted part should have all required fields."""
    labeled, centers = segment_by_color(three_color_rects_png, n_clusters=4)
    img = cv2.imread(three_color_rects_png)
    parts = extract_parts(labeled, img, min_area=100)

    assert len(parts) > 0
    for part in parts:
        assert "name" in part
        assert "bounds" in part
        assert len(part["bounds"]) == 4
        assert "centroid" in part
        assert len(part["centroid"]) == 2
        assert "area" in part
        assert part["area"] > 0
        assert "color_hex" in part
        assert part["color_hex"].startswith("#")


# ---------------------------------------------------------------------------
# filter_outline_regions
# ---------------------------------------------------------------------------


def test_filter_outline_regions_removes_black():
    """filter_outline_regions should remove near-black parts."""
    parts = [
        {"name": "outline", "color_hex": "#0a0a0a", "area": 500},
        {"name": "body", "color_hex": "#ff5500", "area": 1000},
        {"name": "dark_outline", "color_hex": "#1a1a1a", "area": 200},
    ]
    filtered = filter_outline_regions(parts, outline_threshold=40)
    names = [p["name"] for p in filtered]
    assert "body" in names
    assert "outline" not in names
    assert "dark_outline" not in names


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def test_segment_image_full_pipeline(three_color_rects_png):
    """segment_image should return parts with image_size."""
    result = segment_image(three_color_rects_png, n_clusters=4, min_area=100)
    assert "parts" in result
    assert "image_size" in result
    assert result["image_size"] == [200, 200]
    # Should have detected the colored rectangles (outline-filtered)
    assert len(result["parts"]) >= 3


def test_segment_image_invalid_path():
    """segment_image should handle missing files gracefully."""
    result = segment_image("/nonexistent/image.png")
    assert "error" in result
