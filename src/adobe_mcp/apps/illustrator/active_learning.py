"""Active learning question prioritization.

Computes information gain for potential questions about unlabeled parts,
prioritizes questions by expected information gain, and estimates
remaining uncertainty in the labeling process.

Helps guide the user to provide the most valuable input first.
"""

import json
import math
import os
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from adobe_mcp.apps.illustrator.rig_data import _load_rig, _save_rig


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiActiveLearningInput(BaseModel):
    """Active learning: ask the most informative questions first."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ...,
        description="Action: compute_info_gain, prioritize_questions, estimate_uncertainty",
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    parts: Optional[list[dict]] = Field(
        default=None,
        description="List of part dicts with 'name', optional 'label', optional 'joint_type', optional 'symmetry'",
    )
    current_labels: Optional[dict] = Field(
        default=None,
        description="Dict mapping part names to their current labels (empty string = unlabeled)",
    )


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def compute_information_gain(parts: list[dict], current_labels: dict) -> list[dict]:
    """Compute information gain for each possible question type.

    Question types and their information gain:
    - "Is this symmetric?" — splits unlabeled parts into 2 groups.
      High info gain when many parts are unlabeled.
    - "Does part X move?" — determines fixed vs mobile for a specific part.
      High gain when joint type is unknown.
    - "What is part X?" — direct label question for a specific part.
      High gain but requires more user knowledge.

    Args:
        parts: list of part dicts
        current_labels: mapping of part name -> label (or empty/"" for unlabeled)

    Returns:
        List of question dicts with type, target, info_gain score.
    """
    questions = []

    # Count unlabeled parts
    unlabeled = []
    for part in parts:
        name = part.get("name", "")
        label = current_labels.get(name, "")
        if not label:
            unlabeled.append(part)

    total_parts = len(parts)
    unlabeled_count = len(unlabeled)

    if unlabeled_count == 0:
        return []

    # Question type 1: "Is this symmetric?"
    # Splits unlabeled parts into symmetric/asymmetric groups
    # Info gain proportional to how many parts lack symmetry info
    parts_without_symmetry = [
        p for p in unlabeled
        if p.get("symmetry") is None
    ]
    if parts_without_symmetry:
        # Symmetry question can label ~half the parts at once
        symmetry_gain = len(parts_without_symmetry) / total_parts
        questions.append({
            "type": "symmetry",
            "question": "Is this character symmetric?",
            "target": None,
            "info_gain": round(symmetry_gain, 4),
            "affects_parts": len(parts_without_symmetry),
            "reasoning": (
                f"Symmetry check would classify {len(parts_without_symmetry)} "
                f"parts into symmetric/asymmetric groups"
            ),
        })

    # Question type 2: "Does part X move?" for each unlabeled part
    for part in unlabeled:
        name = part.get("name", "unknown")
        joint_type = part.get("joint_type")
        if joint_type is None:
            # Info gain depends on how much this narrows down possibilities
            # Parts without joint type info get higher gain
            move_gain = 1.0 / total_parts
            questions.append({
                "type": "movement",
                "question": f"Does '{name}' move independently?",
                "target": name,
                "info_gain": round(move_gain, 4),
                "affects_parts": 1,
                "reasoning": (
                    f"Knowing if '{name}' moves determines its joint type "
                    "(fixed vs articulated)"
                ),
            })

    # Question type 3: "What is part X?" for each unlabeled part
    for part in unlabeled:
        name = part.get("name", "unknown")
        # Direct labeling has high info gain per part
        # Scaled by how much uncertainty remains
        label_gain = (1.0 / total_parts) * 1.5  # 1.5x multiplier for direct info
        questions.append({
            "type": "direct_label",
            "question": f"What is '{name}'?",
            "target": name,
            "info_gain": round(label_gain, 4),
            "affects_parts": 1,
            "reasoning": f"Direct identification of '{name}' eliminates all uncertainty for this part",
        })

    return questions


def prioritize_questions(parts: list[dict], current_labels: dict) -> list[dict]:
    """Sort questions by information gain, highest first.

    Args:
        parts: list of part dicts
        current_labels: mapping of part name -> label

    Returns:
        Ordered list of questions, highest info gain first.
    """
    questions = compute_information_gain(parts, current_labels)
    questions.sort(key=lambda q: q["info_gain"], reverse=True)
    return questions


def estimate_remaining_uncertainty(parts: list[dict], labels: dict) -> dict:
    """Estimate how much is still unknown about the parts.

    Counts:
    - unlabeled_parts: parts without labels
    - unknown_joints: parts without joint type info
    - unknown_connections: approximate from unlabeled count

    Args:
        parts: list of part dicts
        labels: mapping of part name -> label

    Returns:
        {"unlabeled_parts": int, "unknown_joints": int,
         "total_parts": int, "uncertainty_ratio": float}
    """
    total = len(parts)
    if total == 0:
        return {
            "unlabeled_parts": 0,
            "unknown_joints": 0,
            "total_parts": 0,
            "uncertainty_ratio": 0.0,
        }

    unlabeled = 0
    unknown_joints = 0

    for part in parts:
        name = part.get("name", "")
        label = labels.get(name, "")
        if not label:
            unlabeled += 1
        if part.get("joint_type") is None:
            unknown_joints += 1

    # Uncertainty ratio: how much is unknown (0 = fully known, 1 = fully unknown)
    uncertainty = (unlabeled + unknown_joints) / (total * 2)

    return {
        "unlabeled_parts": unlabeled,
        "unknown_joints": unknown_joints,
        "total_parts": total,
        "uncertainty_ratio": round(uncertainty, 4),
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_active_learning tool."""

    @mcp.tool(
        name="adobe_ai_active_learning",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_active_learning(params: AiActiveLearningInput) -> str:
        """Active learning: ask the most informative questions first.

        Actions:
        - compute_info_gain: calculate information gain for each question
        - prioritize_questions: sort questions by info gain
        - estimate_uncertainty: how much is still unknown
        """
        action = params.action.lower().strip()

        if action == "compute_info_gain":
            if params.parts is None or params.current_labels is None:
                return json.dumps({
                    "error": "compute_info_gain requires parts and current_labels"
                })
            questions = compute_information_gain(params.parts, params.current_labels)
            return json.dumps({
                "action": "compute_info_gain",
                "questions": questions,
                "count": len(questions),
            })

        elif action == "prioritize_questions":
            if params.parts is None or params.current_labels is None:
                return json.dumps({
                    "error": "prioritize_questions requires parts and current_labels"
                })
            questions = prioritize_questions(params.parts, params.current_labels)
            return json.dumps({
                "action": "prioritize_questions",
                "questions": questions,
                "count": len(questions),
            })

        elif action == "estimate_uncertainty":
            if params.parts is None or params.current_labels is None:
                return json.dumps({
                    "error": "estimate_uncertainty requires parts and current_labels"
                })
            result = estimate_remaining_uncertainty(params.parts, params.current_labels)
            return json.dumps({
                "action": "estimate_uncertainty",
                **result,
            })

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": [
                    "compute_info_gain",
                    "prioritize_questions",
                    "estimate_uncertainty",
                ],
            })
