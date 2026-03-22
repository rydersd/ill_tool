// void_run_02_cylinders.jsx — Chunk 02: Cylinder Renderer
// Concatenated AFTER void_engine_lib.jsx + void_style_*.jsx + void_engine_compose.jsx
// Draws all cylinders (multi-section bodies + tubes) onto the "CYLINDERS" layer
// ExtendScript (ES3) — no modern JS features

(function () {

    // ═══════════════════════════════════════════════════════════════
    // renderCylinder — Draw a single multi-section cylinder or tube
    //
    // layer:  target Illustrator layer
    // def:    cylinder definition with cx/cy already in Illustrator coords
    //         { name, cx, cy, axisAngle, halfLength, foreshorten,
    //           sections[], isTube, flangeR }
    // rng:    PRNG instance for rendering variation
    // ═══════════════════════════════════════════════════════════════
    function renderCylinder(layer, def, rng) {
        var items = [];
        var fs = def.foreshorten;
        var eRot = sEllipseRot(def.axisAngle);
        var hiddenDash = sHiddenDash();

        // Axis endpoints in Illustrator coordinates
        var axRad = def.axisAngle * DEG2RAD;
        var axDx = Math.cos(axRad) * def.halfLength;
        var axDy = Math.sin(axRad) * def.halfLength;
        var backAx = [def.cx - axDx, def.cy - axDy];
        var frontAx = [def.cx + axDx, def.cy + axDy];

        // ── Per-Section Rendering ────────────────────────────────
        for (var si = 0; si < def.sections.length; si++) {
            var sec = def.sections[si];

            // Back and front center points for this section along the axis
            var backCenter = axPt(backAx, frontAx, sec.tStart);
            var frontCenter = axPt(backAx, frontAx, sec.tEnd);

            // Ellipse semi-axes: major = radius, minor = radius * foreshorten
            var aBack = sec.radiusTop;
            var bBack = sec.radiusTop * fs;
            var aFront = sec.radiusBottom;
            var bFront = sec.radiusBottom * fs;

            // ── 1. Hidden half of back ellipse (0-180, behind the body) ──
            if (hiddenDash !== -1) {
                items[items.length] = mkER(
                    layer,
                    backCenter[0], backCenter[1],
                    aBack, bBack,
                    0, 180, eRot,
                    sCol("ghost"), sSW("hidden"),
                    hiddenDash === 1   // true = dashed, false = solid ghost
                );
            }

            // ── 2. Visible half of back ellipse (180-360, in front) ──
            items[items.length] = mkER(
                layer,
                backCenter[0], backCenter[1],
                aBack, bBack,
                180, 360, eRot,
                sCol("structural"), sSW("structural"),
                false
            );

            // ── 3. Front ellipse (full, bold) ──
            var frontColor = sAccentOrStructural(rng);
            items[items.length] = mkER(
                layer,
                frontCenter[0], frontCenter[1],
                aFront, bFront,
                0, 360, eRot,
                frontColor, sSW("silhouette"),
                false
            );

            // ── 4. Silhouette lines connecting tangent points ──
            // Tangent points at 90 and 270 degrees on back and front ellipses
            var backTangent90 = eRPt(backCenter[0], backCenter[1], aBack, bBack, 90, eRot);
            var frontTangent90 = eRPt(frontCenter[0], frontCenter[1], aFront, bFront, 90, eRot);
            var backTangent270 = eRPt(backCenter[0], backCenter[1], aBack, bBack, 270, eRot);
            var frontTangent270 = eRPt(frontCenter[0], frontCenter[1], aFront, bFront, 270, eRot);

            items[items.length] = mkL(
                layer,
                backTangent90[0], backTangent90[1],
                frontTangent90[0], frontTangent90[1],
                sCol("structural"), sSW("silhouette"),
                false
            );
            items[items.length] = mkL(
                layer,
                backTangent270[0], backTangent270[1],
                frontTangent270[0], frontTangent270[1],
                sCol("structural"), sSW("silhouette"),
                false
            );

            // ── 5. Band rings (2-4 per section) ──
            var bandCount = rng.randInt(2, 4);
            for (var bi = 0; bi < bandCount; bi++) {
                var bandT = lerp(sec.tStart, sec.tEnd, (bi + 1) / (bandCount + 1));
                var bandCenter = axPt(backAx, frontAx, bandT);
                // Interpolate radius between top and bottom
                var bandFrac = (bandT - sec.tStart) / (sec.tEnd - sec.tStart);
                var bandR = lerp(sec.radiusTop, sec.radiusBottom, bandFrac);
                var bandA = bandR;
                var bandB = bandR * fs;

                // Visible half — structural color
                items[items.length] = mkER(
                    layer,
                    bandCenter[0], bandCenter[1],
                    bandA, bandB,
                    180, 360, eRot,
                    sCol("secondary"), sSW("structural"),
                    false
                );

                // Hidden half — ghost color
                if (hiddenDash !== -1) {
                    items[items.length] = mkER(
                        layer,
                        bandCenter[0], bandCenter[1],
                        bandA, bandB,
                        0, 180, eRot,
                        sCol("ghost"), sSW("hidden"),
                        hiddenDash === 1
                    );
                }
            }

            // ── 6. Panel lines (3-6 per section, visible face) ──
            var panelCount = rng.randInt(3, 6);
            for (var pi = 0; pi < panelCount; pi++) {
                // Angles on the visible face: 200-340 degrees
                var panelAng = rng.range(200, 340);
                var panelT1 = lerp(sec.tStart, sec.tEnd, rng.range(0.05, 0.4));
                var panelT2 = lerp(sec.tStart, sec.tEnd, rng.range(0.6, 0.95));
                var panelCenter1 = axPt(backAx, frontAx, panelT1);
                var panelCenter2 = axPt(backAx, frontAx, panelT2);
                var panelFrac1 = (panelT1 - sec.tStart) / (sec.tEnd - sec.tStart);
                var panelFrac2 = (panelT2 - sec.tStart) / (sec.tEnd - sec.tStart);
                var panelR1 = lerp(sec.radiusTop, sec.radiusBottom, panelFrac1);
                var panelR2 = lerp(sec.radiusTop, sec.radiusBottom, panelFrac2);

                var pp1 = eRPt(panelCenter1[0], panelCenter1[1], panelR1, panelR1 * fs, panelAng, eRot);
                var pp2 = eRPt(panelCenter2[0], panelCenter2[1], panelR2, panelR2 * fs, panelAng, eRot);

                items[items.length] = mkL(
                    layer,
                    pp1[0], pp1[1],
                    pp2[0], pp2[1],
                    sCol("secondary"), sSW("detail"),
                    false
                );
            }

            // ── 7. Hidden panel lines (1-3, back face) ──
            if (hiddenDash !== -1) {
                var hiddenPanelCount = rng.randInt(1, 3);
                for (var hpi = 0; hpi < hiddenPanelCount; hpi++) {
                    // Angles on the hidden face: 30-150 degrees
                    var hpAng = rng.range(30, 150);
                    var hpT1 = lerp(sec.tStart, sec.tEnd, rng.range(0.1, 0.4));
                    var hpT2 = lerp(sec.tStart, sec.tEnd, rng.range(0.6, 0.9));
                    var hpCenter1 = axPt(backAx, frontAx, hpT1);
                    var hpCenter2 = axPt(backAx, frontAx, hpT2);
                    var hpFrac1 = (hpT1 - sec.tStart) / (sec.tEnd - sec.tStart);
                    var hpFrac2 = (hpT2 - sec.tStart) / (sec.tEnd - sec.tStart);
                    var hpR1 = lerp(sec.radiusTop, sec.radiusBottom, hpFrac1);
                    var hpR2 = lerp(sec.radiusTop, sec.radiusBottom, hpFrac2);

                    var hp1 = eRPt(hpCenter1[0], hpCenter1[1], hpR1, hpR1 * fs, hpAng, eRot);
                    var hp2 = eRPt(hpCenter2[0], hpCenter2[1], hpR2, hpR2 * fs, hpAng, eRot);

                    items[items.length] = mkL(
                        layer,
                        hp1[0], hp1[1],
                        hp2[0], hp2[1],
                        sCol("ghost"), sSW("hidden"),
                        hiddenDash === 1
                    );
                }
            }

            // ── 8. Section boundary ring (between adjacent sections) ──
            if (si > 0) {
                var boundaryColor = sAccentOrStructural(rng);
                // Ring at the start of this section (= end of previous section)
                items[items.length] = mkER(
                    layer,
                    backCenter[0], backCenter[1],
                    aBack, bBack,
                    0, 360, eRot,
                    boundaryColor, sSW("structural"),
                    false
                );
            }
        }

        // ── 9. Axis center line (full length, dash-dot) ──
        items[items.length] = mkLD(
            layer,
            backAx[0], backAx[1],
            frontAx[0], frontAx[1],
            sCol("ghost"), sSW("detail"),
            2   // dash-dot pattern [18,4,2,4]
        );

        // ── 10. Tube-specific: flange ellipses at each end ──
        if (def.isTube && def.flangeR) {
            var flangeA = def.flangeR;
            var flangeB = def.flangeR * fs;

            // Back flange
            items[items.length] = mkER(
                layer,
                backAx[0], backAx[1],
                flangeA, flangeB,
                0, 360, eRot,
                sCol("structural"), sSW("structural"),
                false
            );

            // Front flange
            var flangeColor = sAccentOrStructural(rng);
            items[items.length] = mkER(
                layer,
                frontAx[0], frontAx[1],
                flangeA, flangeB,
                0, 360, eRot,
                flangeColor, sSW("structural"),
                false
            );
        }

        // Group all items under the cylinder name
        mkGroup(layer, def.name, items);
    }

    // ═══════════════════════════════════════════════════════════════
    // MAIN CHUNK LOGIC
    // ═══════════════════════════════════════════════════════════════
    var ctx = chunkInit();
    if (!ctx) {
        // chunkInit returns null if artboard or root layer not found
        alert("VOID chunk 02: Cannot find artboard or root layer for seed " + SEED);
        return;
    }

    // Find the CYLINDERS layer (created by chunk 01)
    var cylLayer = findLayer(ctx.root, "CYLINDERS");
    if (!cylLayer) {
        cylLayer = getOrCreateLayer(ctx.root, "CYLINDERS");
    }

    // Render each cylinder with coordinates converted to Illustrator space
    for (var ci = 0; ci < ctx.machine.cylinders.length; ci++) {
        var cyl = ctx.machine.cylinders[ci];

        // Build a definition copy with converted coordinates
        var def = {
            name: cyl.name,
            cx: ctx.toX(cyl.cx),
            cy: ctx.toY(cyl.cy),
            axisAngle: cyl.axisAngle,
            halfLength: cyl.halfLength,
            foreshorten: cyl.foreshorten,
            sections: cyl.sections,
            isTube: cyl.isTube,
            flangeR: cyl.flangeR || 0
        };

        renderCylinder(cylLayer, def, ctx.rng);
    }

    app.redraw();
    ctx.doc.save();

})();
