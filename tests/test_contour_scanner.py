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
    _compute_gradient_magnitude,
    _find_gradient_peaks,
    scan_edges_along_axis,
    scan_edges_gradient,
    _check_boundary_clipping,
    scan_feature_adaptive,
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


# ---------------------------------------------------------------------------
# Helpers: synthetic test images for high-fill / gradient scanning
# ---------------------------------------------------------------------------


def _make_dark_on_dark(
    width=200, height=200, center=(100, 100), radius=40,
    bg_brightness=50, fg_brightness=10,
) -> tuple[str, np.ndarray]:
    """Create a dark circle on a slightly lighter dark background.

    Both regions fall below bright_threshold (80), so threshold-based scanning
    finds no transitions. But gradient-based scanning detects the edge between
    the two dark regions via the brightness gradient.

    Returns (file_path, bgr_image).
    """
    img = np.full((height, width, 3), bg_brightness, dtype=np.uint8)
    cv2.circle(img, center, radius, (fg_brightness, fg_brightness, fg_brightness), -1)

    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    cv2.imwrite(path, img)
    return path, img


def _make_complex_silhouette(width=200, height=300) -> tuple[str, np.ndarray]:
    """Create a complex multi-part silhouette: torso + limb on bright background.

    Simulates a mech body where torso is a large rectangle and an arm extends
    at an angle. The arm overlaps the torso, creating a region where threshold
    scanning sees uniform dark (high fill) but gradient scanning finds the
    actual arm edge within the dark region.

    Returns (file_path, bgr_image).
    """
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = (0, 200, 0)  # Green background

    # Torso: dark rectangle filling center
    cv2.rectangle(img, (60, 50), (140, 250), (15, 15, 15), -1)

    # Arm: slightly different dark tone, overlapping torso edge
    arm_pts = np.array([
        [50, 100], [30, 180], [70, 190], [90, 110]
    ], dtype=np.int32)
    cv2.fillPoly(img, [arm_pts], (35, 35, 35))

    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    cv2.imwrite(path, img)
    return path, img


def _make_star_shape(width=200, height=200, center=(100, 100),
                     outer_r=60, inner_r=25, n_points=5) -> tuple[str, np.ndarray]:
    """Create a black star shape on green background.

    Stars have deep concavities that simple bounding boxes miss — this tests
    whether the scanner captures non-convex silhouettes.

    Returns (file_path, bgr_image).
    """
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = (0, 200, 0)

    angles = []
    for i in range(n_points * 2):
        angle = (i * math.pi / n_points) - math.pi / 2
        r = outer_r if i % 2 == 0 else inner_r
        x = int(center[0] + r * math.cos(angle))
        y = int(center[1] + r * math.sin(angle))
        angles.append([x, y])

    pts = np.array(angles, dtype=np.int32)
    cv2.fillPoly(img, [pts], (0, 0, 0))

    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    cv2.imwrite(path, img)
    return path, img


# ---------------------------------------------------------------------------
# Test: gradient magnitude and peak detection
# ---------------------------------------------------------------------------


