"""JSX Snippet Library — reusable ExtendScript patterns for all Adobe apps.

Each snippet is a tested, composable JSX fragment that the LLM can browse,
combine, and use via adobe_run_jsx. Snippets use {{param}} placeholders
that are filled by the template engine before execution.

Snippets are organized by app and category. The adobe_jsx_snippets tool
lets the LLM browse, search, and compose snippets without needing to
know ExtendScript syntax from scratch.
"""

# ── Snippet Registry ──────────────────────────────────────────────────

SNIPPETS: dict[str, dict] = {}


def _register(name: str, *, app: str, category: str, description: str,
              params: dict[str, str], code: str, example_params: dict | None = None):
    """Register a JSX snippet in the library."""
    SNIPPETS[name] = {
        "name": name,
        "app": app,
        "category": category,
        "description": description,
        "params": params,
        "code": code.strip(),
        "example_params": example_params or {},
    }


# ── Illustrator Snippets ─────────────────────────────────────────────

_register(
    "ai_gradient_fill",
    app="illustrator",
    category="color",
    description="Apply a linear gradient fill to the selected item or a named item",
    params={
        "item_name": "Name of the path item to target",
        "color1_r": "Start color red (0-255)",
        "color1_g": "Start color green",
        "color1_b": "Start color blue",
        "color2_r": "End color red",
        "color2_g": "End color green",
        "color2_b": "End color blue",
        "angle": "Gradient angle in degrees (0-360)",
    },
    code="""
var doc = app.activeDocument;
var item = doc.pathItems.getByName("{{item_name}}");
var grad = doc.gradients.add();
grad.type = GradientType.LINEAR;
var stop1 = grad.gradientStops[0];
var c1 = new RGBColor(); c1.red = {{!color1_r}}; c1.green = {{!color1_g}}; c1.blue = {{!color1_b}};
stop1.color = c1; stop1.rampPoint = 0;
var stop2 = grad.gradientStops[1];
var c2 = new RGBColor(); c2.red = {{!color2_r}}; c2.green = {{!color2_g}}; c2.blue = {{!color2_b}};
stop2.color = c2; stop2.rampPoint = 100;
var gc = new GradientColor();
gc.gradient = grad;
gc.angle = {{!angle}};
item.fillColor = gc;
item.filled = true;
JSON.stringify({result: "gradient_applied", item: "{{item_name}}", angle: {{!angle}}});
""",
    example_params={
        "item_name": "background",
        "color1_r": "0", "color1_g": "0", "color1_b": "0",
        "color2_r": "255", "color2_g": "0", "color2_b": "100",
        "angle": "45",
    },
)

_register(
    "ai_clipping_mask",
    app="illustrator",
    category="masking",
    description="Create a clipping mask from the topmost selected object over all other selected objects",
    params={},
    code="""
var doc = app.activeDocument;
var sel = doc.selection;
if (sel.length < 2) {
    JSON.stringify({error: "Select at least 2 objects: top object becomes the mask"});
} else {
    var group = doc.groupItems.add();
    for (var i = sel.length - 1; i >= 0; i--) {
        sel[i].move(group, ElementPlacement.PLACEATBEGINNING);
    }
    group.clipped = true;
    group.pathItems[0].clipping = true;
    JSON.stringify({result: "clipping_mask_created", items: group.pathItems.length});
}
""",
    example_params={},
)

