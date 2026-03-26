"""Tests for the axis-guided contour scanner.

Tests pure Python scanning, edge detection, contour fitting, and coordinate
transforms using synthetic test images — no Adobe app required.
"""

import math
import os
import tempfile

import cv2
import numpy as np
import pytest

from adobe_mcp.apps.illustrator.contour_scanner import (
    _load_grayscale,
    _pixel_in_bounds,
    scan_edges_along_axis,
    fit_contour_from_edges,
    pixels_to_ai_coords,
    scan_feature,
)
from adobe_mcp.apps.illustrator.landmark_axis import compute_transform


# ---------------------------------------------------------------------------
# Helpers: synthetic test image generators
# ---------------------------------------------------------------------------


def _make_black_triangle_on_green(width=200, height=200) -> tuple[str, np.ndarray]:
    """Create a synthetic image: black filled triangle on bright green background.

    Triangle vertices: (100, 30), (40, 170), (160, 170) — a centered isosceles
    triangle occupying most of the image.

    Returns (file_path, bgr_image).
    """
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # Bright green background (0, 200, 0) in BGR
    img[:, :] = (0, 200, 0)

    # Draw filled black triangle
    pts = np.array([[100, 30], [40, 170], [160, 170]], dtype=np.int32)
    cv2.fillPoly(img, [pts], (0, 0, 0))

    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    cv2.imwrite(path, img)
    return path, img


def _make_black_circle_on_green(
    width=200, height=200, center=(100, 100), radius=50
) -> tuple[str, np.ndarray]:
    """Create a synthetic image: black filled circle on bright green background.

    Returns (file_path, bgr_image).
    """
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = (0, 200, 0)
    cv2.circle(img, center, radius, (0, 0, 0), -1)

    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    cv2.imwrite(path, img)
    return path, img


def _make_black_rect_on_green(
    width=200, height=200, rect_x=60, rect_y=60, rect_w=80, rect_h=80
) -> tuple[str, np.ndarray]:
    """Create a synthetic image: black filled rectangle on bright green background.

    Returns (file_path, bgr_image).
    """
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = (0, 200, 0)
    cv2.rectangle(
        img, (rect_x, rect_y), (rect_x + rect_w, rect_y + rect_h), (0, 0, 0), -1
    )

    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    cv2.imwrite(path, img)
    return path, img


# ---------------------------------------------------------------------------
# Test: image loading
# ---------------------------------------------------------------------------


class TestImageLoading:
    def test_load_grayscale_valid(self):
        """Loading a valid image returns a 2D grayscale array."""
        path, _ = _make_black_circle_on_green()
        try:
            gray = _load_grayscale(path)
            assert gray is not None
            assert gray.ndim == 2
            assert gray.shape == (200, 200)
        finally:
            os.unlink(path)

    def test_load_grayscale_invalid_path(self):
        """Loading from a nonexistent path returns None."""
        result = _load_grayscale("/nonexistent/path/image.png")
        assert result is None

    def test_pixel_in_bounds(self):
        """Boundary checks for pixel coordinates."""
        assert _pixel_in_bounds(0, 0, 100, 100) is True
        assert _pixel_in_bounds(99, 99, 100, 100) is True
        assert _pixel_in_bounds(100, 0, 100, 100) is False
        assert _pixel_in_bounds(-1, 0, 100, 100) is False
        assert _pixel_in_bounds(0, -1, 100, 100) is False


# ---------------------------------------------------------------------------
# Test: edge detection on synthetic images
# ---------------------------------------------------------------------------