class TestGradientUtilities:
    def test_gradient_magnitude_shape(self):
        """Gradient magnitude has the same shape as input."""
        gray = np.zeros((100, 100), dtype=np.uint8)
        grad = _compute_gradient_magnitude(gray)
        assert grad.shape == (100, 100)

    def test_gradient_magnitude_detects_edge(self):
        """Gradient magnitude is high at brightness discontinuities."""
        gray = np.zeros((100, 100), dtype=np.uint8)
        gray[:, 50:] = 200  # Sharp vertical edge at x=50
        grad = _compute_gradient_magnitude(gray)
        # Gradient should peak near the vertical edge
        edge_grad = grad[50, 50]  # At the edge
        flat_grad = grad[50, 25]  # In uniform region
        assert edge_grad > flat_grad * 5, (
            f"Edge gradient {edge_grad:.1f} should be much higher than "
            f"flat gradient {flat_grad:.1f}"
        )

    def test_gradient_on_circle_boundary(self):
        """Gradient magnitude is high around a circle boundary."""
        gray = np.full((200, 200), 50, dtype=np.uint8)
        cv2.circle(gray, (100, 100), 40, 10, -1)
        grad = _compute_gradient_magnitude(gray)
        # Sample gradient at the circle edge (~radius 40 from center)
        edge_val = grad[100, 140]  # Right edge of circle
        interior_val = grad[100, 100]  # Center (uniform)
        assert edge_val > interior_val * 2, (
            f"Circle edge gradient {edge_val:.1f} should exceed "
            f"interior {interior_val:.1f}"
        )

    def test_find_gradient_peaks_basic(self):
        """Peak finder locates local maxima above threshold."""
        signal = np.array([0, 5, 50, 5, 0, 3, 80, 3, 0])
        peaks = _find_gradient_peaks(signal, threshold=20.0, min_distance=1)
        assert 2 in peaks, "Should find peak at index 2 (value 50)"
        assert 6 in peaks, "Should find peak at index 6 (value 80)"

    def test_find_gradient_peaks_below_threshold(self):
        """Peaks below threshold are not returned."""
        signal = np.array([0, 5, 10, 5, 0])
        peaks = _find_gradient_peaks(signal, threshold=20.0)
        assert len(peaks) == 0

    def test_find_gradient_peaks_min_distance(self):
        """Peaks closer than min_distance are filtered."""
        signal = np.array([0, 50, 60, 55, 0, 0])
        peaks = _find_gradient_peaks(signal, threshold=20.0, min_distance=3)
        # Indices 1, 2, 3 are all peaks but within min_distance=3 of each other
        assert len(peaks) <= 2


# ---------------------------------------------------------------------------
# Test: gradient-based edge scanning
# ---------------------------------------------------------------------------


class TestGradientEdgeDetection:
    def test_gradient_scan_finds_circle_edges(self):
        """Gradient scanning detects edges on a black circle (high contrast)."""
        path, _ = _make_black_circle_on_green(
            width=200, height=200, center=(100, 100), radius=40
        )
        try:
            gray = _load_grayscale(path)
            edges = scan_edges_gradient(
                gray,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,
                scan_start=-50.0,
                scan_end=50.0,
                scan_step=5.0,
                cross_range=60.0,
                sample_step=1.0,
                gradient_threshold=20.0,
            )
            assert len(edges["left_edges"]) > 0, "Should find left edges"
            assert len(edges["right_edges"]) > 0, "Should find right edges"
        finally:
            os.unlink(path)

    def test_gradient_scan_dark_on_dark(self):
        """Gradient scanning finds edges between two dark regions.

        This is the key test: threshold mode fails here (both regions below
        bright_threshold), but gradient mode detects the brightness step.
        """
        path, _ = _make_dark_on_dark(
            width=200, height=200, center=(100, 100), radius=40,
            bg_brightness=50, fg_brightness=10,
        )
        try:
            gray = _load_grayscale(path)

            # Threshold mode should find NO edges (both < bright_threshold=80)
            threshold_edges = scan_edges_along_axis(
                gray,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,
                scan_start=-50.0,
                scan_end=50.0,
                scan_step=5.0,
                cross_range=60.0,
                sample_step=1.0,
                bright_threshold=80,
                dark_threshold=30,
            )
            assert len(threshold_edges["left_edges"]) == 0, (
                "Threshold mode should find no edges on dark-on-dark"
            )

            # Gradient mode SHOULD find edges (brightness step 50→10 = gradient)
            gradient_edges = scan_edges_gradient(
                gray,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,
                scan_start=-50.0,
                scan_end=50.0,
                scan_step=5.0,
                cross_range=60.0,
                sample_step=1.0,
                gradient_threshold=10.0,
            )
            assert len(gradient_edges["left_edges"]) > 0, (
                "Gradient mode should find edges on dark-on-dark"
            )
            assert len(gradient_edges["right_edges"]) > 0
        finally:
            os.unlink(path)

    def test_gradient_scan_contour_shape(self):
        """Gradient-scanned circle edges should be well-separated and span the circle."""
        path, _ = _make_black_circle_on_green(
            width=200, height=200, center=(100, 100), radius=40
        )
        try:
            gray = _load_grayscale(path)
            edges = scan_edges_gradient(
                gray,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,
                scan_start=-50.0,
                scan_end=50.0,
                scan_step=3.0,
                cross_range=60.0,
                sample_step=1.0,
                gradient_threshold=20.0,
            )
            # "Left" and "right" refer to scan direction (first/last peak),
            # not spatial position. They should be well-separated and bracket
            # the circle diameter.
            left_xs = [pt[0] for pt in edges["left_edges"]]
            right_xs = [pt[0] for pt in edges["right_edges"]]
            if left_xs and right_xs:
                avg_left = sum(left_xs) / len(left_xs)
                avg_right = sum(right_xs) / len(right_xs)
                span = abs(avg_right - avg_left)
                assert span > 50, (
                    f"Edge span {span:.1f} too narrow for r=40 circle "
                    f"(left avg={avg_left:.1f}, right avg={avg_right:.1f})"
                )
        finally:
            os.unlink(path)

    def test_gradient_scan_empty_region(self):
        """Gradient scan of uniform region returns no edges."""
        # Uniform gray image — no gradients anywhere
        gray = np.full((200, 200), 128, dtype=np.uint8)
        edges = scan_edges_gradient(
            gray,
            axis_center=(100.0, 100.0),
            axis_angle_deg=90.0,
            scan_start=-50.0,
            scan_end=50.0,
            scan_step=5.0,
            cross_range=60.0,
            sample_step=1.0,
            gradient_threshold=20.0,
        )
        assert len(edges["left_edges"]) == 0
        assert len(edges["right_edges"]) == 0


