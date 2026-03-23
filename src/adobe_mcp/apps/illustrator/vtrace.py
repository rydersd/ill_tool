"""Trace raster images to clean vector SVG paths using vtracer (Rust-based).

Better than Illustrator's Image Trace for cartoon/graphic art — produces
cleaner paths with fewer anchors and more faithful color quantization.
"""

import json
import os
import re
import tempfile

import vtracer

from adobe_mcp.engine import _async_run_jsx
from adobe_mcp.jsx.templates import escape_jsx_string
from adobe_mcp.apps.illustrator.models import AiVtraceInput


def register(mcp):
    """Register the adobe_ai_vtrace tool."""

    @mcp.tool(
        name="adobe_ai_vtrace",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_vtrace(params: AiVtraceInput) -> str:
        """Convert a raster image to clean SVG vector paths using vtracer, optionally placing the result in Illustrator."""

        # ------------------------------------------------------------------
        # Validate input image exists
        # ------------------------------------------------------------------
        if not os.path.isfile(params.image_path):
            return f"Error: Image not found at {params.image_path}"

        # ------------------------------------------------------------------
        # Step 1: Run vtracer to convert raster -> SVG string
        # ------------------------------------------------------------------
        try:
            svg_str = vtracer.convert_image_to_svg_py(
                image_path=params.image_path,
                colormode="color",
                hierarchical="stacked",
                mode=params.mode,
                filter_speckle=params.filter_speckle,
                color_precision=params.color_precision,
                layer_difference=25,
                corner_threshold=params.corner_threshold,
                length_threshold=4.0,
                max_iterations=10,
                splice_threshold=45,
                path_precision=params.path_precision,
            )
        except Exception as exc:
            return f"Error: vtracer failed: {exc}"

        # ------------------------------------------------------------------
        # Step 2: Parse SVG to extract path data and metadata
        # ------------------------------------------------------------------
        viewbox_match = re.search(r'viewBox="([^"]*)"', svg_str)
        viewbox = viewbox_match.group(1) if viewbox_match else ""

        path_matches = re.findall(r'<path[^>]*d="([^"]*)"[^>]*/>', svg_str)
        fill_matches = re.findall(r'<path[^>]*fill="([^"]*)"[^>]*/>', svg_str)
        path_count = len(path_matches)

        # ------------------------------------------------------------------
        # Step 3: Save SVG to a temp file
        # ------------------------------------------------------------------
        svg_path = tempfile.mktemp(suffix=".svg", prefix="vtrace_")
        with open(svg_path, "w") as f:
            f.write(svg_str)

        # ------------------------------------------------------------------
        # Step 4: Optionally place in Illustrator
        # ------------------------------------------------------------------
        if params.place_in_ai:
            escaped_svg_path = escape_jsx_string(svg_path)
            escaped_layer_name = escape_jsx_string(params.layer_name)

            jsx = f"""
(function() {{
    var origDoc = app.activeDocument;

    // Find or create target layer
    var targetLayer = null;
    for (var i = 0; i < origDoc.layers.length; i++) {{
        if (origDoc.layers[i].name === "{escaped_layer_name}") {{
            targetLayer = origDoc.layers[i];
            break;
        }}
    }}
    if (!targetLayer) {{
        targetLayer = origDoc.layers.add();
        targetLayer.name = "{escaped_layer_name}";
    }}

    // Open SVG as new document
    var svgFile = new File("{escaped_svg_path}");
    var svgDoc = app.open(svgFile);

    // Select all and copy
    svgDoc.selectAll();
    app.copy();
    svgDoc.close(SaveOptions.DONOTSAVECHANGES);

    // Paste into original document on target layer
    origDoc.activate();
    origDoc.activeLayer = targetLayer;
    app.paste();

    // Get info about pasted items
    var sel = origDoc.selection;
    var info = {{
        layer: targetLayer.name,
        items_pasted: sel.length,
        bounds: sel.length > 0 ? sel[0].geometricBounds : []
    }};
    return JSON.stringify(info);
}})();
"""

            result = await _async_run_jsx("illustrator", jsx)

            if not result["success"]:
                # SVG was still created — return that with an error note
                return json.dumps({
                    "svg_path": svg_path,
                    "path_count": path_count,
                    "viewbox": viewbox,
                    "mode": params.mode,
                    "color_precision": params.color_precision,
                    "placed_in_ai": False,
                    "placement_error": result.get("stderr", "Unknown JSX error"),
                })

            # Parse JSX result for placement info
            try:
                placement = json.loads(result["stdout"])
                return json.dumps({
                    "svg_path": svg_path,
                    "path_count": path_count,
                    "viewbox": viewbox,
                    "placed_in_ai": True,
                    "layer": placement.get("layer", params.layer_name),
                    "items_pasted": placement.get("items_pasted", 0),
                    "bounds": placement.get("bounds", []),
                })
            except (json.JSONDecodeError, TypeError):
                # JSX returned non-JSON — still report success with raw output
                return json.dumps({
                    "svg_path": svg_path,
                    "path_count": path_count,
                    "viewbox": viewbox,
                    "placed_in_ai": True,
                    "layer": params.layer_name,
                    "jsx_output": result["stdout"],
                })

        # ------------------------------------------------------------------
        # Step 5: Return result (no Illustrator placement)
        # ------------------------------------------------------------------
        return json.dumps({
            "svg_path": svg_path,
            "path_count": path_count,
            "viewbox": viewbox,
            "mode": params.mode,
            "color_precision": params.color_precision,
        })
