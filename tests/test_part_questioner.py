"""Tests for the part questioner tool.

Verifies question generation for unlabeled parts and answer application.
All tests are pure Python -- no JSX or Adobe required.
"""

import pytest

from adobe_mcp.apps.illustrator.part_questioner import (
    generate_questions,
    apply_answers,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_parts():
    """Create sample parts for testing."""
    return [
        {
            "name": "part_0",
            "bounds": [10, 10, 70, 70],
            "centroid": [45.0, 45.0],
            "area": 4900,
            "color_hex": "#ff0000",
        },
        {
            "name": "part_1",
            "bounds": [120, 10, 70, 70],
            "centroid": [155.0, 45.0],
            "area": 4900,
            "color_hex": "#00ff00",
        },
        {
            "name": "part_2",
            "bounds": [60, 120, 80, 70],
            "centroid": [100.0, 155.0],
            "area": 5600,
            "color_hex": "#0000ff",
        },
    ]


def _empty_rig():
    """Create a minimal rig with no labels."""
    return {
        "character_name": "test",
        "body_part_labels": {},
        "landmarks": {},
    }


# ---------------------------------------------------------------------------
# generate_questions
# ---------------------------------------------------------------------------


def test_generate_questions_for_all_unlabeled():
    """Should generate question groups for all unlabeled parts."""
    parts = _sample_parts()
    rig = _empty_rig()
    questions = generate_questions(parts, rig, image_size=[200, 200])

    # All 3 parts are unlabeled, so 3 question groups
    assert len(questions) == 3
    for qg in questions:
        assert "part_name" in qg
        assert "questions" in qg
        assert len(qg["questions"]) == 4  # identity, mobility, connection, movement


def test_generate_questions_skips_labeled():
    """Should skip parts that already have labels in the rig."""
    parts = _sample_parts()
    rig = _empty_rig()
    rig["body_part_labels"]["part_0"] = "torso"

    questions = generate_questions(parts, rig, image_size=[200, 200])
    # part_0 is labeled, so only 2 question groups
    assert len(questions) == 2
    part_names = [qg["part_name"] for qg in questions]
    assert "part_0" not in part_names


def test_generate_questions_include_context():
    """Questions should include contextual info like color and position."""
    parts = _sample_parts()
    rig = _empty_rig()
    questions = generate_questions(parts, rig, image_size=[200, 200])

    first_group = questions[0]
    identity_q = first_group["questions"][0]
    assert identity_q["type"] == "identification"
    assert "#ff0000" in identity_q["question"]
    assert "context" in identity_q
    assert "color" in identity_q["context"]


def test_generate_questions_nearest_parts():
    """Connection questions should suggest nearest parts."""
    parts = _sample_parts()
    rig = _empty_rig()
    questions = generate_questions(parts, rig, image_size=[200, 200])

    for qg in questions:
        connection_q = [q for q in qg["questions"] if q["type"] == "connection"][0]
        assert "nearest_parts" in connection_q["context"]
        assert len(connection_q["context"]["nearest_parts"]) > 0


# ---------------------------------------------------------------------------
# apply_answers
# ---------------------------------------------------------------------------


def test_apply_answers_updates_rig():
    """apply_answers should update body_part_labels and landmarks."""
    rig = _empty_rig()
    answers = [
        {
            "part_name": "part_0",
            "identity": "head",
            "mobile": True,
            "attached_to": "part_2",
            "movement_type": "rotate",
        },
        {
            "part_name": "part_1",
            "identity": "left arm",
            "mobile": True,
            "attached_to": "part_2",
            "movement_type": "rotate",
        },
    ]

    result = apply_answers(rig, answers)
    assert result["applied_count"] == 2

    # Check body_part_labels
    assert rig["body_part_labels"]["part_0"] == "head"
    assert rig["body_part_labels"]["part_1"] == "left arm"

    # Check landmarks
    assert rig["landmarks"]["part_0"]["identity"] == "head"
    assert rig["landmarks"]["part_0"]["mobile"] is True
    assert rig["landmarks"]["part_0"]["attached_to"] == "part_2"
    assert rig["landmarks"]["part_1"]["movement_type"] == "rotate"
