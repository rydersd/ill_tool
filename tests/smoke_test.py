"""Smoke test — verify all tools register and core modules import cleanly."""

import sys


def test_tool_registration():
    """Verify all 45 tools register on the MCP instance."""
    from adobe_mcp.server import mcp

    tools = mcp._tool_manager._tools
    assert len(tools) == 45, f"Expected 45 tools, got {len(tools)}"

    # Spot-check key tools from each app module
    expected = [
        "adobe_list_apps", "adobe_app_status", "adobe_run_jsx", "adobe_run_jsx_file",
        "adobe_ps_new_document", "adobe_ps_layers", "adobe_ps_smart_object",
        "adobe_ai_shapes", "adobe_ai_text", "adobe_ai_export",
        "adobe_pr_project", "adobe_pr_timeline",
        "adobe_ae_comp", "adobe_ae_render",
        "adobe_id_document", "adobe_id_text",
        "adobe_an_document", "adobe_an_timeline",
        "adobe_ame_encode",
    ]
    for name in expected:
        assert name in tools, f"Missing tool: {name}"

    print(f"OK: {len(tools)} tools registered, all spot-checks passed")


def test_imports():
    """Verify key module imports work."""
    from adobe_mcp.config import ADOBE_APPS, IS_MACOS, IS_WINDOWS, SCRIPTS_DIR
    from adobe_mcp.enums import AdobeApp, PhotoshopBlendMode, ImageFormat, ColorSpace
    from adobe_mcp.engine import _run_jsx, _run_powershell, _async_run_jsx
    from adobe_mcp.jsx.polyfills import JSON_POLYFILL
    from adobe_mcp.jsx.templates import escape_jsx_string, escape_jsx_path
    from adobe_mcp.models import PsLayerInput, AiShapeInput, AeCompInput

    assert len(ADOBE_APPS) == 8
    assert AdobeApp.PHOTOSHOP.value == "photoshop"
    assert "JSON" in JSON_POLYFILL
    assert escape_jsx_string('he said "hi"') == 'he said \\"hi\\"'
    assert escape_jsx_path("C:\\Users\\file.jsx") == "C:/Users/file.jsx"

    print("OK: All imports verified")


if __name__ == "__main__":
    test_imports()
    test_tool_registration()
    print("\nAll smoke tests passed.")
