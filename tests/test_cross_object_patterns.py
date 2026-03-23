"""Tests for the cross-object pattern recognition system.

Tests recording labeled parts, matching arm-like features, and
empty database behavior.
"""

import json
import os

import pytest

from adobe_mcp.apps.illustrator.cross_object_patterns import (
    extract_features,
    record_labeled_part,
    match_pattern,
    _load_patterns,
)


# ---------------------------------------------------------------------------
# record + match — arm features match
# ---------------------------------------------------------------------------


def test_arm_features_match(tmp_path):
    """Recording 5 arm features, then querying arm-like features returns 'arm'."""
    storage = str(tmp_path / "patterns.json")

    # Record several arm-like features with slight variation
    arm_features_list = [
        {"aspect_ratio": 3.0, "relative_area": 0.15, "symmetry_score": 0.3, "position_quadrant": 4, "compactness": 0.6},
        {"aspect_ratio": 2.8, "relative_area": 0.14, "symmetry_score": 0.35, "position_quadrant": 4, "compactness": 0.58},
        {"aspect_ratio": 3.2, "relative_area": 0.16, "symmetry_score": 0.28, "position_quadrant": 4, "compactness": 0.62},
        {"aspect_ratio": 2.9, "relative_area": 0.15, "symmetry_score": 0.32, "position_quadrant": 4, "compactness": 0.59},
        {"aspect_ratio": 3.1, "relative_area": 0.14, "symmetry_score": 0.30, "position_quadrant": 4, "compactness": 0.61},
    ]
    for features in arm_features_list:
        record_labeled_part(features, "arm", storage_path=storage)

    # Query with a new arm-like feature set
    query = {"aspect_ratio": 3.0, "relative_area": 0.15, "symmetry_score": 0.31, "position_quadrant": 4, "compactness": 0.60}
    result = match_pattern(query, storage_path=storage)

    assert result is not None
    assert result["label"] == "arm"
    assert result["confidence"] > 0.5


# ---------------------------------------------------------------------------
# Non-matching features
# ---------------------------------------------------------------------------


def test_non_matching_features(tmp_path):
    """Features very different from stored patterns return no match."""
    storage = str(tmp_path / "patterns.json")

    # Record arm features
    record_labeled_part(
        {"aspect_ratio": 3.0, "relative_area": 0.15, "symmetry_score": 0.3, "position_quadrant": 4, "compactness": 0.6},
        "arm",
        storage_path=storage,
    )

    # Query with head-like features (very different aspect ratio, compactness, etc.)
    query = {"aspect_ratio": 1.0, "relative_area": 0.8, "symmetry_score": 0.9, "position_quadrant": 1, "compactness": 0.95}
    result = match_pattern(query, storage_path=storage)

    # Distance should exceed max_distance threshold
    assert result is None


# ---------------------------------------------------------------------------
# Empty database
# ---------------------------------------------------------------------------


def test_empty_database_no_match(tmp_path):
    """Empty pattern database returns no match."""
    storage = str(tmp_path / "patterns.json")

    query = {"aspect_ratio": 2.0, "relative_area": 0.3, "symmetry_score": 0.5, "position_quadrant": 1, "compactness": 0.7}
    result = match_pattern(query, storage_path=storage)

    assert result is None
