"""Tests for symmetry_detector — bilateral and radial symmetry detection.

Tests detection on synthetic symmetric and asymmetric images, including
perfect bilateral, perfect radial (circle), and clearly asymmetric shapes.
"""

import os

import cv2
import numpy as np
import pytest

from adobe_mcp.apps.illustrator.symmetry_detector import (
    detect_bilateral_symmetry,
    detect_radial_symmetry,
    get_symmetry_axis,
)


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="session")
def bilateral_symmetric_png():
    """200x200 image with perfect left-right symmetry (centered white rectangle)."""
    path = os.path.join(FIXTURES_DIR, "bilateral_symmetric.png")
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    # Centered rectangle — perfectly symmetric
    cv2.rectangle(img, (50, 40), (150, 160), (255, 255, 255), -1)
    cv2.imwrite(path, img)
    return path


@pytest.fixture(scope="session")
def asymmetric_png():
    """200x200 image with seeded random noise — guaranteed asymmetric.

    Random pixel values will never match when flipped at any axis,
    yielding consistently low bilateral symmetry scores.
    """
    path = os.path.join(FIXTURES_DIR, "asymmetric.png")
    rng = np.random.RandomState(42)  # fixed seed for reproducibility
    img = rng.randint(0, 256, (200, 200), dtype=np.uint8)
    cv2.imwrite(path, img)
    return path


@pytest.fixture(scope="session")
def circle_png():
    """200x200 image with centered white circle (radially symmetric)."""
    path = os.path.join(FIXTURES_DIR, "circle_symmetric.png")
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    cv2.circle(img, (100, 100), 70, (255, 255, 255), -1)
    cv2.imwrite(path, img)
    return path


# ---------------------------------------------------------------------------
# Test: bilateral symmetric image -> high confidence
# ---------------------------------------------------------------------------


def test_bilateral_high_confidence(bilateral_symmetric_png):
    """Perfectly symmetric image should have high bilateral confidence."""
    result = detect_bilateral_symmetry(bilateral_symmetric_png)
    assert "error" not in result
    assert result["detected"] is True
    assert result["confidence"] > 0.8
    # Axis should be near center
    assert abs(result["axis_x"] - 100) < 30


# ---------------------------------------------------------------------------
# Test: asymmetric image -> low bilateral confidence
# ---------------------------------------------------------------------------


def test_asymmetric_low_bilateral(asymmetric_png):
    """Clearly asymmetric image should have low bilateral confidence."""
    result = detect_bilateral_symmetry(asymmetric_png)
    assert "error" not in result
    assert result["confidence"] < 0.7


# ---------------------------------------------------------------------------
# Test: circle -> radial symmetry detected
# ---------------------------------------------------------------------------


def test_circle_radial_detected(circle_png):
    """Circle should be detected as radially symmetric."""
    result = detect_radial_symmetry(circle_png, max_n=8)
    assert "error" not in result
    assert result["detected"] is True
    assert result["confidence"] > 0.7
    # Circle should score high for multiple N values
    high_scoring = [n for n, s in result["all_scores"].items() if s > 0.7]
    assert len(high_scoring) >= 2


# ---------------------------------------------------------------------------
# Test: asymmetric image -> no radial symmetry
# ---------------------------------------------------------------------------


def test_asymmetric_no_radial(asymmetric_png):
    """Clearly asymmetric image should not show radial symmetry."""
    result = detect_radial_symmetry(asymmetric_png, max_n=8)
    assert "error" not in result
    # Should have low confidence
    assert result["confidence"] < 0.85


# ---------------------------------------------------------------------------
# Test: get_symmetry_axis returns correct type
# ---------------------------------------------------------------------------


def test_symmetry_axis_bilateral(bilateral_symmetric_png):
    """Symmetric image should report bilateral symmetry type with axis."""
    result = get_symmetry_axis(bilateral_symmetric_png)
    assert "error" not in result
    assert result["symmetry_type"] == "bilateral"
    assert result["angle"] == 90.0  # vertical axis
    assert result["confidence"] > 0.7
