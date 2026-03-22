// void_run_05_sections.jsx — Chunk 05: Cross-Section Turbine Faces
// Renders concentric rings, spokes, turbine blades, and cross-hatching
// for each cross-section defined in the machine composition.
// Depends on: void_engine_lib.jsx, void_style_*.jsx, void_engine_compose.jsx
// Globals expected: SEED (number)

(function () {
    // ═══════════════════════════════════════════════════════════════
    // RENDER CROSS-SECTION
    // Draws a turbine face: concentric rings, hub, spokes, blades, hatching
    // All ellipses are axis-aligned (cross-section faces the viewer)
    // ═══════════════════════════════════════════════════════════════
    function renderCrossSection(layer, cx, cy, def, rng) {
        var items = [];
        var fs = def.foreshorten;
        var outerR = def.outerRadius;
        var innerR = def.innerRadius;
        var ringCount = def.rings;
        var spokeCount = def.spokes;
        var bladeCount = def.blades;

        // ── 1. Outer ring (bold silhouette) ──────────────────────
        items[items.length] = mkE(layer, cx, cy,
            outerR, outerR * fs,
            0, 360,
            sAccentOrStructural(rng), sSW("silhouette"), false);

        // ── 2. Concentric rings between inner and outer ──────────
        // Evenly space rings from innerR to outerR (exclusive of both)
        for (var ri = 1; ri <= ringCount; ri++) {
            var t = ri / (ringCount + 1);
            var ringR = lerp(innerR, outerR, t);
            items[items.length] = mkE(layer, cx, cy,
                ringR, ringR * fs,
                0, 360,
                sCol("secondary"), sSW("detail"), false);
        }

        // ── 3. Inner ring ────────────────────────────────────────
        items[items.length] = mkE(layer, cx, cy,
            innerR, innerR * fs,
            0, 360,
            sCol("structural"), sSW("structural"), false);

        // ── 4. Hub circle (filled) ───────────────────────────────
        var hubR = innerR * 0.35;
        items[items.length] = mkCirc(layer, cx, cy,
            hubR,
            sCol("structural"), sSW("structural"), true);

        // ── 5. Spokes — radial lines from hub to outer ring ─────
        for (var si = 0; si < spokeCount; si++) {
            var spokeAngle = (360 / spokeCount) * si;
            // Start point on hub ellipse edge
            var sp = ePt(cx, cy, hubR, hubR * fs, spokeAngle);
            // End point on outer ring ellipse edge
            var ep = ePt(cx, cy, outerR, outerR * fs, spokeAngle);
            items[items.length] = mkL(layer,
                sp[0], sp[1], ep[0], ep[1],
                sCol("secondary"), sSW("detail"), false);
        }

        // ── 6. Turbine blades (curved, twisted paths) ───────────
        if (bladeCount > 0) {
            var bladeSteps = 8;
            var bladeInnerR = innerR * 1.2;
            var bladeOuterR = outerR * 0.85;

            for (var bi = 0; bi < bladeCount; bi++) {
                var baseAngle = (360 / bladeCount) * bi;
                var bladePts = [];

                for (var bs = 0; bs <= bladeSteps; bs++) {
                    var t2 = bs / bladeSteps;
                    var curR = lerp(bladeInnerR, bladeOuterR, t2);
                    // 25-degree twist over the blade length
                    var curAng = baseAngle + t2 * 25;
                    var bpt = ePt(cx, cy, curR, curR * fs, curAng);
                    bladePts[bladePts.length] = bpt;
                }

                // Open polyline for each blade
                items[items.length] = mkPoly(layer, bladePts, false,
                    sCol("secondary"), sSW("detail"), false);
            }
        }

        // ── 7. Cross-hatching between inner and first ring ───────
        // Radial hatch lines from inner ring boundary to first ring
        var firstRingR = lerp(innerR, outerR, 1 / (ringCount + 1));
        var hatchCount = 16;

        for (var hi = 0; hi < hatchCount; hi++) {
            // Alternate angle slightly for visual texture
            var hatchAngle = (360 / hatchCount) * hi + (hi % 2 === 0 ? 2 : -2);
            var hp0 = ePt(cx, cy, innerR, innerR * fs, hatchAngle);
            var hp1 = ePt(cx, cy, firstRingR, firstRingR * fs, hatchAngle);
            items[items.length] = mkL(layer,
                hp0[0], hp0[1], hp1[0], hp1[1],
                sCol("ghost"), sSW("hidden"), false);
        }

        // ── Group all items under the section name ───────────────
        return mkGroup(layer, def.name, items);
    }

    // ═══════════════════════════════════════════════════════════════
    // MAIN CHUNK LOGIC
    // ═══════════════════════════════════════════════════════════════
    var ctx = chunkInit();
    if (!ctx) {
        return "ERROR: chunkInit failed — artboard/layer not found for SEED " + SEED;
    }

    var doc = ctx.doc;
    var machine = ctx.machine;
    var rng = ctx.rng;

    // Find the SECTIONS layer created by chunk 01
    var secLayer = findLayer(ctx.root, "SECTIONS");
    if (!secLayer) {
        return "ERROR: SECTIONS layer not found under VOID_s" + SEED;
    }

    // Render each cross-section definition from the machine composition
    for (var i = 0; i < machine.crossSections.length; i++) {
        var cs = machine.crossSections[i];

        // Convert local coords to Illustrator coords
        var illCx = ctx.toX(cs.cx);
        var illCy = ctx.toY(cs.cy);

        renderCrossSection(secLayer, illCx, illCy, cs, rng);
    }

    // Finalize — redraw viewport and persist changes
    app.redraw();
    doc.save();

    return "VOID_s" + SEED + " sections complete: "
        + machine.crossSections.length + " cross-section(s) rendered";
})();
