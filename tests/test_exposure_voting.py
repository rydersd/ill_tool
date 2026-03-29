"""Tests for multi-exposure edge voting and related contour extraction.

Tests synthetic images to verify that form edges (hard brightness boundaries)
get high votes and shadow-like edges (gradual gradients) get low votes, plus
contour extraction and skeleton assignment.
"""

import math
import os
import tempfile

import cv2
import numpy as np
import pytest

from adobe_mcp.apps.illustrator.contour_scanner import (
    multi_exposure_edge_vote,
    classify_edge_votes,
    generate_exposure_gif,
    vote_map_to_contour_candidates,
    assign_contours_to_skeleton,
)


# ---------------------------------------------------------------------------
# Helpers: synthetic test image generators
# ---------------------------------------------------------------------------


def _make_uniform_gray(value: int = 128, width: int = 100, height: int = 100) -> np.ndarray:
    """Create a uniform grayscale image (no edges anywhere)."""
    return np.full((height, width), value, dtype=np.uint8)


def _make_hard_edge_image(width: int = 200, height: int = 200) -> np.ndarray:
    """Create an image with a sharp black-to-white vertical boundary at the center.

    Left half = black (0), right half = white (255).
    The transition is a hard 1-pixel step — a clear form edge that persists
    at every gamma level.
    """
    img = np.zeros((height, width), dtype=np.uint8)
    img[:, width // 2:] = 255
    return img


def _make_gradient_image(width: int = 200, height: int = 200) -> np.ndarray:
    """Create an image with a very gradual horizontal gradient from dark to light.

    The gradient is so gradual that Canny only fires on it at certain gamma
    levels — making it behave like a shadow edge (low vote count).
    """
    row = np.linspace(60, 180, width, dtype=np.float64)
    img = np.tile(row, (height, 1)).astype(np.uint8)
    return img


def _make_form_and_shadow_image(width: int = 400, height: int = 200) -> np.ndarray:
    """Create an image with BOTH a hard edge and a gradual gradient edge.

    Left half (columns 0-199): sharp black-to-white boundary at column 100.
    Right half (columns 200-399): gradual gradient from gray(80) to gray(180).

    The hard edge should get high votes; the gradient edge should get fewer.
    """
    img = np.full((height, width), 128, dtype=np.uint8)

    # Left half: hard edge at column 100
    img[:, :100] = 0
    img[:, 100:200] = 255

    # Right half: gradual gradient
    grad = np.linspace(80, 180, 200, dtype=np.float64)
    img[:, 200:] = np.tile(grad, (height, 1)).astype(np.uint8)

    return img


def _make_circle_on_white(
    width: int = 200, height: int = 200, cx: int = 100, cy: int = 100, radius: int = 40
) -> np.ndarray:
    """Create a black circle on white background for contour extraction tests."""
    img = np.full((height, width), 255, dtype=np.uint8)
    cv2.circle(img, (cx, cy), radius, 0, -1)
    return img


# ---------------------------------------------------------------------------
# Test: vote map properties
# ---------------------------------------------------------------------------


class TestVoteMapProperties:
    def test_vote_map_shape(self):
        """Vote map has same shape as input image."""
        gray = _make_hard_edge_image(150, 100)
        vote_map = multi_exposure_edge_vote(gray, n_levels=5)
        assert vote_map.shape == gray.shape, (
            f"Vote map shape {vote_map.shape} != input shape {gray.shape}"
        )

    def test_vote_map_dtype_is_float(self):
        """Vote map should be a float array for fractional analysis."""
        gray = _make_hard_edge_image(100, 100)
        vote_map = multi_exposure_edge_vote(gray, n_levels=5)
        assert vote_map.dtype == np.float64

    def test_vote_map_range(self):
        """All vote values should be between 0 and n_levels (inclusive)."""
        n_levels = 8
        gray = _make_hard_edge_image(200, 200)
        vote_map = multi_exposure_edge_vote(gray, n_levels=n_levels)
        assert vote_map.min() >= 0, f"Min vote {vote_map.min()} < 0"
        assert vote_map.max() <= n_levels, f"Max vote {vote_map.max()} > {n_levels}"


class TestUniformImage:
    def test_uniform_image_no_votes(self):
        """A uniform gray image produces zero votes everywhere.

        No brightness transitions means Canny finds no edges at any gamma.
        """
        gray = _make_uniform_gray(128, 100, 100)
        vote_map = multi_exposure_edge_vote(gray, n_levels=10)
        assert np.sum(vote_map) == 0, (
            f"Uniform image should produce zero votes, got total={np.sum(vote_map)}"
        )

    def test_uniform_black_no_votes(self):
        """Uniform black image: no edges at any gamma."""
        gray = _make_uniform_gray(0, 80, 80)
        vote_map = multi_exposure_edge_vote(gray, n_levels=10)
        assert np.sum(vote_map) == 0

    def test_uniform_white_no_votes(self):
        """Uniform white image: no edges at any gamma."""
        gray = _make_uniform_gray(255, 80, 80)
        vote_map = multi_exposure_edge_vote(gray, n_levels=10)
        assert np.sum(vote_map) == 0


class TestPermanentEdge:
    def test_permanent_edge_high_votes(self):
        """A hard black/white boundary gets votes at nearly every gamma level.

        This simulates a form edge: the boundary exists in the image structure
        regardless of exposure. Canny should fire on it at most gamma levels.
        """
        n_levels = 10
        gray = _make_hard_edge_image(200, 200)
        vote_map = multi_exposure_edge_vote(gray, n_levels=n_levels)

        # The hard edge is at column 100. Check that pixels near column 100
        # have high vote counts (at least 70% of n_levels).
        edge_region = vote_map[:, 98:103]  # 5-pixel-wide band around the edge
        max_votes_in_region = edge_region.max()
        assert max_votes_in_region >= n_levels * 0.7, (
            f"Hard edge should get >= {n_levels * 0.7} votes, got {max_votes_in_region}"
        )

    def test_non_edge_region_zero_votes(self):
        """Regions far from any edge should have zero votes."""
        gray = _make_hard_edge_image(200, 200)
        vote_map = multi_exposure_edge_vote(gray, n_levels=10)

        # Far left (column 10) and far right (column 190) are flat regions
        left_region = vote_map[:, 0:20]
        right_region = vote_map[:, 180:200]
        assert np.sum(left_region) == 0, "Far-left flat region should have zero votes"
        assert np.sum(right_region) == 0, "Far-right flat region should have zero votes"


class TestShadowSimulation:
    def test_shadow_simulation_low_votes(self):
        """A very gradual gradient (shadow simulation) gets fewer votes than a hard edge.

        At extreme gamma values, the gradient becomes either too compressed or
        too expanded for Canny to fire. Only at mid-range gammas does the
        gradient produce enough local contrast for edge detection.
        """
        n_levels = 10
        gray = _make_gradient_image(200, 200)
        vote_map = multi_exposure_edge_vote(
            gray, n_levels=n_levels, canny_low=30, canny_high=100
        )

        # The max vote count anywhere in the gradient image should be
        # significantly less than n_levels, because Canny won't fire at
        # all gammas on a gradual gradient.
        max_votes = vote_map.max()
        # Gradual gradient should not achieve unanimous votes
        assert max_votes < n_levels, (
            f"Gradual gradient max votes={max_votes}, should be < {n_levels}"
        )


class TestFormVsShadowDistinction:
    def test_form_vs_shadow_distinction(self):
        """An image with both a hard edge and a gradient edge shows clear distinction.

        The hard edge (form) should get significantly more votes than the
        gradient edge (shadow) across the gamma sweep.
        """
        n_levels = 10
        gray = _make_form_and_shadow_image(400, 200)
        vote_map = multi_exposure_edge_vote(
            gray, n_levels=n_levels, canny_low=30, canny_high=100
        )

        # Hard edge at column 100 (within the left half, 0-199)
        hard_edge_votes = vote_map[:, 98:103].max()

        # Gradient region (columns 200-399) — find the max votes anywhere
        gradient_votes = vote_map[:, 200:400].max()

        # The hard edge should have strictly more votes than the gradient
        assert hard_edge_votes > gradient_votes, (
            f"Hard edge votes ({hard_edge_votes}) should exceed gradient votes "
            f"({gradient_votes}) — form edges persist, shadow edges don't"
        )

    def test_form_vs_shadow_ratio(self):
        """Form edge vote count should be at least 2x the shadow edge vote count."""
        n_levels = 12
        gray = _make_form_and_shadow_image(400, 200)
        vote_map = multi_exposure_edge_vote(
            gray, n_levels=n_levels, canny_low=30, canny_high=100
        )

        hard_edge_votes = vote_map[:, 98:103].max()
        gradient_votes = vote_map[:, 200:400].max()

        # Avoid division by zero if gradient gets no votes at all
        if gradient_votes == 0:
            # Perfect separation — hard edge detected, gradient not
            assert hard_edge_votes > 0
        else:
            ratio = hard_edge_votes / gradient_votes
            assert ratio >= 2.0, (
                f"Form/shadow vote ratio={ratio:.1f}, expected >= 2.0 "
                f"(form={hard_edge_votes}, shadow={gradient_votes})"
            )


# ---------------------------------------------------------------------------
# Test: classify_edge_votes
# ---------------------------------------------------------------------------


class TestClassifyEdgeVotes:
    def test_classify_all_form(self):
        """A vote map with all-high values classifies everything as form edges."""
        # Simulate: every edge pixel got 10/10 votes
        vote_map = np.zeros((50, 50), dtype=np.float64)
        vote_map[20, :] = 10.0  # A horizontal line of max votes

        result = classify_edge_votes(vote_map, n_levels=10)
        assert result["form_count"] > 0
        assert result["shadow_count"] == 0

    def test_classify_all_shadow(self):
        """A vote map with all-low values classifies everything as shadow edges."""
        vote_map = np.zeros((50, 50), dtype=np.float64)
        vote_map[20, :] = 2.0  # Low vote line (2 out of 10)

        result = classify_edge_votes(vote_map, n_levels=10)
        assert result["shadow_count"] > 0
        assert result["form_count"] == 0

    def test_classify_mixed(self):
        """A vote map with both high and low values produces both form and shadow."""
        vote_map = np.zeros((50, 50), dtype=np.float64)
        vote_map[10, :] = 9.0  # High-vote line (form)
        vote_map[30, :] = 2.0  # Low-vote line (shadow)

        result = classify_edge_votes(vote_map, n_levels=10)
        assert result["form_count"] > 0
        assert result["shadow_count"] > 0

    def test_classify_empty_vote_map(self):
        """An all-zero vote map produces no edges of any type."""
        vote_map = np.zeros((50, 50), dtype=np.float64)
        result = classify_edge_votes(vote_map, n_levels=10)
        assert result["form_count"] == 0
        assert result["shadow_count"] == 0
        assert np.sum(result["form_edges"]) == 0
        assert np.sum(result["shadow_edges"]) == 0
        assert np.sum(result["ambiguous_edges"]) == 0

    def test_classify_ambiguous_region(self):
        """Votes between shadow and form thresholds are ambiguous."""
        vote_map = np.zeros((50, 50), dtype=np.float64)
        # With n_levels=10, form_threshold=0.7 (7 votes), shadow_threshold=0.3 (3 votes)
        # So 5 votes is ambiguous
        vote_map[20, :] = 5.0

        result = classify_edge_votes(vote_map, n_levels=10)
        assert result["form_count"] == 0
        assert result["shadow_count"] == 0
        assert np.sum(result["ambiguous_edges"]) > 0

    def test_classify_threshold_boundaries(self):
        """Test exact threshold boundary values."""
        vote_map = np.zeros((3, 1), dtype=np.float64)
        # n_levels=10, form_threshold=0.7 -> 7 votes needed
        # shadow_threshold=0.3 -> 3 votes max
        vote_map[0, 0] = 7.0  # Exactly at form threshold
        vote_map[1, 0] = 3.0  # Exactly at shadow threshold
        vote_map[2, 0] = 4.0  # Just above shadow, below form = ambiguous

        result = classify_edge_votes(vote_map, n_levels=10)
        assert result["form_edges"][0, 0] == 1, "7 votes should be form (>= 7)"
        assert result["shadow_edges"][1, 0] == 1, "3 votes should be shadow (<= 3)"
        assert result["ambiguous_edges"][2, 0] == 1, "4 votes should be ambiguous"


# ---------------------------------------------------------------------------
# Test: contour extraction from vote map
# ---------------------------------------------------------------------------


class TestContourExtraction:
    def test_contour_from_circle_vote_map(self):
        """High-vote contours are extracted from a circle with a hard edge."""
        gray = _make_circle_on_white(200, 200, 100, 100, 40)
        vote_map = multi_exposure_edge_vote(gray, n_levels=10)

        contours = vote_map_to_contour_candidates(
            vote_map, min_votes=5, min_contour_length=20
        )
        # Should find at least one contour around the circle boundary
        assert len(contours) > 0, "Expected at least one contour from circle edge"

    def test_contour_extraction_empty_vote_map(self):
        """An all-zero vote map produces no contours."""
        vote_map = np.zeros((100, 100), dtype=np.float64)
        contours = vote_map_to_contour_candidates(vote_map, min_votes=1)
        assert len(contours) == 0

    def test_contour_min_length_filter(self):
        """Contours below min_contour_length are filtered out."""
        # Create a vote map with a tiny dot (very short perimeter)
        vote_map = np.zeros((100, 100), dtype=np.float64)
        vote_map[50, 50] = 10.0
        vote_map[50, 51] = 10.0
        vote_map[51, 50] = 10.0
        vote_map[51, 51] = 10.0

        # With a high min_contour_length, the tiny dot should be filtered out
        contours = vote_map_to_contour_candidates(
            vote_map, min_votes=5, min_contour_length=100
        )
        assert len(contours) == 0, "Tiny dot should be filtered by min_contour_length"

    def test_contour_min_length_passes_large(self):
        """A contour with sufficient perimeter passes the min_length filter."""
        # Draw a large rectangle of high votes
        vote_map = np.zeros((200, 200), dtype=np.float64)
        cv2.rectangle(
            vote_map.view(np.float64).reshape(200, 200),
            (50, 50), (150, 150), 10.0, 2,
        )

        contours = vote_map_to_contour_candidates(
            vote_map, min_votes=5, min_contour_length=20
        )
        assert len(contours) > 0, "Large rectangle contour should pass the filter"

    def test_contour_arrays_are_valid_opencv_format(self):
        """Extracted contours should be in standard cv2 format (Nx1x2 int arrays)."""
        gray = _make_circle_on_white(200, 200, 100, 100, 40)
        vote_map = multi_exposure_edge_vote(gray, n_levels=10)
        contours = vote_map_to_contour_candidates(vote_map, min_votes=5)

        for contour in contours:
            assert contour.ndim == 3, f"Contour should be 3D, got {contour.ndim}D"
            assert contour.shape[1] == 1, f"Second dim should be 1, got {contour.shape[1]}"
            assert contour.shape[2] == 2, f"Third dim should be 2, got {contour.shape[2]}"


# ---------------------------------------------------------------------------
# Test: skeleton assignment
# ---------------------------------------------------------------------------


class TestSkeletonAssignment:
    def _make_two_contours(self):
        """Create two contours at known positions for assignment testing.

        Contour A: small circle at (50, 50)
        Contour B: small circle at (150, 150)
        """
        # Create contours programmatically via cv2
        img_a = np.zeros((200, 200), dtype=np.uint8)
        cv2.circle(img_a, (50, 50), 20, 255, -1)
        contours_a, _ = cv2.findContours(img_a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        img_b = np.zeros((200, 200), dtype=np.uint8)
        cv2.circle(img_b, (150, 150), 20, 255, -1)
        contours_b, _ = cv2.findContours(img_b, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        return list(contours_a) + list(contours_b)

    def test_skeleton_assignment_basic(self):
        """Contours near joints are assigned to the correct joint."""
        contours = self._make_two_contours()
        joints = {
            "head": (50.0, 50.0),
            "foot": (150.0, 150.0),
        }

        result = assign_contours_to_skeleton(contours, joints, max_distance=60.0)
        assert len(result["head"]) == 1, "Contour at (50,50) should assign to head"
        assert len(result["foot"]) == 1, "Contour at (150,150) should assign to foot"
        assert len(result["_unassigned"]) == 0

    def test_skeleton_assignment_unassigned(self):
        """Contours too far from any joint go to _unassigned."""
        contours = self._make_two_contours()
        joints = {
            "elbow": (200.0, 200.0),  # Far from both contours if max_distance is small
        }

        result = assign_contours_to_skeleton(contours, joints, max_distance=30.0)
        # Both contours are far from (200, 200)
        assert len(result["_unassigned"]) == 2

    def test_skeleton_assignment_empty_contours(self):
        """Empty contour list produces empty assignments."""
        joints = {"head": (50.0, 50.0)}
        result = assign_contours_to_skeleton([], joints, max_distance=100.0)
        assert len(result["head"]) == 0
        assert len(result["_unassigned"]) == 0

    def test_skeleton_assignment_empty_joints(self):
        """With no joints, all contours go to _unassigned."""
        contours = self._make_two_contours()
        result = assign_contours_to_skeleton(contours, {}, max_distance=100.0)
        assert len(result["_unassigned"]) == 2

    def test_skeleton_assignment_closest_wins(self):
        """When two joints compete, the closer one gets the contour."""
        contours = self._make_two_contours()
        # Both joints are close to the first contour at (50, 50)
        joints = {
            "near": (45.0, 45.0),   # ~7px from (50, 50)
            "far": (80.0, 80.0),    # ~42px from (50, 50)
        }

        result = assign_contours_to_skeleton(contours, joints, max_distance=200.0)
        # The contour at (50, 50) should go to "near"
        assert len(result["near"]) >= 1, "Closer joint should win the contour"


# ---------------------------------------------------------------------------
# Test: GIF generation
# ---------------------------------------------------------------------------


class TestGifGeneration:
    def test_gif_creates_file(self):
        """generate_exposure_gif creates a GIF file at the specified path."""
        gray = _make_hard_edge_image(100, 100)
        fd, path = tempfile.mkstemp(suffix=".gif")
        os.close(fd)

        try:
            result = generate_exposure_gif(
                gray, path, n_frames=5, duration_ms=50
            )
            assert os.path.exists(result), f"GIF file not found at {result}"
            assert os.path.getsize(result) > 0, "GIF file should not be empty"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_gif_output_path_matches(self):
        """The returned path should match the requested output_path."""
        gray = _make_hard_edge_image(80, 80)
        fd, path = tempfile.mkstemp(suffix=".gif")
        os.close(fd)

        try:
            result = generate_exposure_gif(gray, path, n_frames=3)
            assert result == path
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_gif_with_uniform_image(self):
        """GIF generation works even for uniform images (no edges)."""
        gray = _make_uniform_gray(128, 60, 60)
        fd, path = tempfile.mkstemp(suffix=".gif")
        os.close(fd)

        try:
            result = generate_exposure_gif(gray, path, n_frames=3)
            assert os.path.exists(result)
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ---------------------------------------------------------------------------
# Test: integration — vote map through contour extraction pipeline
# ---------------------------------------------------------------------------


class TestIntegrationPipeline:
    def test_vote_to_contour_pipeline(self):
        """Full pipeline: vote map -> classify -> extract contours from form edges."""
        gray = _make_circle_on_white(200, 200, 100, 100, 40)
        n_levels = 10

        # Step 1: vote
        vote_map = multi_exposure_edge_vote(gray, n_levels=n_levels)
        assert vote_map.shape == gray.shape

        # Step 2: classify
        classified = classify_edge_votes(vote_map, n_levels=n_levels)
        assert classified["form_count"] > 0, "Circle should have form edges"

        # Step 3: extract contours from vote map
        contours = vote_map_to_contour_candidates(vote_map, min_votes=6)
        assert len(contours) > 0, "Should extract contours from circle"

    def test_vote_to_skeleton_pipeline(self):
        """Full pipeline: vote -> extract -> assign to skeleton joints."""
        gray = _make_circle_on_white(200, 200, 100, 100, 30)
        vote_map = multi_exposure_edge_vote(gray, n_levels=10)
        contours = vote_map_to_contour_candidates(vote_map, min_votes=5)

        joints = {"torso": (100.0, 100.0)}
        assigned = assign_contours_to_skeleton(contours, joints, max_distance=80.0)

        # The circle contour should be assigned to "torso" since it's centered at (100,100)
        assert len(assigned["torso"]) > 0, (
            "Circle contour at (100,100) should assign to torso joint at (100,100)"
        )