class TestEdgeDetection:
    def test_scan_finds_edges_on_circle(self):
        """Scanning through a black circle on green detects left and right edges."""
        path, _ = _make_black_circle_on_green(
            width=200, height=200, center=(100, 100), radius=40
        )
        try:
            gray = _load_grayscale(path)
            edges = scan_edges_along_axis(
                gray,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,  # scan vertically (down in image)
                scan_start=-50.0,
                scan_end=50.0,
                scan_step=5.0,
                cross_range=60.0,
                sample_step=1.0,
                bright_threshold=80,
                dark_threshold=30,
            )
            # Should find edges on both sides of the circle
            assert len(edges["left_edges"]) > 0, "Expected left edges on the circle"
            assert len(edges["right_edges"]) > 0, "Expected right edges on the circle"
            assert edges["scan_line_count"] > 0
        finally:
            os.unlink(path)

    def test_scan_finds_edges_on_triangle(self):
        """Scanning through a black triangle on green detects transitions."""
        path, _ = _make_black_triangle_on_green()
        try:
            gray = _load_grayscale(path)
            edges = scan_edges_along_axis(
                gray,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,  # scan vertically
                scan_start=-60.0,
                scan_end=60.0,
                scan_step=3.0,
                cross_range=80.0,
                sample_step=1.0,
            )
            assert len(edges["left_edges"]) > 0
            assert len(edges["right_edges"]) > 0
        finally:
            os.unlink(path)

    def test_scan_empty_region(self):
        """Scanning a region with no features returns empty edge lists."""
        path, _ = _make_black_circle_on_green(
            width=200, height=200, center=(100, 100), radius=20
        )
        try:
            gray = _load_grayscale(path)
            # Scan far from the circle — should find no edges
            edges = scan_edges_along_axis(
                gray,
                axis_center=(10.0, 10.0),
                axis_angle_deg=0.0,
                scan_start=-5.0,
                scan_end=5.0,
                scan_step=1.0,
                cross_range=5.0,
                sample_step=1.0,
            )
            assert len(edges["left_edges"]) == 0
            assert len(edges["right_edges"]) == 0
        finally:
            os.unlink(path)

    def test_scan_rectangle_symmetric_edges(self):
        """Scanning a centered rectangle produces enter/exit edges at the rect boundaries."""
        path, _ = _make_black_rect_on_green(
            width=200, height=200, rect_x=70, rect_y=50, rect_w=60, rect_h=100
        )
        try:
            gray = _load_grayscale(path)
            # Scan vertically through the center of the rectangle
            edges = scan_edges_along_axis(
                gray,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,
                scan_start=-40.0,
                scan_end=40.0,
                scan_step=5.0,
                cross_range=50.0,
                sample_step=1.0,
            )
            # Both edge lists should have entries (rectangle has clear boundaries)
            assert len(edges["left_edges"]) > 0
            assert len(edges["right_edges"]) > 0
            # Enter and exit edges should be at different X positions
            # (they bracket the rectangle's horizontal extent)
            left_xs = [pt[0] for pt in edges["left_edges"]]
            right_xs = [pt[0] for pt in edges["right_edges"]]
            avg_left = sum(left_xs) / len(left_xs)
            avg_right = sum(right_xs) / len(right_xs)
            # The two edge sets should be separated (on opposite sides of the rect)
            assert abs(avg_left - avg_right) > 30, (
                f"Enter/exit edges should be well separated: "
                f"avg_left={avg_left:.1f}, avg_right={avg_right:.1f}"
            )
        finally:
            os.unlink(path)

    def test_horizontal_scan_on_circle(self):
        """Scanning horizontally (axis_angle=0) also detects edges correctly."""
        path, _ = _make_black_circle_on_green(
            width=200, height=200, center=(100, 100), radius=40
        )
        try:
            gray = _load_grayscale(path)
            edges = scan_edges_along_axis(
                gray,
                axis_center=(100.0, 100.0),
                axis_angle_deg=0.0,  # horizontal main axis
                scan_start=-50.0,
                scan_end=50.0,
                scan_step=5.0,
                cross_range=60.0,
                sample_step=1.0,
            )
            assert len(edges["left_edges"]) > 0
            assert len(edges["right_edges"]) > 0
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Test: contour fitting
# ---------------------------------------------------------------------------


