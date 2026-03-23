"""Tests for the asset versioning system.

Tests version bumping, history retrieval, and rollback to previous state.
"""

import copy

import pytest

from adobe_mcp.apps.illustrator.asset_versioning import (
    bump_version,
    get_version_history,
    rollback,
)


# ---------------------------------------------------------------------------
# bump_version
# ---------------------------------------------------------------------------


def test_bump_increments_version():
    """Each bump increments the version number."""
    rig = {"character_name": "hero", "joints": {"head": {"x": 0, "y": 0}}}

    entry1 = bump_version(rig, "initial rig setup")
    assert entry1["version"] == 1
    assert entry1["description"] == "initial rig setup"

    entry2 = bump_version(rig, "added arm joints")
    assert entry2["version"] == 2
    assert entry2["description"] == "added arm joints"

    assert len(rig["version_history"]) == 2


# ---------------------------------------------------------------------------
# get_version_history
# ---------------------------------------------------------------------------


def test_history_logged():
    """Version history contains all bumps with descriptions."""
    rig = {"character_name": "hero", "joints": {}}

    bump_version(rig, "initial setup")
    bump_version(rig, "added skeleton")
    bump_version(rig, "rigged character")

    history = get_version_history(rig)
    assert len(history) == 3
    assert history[0]["version"] == 1
    assert history[0]["description"] == "initial setup"
    assert history[2]["version"] == 3
    assert history[2]["description"] == "rigged character"

    # History entries should not include snapshots (for brevity)
    for entry in history:
        assert "snapshot" not in entry


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------


def test_rollback_restores_state():
    """Rolling back restores the rig to the state at that version."""
    rig = {"character_name": "hero", "joints": {"head": {"x": 0, "y": 0}}}

    # Version 1: just head joint
    bump_version(rig, "initial with head")

    # Modify the rig and bump to version 2
    rig["joints"]["arm"] = {"x": 50, "y": -100}
    bump_version(rig, "added arm")

    # Verify arm exists in current state
    assert "arm" in rig["joints"]

    # Rollback to version 1
    rollback(rig, 1)

    # After rollback, arm should be gone (restored to v1 snapshot)
    assert "arm" not in rig["joints"]
    assert rig["joints"]["head"] == {"x": 0, "y": 0}
    assert rig["character_name"] == "hero"