# ---------------------------------------------------------------------------
# Test: boundary clipping detection
# ---------------------------------------------------------------------------


class TestBoundaryClipping:
    def test_no_clipping_on_centered_feature(self):
        """A feature well inside the scan window shows low clipping ratio."""
        path, _ = _make_black_circle_on_green(
            width=200, height=200, center=(100, 100), radius=20
        )
        try:
            gray = _load_grayscale(path)
            edges = scan_edges_along_axis(
                gray,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,
                scan_start=-30.0,
                scan_end=30.0,
                scan_step=5.0,
                cross_range=60.0,  # Much wider than the r=20 circle
                sample_step=1.0,
            )
            clip_ratio = _check_boundary_clipping(
                edges, cross_range=60.0,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,
            )
            assert clip_ratio < 0.3, (
                f"Small circle should not be clipped, got ratio={clip_ratio:.2f}"
            )
        finally:
            os.unlink(path)

    def test_high_clipping_when_no_transitions(self):
        """When scan finds no transitions (high fill), clipping ratio is 1.0."""
        edges = {
            "left_edges": [],
            "right_edges": [],
            "all_transitions": [],
            "scan_line_count": 10,
        }
        clip_ratio = _check_boundary_clipping(
            edges, cross_range=60.0,
            axis_center=(100.0, 100.0),
            axis_angle_deg=90.0,
        )
        assert clip_ratio == 1.0


# ---------------------------------------------------------------------------
# Test: adaptive scanning
# ---------------------------------------------------------------------------


