"""Tests for object_classifier — silhouette-based object classification.

Tests classification scoring against known arrangements: biped-like,
quadruped-like, and vehicle-like part configurations.
"""

import pytest

from adobe_mcp.apps.illustrator.object_classifier import classify_object


# ---------------------------------------------------------------------------
# Test: biped-like arrangement -> biped classification
# ---------------------------------------------------------------------------


def test_biped_classification():
    """Bilateral symmetric with 2 lower appendages should score biped high."""
    parts = [
        {"name": "torso", "area": 5000, "role": "root",
         "bounding_box": [80, 20, 40, 60], "centroid": [100, 40]},
        {"name": "leg_l", "area": 2000, "role": "major",
         "bounding_box": [70, 80, 25, 50], "centroid": [82, 105]},
        {"name": "leg_r", "area": 2000, "role": "major",
         "bounding_box": [105, 80, 25, 50], "centroid": [117, 105]},
    ]
    symmetry = {
        "bilateral": {"detected": True, "confidence": 0.9},
        "radial": {"detected": False},
    }

    result = classify_object(parts, symmetry)
    assert len(result) == 3
    # Biped should be among top results
    categories = [r["category"] for r in result]
    assert "biped" in categories


# ---------------------------------------------------------------------------
# Test: 4-legged arrangement -> quadruped classification
# ---------------------------------------------------------------------------


def test_quadruped_classification():
    """4 lower appendages with bilateral symmetry should score quadruped high."""
    parts = [
        {"name": "body", "area": 8000, "role": "root",
         "bounding_box": [40, 20, 120, 40], "centroid": [100, 40]},
        {"name": "leg_fl", "area": 1500, "role": "major",
         "bounding_box": [40, 60, 20, 40], "centroid": [50, 80]},
        {"name": "leg_fr", "area": 1500, "role": "major",
         "bounding_box": [140, 60, 20, 40], "centroid": [150, 80]},
        {"name": "leg_bl", "area": 1500, "role": "major",
         "bounding_box": [40, 60, 20, 40], "centroid": [50, 80]},
        {"name": "leg_br", "area": 1500, "role": "major",
         "bounding_box": [140, 60, 20, 40], "centroid": [150, 80]},
    ]
    symmetry = {
        "bilateral": {"detected": True, "confidence": 0.85},
        "radial": {"detected": False},
    }

    result = classify_object(parts, symmetry)
    categories = [r["category"] for r in result]
    # Quadruped should be top or near top
    assert "quadruped" in categories


# ---------------------------------------------------------------------------
# Test: wide rectangle with circles -> vehicle
# ---------------------------------------------------------------------------


def test_vehicle_classification():
    """Wide bilateral shape with circular parts should suggest vehicle."""
    parts = [
        {"name": "body", "area": 10000, "role": "root",
         "bounding_box": [10, 30, 180, 40], "centroid": [100, 50]},
        {"name": "wheel_l", "area": 800, "role": "major",
         "bounding_box": [25, 70, 30, 30], "centroid": [40, 85]},
        {"name": "wheel_r", "area": 800, "role": "major",
         "bounding_box": [145, 70, 30, 30], "centroid": [160, 85]},
    ]
    symmetry = {
        "bilateral": {"detected": True, "confidence": 0.8},
        "radial": {"detected": False},
    }

    result = classify_object(parts, symmetry)
    categories = [r["category"] for r in result]
    assert "vehicle" in categories


# ---------------------------------------------------------------------------
# Test: empty parts list -> abstract fallback
# ---------------------------------------------------------------------------


def test_empty_parts_abstract():
    """Empty or minimal parts should fall back to abstract."""
    parts = []
    symmetry = {"bilateral": {"detected": False}, "radial": {"detected": False}}

    result = classify_object(parts, symmetry)
    assert len(result) == 3
    # Abstract should appear since nothing else matches well
    categories = [r["category"] for r in result]
    assert "abstract" in categories


# ---------------------------------------------------------------------------
# Test: confidence scores are bounded 0-1
# ---------------------------------------------------------------------------


def test_confidence_bounded():
    """All confidence scores should be between 0 and 1."""
    parts = [
        {"name": "body", "area": 5000, "role": "root",
         "bounding_box": [30, 30, 140, 140], "centroid": [100, 100]},
    ]
    symmetry = {
        "bilateral": {"detected": True, "confidence": 0.5},
        "radial": {"detected": True, "confidence": 0.5, "best_n": 4},
    }

    result = classify_object(parts, symmetry)
    for r in result:
        assert 0.0 <= r["confidence"] <= 1.0
