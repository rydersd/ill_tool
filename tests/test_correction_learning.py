"""Tests for the correction learning system.

Tests recording corrections, matching similar features to suggestions,
and no-match scenarios.
"""

import json
import os

import pytest

from adobe_mcp.apps.illustrator.correction_learning import (
    record_correction,
    suggest_from_corrections,
    _load_corrections,
)


# ---------------------------------------------------------------------------
# record_correction
# ---------------------------------------------------------------------------


def test_record_correction(tmp_path):
    """Recording a correction persists it to the storage file."""
    storage = str(tmp_path / "corrections.json")

    result = record_correction(
        correction_type="part_label",
        original="limb",
        corrected="arm",
        context={"area_ratio": 0.15, "aspect_ratio": 3.0, "position_relative_to_root": 0.6},
        storage_path=storage,
    )

    assert result["correction_type"] == "part_label"
    assert result["original"] == "limb"
    assert result["corrected"] == "arm"

    # Verify it was persisted
    corrections = _load_corrections(storage)
    assert len(corrections) == 1
    assert corrections[0]["corrected"] == "arm"


# ---------------------------------------------------------------------------
# suggest_from_corrections — similar features match
# ---------------------------------------------------------------------------


def test_similar_features_suggest_correction(tmp_path):
    """A new part with similar features gets the corrected label."""
    storage = str(tmp_path / "corrections.json")

    # Record a correction for an arm
    record_correction(
        correction_type="part_label",
        original="limb",
        corrected="arm",
        context={"area_ratio": 0.15, "aspect_ratio": 3.0, "position_relative_to_root": 0.6},
        storage_path=storage,
    )

    # Query with very similar features
    result = suggest_from_corrections(
        part_features={"area_ratio": 0.16, "aspect_ratio": 2.9, "position_relative_to_root": 0.62},
        storage_path=storage,
    )

    assert result is not None
    assert result["suggested_label"] == "arm"
    assert result["distance"] < 0.3  # Within threshold


# ---------------------------------------------------------------------------
# suggest_from_corrections — no match
# ---------------------------------------------------------------------------


def test_no_match_returns_none(tmp_path):
    """When features are too different, no suggestion is returned."""
    storage = str(tmp_path / "corrections.json")

    # Record a correction for an arm
    record_correction(
        correction_type="part_label",
        original="limb",
        corrected="arm",
        context={"area_ratio": 0.15, "aspect_ratio": 3.0, "position_relative_to_root": 0.6},
        storage_path=storage,
    )

    # Query with very different features (like a head)
    result = suggest_from_corrections(
        part_features={"area_ratio": 0.8, "aspect_ratio": 1.0, "position_relative_to_root": 0.1},
        storage_path=storage,
    )

    assert result is None