class TestAdaptiveScanning:
    def test_adaptive_uses_threshold_for_high_contrast(self):
        """Adaptive scan uses threshold mode for clear black-on-green features."""
        path, _ = _make_black_circle_on_green(
            width=200, height=200, center=(100, 100), radius=30
        )
        try:
            result = scan_feature_adaptive(
                image_path=path,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,
                scan_start=-40.0,
                scan_end=40.0,
                scan_step=3.0,
                cross_range=50.0,
                sample_step=1.0,
            )
            assert result.get("mode") == "threshold", (
                f"Expected threshold mode, got {result.get('mode')}"
            )
            assert result["anchor_count"] > 0
        finally:
            os.unlink(path)

    def test_adaptive_falls_back_to_gradient_for_dark_on_dark(self):
        """Adaptive scan switches to gradient mode when threshold finds nothing."""
        path, _ = _make_dark_on_dark(
            width=200, height=200, center=(100, 100), radius=40,
            bg_brightness=50, fg_brightness=10,
        )
        try:
            result = scan_feature_adaptive(
                image_path=path,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,
                scan_start=-50.0,
                scan_end=50.0,
                scan_step=3.0,
                cross_range=60.0,
                sample_step=1.0,
                gradient_threshold=10.0,
            )
            assert result.get("mode") == "gradient", (
                f"Expected gradient fallback, got {result.get('mode')}"
            )
            assert result["anchor_count"] > 0, "Gradient mode should produce anchors"
        finally:
            os.unlink(path)

    def test_adaptive_gradient_contour_encloses_feature(self):
        """Gradient-mode contour should roughly enclose the dark-on-dark circle."""
        path, _ = _make_dark_on_dark(
            width=200, height=200, center=(100, 100), radius=35,
            bg_brightness=60, fg_brightness=10,
        )
        try:
            result = scan_feature_adaptive(
                image_path=path,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,
                scan_start=-45.0,
                scan_end=45.0,
                scan_step=2.0,
                cross_range=60.0,
                sample_step=1.0,
                gradient_threshold=10.0,
                error_threshold=3.0,
            )
            assert result.get("contour_points"), "Should produce contour points"
            xs = [pt[0] for pt in result["contour_points"]]
            ys = [pt[1] for pt in result["contour_points"]]
            x_span = max(xs) - min(xs)
            y_span = max(ys) - min(ys)
            assert x_span > 40, f"X span {x_span:.1f} too narrow for r=35 circle"
            assert y_span > 40, f"Y span {y_span:.1f} too narrow for r=35 circle"
            cx = (max(xs) + min(xs)) / 2
            cy = (max(ys) + min(ys)) / 2
            assert abs(cx - 100) < 20, f"Center X={cx:.1f} too far from 100"
            assert abs(cy - 100) < 20, f"Center Y={cy:.1f} too far from 100"
        finally:
            os.unlink(path)

    def test_adaptive_invalid_image(self):
        """Adaptive scan with bad image path returns error."""
        result = scan_feature_adaptive(
            image_path="/nonexistent/image.png",
            axis_center=(0.0, 0.0),
            axis_angle_deg=0.0,
        )
        assert "error" in result

    def test_star_shape_captures_concavities(self):
        """Scanner on a star captures non-convex contour, not a bounding box."""
        path, _ = _make_star_shape(
            width=200, height=200, center=(100, 100),
            outer_r=60, inner_r=25, n_points=5,
        )
        try:
            result = scan_feature_adaptive(
                image_path=path,
                axis_center=(100.0, 100.0),
                axis_angle_deg=90.0,
                scan_start=-70.0,
                scan_end=70.0,
                scan_step=2.0,
                cross_range=80.0,
                sample_step=1.0,
                error_threshold=2.0,
            )
            assert result["anchor_count"] > 4, (
                f"Star contour should need >4 anchors, got {result['anchor_count']}"
            )
            # The left/right edges should show variation (concavities)
            # not straight lines like a bounding box
            if result.get("left_edges") and len(result["left_edges"]) > 5:
                left_xs = [pt[0] for pt in result["left_edges"]]
                x_variance = np.var(left_xs)
                assert x_variance > 10, (
                    f"Star left edge X variance {x_variance:.1f} too low — "
                    f"looks like a straight line (bounding box)"
                )
        finally:
            os.unlink(path)

    def test_complex_silhouette_finds_arm_edge(self):
        """Gradient scan finds the arm edge within a dark torso region."""
        path, _ = _make_complex_silhouette(width=200, height=300)
        try:
            # Scan horizontally through the torso+arm overlap region
            result = scan_feature_adaptive(
                image_path=path,
                axis_center=(70.0, 145.0),  # Center of arm/torso overlap
                axis_angle_deg=90.0,
                scan_start=-40.0,
                scan_end=40.0,
                scan_step=3.0,
                cross_range=60.0,
                sample_step=1.0,
                gradient_threshold=8.0,
            )
            assert result["anchor_count"] > 0, (
                "Should find edges in the arm/torso region"
            )
        finally:
            os.unlink(path)