_register(
    "ai_distribute_grid",
    app="illustrator",
    category="layout",
    description="Distribute selected items into a grid layout with specified columns and spacing",
    params={
        "columns": "Number of columns in the grid",
        "spacing_x": "Horizontal spacing between items in points",
        "spacing_y": "Vertical spacing between items in points",
        "start_x": "Grid starting X position",
        "start_y": "Grid starting Y position",
    },
    code="""
var doc = app.activeDocument;
var items = doc.selection;
if (items.length === 0) {
    JSON.stringify({error: "No items selected"});
} else {
    var cols = {{!columns}};
    var sx = {{!spacing_x}};
    var sy = {{!spacing_y}};
    var baseX = {{!start_x}};
    var baseY = {{!start_y}};
    var maxW = 0, maxH = 0;
    for (var i = 0; i < items.length; i++) {
        var b = items[i].geometricBounds;
        var w = b[2] - b[0]; var h = b[1] - b[3];
        if (w > maxW) maxW = w;
        if (h > maxH) maxH = h;
    }
    for (var i = 0; i < items.length; i++) {
        var col = i % cols;
        var row = Math.floor(i / cols);
        items[i].position = [baseX + col * (maxW + sx), baseY - row * (maxH + sy)];
    }
    JSON.stringify({result: "grid_distributed", items: items.length, columns: cols, rows: Math.ceil(items.length / cols)});
}
""",
    example_params={"columns": "4", "spacing_x": "20", "spacing_y": "20", "start_x": "50", "start_y": "550"},
)

_register(
    "ai_composition_metrics",
    app="illustrator",
    category="analysis",
    description="Analyze composition — item count, artboard fill, color distribution, text inventory, layer structure",
    params={
        "artboard_index": "Artboard index to analyze (default 0)",
    },
    code="""
var doc = app.activeDocument;
var abIdx = parseInt("{{artboard_index}}") || 0;
var ab = doc.artboards[abIdx];
var abRect = ab.artboardRect;
var abW = abRect[2] - abRect[0];
var abH = abRect[1] - abRect[3];
var abArea = abW * abH;

var counts = {
    pathItems: doc.pathItems.length,
    textFrames: doc.textFrames.length,
    groupItems: doc.groupItems.length,
    rasterItems: doc.rasterItems.length,
    placedItems: doc.placedItems.length,
    total: doc.pageItems.length
};

var colors = {};
for (var i = 0; i < doc.pathItems.length && i < 500; i++) {
    var p = doc.pathItems[i];
    if (p.filled) {
        try {
            var fc = p.fillColor;
            if (fc.typename === "RGBColor") {
                var key = Math.round(fc.red) + "," + Math.round(fc.green) + "," + Math.round(fc.blue);
                colors[key] = (colors[key] || 0) + 1;
            }
        } catch(e) {}
    }
}

var colorArr = [];
for (var k in colors) {
    var parts = k.split(",");
    colorArr.push({rgb: [parseInt(parts[0]), parseInt(parts[1]), parseInt(parts[2])], count: colors[k]});
}
colorArr.sort(function(a, b) { return b.count - a.count; });

var texts = [];
for (var t = 0; t < doc.textFrames.length && t < 50; t++) {
    var tf = doc.textFrames[t];
    var fontName = "unknown";
    var fontSize = 0;
    try {
        fontName = tf.textRange.characterAttributes.textFont.name;
        fontSize = tf.textRange.characterAttributes.size;
    } catch(e) {}
    texts.push({
        content: tf.contents.substring(0, 30),
        font: fontName,
        size: Math.round(fontSize * 10) / 10,
        x: Math.round(tf.left),
        y: Math.round(tf.top),
        width: Math.round(tf.width),
        height: Math.round(tf.height)
    });
}

var layers = [];
for (var l = 0; l < doc.layers.length; l++) {
    var ly = doc.layers[l];
    layers.push({
        name: ly.name,
        items: ly.pageItems.length,
        visible: ly.visible,
        locked: ly.locked
    });
}

var coveredArea = 0;
var itemsOnArtboard = 0;
for (var pi = 0; pi < doc.pageItems.length && pi < 500; pi++) {
    var item = doc.pageItems[pi];
    var gb = item.geometricBounds;
    if (gb[2] > abRect[0] && gb[0] < abRect[2] && gb[1] > abRect[3] && gb[3] < abRect[1]) {
        var clampL = Math.max(gb[0], abRect[0]);
        var clampR = Math.min(gb[2], abRect[2]);
        var clampT = Math.min(gb[1], abRect[1]);
        var clampB = Math.max(gb[3], abRect[3]);
        coveredArea += (clampR - clampL) * (clampT - clampB);
        itemsOnArtboard++;
    }
}
var fillRatio = abArea > 0 ? Math.round((coveredArea / abArea) * 100) / 100 : 0;

var result = {
    artboard: {width: Math.round(abW), height: Math.round(abH), area: Math.round(abArea)},
    counts: counts,
    fill_ratio: fillRatio,
    items_on_artboard: itemsOnArtboard,
    colors: colorArr.slice(0, 20),
    text_frames: texts,
    layers: layers
};
JSON.stringify(result);
""",
    example_params={"artboard_index": "0"},
)