class TestContourFitting:
    def test_fit_contour_produces_anchors(self):
        """fit_contour_from_edges produces a reasonable anchor count from edge points."""
        # Simulate edge points from a half-circle (left side)
        angles = np.linspace(math.pi / 2, -math.pi / 2, 30)
        radius = 40.0
        center = (100.0, 100.0)
        left_edges = [
            [center[0] + radius * math.cos(a), center[1] + radius * math.sin(a)]
            for a in angles
        ]
        right_edges = [
            [center[0] - radius * math.cos(a), center[1] + radius * math.sin(a)]
            for a in angles
        ]

        result = fit_contour_from_edges(left_edges, right_edges, error_threshold=3.0)
        assert result["anchor_count"] > 0
        assert len(result["contour_points"]) > 0

    def test_fit_contour_fewer_anchors_than_inputs(self):
        """Curve fitting reduces the number of anchor points from raw edge data.

        The bezier fitter groups points into segments. Each segment junction
        shares an anchor with the next, so total anchors = segments + 1.
        For smooth curves, this should be significantly fewer than the raw
        input point count.
        """
        # 80 points along a smooth quarter-circle arc
        t_vals = np.linspace(0, math.pi / 2, 80)
        radius = 60.0
        left_edges = [
            [100 + radius * math.cos(t), 100 + radius * math.sin(t)]
            for t in t_vals
        ]
        right_edges = [
            [100 - radius * math.cos(t), 100 + radius * math.sin(t)]
            for t in t_vals
        ]

        result = fit_contour_from_edges(
            left_edges, right_edges, error_threshold=5.0, max_segments=10
        )
        # With max_segments=10 per edge (20 total), anchors should be well under 160
        assert result["anchor_count"] < 80, (
            f"Expected significant reduction, got {result['anchor_count']} anchors "
            f"from 160 input points"
        )

    def test_fit_contour_empty_input(self):
        """Empty edge lists produce zero anchors."""
        result = fit_contour_from_edges([], [])
        assert result["anchor_count"] == 0
        assert result["contour_points"] == []

    def test_fit_contour_single_edge(self):
        """Single point edges are handled gracefully."""
        result = fit_contour_from_edges([[50.0, 50.0]], [[150.0, 50.0]])
        assert result["anchor_count"] == 2
        assert len(result["contour_points"]) == 2

    def test_fit_contour_closed_ordering(self):
        """Closed contour starts with left edges and ends with reversed right edges."""
        left_edges = [[10.0, 0.0], [10.0, 50.0], [10.0, 100.0]]
        right_edges = [[90.0, 0.0], [90.0, 50.0], [90.0, 100.0]]

        result = fit_contour_from_edges(
            left_edges, right_edges, error_threshold=5.0, closed=True
        )
        contour = result["contour_points"]
        # First point should be near the start of left edges
        assert len(contour) > 0
        # Last points should come from reversed right edges (near 90, 0)
        last_pt = contour[-1]
        # The last anchor from the reversed right edges should be near (90, 0)
        assert last_pt[0] > 50.0, "Last contour point should come from right edges"


# ---------------------------------------------------------------------------
# Test: coordinate transforms
# ---------------------------------------------------------------------------


class TestCoordinateTransforms:
    def test_pixels_to_ai_fallback(self):
        """Without a transform, pixels_to_ai uses simple Y-flip."""
        points = [[100.0, 50.0], [200.0, 150.0]]
        ai = pixels_to_ai_coords(points, transform=None)
        assert ai[0] == [100.0, -50.0]
        assert ai[1] == [200.0, -150.0]

    def test_pixels_to_ai_with_transform(self):
        """With a computed transform, pixel coords map correctly to AI space."""
        # 200x200 image on a 200x200 artboard at origin
        transform = compute_transform(200, 200, 0.0, 200.0, 200.0, 0.0)
        points = [[0.0, 0.0], [100.0, 100.0], [200.0, 200.0]]
        ai = pixels_to_ai_coords(points, transform)

        # Pixel (0,0) = top-left -> AI (0, 200) = top-left
        assert ai[0][0] == pytest.approx(0.0, abs=1.0)
        assert ai[0][1] == pytest.approx(200.0, abs=1.0)

        # Pixel (100,100) = center -> AI (100, 100)
        assert ai[1][0] == pytest.approx(100.0, abs=1.0)
        assert ai[1][1] == pytest.approx(100.0, abs=1.0)

        # Pixel (200,200) = bottom-right -> AI (200, 0)
        assert ai[2][0] == pytest.approx(200.0, abs=1.0)
        assert ai[2][1] == pytest.approx(0.0, abs=1.0)

    def test_transform_preserves_relative_positions(self):
        """Points that are equidistant in pixel space stay equidistant in AI space."""
        transform = compute_transform(400, 400, 0.0, 400.0, 400.0, 0.0)
        points = [[100.0, 100.0], [200.0, 100.0], [300.0, 100.0]]
        ai = pixels_to_ai_coords(points, transform)

        # All three points share the same Y in pixel space, so should share AI Y
        assert ai[0][1] == pytest.approx(ai[1][1], abs=0.1)
        assert ai[1][1] == pytest.approx(ai[2][1], abs=0.1)

        # X spacing should be preserved (100px apart)
        dx_01 = ai[1][0] - ai[0][0]
        dx_12 = ai[2][0] - ai[1][0]
        assert dx_01 == pytest.approx(dx_12, abs=0.1)


