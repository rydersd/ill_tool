// void_run_04_connections.jsx — Chunk 04: Pipe Connections
// Renders pipes with flanges, silhouette lines, center lines, and bolt circles
// Depends on: void_engine_lib.jsx, void_style_*.jsx, void_engine_compose.jsx
// Globals expected: SEED (number), all lib/style/compose functions loaded

(function () {

    // ═══════════════════════════════════════════════════════════════
    // RENDER PIPE
    // Draws a single pipe connecting two points with:
    //   - Silhouette lines (structural weight, offset perpendicular)
    //   - End ellipses (pipe cross-section at each terminus)
    //   - Flange ellipses (wider caps at each terminus)
    //   - Center line (dash-dot pattern along axis)
    //   - Bolt circles (small filled dots around each flange)
    // ═══════════════════════════════════════════════════════════════
    function renderPipe(layer, def, rng) {
        var items = [];

        var sp = def.startPt;
        var ep = def.endPt;
        var r = def.radius;
        var fr = def.flangeRadius;

        // ── Pipe axis direction and perpendicular normal ─────────
        var adx = ep[0] - sp[0];
        var ady = ep[1] - sp[1];
        var alen = Math.sqrt(adx * adx + ady * ady);

        // Guard against degenerate zero-length pipes
        if (alen < 0.01) return mkGroup(layer, def.name, []);

        var nx = -ady / alen;  // perpendicular x
        var ny = adx / alen;   // perpendicular y

        // ── 1. Silhouette lines ──────────────────────────────────
        // Two lines at ±radius offset perpendicular to pipe axis
        var silCol = sCol("structural");
        var silSW = sSW("silhouette");

        items[items.length] = mkL(layer,
            sp[0] + nx * r, sp[1] + ny * r,
            ep[0] + nx * r, ep[1] + ny * r,
            silCol, silSW, false);

        items[items.length] = mkL(layer,
            sp[0] - nx * r, sp[1] - ny * r,
            ep[0] - nx * r, ep[1] - ny * r,
            silCol, silSW, false);

        // ── 2. End ellipses ──────────────────────────────────────
        // Axis-aligned ellipses at start and end showing pipe bore
        var fs = 0.35;  // pipe foreshorten is tighter than cylinder
        var endCol = sCol("secondary");
        var endSW = sSW("structural");

        items[items.length] = mkE(layer,
            sp[0], sp[1], r, r * fs,
            0, 360, endCol, endSW, false);

        items[items.length] = mkE(layer,
            ep[0], ep[1], r, r * fs,
            0, 360, endCol, endSW, false);

        // ── 3. Flange ellipses ───────────────────────────────────
        // Wider ellipses at each end representing flange plates
        items[items.length] = mkE(layer,
            sp[0], sp[1], fr, fr * fs,
            0, 360, endCol, endSW, false);

        items[items.length] = mkE(layer,
            ep[0], ep[1], fr, fr * fs,
            0, 360, endCol, endSW, false);

        // ── 4. Center line ───────────────────────────────────────
        // Dash-dot pattern [18,4,2,4] along pipe axis
        items[items.length] = mkLD(layer,
            sp[0], sp[1], ep[0], ep[1],
            sCol("ghost"), sSW("detail"), 2);

        // ── 5. Bolt circles ─────────────────────────────────────
        // 6 bolts evenly spaced on flange at each end
        // Bolt circle sits between pipe radius and flange radius
        var boltR = (r + fr) / 2;
        var boltSize = r * 0.08;
        var boltCol = sCol("secondary");
        var boltSW = sSW("detail");
        var boltCount = 6;

        for (var bi = 0; bi < boltCount; bi++) {
            var boltDeg = (360 / boltCount) * bi;

            // Start flange bolts
            var bpS = ePt(sp[0], sp[1], boltR, boltR * fs, boltDeg);
            items[items.length] = mkCirc(layer,
                bpS[0], bpS[1], boltSize,
                boltCol, boltSW, true);

            // End flange bolts
            var bpE = ePt(ep[0], ep[1], boltR, boltR * fs, boltDeg);
            items[items.length] = mkCirc(layer,
                bpE[0], bpE[1], boltSize,
                boltCol, boltSW, true);
        }

        // ── Group all items under pipe name ──────────────────────
        return mkGroup(layer, def.name, items);
    }

    // ═══════════════════════════════════════════════════════════════
    // MAIN CHUNK LOGIC
    // ═══════════════════════════════════════════════════════════════

    var ctx = chunkInit();
    if (!ctx) return "ERROR: chunkInit failed — run void_run_01_setup.jsx first";

    var doc = ctx.doc;
    var connLayer = findLayer(ctx.root, "CONNECTIONS");
    if (!connLayer) return "ERROR: CONNECTIONS layer not found";

    var pipes = ctx.machine.pipes;
    for (var i = 0; i < pipes.length; i++) {
        var def = pipes[i];

        // Convert local Y-down coords to Illustrator Y-up coords
        var convertedDef = {
            name: def.name,
            startPt: ctx.toPt(def.startPt),
            endPt: ctx.toPt(def.endPt),
            radius: def.radius,
            flangeRadius: def.flangeRadius
        };

        renderPipe(connLayer, convertedDef, ctx.rng);
    }

    // ═══════════════════════════════════════════════════════════════
    // FINALIZE
    // ═══════════════════════════════════════════════════════════════
    app.redraw();
    doc.save();

    return "VOID_s" + SEED + " connections: " + pipes.length + " pipes rendered";
})();
