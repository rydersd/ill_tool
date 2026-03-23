"""Trace raster images to vector paths in Illustrator via Image Trace."""

import json

from adobe_mcp.engine import _async_run_jsx
from adobe_mcp.jsx.templates import escape_jsx_string
from adobe_mcp.apps.illustrator.models import AiImageTraceInput
from adobe_mcp.tokens import tokens as token_registry


def register(mcp):
    """Register the adobe_ai_image_trace tool."""

    @mcp.tool(
        name="adobe_ai_image_trace",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_image_trace(params: AiImageTraceInput) -> str:
        """Place a raster image, run Image Trace, expand to editable paths, and optionally recolor to design token palette."""

        # Escape the image path for safe JSX string embedding
        escaped_path = escape_jsx_string(params.image_path)
        escaped_layer_name = escape_jsx_string(params.layer_name or "traced")
        escaped_preset = escape_jsx_string(params.preset)

        # Build optional max_colors override
        max_colors_jsx = ""
        if params.max_colors is not None:
            max_colors_jsx = f"tracing.tracingOptions.maxColors = {params.max_colors};"

        # Build optional position override (applied after trace/expand)
        position_jsx = ""
        if params.x is not None and params.y is not None:
            position_jsx = f"resultGroup.position = [{params.x}, {params.y}];"
        elif params.x is not None:
            position_jsx = f"resultGroup.position = [{params.x}, resultGroup.position[1]];"
        elif params.y is not None:
            position_jsx = f"resultGroup.position = [resultGroup.position[0], {params.y}];"

        # Build recolor JSX if requested — inject color tokens as a JSON array
        recolor_jsx = ""
        if params.recolor_to_dna:
            color_tokens = token_registry.list_tokens(category="color")
            if color_tokens:
                # Extract RGB values from color tokens
                palette = []
                for t in color_tokens:
                    val = t.get("value", {})
                    if isinstance(val, dict) and "r" in val and "g" in val and "b" in val:
                        palette.append({
                            "name": t.get("name", ""),
                            "r": val["r"],
                            "g": val["g"],
                            "b": val["b"],
                        })
                if palette:
                    palette_json = json.dumps(palette)
                    recolor_jsx = f"""
// --- Recolor to design token palette ---
var palette = {palette_json};

// Find nearest palette color by Euclidean distance in RGB space
function nearestColor(r, g, b) {{
    var bestIdx = 0;
    var bestDist = 999999;
    for (var i = 0; i < palette.length; i++) {{
        var dr = r - palette[i].r;
        var dg = g - palette[i].g;
        var db = b - palette[i].b;
        var dist = dr * dr + dg * dg + db * db;
        if (dist < bestDist) {{
            bestDist = dist;
            bestIdx = i;
        }}
    }}
    return palette[bestIdx];
}}

// Apply nearest palette color to each path in the expanded group
for (var p = 0; p < resultGroup.pathItems.length; p++) {{
    var pi = resultGroup.pathItems[p];
    if (pi.filled && pi.fillColor.typename === "RGBColor") {{
        var nearest = nearestColor(
            pi.fillColor.red,
            pi.fillColor.green,
            pi.fillColor.blue
        );
        var newFill = new RGBColor();
        newFill.red = nearest.r;
        newFill.green = nearest.g;
        newFill.blue = nearest.b;
        pi.fillColor = newFill;
        recolorCount++;
    }}
}}
"""

        # Decide expand or keep live trace based on params
        expand_flag = "true" if params.expand else "false"

        # ----- Main JSX: API approach with menu-command fallback -----
        jsx = f"""
(function() {{
    var doc = app.activeDocument;
    var recolorCount = 0;

    // --- Step 1: Place the raster image ---
    var placed = doc.placedItems.add();
    placed.file = new File("{escaped_path}");

    // --- Step 2: Embed to convert from linked to raster ---
    placed.embed();

    // After embed the placed item becomes a raster item at the end of the collection
    var raster = doc.rasterItems[doc.rasterItems.length - 1];

    var resultGroup = null;

    // --- Step 3: Trace using the scripting API (primary approach) ---
    try {{
        var tracePlugin = raster.trace();
        // tracePlugin is a PluginItem with a .tracing property
        var tracing = tracePlugin.tracing;
        tracing.tracingOptions.loadFromPreset("{escaped_preset}");
        {max_colors_jsx}

        if ({expand_flag}) {{
            // Expand tracing to editable vector paths (returns a GroupItem)
            resultGroup = tracing.expandTracing();
        }} else {{
            // Keep as live trace — return info about the plugin item
            tracePlugin.name = "{escaped_layer_name}";
            var info = {{
                name: tracePlugin.name,
                type: "liveTrace",
                expanded: false,
                bounds: tracePlugin.geometricBounds
            }};
            return JSON.stringify(info);
        }}
    }} catch (apiErr) {{
        // --- Step 3b: Fallback via menu commands ---
        try {{
            // Select the raster item for menu-command tracing
            doc.selection = null;
            raster.selected = true;

            // Map preset names to menu command IDs
            var presetMenuMap = {{
                "3 Colors": "Live Trace Tracing Presets 3 Colors",
                "6 Colors": "Live Trace Tracing Presets 6 Colors",
                "16 Colors": "Live Trace Tracing Presets 16 Colors",
                "High Fidelity Photo": "Live Trace Tracing Presets High Fidelity Photo",
                "Low Fidelity Photo": "Live Trace Tracing Presets Low Fidelity Photo",
                "Black and White Logo": "Live Trace Tracing Presets Black and White Logo",
                "Shades of Gray": "Live Trace Tracing Presets Shades of Gray",
                "Silhouettes": "Live Trace Tracing Presets Silhouettes",
                "Line Art": "Live Trace Tracing Presets Line Art",
                "Technical Drawing": "Live Trace Tracing Presets Technical Drawing"
            }};
            var menuCmd = presetMenuMap["{escaped_preset}"];
            if (!menuCmd) {{
                menuCmd = "Live Trace Tracing Presets 6 Colors";
            }}

            app.executeMenuCommand(menuCmd);

            if ({expand_flag}) {{
                // Expand the live trace result
                app.executeMenuCommand("expandStyle");

                // After expand, the result should be the current selection
                if (doc.selection.length > 0) {{
                    resultGroup = doc.selection[0];
                }} else {{
                    // Try the last page item
                    resultGroup = doc.pageItems[doc.pageItems.length - 1];
                }}
            }} else {{
                // Live trace kept — return info about selection
                var sel = doc.selection.length > 0 ? doc.selection[0] : doc.pageItems[doc.pageItems.length - 1];
                sel.name = "{escaped_layer_name}";
                var info = {{
                    name: sel.name,
                    type: "liveTrace",
                    expanded: false,
                    bounds: sel.geometricBounds,
                    note: "Used menu-command fallback"
                }};
                return JSON.stringify(info);
            }}
        }} catch (menuErr) {{
            return JSON.stringify({{
                error: "Image Trace failed",
                apiError: apiErr.toString(),
                menuError: menuErr.toString()
            }});
        }}
    }}

    // --- Step 4: Name and position the expanded result ---
    if (resultGroup) {{
        resultGroup.name = "{escaped_layer_name}";
        {position_jsx}

        {recolor_jsx}

        var info = {{
            name: resultGroup.name,
            type: resultGroup.typename,
            expanded: true,
            pathCount: resultGroup.pathItems ? resultGroup.pathItems.length : 0,
            bounds: resultGroup.geometricBounds,
            recolored: recolorCount
        }};
        return JSON.stringify(info);
    }}

    return JSON.stringify({{ error: "No result group produced after trace + expand" }});
}})();
"""

        result = await _async_run_jsx("illustrator", jsx)
        if not result["success"]:
            return f"Error: {result['stderr']}"

        # Parse the result to provide a clean summary
        stdout = result["stdout"]
        try:
            data = json.loads(stdout)
            if "error" in data:
                return f"Image Trace failed: {data['error']}" + (
                    f" (API: {data.get('apiError', 'n/a')}, Menu: {data.get('menuError', 'n/a')})"
                    if "apiError" in data else ""
                )
            # Build a readable summary
            parts = [f"Image traced: '{data.get('name', 'traced')}'"]
            if data.get("expanded"):
                parts.append(f"{data.get('pathCount', '?')} paths")
            else:
                parts.append("live trace (not expanded)")
            if data.get("recolored", 0) > 0:
                parts.append(f"{data['recolored']} paths recolored to DNA palette")
            bounds = data.get("bounds", [])
            if bounds:
                parts.append(f"bounds: {bounds}")
            return " | ".join(parts)
        except (json.JSONDecodeError, TypeError):
            # JSX returned a plain string — pass through as-is
            return stdout