# ---------------------------------------------------------------------------
# Test: full scan_feature pipeline
# ---------------------------------------------------------------------------


class TestScanFeaturePipeline:
    def test_scan_feature_circle(self):
        """Full pipeline on a black circle returns a contour with reasonable anchors."""
        path, _ = _make_black_circle_on_green(
            width=200, height=200, center=(100, 100), radius=40
        )
        try:
            result = scan_feature(
                image_path=path,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,
                scan_start=-50.0,
                scan_end=50.0,
                scan_step=3.0,
                cross_range=60.0,
                sample_step=1.0,
                error_threshold=3.0,
                closed=True,
            )
            assert "error" not in result or result.get("contour_points")
            assert result["anchor_count"] > 2
            # A circle contour should have more than 4 anchors for reasonable fidelity
            assert result["scan_line_count"] > 10
        finally:
            os.unlink(path)

    def test_scan_feature_triangle(self):
        """Full pipeline on a black triangle finds edges along axis."""
        path, _ = _make_black_triangle_on_green()
        try:
            result = scan_feature(
                image_path=path,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,
                scan_start=-60.0,
                scan_end=60.0,
                scan_step=3.0,
                cross_range=80.0,
                sample_step=1.0,
            )
            assert result["anchor_count"] > 0
            assert len(result["left_edges"]) > 0
            assert len(result["right_edges"]) > 0
        finally:
            os.unlink(path)

    def test_scan_feature_invalid_image(self):
        """scan_feature with a bad image path returns an error."""
        result = scan_feature(
            image_path="/nonexistent/image.png",
            axis_center=(0.0, 0.0),
            axis_angle_deg=0.0,
        )
        assert "error" in result

    def test_scan_feature_no_edges_in_region(self):
        """scan_feature on a region with no features returns an error/empty result."""
        path, _ = _make_black_circle_on_green(
            width=200, height=200, center=(100, 100), radius=20
        )
        try:
            result = scan_feature(
                image_path=path,
                axis_center=(10.0, 10.0),
                axis_angle_deg=0.0,
                scan_start=-5.0,
                scan_end=5.0,
                scan_step=1.0,
                cross_range=5.0,
                sample_step=1.0,
            )
            assert "error" in result
        finally:
            os.unlink(path)

    def test_scan_feature_contour_encloses_feature(self):
        """The scanned contour points should roughly enclose the feature region."""
        path, _ = _make_black_circle_on_green(
            width=200, height=200, center=(100, 100), radius=35
        )
        try:
            result = scan_feature(
                image_path=path,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,
                scan_start=-45.0,
                scan_end=45.0,
                scan_step=2.0,
                cross_range=50.0,
                sample_step=1.0,
                error_threshold=3.0,
                closed=True,
            )
            if result.get("contour_points"):
                xs = [pt[0] for pt in result["contour_points"]]
                ys = [pt[1] for pt in result["contour_points"]]
                # Contour should span roughly the circle's width (2*35 = 70px)
                x_span = max(xs) - min(xs)
                y_span = max(ys) - min(ys)
                assert x_span > 40, f"X span {x_span} too narrow for r=35 circle"
                assert y_span > 40, f"Y span {y_span} too narrow for r=35 circle"
                # Contour center should be near the circle center
                cx = (max(xs) + min(xs)) / 2
                cy = (max(ys) + min(ys)) / 2
                assert abs(cx - 100) < 20, f"Contour center X={cx} too far from 100"
                assert abs(cy - 100) < 20, f"Contour center Y={cy} too far from 100"
        finally:
            os.unlink(path)