_register(
    "ai_random_scatter",
    app="illustrator",
    category="generative",
    description="Randomly scatter copies of a named symbol across the artboard with random scale and rotation",
    params={
        "symbol_name": "Name of the symbol to scatter",
        "count": "Number of copies to create",
        "min_scale": "Minimum scale percentage",
        "max_scale": "Maximum scale percentage",
        "artboard_width": "Artboard width for random positioning",
        "artboard_height": "Artboard height for random positioning",
    },
    code="""
var doc = app.activeDocument;
var sym = null;
for (var i = 0; i < doc.symbols.length; i++) {
    if (doc.symbols[i].name === "{{symbol_name}}") { sym = doc.symbols[i]; break; }
}
if (!sym) {
    JSON.stringify({error: "Symbol '{{symbol_name}}' not found"});
} else {
    var count = {{!count}};
    var w = {{!artboard_width}}; var h = {{!artboard_height}};
    for (var i = 0; i < count; i++) {
        var si = doc.symbolItems.add(sym);
        si.position = [Math.random() * w, -(Math.random() * h)];
        var s = {{!min_scale}} + Math.random() * ({{!max_scale}} - {{!min_scale}});
        si.resize(s, s);
        si.rotate(Math.random() * 360);
    }
    JSON.stringify({result: "scattered", count: count, symbol: "{{symbol_name}}"});
}
""",
    example_params={"symbol_name": "star", "count": "50", "min_scale": "20", "max_scale": "100", "artboard_width": "800", "artboard_height": "600"},
)

# ── Photoshop Snippets ────────────────────────────────────────────────

_register(
    "ps_content_aware_fill",
    app="photoshop",
    category="editing",
    description="Fill the current selection with content-aware fill (remove objects seamlessly)",
    params={},
    code="""
var doc = app.activeDocument;
doc.activeLayer.applyContentAwareFill();
"Content-aware fill applied to selection";
""",
    example_params={},
)

_register(
    "ps_halftone_pattern",
    app="photoshop",
    category="effects",
    description="Apply a color halftone effect to the current layer for a CMYK print-style look",
    params={
        "max_radius": "Maximum dot radius in pixels (4-127)",
        "angle_c": "Cyan channel angle",
        "angle_m": "Magenta channel angle",
        "angle_y": "Yellow channel angle",
        "angle_k": "Black channel angle",
    },
    code="""
var doc = app.activeDocument;
var desc = new ActionDescriptor();
desc.putInteger(charIDToTypeID('Mxm '), {{!max_radius}});
var angles = new ActionList();
angles.putInteger({{!angle_c}});
angles.putInteger({{!angle_m}});
angles.putInteger({{!angle_y}});
angles.putInteger({{!angle_k}});
desc.putList(charIDToTypeID('Angl'), angles);
executeAction(stringIDToTypeID('colorHalftone'), desc, DialogModes.NO);
"Halftone applied: radius={{!max_radius}}";
""",
    example_params={"max_radius": "8", "angle_c": "108", "angle_m": "162", "angle_y": "90", "angle_k": "45"},
)

_register(
    "ps_vignette",
    app="photoshop",
    category="effects",
    description="Create a vignette effect on the current document (dark edges, bright center)",
    params={
        "feather": "Feather radius in pixels for the edge softness",
        "opacity": "Darkness of vignette (0-100)",
    },
    code="""
var doc = app.activeDocument;
var w = doc.width.as("px"); var h = doc.height.as("px");
var margin = Math.min(w, h) * 0.15;
doc.selection.select([
    [margin, margin], [w - margin, margin],
    [w - margin, h - margin], [margin, h - margin]
], SelectionType.REPLACE, {{!feather}}, false);
doc.selection.invert();
var layer = doc.artLayers.add();
layer.name = "Vignette";
layer.blendMode = BlendMode.MULTIPLY;
layer.opacity = {{!opacity}};
var black = new SolidColor(); black.rgb.red = 0; black.rgb.green = 0; black.rgb.blue = 0;
doc.selection.fill(black);
doc.selection.deselect();
"Vignette created: feather={{!feather}}, opacity={{!opacity}}%";
""",
    example_params={"feather": "100", "opacity": "60"},
)

