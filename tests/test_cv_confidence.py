"""Tests for the CV confidence scoring system.

Tests segmentation scoring (distinct vs noisy), connection scoring,
and symmetry scoring.
"""

import pytest

from adobe_mcp.apps.illustrator.cv_confidence import (
    score_segmentation,
    score_connection,
    score_symmetry,
)


# ---------------------------------------------------------------------------
# score_segmentation — clear distinct parts
# ---------------------------------------------------------------------------


def test_high_confidence_segmentation():
    """Clear distinct parts with good coverage produce high confidence."""
    parts = [
        {"area": 500},
        {"area": 300},
        {"area": 200},
        {"area": 150},
        {"area": 100},
    ]
    image_stats = {
        "total_pixels": 10000,
        "non_white_pixels": 1400,
        "color_clusters": 5,
    }

    result = score_segmentation(parts, image_stats)
    assert result["score"] >= 0.8
    assert "ideal range" in result["reasoning"]


# ---------------------------------------------------------------------------
# score_segmentation — noisy gradients
# ---------------------------------------------------------------------------


def test_low_confidence_gradient():
    """Many parts from gradient image with low coverage produce low confidence."""
    # Over-segmented: 25 parts from gradient noise
    parts = [{"area": 10} for _ in range(25)]
    image_stats = {
        "total_pixels": 10000,
        "non_white_pixels": 5000,
        "color_clusters": 2,  # Few clusters but many parts = confusion
    }

    result = score_segmentation(parts, image_stats)
    # Low score due to: over-segmented part count + cluster mismatch + low coverage
    assert result["score"] < 0.5
    assert "over-segmentation" in result["reasoning"]


# ---------------------------------------------------------------------------
# score_connection — clean connection
# ---------------------------------------------------------------------------


def test_high_confidence_connection():
    """Clean boundary with consistent width produces high confidence."""
    connection = {
        "boundary_clarity": 0.95,
        "width_consistency": 0.90,
    }

    result = score_connection(connection)
    assert result["score"] >= 0.9
    assert "Clear boundary" in result["reasoning"]
    assert "Consistent" in result["reasoning"]
