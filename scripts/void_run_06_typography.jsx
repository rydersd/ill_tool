// void_run_06_typography.jsx — Chunk 06: Typography, Data Panels & Dimensions
// Concatenated AFTER void_engine_lib.jsx + void_style_*.jsx + void_engine_compose.jsx
// Renders data panel readouts, engineering dimension lines, and all typographic labels
// This is the chunk that sells the DR aesthetic — dense technical overlays
// ExtendScript (ES3) — no modern JS features

(function () {

    // ═══════════════════════════════════════════════════════════════
    // renderDataPanel — Technical readout box with scan lines,
    // corner ticks, optional gauge, and micro label
    //
    // layer:  target Illustrator layer (DATA_PANELS)
    // def:    { name, x, y, w, h, scanLines, hasGauge }
    //         x/y/w/h already in Illustrator Y-up coords
    // rng:    PRNG instance for rendering variation
    // ═══════════════════════════════════════════════════════════════
    function renderDataPanel(layer, def, rng) {
        var items = [];
        var x = def.x;
        var y = def.y;
        var w = def.w;
        var h = def.h;
        var margin = 4;

        // ── 1. Outer border ──────────────────────────────────────
        items[items.length] = mkRect(
            layer, x, y, w, h,
            sCol("structural"), sSW("structural"), false
        );

        // ── 2. Inner margin rect ─────────────────────────────────
        // In Illustrator Y-up, mkRect y is the TOP edge
        // Inner rect: move x right, y down (y - margin), shrink w/h
        var ix = x + margin;
        var iy = y - margin;
        var iw = w - margin * 2;
        var ih = h - margin * 2;
        items[items.length] = mkRect(
            layer, ix, iy, iw, ih,
            sCol("secondary"), sSW("detail"), false
        );

        // ── 3. Scan lines ────────────────────────────────────────
        // Horizontal lines evenly spaced within inner margins
        var scanCol = sCol("ghost");
        var scanSW = sSW("construction");
        var scanSpacing = ih / (def.scanLines + 1);
        for (var si = 1; si <= def.scanLines; si++) {
            var scanY = iy - si * scanSpacing;
            items[items.length] = mkL(
                layer,
                ix, scanY,
                ix + iw, scanY,
                scanCol, scanSW, false
            );
        }

        // ── 4. Corner tick marks ─────────────────────────────────
        // L-shaped marks at all 4 corners of the inner rect
        var tickLen = 8;
        var tickCol = sCol("accent");
        var tickSW = sSW("detail");

        // Top-left: horizontal right + vertical down
        items[items.length] = mkL(layer, ix, iy, ix + tickLen, iy, tickCol, tickSW, false);
        items[items.length] = mkL(layer, ix, iy, ix, iy - tickLen, tickCol, tickSW, false);

        // Top-right: horizontal left + vertical down
        items[items.length] = mkL(layer, ix + iw, iy, ix + iw - tickLen, iy, tickCol, tickSW, false);
        items[items.length] = mkL(layer, ix + iw, iy, ix + iw, iy - tickLen, tickCol, tickSW, false);

        // Bottom-left: horizontal right + vertical up
        items[items.length] = mkL(layer, ix, iy - ih, ix + tickLen, iy - ih, tickCol, tickSW, false);
        items[items.length] = mkL(layer, ix, iy - ih, ix, iy - ih + tickLen, tickCol, tickSW, false);

        // Bottom-right: horizontal left + vertical up
        items[items.length] = mkL(layer, ix + iw, iy - ih, ix + iw - tickLen, iy - ih, tickCol, tickSW, false);
        items[items.length] = mkL(layer, ix + iw, iy - ih, ix + iw, iy - ih + tickLen, tickCol, tickSW, false);

        // ── 5. Optional gauge ────────────────────────────────────
        if (def.hasGauge) {
            // Gauge center at 70% x, 65% y within inner panel
            var gaugeCX = ix + iw * 0.7;
            var gaugeCY = iy - ih * 0.35;  // 65% from top in Y-up = y - 0.35*h
            var gaugeR = Math.min(iw, ih) * 0.15;
            var gaugeCol = sCol("accent");
            var gaugeSW = sSW("detail");

            // Gauge circle outline
            items[items.length] = mkCirc(layer, gaugeCX, gaugeCY, gaugeR, gaugeCol, gaugeSW, false);

            // Needle at random angle
            var needleAng = rng.range(0, 360) * DEG2RAD;
            var needleLen = gaugeR * 0.85;
            items[items.length] = mkL(
                layer,
                gaugeCX, gaugeCY,
                gaugeCX + Math.cos(needleAng) * needleLen,
                gaugeCY + Math.sin(needleAng) * needleLen,
                gaugeCol, gaugeSW, false
            );

            // Hub dot (filled)
            var hubR = gaugeR * 0.12;
            items[items.length] = mkCirc(layer, gaugeCX, gaugeCY, hubR, gaugeCol, gaugeSW, true);
        }

        // ── 6. Panel label text ──────────────────────────────────
        // Place below the inner rect, left-aligned
        var labelText = def.name.toUpperCase().replace(/_/g, ".");
        var labelSize = STYLE.typography.micro_size;
        items[items.length] = mkText(
            layer,
            ix + 2, iy - ih - labelSize - 2,
            labelText, labelSize, sCol("structural")
        );

        // Add a system-text readout inside the panel (top-left area)
        var readoutText = sSystemText(rng);
        items[items.length] = mkText(
            layer,
            ix + 2, iy - 2,
            readoutText, STYLE.typography.micro_size, sCol("secondary")
        );

        mkGroup(layer, def.name, items);
    }

    // ═══════════════════════════════════════════════════════════════
    // renderDimension — Engineering measurement annotation
    //
    // layer:  target Illustrator layer (DIMENSIONS)
    // def:    { name, startPt, endPt, offset }
    //         startPt/endPt already in Illustrator Y-up coords
    // rng:    PRNG instance
    // ═══════════════════════════════════════════════════════════════
    function renderDimension(layer, def, rng) {
        var items = [];
        var sp = def.startPt;
        var ep = def.endPt;
        var offset = def.offset;

        // ── Direction and perpendicular ──────────────────────────
        var dx = ep[0] - sp[0];
        var dy = ep[1] - sp[1];
        var len = Math.sqrt(dx * dx + dy * dy);
        if (len < 1) return;  // degenerate — skip

        // Unit direction along dimension
        var ux = dx / len;
        var uy = dy / len;

        // Perpendicular (rotate 90 CCW)
        var px = -uy;
        var py = ux;

        // Offset points — the dimension line sits offset from the object
        var osp = [sp[0] + px * offset, sp[1] + py * offset];
        var oep = [ep[0] + px * offset, ep[1] + py * offset];

        var dimCol = sCol("ghost");
        var dimSW = sSW("construction");
        var tickCol = sCol("secondary");
        var tickSW = sSW("detail");

        // ── 1. Extension lines ───────────────────────────────────
        // From original points toward the dimension line, with small gap
        var extGap = 3;   // gap near the object
        var extOver = 4;  // overshoot past dimension line
        var extStart1 = [sp[0] + px * extGap, sp[1] + py * extGap];
        var extEnd1   = [sp[0] + px * (offset + extOver), sp[1] + py * (offset + extOver)];
        var extStart2 = [ep[0] + px * extGap, ep[1] + py * extGap];
        var extEnd2   = [ep[0] + px * (offset + extOver), ep[1] + py * (offset + extOver)];

        items[items.length] = mkL(
            layer,
            extStart1[0], extStart1[1], extEnd1[0], extEnd1[1],
            dimCol, dimSW, false
        );
        items[items.length] = mkL(
            layer,
            extStart2[0], extStart2[1], extEnd2[0], extEnd2[1],
            dimCol, dimSW, false
        );

        // ── 2. Dimension line ────────────────────────────────────
        items[items.length] = mkL(
            layer,
            osp[0], osp[1], oep[0], oep[1],
            dimCol, dimSW, false
        );

        // ── 3. Tick marks (slash marks at each end) ──────────────
        // Angled slashes perpendicular to dimension line
        var tickLen = 5;
        // Slash direction: 45 degrees relative to dimension direction
        var slashDx = (ux + px) * tickLen;
        var slashDy = (uy + py) * tickLen;

        items[items.length] = mkL(
            layer,
            osp[0] - slashDx, osp[1] - slashDy,
            osp[0] + slashDx, osp[1] + slashDy,
            tickCol, tickSW, false
        );
        items[items.length] = mkL(
            layer,
            oep[0] - slashDx, oep[1] - slashDy,
            oep[0] + slashDx, oep[1] + slashDy,
            tickCol, tickSW, false
        );

        // ── 4. Dimension text ────────────────────────────────────
        // Measurement value (formatted distance) centered on dimension line
        var measVal = Math.round(len * 10) / 10;
        var measStr = "" + measVal;
        var midX = (osp[0] + oep[0]) / 2;
        var midY = (osp[1] + oep[1]) / 2;
        // Offset text slightly away from the line
        var textOffX = px * 6;
        var textOffY = py * 6;

        items[items.length] = mkText(
            layer,
            midX + textOffX, midY + textOffY,
            measStr, STYLE.typography.label_size, sCol("secondary")
        );

        mkGroup(layer, def.name, items);
    }

    // ═══════════════════════════════════════════════════════════════
    // renderLabels — All typographic labels + title block
    //
    // layer:  target Illustrator layer (TYPOGRAPHY)
    // labels: machine.labels[] array (already coord-converted)
    // ctx:    chunkInit context for artboard bounds
    // rng:    PRNG instance
    // ═══════════════════════════════════════════════════════════════
    function renderLabels(layer, labels, ctx, rng) {
        var items = [];

        // ── Machine labels ───────────────────────────────────────
        for (var li = 0; li < labels.length; li++) {
            var lbl = labels[li];
            var lx = ctx.toX(lbl.x);
            var ly = ctx.toY(lbl.y);
            var lCol;
            var lSize;

            if (lbl.type === "section") {
                lCol = sCol("structural");
                lSize = STYLE.typography.label_size;
            } else if (lbl.type === "coord") {
                lCol = sCol("ghost");
                lSize = STYLE.typography.micro_size;
            } else {
                // "system" type — accent or structural variation
                lCol = sAccentOrStructural(rng);
                lSize = lbl.size || STYLE.typography.heading_size;
            }

            items[items.length] = mkText(layer, lx, ly, lbl.text, lSize, lCol);
        }

        // ── Title block ──────────────────────────────────────────
        // Bottom-right corner of artboard — signature DR placement
        var tbMargin = 30;
        var tbX = ctx.abX + ctx.AB_W - tbMargin;
        var tbBaseY = ctx.abY - ctx.AB_H + tbMargin;

        // Right-align by placing text leftward from the margin edge
        // (mkText positions at left of text frame — offset by estimated width)
        var tbOffsetX = 260;
        var tbAnchorX = tbX - tbOffsetX;

        // Line 1: Engine title with seed
        var seedStr = "" + SEED;
        items[items.length] = mkText(
            layer,
            tbAnchorX, tbBaseY + 56,
            "VOID.ENGINE.MK" + seedStr,
            STYLE.typography.heading_size,
            sCol("structural")
        );

        // Line 2: Series designation
        items[items.length] = mkText(
            layer,
            tbAnchorX, tbBaseY + 40,
            "EXPERIMENTAL.DESIGN.SERIES",
            STYLE.typography.label_size,
            sCol("secondary")
        );

        // Line 3: Date stamp — procedural from seed
        var dateYear = 2025 + (SEED % 3);
        var dateMonth = ((SEED * 7) % 12) + 1;
        var dateDay = ((SEED * 13) % 28) + 1;
        var monthStr = dateMonth < 10 ? "0" + dateMonth : "" + dateMonth;
        var dayStr = dateDay < 10 ? "0" + dateDay : "" + dateDay;
        var dateStamp = dateYear + "." + monthStr + "." + dayStr;

        items[items.length] = mkText(
            layer,
            tbAnchorX, tbBaseY + 26,
            "DATE." + dateStamp,
            STYLE.typography.micro_size,
            sCol("ghost")
        );

        // Line 4: Drawing number — hex-style from seed
        var drawNum = "DRW-" + ((SEED * 2749) & 0xFFFF).toString(16).toUpperCase();
        while (drawNum.length < 10) drawNum = drawNum.substring(0, 4) + "0" + drawNum.substring(4);

        items[items.length] = mkText(
            layer,
            tbAnchorX, tbBaseY + 14,
            drawNum,
            STYLE.typography.micro_size,
            sCol("ghost")
        );

        // Line 5: Scale and revision
        items[items.length] = mkText(
            layer,
            tbAnchorX, tbBaseY + 2,
            "SCALE.1:1  REV." + String.fromCharCode(65 + (SEED % 26)),
            STYLE.typography.micro_size,
            sCol("ghost")
        );

        // ── Title block accent line ──────────────────────────────
        // Horizontal rule above the title block
        items[items.length] = mkL(
            layer,
            tbAnchorX, tbBaseY + 64,
            tbAnchorX + tbOffsetX, tbBaseY + 64,
            sCol("accent"), sSW("detail"), false
        );

        // Vertical rule left of title block
        items[items.length] = mkL(
            layer,
            tbAnchorX - 4, tbBaseY,
            tbAnchorX - 4, tbBaseY + 64,
            sCol("structural"), sSW("construction"), false
        );

        mkGroup(layer, "TITLE_BLOCK", items);
    }

    // ═══════════════════════════════════════════════════════════════
    // MAIN CHUNK LOGIC
    // ═══════════════════════════════════════════════════════════════
    var ctx = chunkInit();
    if (!ctx) {
        alert("VOID chunk 06: Cannot find artboard or root layer for seed " + SEED);
        return;
    }

    var rng = ctx.rng;

    // ── 1. DATA PANELS ───────────────────────────────────────────
    var dpLayer = findLayer(ctx.root, "DATA_PANELS");
    if (!dpLayer) {
        dpLayer = getOrCreateLayer(ctx.root, "DATA_PANELS");
    }

    for (var di = 0; di < ctx.machine.dataPanels.length; di++) {
        var dp = ctx.machine.dataPanels[di];
        // Convert local (Y-down) coordinates to Illustrator (Y-up)
        var dpDef = {
            name: dp.name,
            x: ctx.toX(dp.x),
            y: ctx.toY(dp.y),
            w: dp.w,
            h: dp.h,
            scanLines: dp.scanLines,
            hasGauge: dp.hasGauge
        };
        renderDataPanel(dpLayer, dpDef, rng);
    }

    // ── 2. DIMENSIONS ────────────────────────────────────────────
    var dimLayer = findLayer(ctx.root, "DIMENSIONS");
    if (!dimLayer) {
        dimLayer = getOrCreateLayer(ctx.root, "DIMENSIONS");
    }

    for (var dmi = 0; dmi < ctx.machine.dimensions.length; dmi++) {
        var dim = ctx.machine.dimensions[dmi];
        // Convert both endpoints from local to Illustrator coords
        var dimDef = {
            name: dim.name,
            startPt: ctx.toPt(dim.startPt),
            endPt: ctx.toPt(dim.endPt),
            offset: dim.offset
        };
        renderDimension(dimLayer, dimDef, rng);
    }

    // ── 3. TYPOGRAPHY / LABELS ───────────────────────────────────
    var typoLayer = findLayer(ctx.root, "TYPOGRAPHY");
    if (!typoLayer) {
        typoLayer = getOrCreateLayer(ctx.root, "TYPOGRAPHY");
    }

    renderLabels(typoLayer, ctx.machine.labels, ctx, rng);

    // ── FINALIZE ─────────────────────────────────────────────────
    app.redraw();
    ctx.doc.save();

})();
