// void_run_01_setup.jsx — Chunk 01: Artboard + Layer Setup
// Creates the artboard, layer stack, and background for a VOID machine
// MUST run first — all subsequent chunks depend on the artboard and layers
// Depends on: void_engine_lib.jsx, void_style_*.jsx, void_engine_compose.jsx
// Globals expected: SEED (number)

(function () {
    var doc = app.activeDocument;
    var abName = "VOID_s" + SEED;

    // ═══════════════════════════════════════════════════════════════
    // FIND LOWEST EXISTING ARTBOARD
    // Illustrator Y-up: artboardRect = [left, top, right, bottom]
    // "lowest visually" = smallest bottom value
    // New artboard goes below all existing ones with a 120pt gap
    // ═══════════════════════════════════════════════════════════════
    var lowestBottom = 0;
    for (var i = 0; i < doc.artboards.length; i++) {
        var r = doc.artboards[i].artboardRect;
        // r[3] is the bottom edge (smaller Y = further down visually)
        if (r[3] < lowestBottom) {
            lowestBottom = r[3];
        }
    }

    // Position new artboard 120pt below the lowest existing one
    var gap = 120;
    var newTop = lowestBottom - gap;
    var newLeft = 0;
    var newRight = newLeft + AB_W;
    var newBottom = newTop - AB_H;

    // ═══════════════════════════════════════════════════════════════
    // CREATE ARTBOARD
    // artboardRect format: [left, top, right, bottom] (Y-up)
    // ═══════════════════════════════════════════════════════════════
    var abRect = [newLeft, newTop, newRight, newBottom];
    var ab = doc.artboards.add(abRect);
    ab.name = abName;

    // Store artboard origin for coordinate conversions
    var abX = newLeft;
    var abY = newTop;

    // ═══════════════════════════════════════════════════════════════
    // CREATE ROOT LAYER
    // Named same as artboard for easy lookup by chunkInit()
    // ═══════════════════════════════════════════════════════════════
    var root = doc.layers.add();
    root.name = abName;

    // ═══════════════════════════════════════════════════════════════
    // CREATE SUB-LAYERS
    // Order: first created = topmost in Layers panel
    // We want TYPOGRAPHY on top, BG on bottom
    // So create in visual order: top → bottom
    // Illustrator layers.add() inserts at TOP of parent, so we
    // create in REVERSE order (bottom first) to get correct stacking
    // ═══════════════════════════════════════════════════════════════
    var layerNames = [
        "TYPOGRAPHY",     // topmost — text overlays everything
        "DATA_PANELS",    // technical readout boxes
        "DIMENSIONS",     // engineering measurement lines
        "CONNECTIONS",    // pipes and wiring between components
        "HOUSINGS",       // rectangular enclosures on cylinders
        "SECTIONS",       // cross-section turbine faces
        "CYLINDERS",      // main cylinder bodies and tubes
        "GRID",           // construction grid overlay
        "BG"              // background fill — bottommost
    ];

    // Create in reverse so first entry ends up on top
    for (var li = layerNames.length - 1; li >= 0; li--) {
        var sub = root.layers.add();
        sub.name = layerNames[li];
    }

    // ═══════════════════════════════════════════════════════════════
    // FILL BACKGROUND
    // Full-bleed rectangle on BG layer using style background color
    // mkFilledRect expects Illustrator coords: (layer, x, y_top, w, h)
    // ═══════════════════════════════════════════════════════════════
    var bgLayer = findLayer(root, "BG");
    mkFilledRect(bgLayer, abX, abY, AB_W, AB_H, sCol("bg"));

    // ═══════════════════════════════════════════════════════════════
    // CONSTRUCTION GRID (conditional)
    // When STYLE.composition.negative_space_fill is true, draw faint
    // construction lines across the artboard at each angle in the
    // style's angle_grid, plus horizontal (0 deg) if not already present
    // ═══════════════════════════════════════════════════════════════
    if (STYLE.composition.negative_space_fill) {
        var gridLayer = findLayer(root, "GRID");
        var gridCol = sCol("ghost");
        var gridSW = sSW("construction");
        var gridSpacing = 200;

        // Collect unique angles: style angles + horizontal baseline
        var angles = [];
        var anglesSeen = {};
        for (var ai = 0; ai < STYLE.angle_grid.length; ai++) {
            var ang = STYLE.angle_grid[ai];
            if (!anglesSeen[ang]) {
                anglesSeen[ang] = true;
                angles[angles.length] = ang;
            }
        }
        // Ensure horizontal (0 deg) is included
        if (!anglesSeen[0]) {
            angles[angles.length] = 0;
        }

        // Draw grid lines at each unique angle
        for (var gi = 0; gi < angles.length; gi++) {
            drawGridLines(gridLayer, abX, abY, AB_W, AB_H,
                angles[gi], gridSpacing, gridCol, gridSW);
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // FINALIZE
    // Redraw viewport and save document to persist artboard + layers
    // ═══════════════════════════════════════════════════════════════
    app.redraw();
    doc.save();

    return "VOID_s" + SEED + " setup complete: artboard " + AB_W + "x" + AB_H
        + " at [" + abX + ", " + abY + "], 9 layers created";
})();