_register(
    "ps_duotone_effect",
    app="photoshop",
    category="effects",
    description="Create a duotone effect using two colors with a gradient map adjustment layer",
    params={
        "color1_r": "Shadow color red (0-255)",
        "color1_g": "Shadow color green",
        "color1_b": "Shadow color blue",
        "color2_r": "Highlight color red",
        "color2_g": "Highlight color green",
        "color2_b": "Highlight color blue",
    },
    code="""
var doc = app.activeDocument;
var desc = new ActionDescriptor();
var gmap = new ActionDescriptor();
var colors = new ActionList();
var c1desc = new ActionDescriptor();
c1desc.putDouble(charIDToTypeID('Rd  '), {{!color1_r}});
c1desc.putDouble(charIDToTypeID('Grn '), {{!color1_g}});
c1desc.putDouble(charIDToTypeID('Bl  '), {{!color1_b}});
var c2desc = new ActionDescriptor();
c2desc.putDouble(charIDToTypeID('Rd  '), {{!color2_r}});
c2desc.putDouble(charIDToTypeID('Grn '), {{!color2_g}});
c2desc.putDouble(charIDToTypeID('Bl  '), {{!color2_b}});
var color1 = new ActionDescriptor();
color1.putObject(stringIDToTypeID('color'), charIDToTypeID('RGBC'), c1desc);
color1.putInteger(stringIDToTypeID('location'), 0);
colors.putObject(stringIDToTypeID('colorStop'), color1);
var color2 = new ActionDescriptor();
color2.putObject(stringIDToTypeID('color'), charIDToTypeID('RGBC'), c2desc);
color2.putInteger(stringIDToTypeID('location'), 4096);
colors.putObject(stringIDToTypeID('colorStop'), color2);
gmap.putList(stringIDToTypeID('colors'), colors);
desc.putObject(stringIDToTypeID('type'), stringIDToTypeID('gradientMapClass'), gmap);
executeAction(stringIDToTypeID('make'), desc, DialogModes.NO);
"Duotone gradient map applied";
""",
    example_params={"color1_r": "10", "color1_g": "0", "color1_b": "30", "color2_r": "255", "color2_g": "100", "color2_b": "50"},
)

# ── After Effects Snippets ────────────────────────────────────────────

_register(
    "ae_wiggle_expression",
    app="aftereffects",
    category="expressions",
    description="Apply a wiggle expression to a property (position, scale, rotation, etc.)",
    params={
        "layer_name": "Name of the layer",
        "property_path": "Property path (e.g. 'position', 'rotation', 'opacity')",
        "frequency": "Wiggles per second",
        "amplitude": "Wiggle amount",
    },
    code="""
var comp = app.project.activeItem;
var layer = comp.layer("{{layer_name}}");
var prop = layer.property("{{property_path}}");
prop.expression = "wiggle({{!frequency}}, {{!amplitude}})";
JSON.stringify({result: "wiggle_applied", layer: "{{layer_name}}", property: "{{property_path}}", freq: {{!frequency}}, amp: {{!amplitude}}});
""",
    example_params={"layer_name": "Logo", "property_path": "position", "frequency": "3", "amplitude": "25"},
)

