"""Place a reference image as a locked, dimmed background layer in Illustrator."""

import json

from adobe_mcp.engine import _async_run_jsx
from adobe_mcp.jsx.templates import escape_jsx_string
from adobe_mcp.apps.illustrator.models import AiReferenceUnderlayInput


def register(mcp):
    """Register the adobe_ai_reference_underlay tool."""

    @mcp.tool(
        name="adobe_ai_reference_underlay",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_reference_underlay(params: AiReferenceUnderlayInput) -> str:
        """Place a reference image as a locked, dimmed background layer for tracing. Idempotent — re-running replaces the existing reference."""

        escaped_path = escape_jsx_string(params.image_path)
        escaped_drawing_name = escape_jsx_string(params.drawing_layer_name)
        opacity = params.opacity
        fit_to_artboard = "true" if params.fit_to_artboard else "false"

        jsx = f"""
(function() {{
    var doc = app.activeDocument;

    // --- Helper: find or create a layer by name ---
    function findOrCreateLayer(doc, name) {{
        for (var i = 0; i < doc.layers.length; i++) {{
            if (doc.layers[i].name === name) return doc.layers[i];
        }}
        var lyr = doc.layers.add();
        lyr.name = name;
        return lyr;
    }}

    // --- Step 1: Get or create the Reference layer ---
    var refLayer = findOrCreateLayer(doc, "Reference");

    // Unlock it so we can modify contents (may be locked from a previous run)
    refLayer.locked = false;
    refLayer.visible = true;

    // --- Step 2: Clear any existing items on the Reference layer ---
    while (refLayer.pageItems.length > 0) {{
        refLayer.pageItems[0].remove();
    }}

    // --- Step 3: Move Reference layer to the bottom of the stack ---
    // In Illustrator, layers are indexed 0 = top, so move to last position.
    // zOrder on layers is done by reordering — move after the last layer.
    if (doc.layers.length > 1) {{
        refLayer.move(doc.layers[doc.layers.length - 1], ElementPlacement.PLACEAFTER);
    }}

    // --- Step 4: Place the image on the Reference layer ---
    doc.activeLayer = refLayer;
    var placed = refLayer.placedItems.add();
    placed.file = new File("{escaped_path}");
    placed.embed();

    // After embed, the placed item becomes a raster item.
    // Re-acquire the item from the layer to get accurate bounds.
    var imgItem = refLayer.pageItems[refLayer.pageItems.length - 1];

    // --- Step 5: Fit to artboard if requested ---
    var scaleApplied = 100;
    if ({fit_to_artboard}) {{
        var ab = doc.artboards[doc.artboards.getActiveArtboardIndex()];
        var abRect = ab.artboardRect; // [left, top, right, bottom]
        var abW = abRect[2] - abRect[0];
        var abH = abRect[1] - abRect[3]; // top > bottom in AI coordinate system

        var imgW = imgItem.width;
        var imgH = imgItem.height;
        scaleApplied = Math.min(abW / imgW, abH / imgH) * 100;
        imgItem.resize(scaleApplied, scaleApplied);

        // Center on artboard
        imgItem.position = [
            abRect[0] + (abW - imgItem.width) / 2,
            abRect[1] - (abH - imgItem.height) / 2
        ];
    }}

    // --- Step 6: Set Reference layer opacity and lock it ---
    refLayer.opacity = {opacity};
    refLayer.locked = true;

    // --- Step 7: Create or find the Drawing layer above Reference ---
    var drawingLayer = findOrCreateLayer(doc, "{escaped_drawing_name}");
    drawingLayer.locked = false;
    drawingLayer.visible = true;

    // Ensure Drawing layer is above Reference (move to top-ish position)
    // If it was just created, it's already at the top. If it existed, move it
    // above Reference to be sure.
    if (doc.layers.length > 1) {{
        // Move drawing layer before the first layer (top of stack) if not already there
        try {{
            drawingLayer.move(doc.layers[0], ElementPlacement.PLACEBEFORE);
        }} catch (e) {{
            // Already at the top — no-op
        }}
    }}

    doc.activeLayer = drawingLayer;

    // --- Step 8: Build result info ---
    var info = {{
        referenceLayer: "Reference",
        drawingLayer: "{escaped_drawing_name}",
        imagePath: "{escaped_path}",
        imageBounds: imgItem.geometricBounds,
        scaleApplied: Math.round(scaleApplied * 100) / 100,
        opacity: {opacity},
        locked: true
    }};
    return JSON.stringify(info);
}})();
"""

        result = await _async_run_jsx("illustrator", jsx)
        if not result["success"]:
            return f"Error: {result['stderr']}"

        stdout = result["stdout"]
        try:
            data = json.loads(stdout)
            if "error" in data:
                return f"Reference underlay failed: {data['error']}"
            parts = [
                f"Reference placed on '{data.get('referenceLayer', 'Reference')}' layer",
                f"opacity {data.get('opacity', '?')}%",
                f"scale {data.get('scaleApplied', '?')}%",
                f"locked: {data.get('locked', True)}",
                f"active layer: '{data.get('drawingLayer', 'Drawing')}'",
            ]
            bounds = data.get("imageBounds", [])
            if bounds:
                parts.append(f"bounds: {bounds}")
            return " | ".join(parts)
        except (json.JSONDecodeError, TypeError):
            return stdout
