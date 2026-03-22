// void_run_03_housings.jsx — Chunk 03: 3D Isometric Housings
// Renders rectangular enclosures attached to main cylinder surfaces
// Each housing is a 3-face isometric box with panel lines, silhouette edges,
// optional hidden back edges, and mounting bracket detail
// Depends on: void_engine_lib.jsx, void_style_*.jsx, void_engine_compose.jsx
// Globals expected: SEED (number)

(function () {

    // ═══════════════════════════════════════════════════════════════
    // INIT — Recover artboard, layers, and deterministic machine data
    // ═══════════════════════════════════════════════════════════════
    var ctx = chunkInit();
    if (!ctx) return "ERROR: chunkInit failed — run chunk 01 first";

    var doc = ctx.doc;
    var root = ctx.root;
    var machine = ctx.machine;
    var rng = ctx.rng;

    var layer = findLayer(root, "HOUSINGS");
    if (!layer) return "ERROR: HOUSINGS layer not found";

    // ═══════════════════════════════════════════════════════════════
    // renderHousing — Draws a single 3D isometric box
    //
    // Geometry overview (Illustrator Y-up after toY conversion):
    //
    //   Back-top-left ────── Back-top-right
    //   ╱|                    ╱|
    //  Front-top-left ── Front-top-right |
    //  |  |                |  |
    //  |  Back-bot-left ── | ─Back-bot-right
    //  | ╱                 | ╱
    //  Front-bot-left ── Front-bot-right
    //
    // Front face:  fl, fr, frt, flt (visible)
    // Top face:    flt, frt, brt, blt (visible)
    // Right face:  fr, frt, brt, br  (visible)
    // Back edges:  bl, br, blt, brt  (hidden, shown if showHidden)
    // ═══════════════════════════════════════════════════════════════

    function renderHousing(ly, def, localRng) {
        var items = [];

        // Screen coordinates — already in Illustrator Y-up space
        var x = ctx.toX(def.x);
        var y = ctx.toY(def.y);
        var w = def.w;
        var h = def.h;
        var d = def.d;

        // ── Depth offset from isometric projection angle ─────────
        // Positive dxOff pushes the back face to the right
        // Positive dyOff pushes the back face upward (Illustrator Y-up)
        var angRad = def.angle * DEG2RAD;
        var dxOff = d * Math.cos(angRad);
        var dyOff = d * Math.sin(angRad);

        // ── Front face corners ───────────────────────────────────
        // After toY, y is the Illustrator Y value for the TOP edge
        // of this housing in local-Y-down terms. In Illustrator Y-up,
        // adding h goes UPWARD, so:
        //   bottom-left  = [x, y]         (lower edge)
        //   bottom-right = [x+w, y]
        //   top-right    = [x+w, y+h]     (upper edge)
        //   top-left     = [x, y+h]
        var fl  = [x,     y];
        var fr  = [x + w, y];
        var frt = [x + w, y + h];
        var flt = [x,     y + h];

        // ── Back face corners (offset by depth projection) ───────
        var bl  = [fl[0]  + dxOff, fl[1]  + dyOff];
        var br  = [fr[0]  + dxOff, fr[1]  + dyOff];
        var brt = [frt[0] + dxOff, frt[1] + dyOff];
        var blt = [flt[0] + dxOff, flt[1] + dyOff];

        // ── Face colors and strokes ──────────────────────────────
        var faceCol = sCol("secondary");
        var faceSW  = sSW("structural");

        // ── Draw Front Face ──────────────────────────────────────
        items[items.length] = mkPoly(ly, [fl, fr, frt, flt], true, faceCol, faceSW, false);

        // ── Draw Top Face ────────────────────────────────────────
        items[items.length] = mkPoly(ly, [flt, frt, brt, blt], true, faceCol, faceSW, false);

        // ── Draw Right Side Face ─────────────────────────────────
        items[items.length] = mkPoly(ly, [fr, frt, brt, br], true, faceCol, faceSW, false);

        // ── Bold Silhouette Edges ────────────────────────────────
        // The 6 visible outline edges that define the box silhouette
        var silCol = sCol("structural");
        var silSW  = sSW("silhouette");

        // Front bottom edge
        items[items.length] = mkL(ly, fl[0], fl[1], fr[0], fr[1], silCol, silSW, false);
        // Front left edge
        items[items.length] = mkL(ly, fl[0], fl[1], flt[0], flt[1], silCol, silSW, false);
        // Top back-left edge
        items[items.length] = mkL(ly, flt[0], flt[1], blt[0], blt[1], silCol, silSW, false);
        // Top back-right edge
        items[items.length] = mkL(ly, blt[0], blt[1], brt[0], brt[1], silCol, silSW, false);
        // Right back-bottom edge
        items[items.length] = mkL(ly, brt[0], brt[1], br[0], br[1], silCol, silSW, false);
        // Right front-bottom edge
        items[items.length] = mkL(ly, br[0], br[1], fr[0], fr[1], silCol, silSW, false);

        // ── Panel Lines on Front Face ────────────────────────────
        // 2-4 vertical lines evenly spaced across the front face
        var panelCol = sCol("secondary");
        var panelSW  = sSW("detail");
        var panelCount = localRng.randInt(2, 4);

        for (var pi = 1; pi <= panelCount; pi++) {
            var t = pi / (panelCount + 1);
            var px1 = lerp(fl[0], fr[0], t);
            var py1 = lerp(fl[1], fr[1], t);
            var px2 = lerp(flt[0], frt[0], t);
            var py2 = lerp(flt[1], frt[1], t);
            items[items.length] = mkL(ly, px1, py1, px2, py2, panelCol, panelSW, false);
        }

        // ── Hidden Back Edges (optional) ─────────────────────────
        // Three edges on the back face that would be occluded
        if (def.showHidden) {
            var hiddenDash = sHiddenDash();
            // Skip drawing if style says "none" (hiddenDash === -1)
            if (hiddenDash !== -1) {
                var ghostCol = sCol("ghost");
                var ghostSW  = sSW("hidden");

                // Back bottom edge: bl → br
                items[items.length] = mkLD(ly,
                    bl[0], bl[1], br[0], br[1],
                    ghostCol, ghostSW, hiddenDash);
                // Back left edge: bl → blt
                items[items.length] = mkLD(ly,
                    bl[0], bl[1], blt[0], blt[1],
                    ghostCol, ghostSW, hiddenDash);
                // Back-to-front bottom-left edge: bl → fl
                items[items.length] = mkLD(ly,
                    bl[0], bl[1], fl[0], fl[1],
                    ghostCol, ghostSW, hiddenDash);
            }
        }

        // ── Bottom Bracket (mounting detail) ─────────────────────
        // Small L-shaped mounting tabs at the bottom corners of the
        // front face, suggesting mechanical attachment to the cylinder
        var bracketCol = sCol("secondary");
        var bracketSW  = sSW("detail");
        var bracketH   = h * 0.12;       // bracket drop height
        var bracketW   = w * 0.08;       // bracket tab width

        // Left bracket: vertical drop + horizontal tab
        items[items.length] = mkL(ly,
            fl[0], fl[1],
            fl[0], fl[1] - bracketH,
            bracketCol, bracketSW, false);
        items[items.length] = mkL(ly,
            fl[0], fl[1] - bracketH,
            fl[0] + bracketW, fl[1] - bracketH,
            bracketCol, bracketSW, false);

        // Right bracket: vertical drop + horizontal tab
        items[items.length] = mkL(ly,
            fr[0], fr[1],
            fr[0], fr[1] - bracketH,
            bracketCol, bracketSW, false);
        items[items.length] = mkL(ly,
            fr[0], fr[1] - bracketH,
            fr[0] - bracketW, fr[1] - bracketH,
            bracketCol, bracketSW, false);

        // Center bracket: small crossbar between the two tabs
        var cbY = fl[1] - bracketH * 0.6;
        items[items.length] = mkL(ly,
            fl[0] + bracketW, cbY,
            fr[0] - bracketW, cbY,
            bracketCol, bracketSW, false);

        // ── Group All Items ──────────────────────────────────────
        return mkGroup(ly, def.name, items);
    }

    // ═══════════════════════════════════════════════════════════════
    // MAIN LOOP — Render each housing from the machine definition
    // ═══════════════════════════════════════════════════════════════
    var housings = machine.housings;

    for (var i = 0; i < housings.length; i++) {
        renderHousing(layer, housings[i], rng);
    }

    // ═══════════════════════════════════════════════════════════════
    // FINALIZE — Redraw viewport and save
    // ═══════════════════════════════════════════════════════════════
    app.redraw();
    doc.save();

    return "VOID_s" + SEED + " housings: " + housings.length + " rendered";
})();