_register(
    "ae_fade_in_out",
    app="aftereffects",
    category="animation",
    description="Add keyframed fade-in and fade-out to a layer's opacity",
    params={
        "layer_name": "Name of the layer",
        "fade_in_duration": "Fade-in duration in seconds",
        "fade_out_duration": "Fade-out duration in seconds",
    },
    code="""
var comp = app.project.activeItem;
var layer = comp.layer("{{layer_name}}");
var op = layer.property("opacity");
var inT = layer.inPoint;
var outT = layer.outPoint;
op.setValueAtTime(inT, 0);
op.setValueAtTime(inT + {{!fade_in_duration}}, 100);
op.setValueAtTime(outT - {{!fade_out_duration}}, 100);
op.setValueAtTime(outT, 0);
JSON.stringify({result: "fade_added", layer: "{{layer_name}}", fade_in: {{!fade_in_duration}}, fade_out: {{!fade_out_duration}}});
""",
    example_params={"layer_name": "Title", "fade_in_duration": "0.5", "fade_out_duration": "0.5"},
)

# ── Premiere Pro Snippets ─────────────────────────────────────────────

_register(
    "pr_add_markers",
    app="premierepro",
    category="editing",
    description="Add markers at specified time positions on the active sequence",
    params={
        "times_json": "JSON array of time positions in seconds, e.g. [1.0, 5.5, 10.0]",
        "color": "Marker color: green, red, blue, yellow, purple, orange, white",
    },
    code="""
var seq = app.project.activeSequence;
var times = {{!times_json}};
var colorMap = {green: 0, red: 1, blue: 2, yellow: 3, purple: 4, orange: 5, white: 6};
var colorIdx = colorMap["{{color}}"] || 0;
for (var i = 0; i < times.length; i++) {
    var m = seq.markers.createMarker(times[i]);
    m.setColorByIndex(colorIdx);
    m.name = "Marker " + (i + 1);
}
JSON.stringify({result: "markers_added", count: times.length, color: "{{color}}"});
""",
    example_params={"times_json": "[1.0, 5.5, 10.0, 15.0]", "color": "green"},
)

# ── Utility / Cross-App Snippets ─────────────────────────────────────

_register(
    "util_color_palette",
    app="illustrator",
    category="utility",
    description="Generate a visual color palette — creates labeled swatches on the artboard",
    params={
        "colors_json": "JSON array of color objects: [{\"name\": \"primary\", \"r\": 255, \"g\": 0, \"b\": 100}]",
        "swatch_size": "Size of each swatch square in points",
        "start_x": "Starting X position",
        "start_y": "Starting Y position",
    },
    code="""
var doc = app.activeDocument;
var colors = {{!colors_json}};
var size = {{!swatch_size}};
var x = {{!start_x}}; var y = {{!start_y}};

for (var i = 0; i < colors.length; i++) {
    var c = colors[i];
    var rect = doc.pathItems.rectangle(y, x + i * (size + 10), size, size);
    var fc = new RGBColor();
    fc.red = c.r; fc.green = c.g; fc.blue = c.b;
    rect.fillColor = fc;
    rect.stroked = false;
    rect.name = c.name || ("swatch_" + i);

    var label = doc.textFrames.add();
    label.contents = c.name || "";
    label.position = [x + i * (size + 10), y - size - 5];
    label.textRange.characterAttributes.size = 8;
}
JSON.stringify({result: "palette_created", swatches: colors.length});
""",
    example_params={
        "colors_json": '[{"name":"primary","r":255,"g":0,"b":100},{"name":"dark","r":10,"g":10,"b":10},{"name":"accent","r":0,"g":200,"b":255}]',
        "swatch_size": "50",
        "start_x": "50",
        "start_y": "100",
    },
)


def get_snippet(name: str) -> dict | None:
    """Get a snippet by name."""
    return SNIPPETS.get(name)


def search_snippets(query: str, app: str | None = None) -> list[dict]:
    """Search snippets by keyword in name, description, or category."""
    query_lower = query.lower()
    results = []
    for snippet in SNIPPETS.values():
        if app and snippet["app"] != app:
            continue
        if (query_lower in snippet["name"].lower() or
            query_lower in snippet["description"].lower() or
            query_lower in snippet["category"].lower()):
            results.append(snippet)
    return results


def list_snippets(app: str | None = None, category: str | None = None) -> list[dict]:
    """List snippets, optionally filtered by app and/or category."""
    results = []
    for snippet in SNIPPETS.values():
        if app and snippet["app"] != app:
            continue
        if category and snippet["category"] != category:
            continue
        results.append(snippet)
    return results
