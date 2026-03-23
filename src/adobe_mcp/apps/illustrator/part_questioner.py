"""Generate structured questions for unknown/unlabeled parts.

When the segmenter detects parts but doesn't know what they are, this tool
generates context-rich questions for the user to identify each part, its
mobility, connections, and movement type. User answers are then applied
back to the rig.

Pure Python implementation.
"""

import json
import math
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from adobe_mcp.apps.illustrator.rig_data import _load_rig, _save_rig


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiPartQuestionerInput(BaseModel):
    """Generate questions for unlabeled parts or apply answers."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ..., description="Action: generate, apply_answers"
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    parts: Optional[list[dict]] = Field(
        default=None,
        description="List of part dicts from segmenter (for 'generate' action)",
    )
    answers: Optional[list[dict]] = Field(
        default=None,
        description="List of answer dicts to apply (for 'apply_answers' action). "
                    "Each has: part_name, identity, mobile (bool), attached_to, movement_type",
    )


# ---------------------------------------------------------------------------
# Pure Python helpers
# ---------------------------------------------------------------------------


def _describe_position(centroid: list[float], image_size: list[int]) -> str:
    """Describe position in human-readable terms (top-left, center, etc.)."""
    if not image_size or image_size[0] == 0 or image_size[1] == 0:
        return "unknown position"

    w, h = image_size
    cx, cy = centroid

    # Horizontal position
    if cx < w * 0.33:
        horiz = "left"
    elif cx > w * 0.67:
        horiz = "right"
    else:
        horiz = "center"

    # Vertical position
    if cy < h * 0.33:
        vert = "top"
    elif cy > h * 0.67:
        vert = "bottom"
    else:
        vert = "middle"

    if vert == "middle" and horiz == "center":
        return "center"
    return f"{vert}-{horiz}"


def _find_nearest_parts(
    target_part: dict,
    all_parts: list[dict],
    max_suggestions: int = 3,
) -> list[str]:
    """Find the nearest other parts by centroid distance."""
    target_cx, target_cy = target_part["centroid"]
    distances = []

    for part in all_parts:
        if part["name"] == target_part["name"]:
            continue
        cx, cy = part["centroid"]
        dist = math.sqrt((cx - target_cx) ** 2 + (cy - target_cy) ** 2)
        distances.append((part["name"], dist))

    distances.sort(key=lambda x: x[1])
    return [name for name, _ in distances[:max_suggestions]]


def generate_questions(
    parts: list[dict],
    rig: dict,
    image_size: Optional[list[int]] = None,
) -> list[dict]:
    """Generate structured questions for each unlabeled part.

    For each part without a label in the rig, generates four questions:
    1. Identification: "What is the [color] shape at [position]?"
    2. Mobility: "Does it move independently?"
    3. Connection: "What is it attached to?" with suggestions
    4. Movement type: "How does it move?"

    Returns a list of question groups, one per unlabeled part.
    """
    labeled_parts = set()
    body_labels = rig.get("body_part_labels", {})
    for part_name, label in body_labels.items():
        if label:
            labeled_parts.add(part_name)

    # Find the largest part for size context
    max_area = max((p.get("area", 0) for p in parts), default=1) or 1

    question_groups = []
    for part in parts:
        if part["name"] in labeled_parts:
            continue

        position_desc = _describe_position(
            part.get("centroid", [0, 0]),
            image_size or [0, 0],
        )
        color_hex = part.get("color_hex", "#unknown")
        area = part.get("area", 0)
        size_pct = round(area / max_area * 100, 1)
        nearest = _find_nearest_parts(part, parts)
        nearest_str = ", ".join(nearest) if nearest else "none detected"

        questions = [
            {
                "id": f"{part['name']}_identity",
                "question": f"What is the {color_hex} shape at {position_desc}?",
                "type": "identification",
                "context": {
                    "color": color_hex,
                    "position": position_desc,
                    "bounds": part.get("bounds"),
                    "relative_size": f"{size_pct}% of largest part",
                },
            },
            {
                "id": f"{part['name']}_mobility",
                "question": "Does it move independently?",
                "type": "mobility",
                "context": {
                    "expected_answers": ["yes", "no", "partially"],
                },
            },
            {
                "id": f"{part['name']}_connection",
                "question": f"What is it attached to? (nearest parts: {nearest_str})",
                "type": "connection",
                "context": {
                    "nearest_parts": nearest,
                },
            },
            {
                "id": f"{part['name']}_movement",
                "question": "How does it move? (rotate, slide, flex, fixed)",
                "type": "relationship",
                "context": {
                    "expected_answers": [
                        "rotate", "slide", "flex", "telescoping", "fixed"
                    ],
                },
            },
        ]

        question_groups.append({
            "part_name": part["name"],
            "part_info": {
                "color": color_hex,
                "position": position_desc,
                "bounds": part.get("bounds"),
                "area": area,
            },
            "questions": questions,
        })

    return question_groups


def apply_answers(rig: dict, answers: list[dict]) -> dict:
    """Apply user answers back to the rig.

    Each answer dict should have:
    - part_name: which part this answer is for
    - identity: what the part is (e.g. "left arm")
    - mobile: bool, whether it moves independently
    - attached_to: what it's connected to
    - movement_type: how it moves (rotate, slide, etc.)

    Updates body_part_labels and landmarks in the rig.

    Returns summary of applied changes.
    """
    if "body_part_labels" not in rig:
        rig["body_part_labels"] = {}
    if "landmarks" not in rig:
        rig["landmarks"] = {}

    applied = []
    for answer in answers:
        part_name = answer.get("part_name", "")
        identity = answer.get("identity", "")
        mobile = answer.get("mobile", False)
        attached_to = answer.get("attached_to", "")
        movement_type = answer.get("movement_type", "fixed")

        if not part_name:
            continue

        # Update body part label
        rig["body_part_labels"][part_name] = identity

        # Create/update landmark with connection info
        landmark = rig["landmarks"].get(part_name, {})
        landmark["identity"] = identity
        landmark["mobile"] = mobile
        landmark["attached_to"] = attached_to
        landmark["movement_type"] = movement_type
        rig["landmarks"][part_name] = landmark

        applied.append({
            "part_name": part_name,
            "identity": identity,
            "mobile": mobile,
            "attached_to": attached_to,
            "movement_type": movement_type,
        })

    return {
        "applied_count": len(applied),
        "applied": applied,
    }


# ---------------------------------------------------------------------------
# MCP Registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_part_questioner tool."""

    @mcp.tool(
        name="adobe_ai_part_questioner",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_part_questioner(params: AiPartQuestionerInput) -> str:
        """Generate structured questions for unlabeled parts or apply user answers.

        Actions:
        - generate: Create questions for each unlabeled part
        - apply_answers: Apply user responses back to the rig
        """
        rig = _load_rig(params.character_name)
        action = params.action.lower().strip()

        if action == "generate":
            parts = params.parts or []
            if not parts:
                return json.dumps({
                    "error": "No parts provided. Run part_segmenter first.",
                })
            questions = generate_questions(parts, rig)
            return json.dumps({
                "action": "generate",
                "question_groups": questions,
                "total_parts": len(questions),
            }, indent=2)

        elif action == "apply_answers":
            answers = params.answers or []
            if not answers:
                return json.dumps({"error": "No answers provided."})
            result = apply_answers(rig, answers)
            _save_rig(params.character_name, rig)
            return json.dumps({
                "action": "apply_answers",
                **result,
            }, indent=2)

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["generate", "apply_answers"],
            })
