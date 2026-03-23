"""App-based tool registration orchestrator.

All 8 app packages import from apps/<app>/ sub-packages.
Split apps (premiere, aftereffects, illustrator, photoshop) have per-feature files.
Flat apps (common, indesign, animate, media_encoder) use a single tools.py.
"""

from adobe_mcp.apps.common import register_common_tools, register_compare_tool
from adobe_mcp.apps.photoshop import register_photoshop_tools
from adobe_mcp.apps.illustrator import register_illustrator_tools
from adobe_mcp.apps.premiere import register_premiere_tools
from adobe_mcp.apps.aftereffects import register_aftereffects_tools
from adobe_mcp.apps.indesign import register_indesign_tools
from adobe_mcp.apps.animate import register_animate_tools
from adobe_mcp.apps.media_encoder import register_media_encoder_tools


def register_all_tools(mcp):
    """Register all Adobe MCP tools on the given FastMCP instance.

    Delegates to per-app registration functions. Currently passes through
    to tools/ modules; will be updated as apps are migrated in-place.
    """
    register_common_tools(mcp)
    register_compare_tool(mcp)
    register_photoshop_tools(mcp)
    register_illustrator_tools(mcp)
    register_premiere_tools(mcp)
    register_aftereffects_tools(mcp)
    register_indesign_tools(mcp)
    register_animate_tools(mcp)
    register_media_encoder_tools(mcp)
