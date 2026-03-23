"""Object contact and interaction point management.

Defines spatial zones on characters where interactions occur (grip points,
ground contact, collision areas, trigger zones). Tests overlap between
zones on different rigs for interaction detection.

Zones are stored in the rig under 'interaction_zones'.
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


class AiInteractionZonesInput(BaseModel):
    """Manage interaction zones on character rigs."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ...,
        description="Action: define_zone, check_interaction, get_zones",
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    zone_name: Optional[str] = Field(
        default=None, description="Name for the interaction zone"
    )
    position: Optional[list[float]] = Field(
        default=None, description="Zone center [x, y]"
    )
    radius: Optional[float] = Field(
        default=None, description="Zone radius", gt=0
    )
    zone_type: Optional[str] = Field(
        default=None,
        description="Zone type: grip, ground_contact, collision, trigger",
    )
    # For check_interaction
    other_character: Optional[str] = Field(
        default=None, description="Other character for interaction check"
    )
    zone_a: Optional[str] = Field(
        default=None, description="Zone name on this character"
    )
    zone_b: Optional[str] = Field(
        default=None, description="Zone name on other character"
    )


# ---------------------------------------------------------------------------
# Zone types
# ---------------------------------------------------------------------------

VALID_ZONE_TYPES = {"grip", "ground_contact", "collision", "trigger"}


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def define_interaction_zone(
    rig: dict,
    zone_name: str,
    position: list[float],
    radius: float,
    zone_type: str,
) -> dict:
    """Define an interaction zone on a rig.

    Args:
        rig: the character rig dict
        zone_name: unique name for the zone
        position: [x, y] center coordinates
        radius: zone radius
        zone_type: one of grip, ground_contact, collision, trigger

    Returns:
        The zone definition dict.

    Raises:
        ValueError: if zone_type is invalid.
    """
    if zone_type not in VALID_ZONE_TYPES:
        raise ValueError(
            f"Invalid zone type '{zone_type}'. "
            f"Valid types: {sorted(VALID_ZONE_TYPES)}"
        )

    if "interaction_zones" not in rig:
        rig["interaction_zones"] = {}

    zone = {
        "name": zone_name,
        "position": list(position),
        "radius": radius,
        "zone_type": zone_type,
    }
    rig["interaction_zones"][zone_name] = zone
    return zone


def check_interaction(
    rig_a: dict,
    zone_a_name: str,
    rig_b: dict,
    zone_b_name: str,
) -> dict:
    """Test if two zones on different rigs overlap.

    Two zones overlap when the distance between their centers is less
    than the sum of their radii.

    Args:
        rig_a: first character rig
        zone_a_name: zone name on rig_a
        rig_b: second character rig
        zone_b_name: zone name on rig_b

    Returns:
        {"overlapping": bool, "distance": float, "threshold": float, ...}
    """
    zones_a = rig_a.get("interaction_zones", {})
    zones_b = rig_b.get("interaction_zones", {})

    if zone_a_name not in zones_a:
        return {"error": f"Zone '{zone_a_name}' not found on first rig"}
    if zone_b_name not in zones_b:
        return {"error": f"Zone '{zone_b_name}' not found on second rig"}

    za = zones_a[zone_a_name]
    zb = zones_b[zone_b_name]

    dx = za["position"][0] - zb["position"][0]
    dy = za["position"][1] - zb["position"][1]
    distance = math.sqrt(dx * dx + dy * dy)
    threshold = za["radius"] + zb["radius"]

    return {
        "overlapping": distance < threshold,
        "distance": round(distance, 4),
        "threshold": round(threshold, 4),
        "zone_a": za,
        "zone_b": zb,
    }


def get_zones(rig: dict) -> list[dict]:
    """List all interaction zones on a rig.

    Returns:
        List of zone definition dicts.
    """
    zones = rig.get("interaction_zones", {})
    return list(zones.values())


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_interaction_zones tool."""

    @mcp.tool(
        name="adobe_ai_interaction_zones",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_interaction_zones(params: AiInteractionZonesInput) -> str:
        """Manage interaction zones for object contact points.

        Actions:
        - define_zone: create a named interaction zone on a rig
        - check_interaction: test if two zones overlap
        - get_zones: list all zones on a rig
        """
        action = params.action.lower().strip()
        rig = _load_rig(params.character_name)

        if action == "define_zone":
            if not params.zone_name or params.position is None or params.radius is None or not params.zone_type:
                return json.dumps({
                    "error": "define_zone requires zone_name, position, radius, zone_type"
                })
            try:
                zone = define_interaction_zone(
                    rig, params.zone_name, params.position,
                    params.radius, params.zone_type,
                )
            except ValueError as e:
                return json.dumps({"error": str(e)})

            _save_rig(params.character_name, rig)
            return json.dumps({
                "action": "define_zone",
                "zone": zone,
                "total_zones": len(rig.get("interaction_zones", {})),
            })

        elif action == "check_interaction":
            if not params.other_character or not params.zone_a or not params.zone_b:
                return json.dumps({
                    "error": "check_interaction requires other_character, zone_a, zone_b"
                })
            rig_b = _load_rig(params.other_character)
            result = check_interaction(rig, params.zone_a, rig_b, params.zone_b)
            return json.dumps({
                "action": "check_interaction",
                **result,
            })

        elif action == "get_zones":
            zones = get_zones(rig)
            return json.dumps({
                "action": "get_zones",
                "zones": zones,
                "count": len(zones),
            })

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["define_zone", "check_interaction", "get_zones"],
            })
