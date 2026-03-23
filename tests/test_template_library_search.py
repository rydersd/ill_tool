"""Tests for template_library_search — multi-criteria template search.

Tests tag-based search, empty results, and multi-criteria filtering.
"""

import pytest

from adobe_mcp.apps.illustrator.template_library_search import (
    search_templates,
    tag_template,
)


def _make_template_library():
    """Helper: create a small library of templates for search tests."""
    return [
        {
            "name": "biped_basic",
            "parts": [{"name": "torso"}, {"name": "leg_l"}, {"name": "leg_r"}],
            "tags": ["biped", "basic", "bilateral"],
            "metadata": {"symmetry": "bilateral"},
        },
        {
            "name": "quadruped_dog",
            "parts": [
                {"name": "body"}, {"name": "leg_fl"}, {"name": "leg_fr"},
                {"name": "leg_bl"}, {"name": "leg_br"}, {"name": "tail"},
            ],
            "tags": ["quadruped", "animal", "bilateral"],
            "metadata": {"symmetry": "bilateral"},
        },
        {
            "name": "bird_winged",
            "parts": [
                {"name": "body"}, {"name": "wing_l"}, {"name": "wing_r"},
                {"name": "leg_l"}, {"name": "leg_r"}, {"name": "tail"},
                {"name": "head"},
            ],
            "tags": ["biped", "wings", "bilateral", "flying"],
            "metadata": {"symmetry": "bilateral"},
        },
        {
            "name": "flower",
            "parts": [{"name": "stem"}, {"name": "petal_1"}, {"name": "petal_2"}],
            "tags": ["plant", "radial"],
            "metadata": {"symmetry": "radial"},
        },
    ]


# ---------------------------------------------------------------------------
# Test: search by tag finds match
# ---------------------------------------------------------------------------


def test_search_by_tag_finds_match():
    """Searching for 'wings' tag should find the bird template."""
    library = _make_template_library()
    results = search_templates({"tags": ["wings"]}, library)

    assert len(results) == 1
    assert results[0]["name"] == "bird_winged"


# ---------------------------------------------------------------------------
# Test: no match returns empty
# ---------------------------------------------------------------------------


def test_search_no_match_returns_empty():
    """Searching for a tag that doesn't exist should return no results."""
    library = _make_template_library()
    results = search_templates({"tags": ["robot", "mechanical"]}, library)

    assert len(results) == 0


# ---------------------------------------------------------------------------
# Test: multi-criteria filtering
# ---------------------------------------------------------------------------


def test_multi_criteria_filtering():
    """Search with min_parts + symmetry should narrow results."""
    library = _make_template_library()
    results = search_templates(
        {"min_parts": 5, "symmetry": "bilateral"},
        library,
    )

    # Only quadruped (6 parts) and bird (7 parts) have >= 5 parts + bilateral
    names = [r["name"] for r in results]
    assert "quadruped_dog" in names
    assert "bird_winged" in names
    assert "biped_basic" not in names  # only 3 parts
    assert "flower" not in names  # radial, not bilateral
