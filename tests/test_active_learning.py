"""Tests for the active learning question prioritization system.

Tests that all-unlabeled parts produce symmetry question first,
partial labeling shifts priority, and fully labeled produces no questions.
"""

import pytest

from adobe_mcp.apps.illustrator.active_learning import (
    compute_information_gain,
    prioritize_questions,
    estimate_remaining_uncertainty,
)


# ---------------------------------------------------------------------------
# All unlabeled — symmetry question first
# ---------------------------------------------------------------------------


def test_all_unlabeled_symmetry_first():
    """When all parts are unlabeled, symmetry question has highest info gain."""
    parts = [
        {"name": "body"},
        {"name": "head"},
        {"name": "arm_left"},
        {"name": "arm_right"},
        {"name": "leg_left"},
    ]
    # All unlabeled
    current_labels = {"body": "", "head": "", "arm_left": "", "arm_right": "", "leg_left": ""}

    questions = prioritize_questions(parts, current_labels)
    assert len(questions) > 0

    # Symmetry question should be first (highest info gain) because
    # it affects all 5 parts at once
    first = questions[0]
    assert first["type"] == "symmetry"
    assert first["info_gain"] > 0

    # Verify all questions are sorted by info_gain descending
    for i in range(len(questions) - 1):
        assert questions[i]["info_gain"] >= questions[i + 1]["info_gain"]


# ---------------------------------------------------------------------------
# Some labeled — specific part questions rise
# ---------------------------------------------------------------------------


def test_some_labeled_part_questions():
    """When some parts are labeled, only unlabeled parts generate questions."""
    parts = [
        {"name": "body"},
        {"name": "head"},
        {"name": "arm_left"},
    ]
    # body and head are labeled, only arm_left is unknown
    current_labels = {"body": "torso", "head": "head", "arm_left": ""}

    questions = prioritize_questions(parts, current_labels)

    # Should still have questions but only about arm_left
    target_names = [q["target"] for q in questions if q["target"] is not None]
    assert all(name == "arm_left" for name in target_names)

    # Should have at least a direct_label question for arm_left
    direct_labels = [q for q in questions if q["type"] == "direct_label"]
    assert len(direct_labels) >= 1
    assert direct_labels[0]["target"] == "arm_left"


# ---------------------------------------------------------------------------
# Fully labeled — no questions
# ---------------------------------------------------------------------------


def test_fully_labeled_no_questions():
    """When all parts are labeled, no questions are generated."""
    parts = [
        {"name": "body", "joint_type": "fixed", "symmetry": True},
        {"name": "head", "joint_type": "ball", "symmetry": True},
        {"name": "arm", "joint_type": "hinge", "symmetry": False},
    ]
    current_labels = {"body": "torso", "head": "head", "arm": "arm"}

    questions = prioritize_questions(parts, current_labels)
    assert len(questions) == 0

    # Uncertainty should also be zero for labeling
    uncertainty = estimate_remaining_uncertainty(parts, current_labels)
    assert uncertainty["unlabeled_parts"] == 0
