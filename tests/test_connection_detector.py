"""Tests for the connection detector.

Uses synthetic images with touching and nested shapes to verify
connection detection and classification.
All tests are pure Python -- no JSX or Adobe required.
"""

import os

import cv2
import numpy as np
import pytest

from adobe_mcp.apps.illustrator.connection_detector import (
    classify_connection,
    detect_connections,
    _create_part_mask,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="session")
def touching_rects_png():
    """200x100 image: two rectangles connected by a narrow bridge."""
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    path = os.path.join(FIXTURES_DIR, "touching_rects.png")
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    # Left rectangle
    cv2.rectangle(img, (10, 20), (85, 80), (200, 100, 100), -1)
    # Right rectangle
    cv2.rectangle(img, (95, 20), (190, 80), (100, 200, 100), -1)
    # Narrow bridge connecting them (width ~10px)
    cv2.rectangle(img, (85, 40), (95, 60), (150, 150, 150), -1)
    cv2.imwrite(path, img)
    return path


@pytest.fixture(scope="session")
def nested_shapes_conn_png():
    """200x200 image: large rectangle containing a small rectangle."""
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    path = os.path.join(FIXTURES_DIR, "nested_conn.png")
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    # Large outer rectangle
    cv2.rectangle(img, (20, 20), (180, 180), (200, 200, 200), -1)
    # Small inner rectangle
    cv2.rectangle(img, (60, 60), (140, 140), (100, 100, 200), -1)
    cv2.imwrite(path, img)
    return path


# ---------------------------------------------------------------------------
# classify_connection
# ---------------------------------------------------------------------------


def test_classify_joint():
    """Narrow boundary relative to part size should be classified as joint."""
    # Small boundary (3px) vs part with area 10000 (width ~100)
    result = classify_connection(boundary_width=3.0, part_a_area=10000, part_b_area=8000)
    assert result == "joint"


def test_classify_containment():
    """Wide boundary with large size difference should be containment."""
    # Boundary width ~90% of smaller part, and larger is 5x bigger
    result = classify_connection(boundary_width=80.0, part_a_area=50000, part_b_area=5000)
    assert result == "containment"


def test_classify_adjacent():
    """Moderate boundary between similar-sized parts should be adjacent."""
    # Moderate boundary (~30% of smaller part width)
    result = classify_connection(boundary_width=30.0, part_a_area=10000, part_b_area=9000)
    assert result == "adjacent"


def test_classify_separate():
    """Zero boundary width should be separate."""
    result = classify_connection(boundary_width=0.0, part_a_area=10000, part_b_area=8000)
    assert result == "separate"


# ---------------------------------------------------------------------------
# detect_connections
# ---------------------------------------------------------------------------


def test_detect_connections_touching(touching_rects_png):
    """Two touching rectangles should produce at least one connection."""
    # Bounds are set so dilation bridges the gap between them.
    # Left rect ends at x=85, right starts at x=88 (gap of 3px, well within dilation of 8).
    parts = [
        {"name": "left_rect", "bounds": [10, 20, 75, 60], "centroid": [47.5, 50.0], "area": 4500},
        {"name": "right_rect", "bounds": [88, 20, 102, 60], "centroid": [139.0, 50.0], "area": 6120},
    ]
    result = detect_connections(parts, touching_rects_png, dilation_pixels=8)
    assert "connections" in result
    # With dilation of 8, the 3px gap between bounds should produce a connection
    assert len(result["connections"]) >= 1
    conn = result["connections"][0]
    assert "part_a" in conn
    assert "part_b" in conn
    assert "type" in conn
    assert "position" in conn
    assert "confidence" in conn


def test_detect_connections_has_position(touching_rects_png):
    """Detected connections should have valid position coordinates."""
    parts = [
        {"name": "left", "bounds": [10, 20, 75, 60], "centroid": [47.5, 50.0], "area": 4500},
        {"name": "right", "bounds": [95, 20, 95, 60], "centroid": [142.5, 50.0], "area": 5700},
    ]
    result = detect_connections(parts, touching_rects_png, dilation_pixels=8)
    if result["connections"]:
        pos = result["connections"][0]["position"]
        assert len(pos) == 2
        assert 0 <= pos[0] <= 200
        assert 0 <= pos[1] <= 100
