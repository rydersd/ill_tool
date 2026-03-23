"""Asset versioning for rig change tracking.

Tracks version history for character rigs, logging each change with
a description, timestamp, and full snapshot for rollback.

Version history is stored in the rig under 'version_history'.
"""

import copy
import json
import math
import os
import time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from adobe_mcp.apps.illustrator.rig_data import _load_rig, _save_rig


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiAssetVersioningInput(BaseModel):
    """Track rig version changes with rollback support."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ...,
        description="Action: bump_version, get_history, rollback",
    )
    character_name: str = Field(
        default="character", description="Character identifier"
    )
    change_description: Optional[str] = Field(
        default=None, description="Description of the change for version bump"
    )
    version_number: Optional[int] = Field(
        default=None, description="Version number to rollback to"
    )


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def bump_version(rig: dict, change_description: str) -> dict:
    """Increment rig version and log the change with a full snapshot.

    Args:
        rig: the character rig dict (modified in place)
        change_description: human-readable description of what changed

    Returns:
        The new version entry dict.
    """
    if "version_history" not in rig:
        rig["version_history"] = []

    # Determine new version number
    history = rig["version_history"]
    if history:
        current_version = max(entry["version"] for entry in history)
        new_version = current_version + 1
    else:
        new_version = 1

    # Take a snapshot of the current rig state (excluding version_history
    # itself to avoid recursive growth)
    snapshot = {k: copy.deepcopy(v) for k, v in rig.items() if k != "version_history"}

    entry = {
        "version": new_version,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "description": change_description,
        "snapshot": snapshot,
    }
    history.append(entry)

    return entry


def get_version_history(rig: dict) -> list[dict]:
    """Return the changelog (version history without snapshots for brevity).

    Returns:
        List of version entries with version, timestamp, description.
    """
    history = rig.get("version_history", [])
    # Return summaries without the full snapshots for readability
    return [
        {
            "version": entry["version"],
            "timestamp": entry["timestamp"],
            "description": entry["description"],
        }
        for entry in history
    ]


def rollback(rig: dict, version_number: int) -> dict:
    """Restore rig to a previous version snapshot.

    The version history is preserved up to and including the target version,
    and a new "rollback" entry is added.

    Args:
        rig: the character rig dict (modified in place)
        version_number: the version to restore to

    Returns:
        The restored rig state.

    Raises:
        ValueError: if version_number is not found.
    """
    history = rig.get("version_history", [])
    target_entry = None
    for entry in history:
        if entry["version"] == version_number:
            target_entry = entry
            break

    if target_entry is None:
        available = [e["version"] for e in history]
        raise ValueError(
            f"Version {version_number} not found. "
            f"Available versions: {available}"
        )

    # Restore the snapshot into the rig
    snapshot = target_entry["snapshot"]
    # Keep version_history but trim everything after the target version,
    # then add a rollback entry
    preserved_history = [e for e in history if e["version"] <= version_number]

    # Clear rig and restore from snapshot
    keys_to_remove = [k for k in rig if k != "version_history"]
    for k in keys_to_remove:
        del rig[k]

    for k, v in copy.deepcopy(snapshot).items():
        rig[k] = v

    # Restore the history with rollback note
    rollback_entry = {
        "version": version_number,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "description": f"Rolled back to version {version_number}",
        "snapshot": copy.deepcopy(snapshot),
    }
    preserved_history.append(rollback_entry)
    rig["version_history"] = preserved_history

    return rig


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_asset_versioning tool."""

    @mcp.tool(
        name="adobe_ai_asset_versioning",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_asset_versioning(params: AiAssetVersioningInput) -> str:
        """Track rig version changes with rollback support.

        Actions:
        - bump_version: increment version with change description
        - get_history: return version changelog
        - rollback: restore rig to a previous version
        """
        action = params.action.lower().strip()
        rig = _load_rig(params.character_name)

        if action == "bump_version":
            if not params.change_description:
                return json.dumps({
                    "error": "bump_version requires change_description"
                })
            entry = bump_version(rig, params.change_description)
            _save_rig(params.character_name, rig)
            return json.dumps({
                "action": "bump_version",
                "version": entry["version"],
                "timestamp": entry["timestamp"],
                "description": entry["description"],
            })

        elif action == "get_history":
            history = get_version_history(rig)
            return json.dumps({
                "action": "get_history",
                "history": history,
                "version_count": len(history),
            })

        elif action == "rollback":
            if params.version_number is None:
                return json.dumps({
                    "error": "rollback requires version_number"
                })
            try:
                rollback(rig, params.version_number)
            except ValueError as e:
                return json.dumps({"error": str(e)})
            _save_rig(params.character_name, rig)
            return json.dumps({
                "action": "rollback",
                "restored_to_version": params.version_number,
                "character_name": params.character_name,
            })

        else:
            return json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["bump_version", "get_history", "rollback"],
            })
