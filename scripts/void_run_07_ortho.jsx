// void_run_07_ortho.jsx — Chunk 07: Orthographic Projection Views
// Concatenated AFTER void_engine_lib.jsx + void_style_*.jsx + void_engine_compose.jsx
// Creates 3 orthographic engineering views (front, side, top) adjacent to the main poster
// ExtendScript (ES3) — no modern JS features
// Globals expected: SEED (number), all lib/style/compose functions loaded

(function () {

    // ═══════════════════════════════════════════════════════════════
    // CONSTANTS
    // ═══════════════════════════════════════════════════════════════
    var ORTHO_SCALE = 0.7;       // Scale factor for ortho views relative to machine
    var GAP = 60;                // Gap between artboards (pt)
    var FRONT_W = 700;           // Front view artboard width
    var FRONT_H = 450;           // Front view artboard height
    var SIDE_W = 400;            // Side/end view artboard width
    var SIDE_H = 450;            // Side/end view artboard height (matches front)
    var TOP_W = 700;             // Top/plan view artboard width (matches front)
    var TOP_H = 300;             // Top/plan view artboard height
    var HATCH_SPACING = 6;       // Cross-hatch line spacing (pt)
    var HATCH_ANGLE = 45;        // Cross-hatch angle (degrees)
    var WALL_THICKNESS = 0.15;   // Wall thickness as fraction of outer radius
    var BORE_RATIO = 0.25;       // Center bore as fraction of outer radius
    var CORNER_MARK_LEN = 30;    // L-shaped corner mark arm length (pt)
    var VIEW_MARGIN = 20;        // Margin inside each view artboard (pt)

    // ═══════════════════════════════════════════════════════════════
    // INIT
    // ═══════════════════════════════════════════════════════════════
    var ctx = chunkInit();
    if (!ctx) {
        alert("VOID chunk 07: Cannot find artboard or root layer for seed " + SEED);
        return;
    }

    var doc = ctx.doc;
    var rng = ctx.rng;
    var machine = ctx.machine;

    // Bail out if no cylinders to project
    if (!machine.cylinders || machine.cylinders.length === 0) {
        return "VOID chunk 07: No cylinders to project";
    }

    var cyl = machine.cylinders[0]; // Main cylinder for orthographic projection

    // ═══════════════════════════════════════════════════════════════
    // FIND MAIN ARTBOARD RECT
    // ═══════════════════════════════════════════════════════════════
    var mainAb = findArtboard(doc, "VOID_s" + SEED);
    if (!mainAb) {
        alert("VOID chunk 07: Cannot find main artboard VOID_s" + SEED);
        return;
    }

    var mainLeft = mainAb.rect[0];
    var mainTop = mainAb.rect[1];
    var mainRight = mainAb.rect[2];
    var mainBottom = mainAb.rect[3];

    // ═══════════════════════════════════════════════════════════════
    // EXTRACT CYLINDER GEOMETRY FOR ORTHO PROJECTION
    // All measurements in local units, scaled by ORTHO_SCALE
    // ═══════════════════════════════════════════════════════════════
    var sections = cyl.sections;
    var totalLength = cyl.halfLength * 2 * ORTHO_SCALE;

    // Collect radii at section boundaries for the profile
    var secRadii = [];
    for (var si = 0; si < sections.length; si++) {
        secRadii[secRadii.length] = {
            t: sections[si].tStart,
            rTop: sections[si].radiusTop * ORTHO_SCALE,
            rBot: sections[si].radiusBottom * ORTHO_SCALE
        };
    }
    // Final boundary
    var lastSec = sections[sections.length - 1];
    secRadii[secRadii.length] = {
        t: lastSec.tEnd,
        rTop: lastSec.radiusBottom * ORTHO_SCALE,
        rBot: lastSec.radiusBottom * ORTHO_SCALE
    };

    // Maximum radius for view centering
    var maxR = 0;
    for (var ri = 0; ri < secRadii.length; ri++) {
        if (secRadii[ri].rTop > maxR) maxR = secRadii[ri].rTop;
        if (secRadii[ri].rBot > maxR) maxR = secRadii[ri].rBot;
    }

    var wallThick = maxR * WALL_THICKNESS;
    var boreR = maxR * BORE_RATIO;

    // ═══════════════════════════════════════════════════════════════
    // CREATE 3 NEW ARTBOARDS
    // Position relative to the main artboard:
    //   Front: to the RIGHT of main
    //   Side:  to the RIGHT of front
    //   Top:   ABOVE front view
    // Illustrator Y-up: top > bottom, left < right
    // ═══════════════════════════════════════════════════════════════

    // Front view: right of main artboard, vertically centered with main top
    var frontLeft = mainRight + GAP;
    var frontTop = mainTop;
    var frontRight = frontLeft + FRONT_W;
    var frontBottom = frontTop - FRONT_H;

    var frontRect = [frontLeft, frontTop, frontRight, frontBottom];
    var frontAb = doc.artboards.add(frontRect);
    frontAb.name = "ORTHO_FRONT_s" + SEED;

    // Side view: right of front artboard, same vertical position
    var sideLeft = frontRight + GAP;
    var sideTop = frontTop;
    var sideRight = sideLeft + SIDE_W;
    var sideBottom = sideTop - SIDE_H;

    var sideRect = [sideLeft, sideTop, sideRight, sideBottom];
    var sideAb = doc.artboards.add(sideRect);
    sideAb.name = "ORTHO_SIDE_s" + SEED;

    // Top view: above front artboard, same horizontal position
    var topLeft = frontLeft;
    var topTop = frontTop + GAP + TOP_H;
    var topRight = topLeft + TOP_W;
    var topBottom = topTop - TOP_H;

    var topRect = [topLeft, topTop, topRight, topBottom];
    var topAb = doc.artboards.add(topRect);
    topAb.name = "ORTHO_TOP_s" + SEED;

    // ═══════════════════════════════════════════════════════════════
    // CREATE LAYER STRUCTURE
    // "ORTHO_s{SEED}" root with sub-layers
    // ═══════════════════════════════════════════════════════════════
    var orthoRoot = doc.layers.add();
    orthoRoot.name = "ORTHO_s" + SEED;

    // Create sub-layers in reverse order so first listed ends up on top
    var subNames = ["ORTHO_projections", "ORTHO_front", "ORTHO_side", "ORTHO_top", "ORTHO_BG"];
    for (var sli = subNames.length - 1; sli >= 0; sli--) {
        var sub = orthoRoot.layers.add();
        sub.name = subNames[sli];
    }

    var bgLayer = findLayer(orthoRoot, "ORTHO_BG");
    var frontLayer = findLayer(orthoRoot, "ORTHO_front");
    var sideLayer = findLayer(orthoRoot, "ORTHO_side");
    var topLayer = findLayer(orthoRoot, "ORTHO_top");
    var projLayer = findLayer(orthoRoot, "ORTHO_projections");

    // ═══════════════════════════════════════════════════════════════
    // BACKGROUND FILLS
    // ═══════════════════════════════════════════════════════════════
    var bgCol = sCol("bg");
    mkFilledRect(bgLayer, frontLeft, frontTop, FRONT_W, FRONT_H, bgCol);
    mkFilledRect(bgLayer, sideLeft, sideTop, SIDE_W, SIDE_H, bgCol);
    mkFilledRect(bgLayer, topLeft, topTop, TOP_W, TOP_H, bgCol);

    // ═══════════════════════════════════════════════════════════════
    // HELPER: Radius at parametric t along cylinder
    // Interpolates through section boundaries
    // ═══════════════════════════════════════════════════════════════
    function radiusAtT(t) {
        for (var i = 0; i < sections.length; i++) {
            var sec = sections[i];
            if (t >= sec.tStart && t <= sec.tEnd) {
                var localT = (t - sec.tStart) / (sec.tEnd - sec.tStart);
                return lerp(sec.radiusTop, sec.radiusBottom, localT) * ORTHO_SCALE;
            }
        }
        // Fallback: use last section's bottom radius
        return sections[sections.length - 1].radiusBottom * ORTHO_SCALE;
    }

    // ═══════════════════════════════════════════════════════════════
    // HELPER: Draw cross-hatch lines in a rectangular region
    // Clips to region bounds. Draws 45-degree parallel lines.
    // ═══════════════════════════════════════════════════════════════
    function drawCrossHatch(layer, x, y, w, h, spacing, col, sw) {
        // x, y = top-left in Illustrator coords (y is top edge)
        // h is positive, extends downward (y - h = bottom)
        var items = [];
        var diag = Math.sqrt(w * w + h * h);
        var count = Math.ceil(diag / spacing);
        var angR = HATCH_ANGLE * DEG2RAD;
        var dx = Math.cos(angR);
        var dy = Math.sin(angR);
        var px = -dy;
        var py = dx;
        var cx = x + w / 2;
        var cy = y - h / 2;

        for (var i = -count; i <= count; i++) {
            var ox = cx + px * i * spacing;
            var oy = cy + py * i * spacing;
            var x1 = ox - dx * diag;
            var y1 = oy - dy * diag;
            var x2 = ox + dx * diag;
            var y2 = oy + dy * diag;

            // Clip to rectangle bounds
            // The region is: left=x, right=x+w, top=y, bottom=y-h
            var clipPts = clipLineToRect(x1, y1, x2, y2, x, y - h, x + w, y);
            if (clipPts) {
                items[items.length] = mkL(layer,
                    clipPts[0], clipPts[1], clipPts[2], clipPts[3],
                    col, sw, false);
            }
        }
        return items;
    }

    // ═══════════════════════════════════════════════════════════════
    // HELPER: Cohen-Sutherland line clipping to rectangle
    // rect: left, bottom, right, top (Illustrator Y-up)
    // Returns [x1, y1, x2, y2] or null if entirely outside
    // ═══════════════════════════════════════════════════════════════
    function clipLineToRect(x1, y1, x2, y2, left, bottom, right, top) {
        var INSIDE = 0, LEFT_B = 1, RIGHT_B = 2, BOTTOM_B = 4, TOP_B = 8;

        function outCode(x, y) {
            var code = INSIDE;
            if (x < left) code = code | LEFT_B;
            else if (x > right) code = code | RIGHT_B;
            if (y < bottom) code = code | BOTTOM_B;
            else if (y > top) code = code | TOP_B;
            return code;
        }

        var code1 = outCode(x1, y1);
        var code2 = outCode(x2, y2);
        var accept = false;

        for (var iter = 0; iter < 20; iter++) {
            if ((code1 | code2) === 0) {
                accept = true;
                break;
            }
            if ((code1 & code2) !== 0) {
                break;
            }

            var codeOut = (code1 !== 0) ? code1 : code2;
            var nx, ny;

            if (codeOut & TOP_B) {
                nx = x1 + (x2 - x1) * (top - y1) / (y2 - y1);
                ny = top;
            } else if (codeOut & BOTTOM_B) {
                nx = x1 + (x2 - x1) * (bottom - y1) / (y2 - y1);
                ny = bottom;
            } else if (codeOut & RIGHT_B) {
                ny = y1 + (y2 - y1) * (right - x1) / (x2 - x1);
                nx = right;
            } else {
                ny = y1 + (y2 - y1) * (left - x1) / (x2 - x1);
                nx = left;
            }

            if (codeOut === code1) {
                x1 = nx;
                y1 = ny;
                code1 = outCode(x1, y1);
            } else {
                x2 = nx;
                y2 = ny;
                code2 = outCode(x2, y2);
            }
        }

        if (accept) return [x1, y1, x2, y2];
        return null;
    }

    // ═══════════════════════════════════════════════════════════════
    // HELPER: Draw cross-hatch in a circular sector (upper-right quadrant)
    // Used for side view hatching. Clips lines to circle.
    // ═══════════════════════════════════════════════════════════════
    function drawCircularHatch(layer, cx, cy, outerR, innerR, spacing, col, sw) {
        var items = [];
        var count = Math.ceil(outerR * 2 / spacing);

        for (var i = -count; i <= count; i++) {
            // Hatch lines at 45 degrees
            var offset = i * spacing;
            // Line: y - cy = (x - cx) + offset  =>  45 degree lines
            // Parameterize: x from cx to cx + outerR (right half)
            //               y from cy to cy + outerR (upper half, Illustrator Y-up)

            // Start/end of 45-degree line spanning the bounding box
            var lx1 = cx + offset - outerR;
            var ly1 = cy;
            var lx2 = cx + offset;
            var ly2 = cy + outerR;

            // Extend the line further to ensure full coverage
            lx1 = lx1 - outerR;
            ly1 = ly1 - outerR;
            lx2 = lx2 + outerR;
            ly2 = ly2 + outerR;

            // Clip to upper-right quadrant bounding box first
            var clipPts = clipLineToRect(lx1, ly1, lx2, ly2, cx, cy, cx + outerR, cy + outerR);
            if (!clipPts) continue;

            // Further clip to annular region (between inner and outer circles)
            // For simplicity, clip endpoints to outer circle
            var clipped = clipLineToAnnulus(clipPts[0], clipPts[1], clipPts[2], clipPts[3],
                cx, cy, innerR, outerR);
            if (clipped) {
                items[items.length] = mkL(layer,
                    clipped[0], clipped[1], clipped[2], clipped[3],
                    col, sw, false);
            }
        }
        return items;
    }

    // ═══════════════════════════════════════════════════════════════
    // HELPER: Clip a line segment to an annular region (ring between two circles)
    // Returns clipped [x1,y1,x2,y2] or null
    // ═══════════════════════════════════════════════════════════════
    function clipLineToAnnulus(x1, y1, x2, y2, cx, cy, rInner, rOuter) {
        // Find intersections of line with outer circle
        var outerHits = lineCircleIntersect(x1, y1, x2, y2, cx, cy, rOuter);
        if (!outerHits || outerHits.length < 2) return null;

        // Parameterize: the line segment from t=0 (x1,y1) to t=1 (x2,y2)
        var dx = x2 - x1;
        var dy = y2 - y1;
        var segLen = Math.sqrt(dx * dx + dy * dy);
        if (segLen < 0.01) return null;

        // Clip to outer circle: find t-range inside outer circle
        var tOuter = [];
        for (var oi = 0; oi < outerHits.length; oi++) {
            var ot = ((outerHits[oi][0] - x1) * dx + (outerHits[oi][1] - y1) * dy) / (segLen * segLen);
            tOuter[tOuter.length] = ot;
        }
        if (tOuter.length < 2) return null;
        var tMin = Math.max(0, Math.min(tOuter[0], tOuter[1]));
        var tMax = Math.min(1, Math.max(tOuter[0], tOuter[1]));
        if (tMin >= tMax) return null;

        // Check if line crosses inner circle — if so, exclude that segment
        var innerHits = lineCircleIntersect(x1, y1, x2, y2, cx, cy, rInner);
        if (innerHits && innerHits.length >= 2) {
            var tInner = [];
            for (var ii = 0; ii < innerHits.length; ii++) {
                var it = ((innerHits[ii][0] - x1) * dx + (innerHits[ii][1] - y1) * dy) / (segLen * segLen);
                tInner[tInner.length] = it;
            }
            var tiMin = Math.min(tInner[0], tInner[1]);
            var tiMax = Math.max(tInner[0], tInner[1]);

            // Use the segment from tMin to tiMin (before inner circle)
            // This is approximate — for hatching it looks correct
            if (tiMin > tMin && tiMin < tMax) {
                tMax = tiMin;
            }
        }

        if (tMax - tMin < 0.001) return null;

        return [
            x1 + dx * tMin, y1 + dy * tMin,
            x1 + dx * tMax, y1 + dy * tMax
        ];
    }

    // ═══════════════════════════════════════════════════════════════
    // HELPER: Line-circle intersection
    // Returns array of [x,y] points (0, 1, or 2)
    // ═══════════════════════════════════════════════════════════════
    function lineCircleIntersect(x1, y1, x2, y2, cx, cy, r) {
        var dx = x2 - x1;
        var dy = y2 - y1;
        var fx = x1 - cx;
        var fy = y1 - cy;

        var a = dx * dx + dy * dy;
        var b = 2 * (fx * dx + fy * dy);
        var c = fx * fx + fy * fy - r * r;
        var disc = b * b - 4 * a * c;

        if (disc < 0) return null;

        var sqrtDisc = Math.sqrt(disc);
        var t1 = (-b - sqrtDisc) / (2 * a);
        var t2 = (-b + sqrtDisc) / (2 * a);

        var results = [];
        results[0] = [x1 + t1 * dx, y1 + t1 * dy];
        results[1] = [x1 + t2 * dx, y1 + t2 * dy];
        return results;
    }

    // ═══════════════════════════════════════════════════════════════
    // HELPER: Draw L-shaped corner mark
    // corner: "TL", "TR", "BL", "BR"
    // ═══════════════════════════════════════════════════════════════
    function drawCornerMark(layer, x, y, corner, len, col, sw) {
        var items = [];
        var hx = 0, hy = 0, vx = 0, vy = 0;

        if (corner === "TL") {
            // Top-left: horizontal goes right, vertical goes down
            hx = len; vy = -len;
        } else if (corner === "TR") {
            hx = -len; vy = -len;
        } else if (corner === "BL") {
            hx = len; vy = len;
        } else if (corner === "BR") {
            hx = -len; vy = len;
        }

        items[items.length] = mkL(layer, x, y, x + hx, y, col, sw, false);
        items[items.length] = mkL(layer, x, y, x, y + vy, col, sw, false);
        return items;
    }

    // ═══════════════════════════════════════════════════════════════
    // FRONT ELEVATION VIEW (drawOrthoFront)
    // Longitudinal cross-section: X = along cylinder axis, Y = up
    // Positioned on the "front" artboard
    // ═══════════════════════════════════════════════════════════════

    function drawOrthoFront() {
        var items = [];
        var ly = frontLayer;
        var strCol = sCol("structural");
        var secCol = sCol("secondary");
        var ghostCol = sCol("ghost");
        var accCol = sCol("accent");

        // View center in Illustrator coords
        var vcx = frontLeft + FRONT_W / 2;
        var vcy = frontTop - FRONT_H / 2;

        // Cylinder spans horizontally, centered in view
        var halfLen = totalLength / 2;

        // ── Top silhouette (upper profile) ─────────────────────────
        var topPts = [];
        var botPts = [];
        var steps = sections.length * 2 + 2;

        for (var si = 0; si < sections.length; si++) {
            var sec = sections[si];
            var rStart = sec.radiusTop * ORTHO_SCALE;
            var rEnd = sec.radiusBottom * ORTHO_SCALE;
            var xStart = vcx - halfLen + sec.tStart * totalLength;
            var xEnd = vcx - halfLen + sec.tEnd * totalLength;

            topPts[topPts.length] = [xStart, vcy + rStart];
            topPts[topPts.length] = [xEnd, vcy + rEnd];
            botPts[botPts.length] = [xStart, vcy - rStart];
            botPts[botPts.length] = [xEnd, vcy - rEnd];
        }

        // Draw top silhouette polyline
        items[items.length] = mkPoly(ly, topPts, false, strCol, sSW("silhouette"), false);

        // Draw bottom silhouette polyline
        items[items.length] = mkPoly(ly, botPts, false, strCol, sSW("silhouette"), false);

        // ── End caps (vertical lines at left and right ends) ───────
        var leftX = vcx - halfLen;
        var rightX = vcx + halfLen;
        var rLeft = sections[0].radiusTop * ORTHO_SCALE;
        var rRight = lastSec.radiusBottom * ORTHO_SCALE;

        items[items.length] = mkL(ly, leftX, vcy - rLeft, leftX, vcy + rLeft,
            strCol, sSW("silhouette"), false);
        items[items.length] = mkL(ly, rightX, vcy - rRight, rightX, vcy + rRight,
            strCol, sSW("silhouette"), false);

        // ── Section boundary lines (vertical at each section join) ─
        for (var sbi = 1; sbi < sections.length; sbi++) {
            var sbT = sections[sbi].tStart;
            var sbX = vcx - halfLen + sbT * totalLength;
            var sbR = radiusAtT(sbT);
            var sbCol = sAccentOrStructural(rng);
            items[items.length] = mkL(ly, sbX, vcy - sbR, sbX, vcy + sbR,
                sbCol, sSW("structural"), false);
        }

        // ── Wall thickness lines (inner profile) ──────────────────
        var wallTopPts = [];
        var wallBotPts = [];
        for (var wi = 0; wi < sections.length; wi++) {
            var wSec = sections[wi];
            var wrStart = (wSec.radiusTop * ORTHO_SCALE) - wallThick;
            var wrEnd = (wSec.radiusBottom * ORTHO_SCALE) - wallThick;
            var wxStart = vcx - halfLen + wSec.tStart * totalLength;
            var wxEnd = vcx - halfLen + wSec.tEnd * totalLength;

            wallTopPts[wallTopPts.length] = [wxStart, vcy + wrStart];
            wallTopPts[wallTopPts.length] = [wxEnd, vcy + wrEnd];
            wallBotPts[wallBotPts.length] = [wxStart, vcy - wrStart];
            wallBotPts[wallBotPts.length] = [wxEnd, vcy - wrEnd];
        }

        items[items.length] = mkPoly(ly, wallTopPts, false, secCol, sSW("detail"), false);
        items[items.length] = mkPoly(ly, wallBotPts, false, secCol, sSW("detail"), false);

        // ── Hidden center bore (dashed) ───────────────────────────
        var hiddenDash = sHiddenDash();
        if (hiddenDash !== -1) {
            items[items.length] = mkL(ly, leftX, vcy + boreR, rightX, vcy + boreR,
                ghostCol, sSW("hidden"), hiddenDash === 1);
            items[items.length] = mkL(ly, leftX, vcy - boreR, rightX, vcy - boreR,
                ghostCol, sSW("hidden"), hiddenDash === 1);
        }

        // ── Center line (dash-dot, horizontal) ────────────────────
        // Extend slightly beyond the cylinder ends
        var clExt = 20;
        items[items.length] = mkLD(ly,
            leftX - clExt, vcy, rightX + clExt, vcy,
            ghostCol, sSW("detail"), 2);

        // ── Cross-hatching on first section cut face (left end) ───
        var hatchR = rLeft;
        var hatchWallR = rLeft - wallThick;
        // Hatch the cut face: two small rectangular strips (top wall, bottom wall)
        var hatchCol = secCol;
        var hatchSW = sSW("construction");

        // Top wall hatch region
        drawCrossHatch(ly, leftX - 2, vcy + hatchR, 4, hatchR - hatchWallR,
            HATCH_SPACING, hatchCol, hatchSW);

        // Bottom wall hatch region
        drawCrossHatch(ly, leftX - 2, vcy - hatchWallR, 4, hatchR - hatchWallR,
            HATCH_SPACING, hatchCol, hatchSW);

        // ── Housing rectangles projected onto front view ──────────
        for (var hi = 0; hi < machine.housings.length; hi++) {
            var hDef = machine.housings[hi];
            var hT = hDef.attachT;
            var hX = vcx - halfLen + hT * totalLength;
            var hR = radiusAtT(hT);
            var hW = hDef.w * ORTHO_SCALE;
            var hH = hDef.h * ORTHO_SCALE;

            // Housing drawn above or below the cylinder profile
            var hSide = (hDef.y < cyl.cy) ? 1 : -1;
            var hBaseY = vcy + hSide * hR;

            items[items.length] = mkRect(ly,
                hX - hW / 2,
                hBaseY + (hSide > 0 ? hH : 0),
                hW, hH,
                secCol, sSW("structural"), false);
        }

        // ── Overall length dimension line ─────────────────────────
        var dimOff = maxR + 35;
        var dimCol = sAccentOrStructural(rng);
        var dimSW = sSW("detail");

        // Horizontal dimension line below the cylinder
        items[items.length] = mkL(ly, leftX, vcy - dimOff, rightX, vcy - dimOff,
            dimCol, dimSW, false);
        // Arrow ticks (short vertical marks at each end)
        items[items.length] = mkL(ly, leftX, vcy - dimOff - 4, leftX, vcy - dimOff + 4,
            dimCol, dimSW, false);
        items[items.length] = mkL(ly, rightX, vcy - dimOff - 4, rightX, vcy - dimOff + 4,
            dimCol, dimSW, false);
        // Extension lines from profile to dimension
        items[items.length] = mkL(ly, leftX, vcy - rLeft - 5, leftX, vcy - dimOff - 8,
            ghostCol, sSW("construction"), false);
        items[items.length] = mkL(ly, rightX, vcy - rRight - 5, rightX, vcy - dimOff - 8,
            ghostCol, sSW("construction"), false);

        // Dimension text
        var dimVal = Math.round(totalLength / ORTHO_SCALE);
        mkText(ly, vcx - 20, vcy - dimOff - 12,
            "" + dimVal, STYLE.typography.label_size, dimCol);

        // ── View label ────────────────────────────────────────────
        mkText(ly, frontLeft + VIEW_MARGIN, frontBottom + 18,
            "FRONT ELEVATION", STYLE.typography.label_size, accCol);

        return items;
    }

    // ═══════════════════════════════════════════════════════════════
    // SIDE / END VIEW (drawOrthoSide)
    // Looking down the cylinder axis — concentric circles
    // Positioned on the "side" artboard
    // ═══════════════════════════════════════════════════════════════

    function drawOrthoSide() {
        var items = [];
        var ly = sideLayer;
        var strCol = sCol("structural");
        var secCol = sCol("secondary");
        var ghostCol = sCol("ghost");
        var accCol = sCol("accent");

        // View center
        var vcx = sideLeft + SIDE_W / 2;
        var vcy = sideTop - SIDE_H / 2;

        // ── Concentric circles for each section radius ────────────
        // Show radii at each section boundary (front-facing end)
        var drawnRadii = {};
        for (var si = 0; si < sections.length; si++) {
            var rTop = Math.round(sections[si].radiusTop * ORTHO_SCALE);
            var rBot = Math.round(sections[si].radiusBottom * ORTHO_SCALE);

            if (!drawnRadii[rTop]) {
                drawnRadii[rTop] = true;
                var circCol = sAccentOrStructural(rng);
                items[items.length] = mkCirc(ly, vcx, vcy, rTop, circCol, sSW("structural"), false);
            }
            if (!drawnRadii[rBot]) {
                drawnRadii[rBot] = true;
                items[items.length] = mkCirc(ly, vcx, vcy, rBot, strCol, sSW("structural"), false);
            }
        }

        // ── Wall thickness circle ─────────────────────────────────
        // Inner wall at the front-facing section
        var frontR = lastSec.radiusBottom * ORTHO_SCALE;
        var wallR = frontR - wallThick;
        items[items.length] = mkCirc(ly, vcx, vcy, wallR, secCol, sSW("detail"), false);

        // ── Center bore circle ────────────────────────────────────
        var hiddenDash = sHiddenDash();
        if (hiddenDash !== -1) {
            var borePath = mkCirc(ly, vcx, vcy, boreR, ghostCol, sSW("hidden"), false);
            if (hiddenDash === 1) borePath.strokeDashes = [4, 3];
            items[items.length] = borePath;
        }

        // ── Spokes / internal structure ───────────────────────────
        // Radial lines from bore to wall, evenly spaced
        var spokeCount = rng.randInt(4, 8);
        for (var spi = 0; spi < spokeCount; spi++) {
            var spokeAng = (360 / spokeCount) * spi;
            var spokeAngR = spokeAng * DEG2RAD;
            var sx1 = vcx + boreR * Math.cos(spokeAngR);
            var sy1 = vcy + boreR * Math.sin(spokeAngR);
            var sx2 = vcx + wallR * Math.cos(spokeAngR);
            var sy2 = vcy + wallR * Math.sin(spokeAngR);
            items[items.length] = mkL(ly, sx1, sy1, sx2, sy2,
                secCol, sSW("detail"), false);
        }

        // ── Cross-hair center lines (dash-dot) ───────────────────
        // Extend slightly beyond the largest circle
        var clExt = 15;
        // Horizontal center line
        items[items.length] = mkLD(ly,
            vcx - maxR - clExt, vcy,
            vcx + maxR + clExt, vcy,
            ghostCol, sSW("detail"), 2);
        // Vertical center line
        items[items.length] = mkLD(ly,
            vcx, vcy - maxR - clExt,
            vcx, vcy + maxR + clExt,
            ghostCol, sSW("detail"), 2);

        // ── Cross-hatching in upper-right quadrant ────────────────
        var hatchCol = secCol;
        var hatchSW = sSW("construction");
        drawCircularHatch(ly, vcx, vcy, frontR, wallR, HATCH_SPACING, hatchCol, hatchSW);

        // ── View label ────────────────────────────────────────────
        mkText(ly, sideLeft + VIEW_MARGIN, sideBottom + 18,
            "SIDE VIEW (END)", STYLE.typography.label_size, accCol);

        return items;
    }

    // ═══════════════════════════════════════════════════════════════
    // TOP / PLAN VIEW (drawOrthoTop)
    // Looking straight down — cylinder as tapered rectangle (plan)
    // Positioned on the "top" artboard
    // ═══════════════════════════════════════════════════════════════

    function drawOrthoTop() {
        var items = [];
        var ly = topLayer;
        var strCol = sCol("structural");
        var secCol = sCol("secondary");
        var ghostCol = sCol("ghost");
        var accCol = sCol("accent");

        // View center
        var vcx = topLeft + TOP_W / 2;
        var vcy = topTop - TOP_H / 2;

        // Cylinder spans horizontally in plan, width = diameter (looking down)
        var halfLen = totalLength / 2;

        // ── Main cylinder outer profile (tapered rectangle, plan) ─
        // Top-down view: X = along axis, Y = width (diameter)
        var planTopPts = [];
        var planBotPts = [];

        for (var si = 0; si < sections.length; si++) {
            var sec = sections[si];
            var rStart = sec.radiusTop * ORTHO_SCALE;
            var rEnd = sec.radiusBottom * ORTHO_SCALE;
            var xStart = vcx - halfLen + sec.tStart * totalLength;
            var xEnd = vcx - halfLen + sec.tEnd * totalLength;

            planTopPts[planTopPts.length] = [xStart, vcy + rStart];
            planTopPts[planTopPts.length] = [xEnd, vcy + rEnd];
            planBotPts[planBotPts.length] = [xStart, vcy - rStart];
            planBotPts[planBotPts.length] = [xEnd, vcy - rEnd];
        }

        // Outer silhouette: top edge, bottom edge, end caps
        items[items.length] = mkPoly(ly, planTopPts, false, strCol, sSW("silhouette"), false);
        items[items.length] = mkPoly(ly, planBotPts, false, strCol, sSW("silhouette"), false);

        // End caps
        var leftX = vcx - halfLen;
        var rightX = vcx + halfLen;
        var rLeft = sections[0].radiusTop * ORTHO_SCALE;
        var rRight = lastSec.radiusBottom * ORTHO_SCALE;

        items[items.length] = mkL(ly, leftX, vcy - rLeft, leftX, vcy + rLeft,
            strCol, sSW("silhouette"), false);
        items[items.length] = mkL(ly, rightX, vcy - rRight, rightX, vcy + rRight,
            strCol, sSW("silhouette"), false);

        // ── Wall thickness rectangles (inner profile) ─────────────
        var wallTopPts = [];
        var wallBotPts = [];
        for (var wi = 0; wi < sections.length; wi++) {
            var wSec = sections[wi];
            var wrStart = (wSec.radiusTop * ORTHO_SCALE) - wallThick;
            var wrEnd = (wSec.radiusBottom * ORTHO_SCALE) - wallThick;
            var wxStart = vcx - halfLen + wSec.tStart * totalLength;
            var wxEnd = vcx - halfLen + wSec.tEnd * totalLength;

            wallTopPts[wallTopPts.length] = [wxStart, vcy + wrStart];
            wallTopPts[wallTopPts.length] = [wxEnd, vcy + wrEnd];
            wallBotPts[wallBotPts.length] = [wxStart, vcy - wrStart];
            wallBotPts[wallBotPts.length] = [wxEnd, vcy - wrEnd];
        }

        items[items.length] = mkPoly(ly, wallTopPts, false, secCol, sSW("detail"), false);
        items[items.length] = mkPoly(ly, wallBotPts, false, secCol, sSW("detail"), false);

        // ── Hidden center bore lines ──────────────────────────────
        var hiddenDash = sHiddenDash();
        if (hiddenDash !== -1) {
            items[items.length] = mkL(ly, leftX, vcy + boreR, rightX, vcy + boreR,
                ghostCol, sSW("hidden"), hiddenDash === 1);
            items[items.length] = mkL(ly, leftX, vcy - boreR, rightX, vcy - boreR,
                ghostCol, sSW("hidden"), hiddenDash === 1);
        }

        // ── Center line (dash-dot) ────────────────────────────────
        var clExt = 20;
        items[items.length] = mkLD(ly,
            leftX - clExt, vcy, rightX + clExt, vcy,
            ghostCol, sSW("detail"), 2);

        // ── Section boundary lines ────────────────────────────────
        for (var sbi = 1; sbi < sections.length; sbi++) {
            var sbT = sections[sbi].tStart;
            var sbX = vcx - halfLen + sbT * totalLength;
            var sbR = radiusAtT(sbT);
            var sbCol = sAccentOrStructural(rng);
            items[items.length] = mkL(ly, sbX, vcy - sbR, sbX, vcy + sbR,
                sbCol, sSW("structural"), false);
        }

        // ── Housing rectangles in plan ────────────────────────────
        for (var hi = 0; hi < machine.housings.length; hi++) {
            var hDef = machine.housings[hi];
            var hT = hDef.attachT;
            var hX = vcx - halfLen + hT * totalLength;
            var hR = radiusAtT(hT);
            var hW = hDef.w * ORTHO_SCALE;
            var hD = hDef.d * ORTHO_SCALE; // In plan view, depth becomes the Y extent

            // Housing extends outward from cylinder surface
            var hSide = (hDef.y < cyl.cy) ? 1 : -1;
            var hBaseY = vcy + hSide * hR;

            items[items.length] = mkRect(ly,
                hX - hW / 2,
                hBaseY + (hSide > 0 ? hD : 0),
                hW, hD,
                secCol, sSW("structural"), false);
        }

        // ── View label ────────────────────────────────────────────
        mkText(ly, topLeft + VIEW_MARGIN, topBottom + 18,
            "TOP VIEW (PLAN)", STYLE.typography.label_size, accCol);

        return items;
    }

    // ═══════════════════════════════════════════════════════════════
    // PROJECTION LINES
    // Connect the 3 views with construction lines showing alignment
    // ═══════════════════════════════════════════════════════════════

    function drawProjectionLines() {
        var items = [];
        var ly = projLayer;
        var projCol = sCol("ghost");
        var projSW = sSW("construction");

        // Front view center
        var fvcx = frontLeft + FRONT_W / 2;
        var fvcy = frontTop - FRONT_H / 2;

        // Side view center
        var svcx = sideLeft + SIDE_W / 2;
        var svcy = sideTop - SIDE_H / 2;

        // Top view center
        var tvcx = topLeft + TOP_W / 2;
        var tvcy = topTop - TOP_H / 2;

        var halfLen = totalLength / 2;

        // ── Horizontal lines: Front → Side ────────────────────────
        // At cylinder top, center, and bottom extents
        var projRadii = [maxR, 0, -maxR];
        for (var pi = 0; pi < projRadii.length; pi++) {
            var py = fvcy + projRadii[pi];
            // Line from right edge of front view to left edge of side view
            items[items.length] = mkLD(ly,
                frontRight + 5, py,
                sideLeft - 5, py,
                projCol, projSW, 1);  // dashed
        }

        // Also add wall thickness projection lines
        var wallProjR = maxR - wallThick;
        items[items.length] = mkLD(ly,
            frontRight + 5, fvcy + wallProjR,
            sideLeft - 5, fvcy + wallProjR,
            projCol, projSW, 1);
        items[items.length] = mkLD(ly,
            frontRight + 5, fvcy - wallProjR,
            sideLeft - 5, fvcy - wallProjR,
            projCol, projSW, 1);

        // ── Vertical lines: Front → Top ───────────────────────────
        // At section boundaries and cylinder ends
        var leftX = fvcx - halfLen;
        var rightX = fvcx + halfLen;

        // Cylinder end lines
        items[items.length] = mkLD(ly,
            leftX, frontTop + 5,
            leftX, topBottom - 5,
            projCol, projSW, 1);
        items[items.length] = mkLD(ly,
            rightX, frontTop + 5,
            rightX, topBottom - 5,
            projCol, projSW, 1);

        // Section boundary vertical projection lines
        for (var sbi = 1; sbi < sections.length; sbi++) {
            var sbT = sections[sbi].tStart;
            var sbX = fvcx - halfLen + sbT * totalLength;
            items[items.length] = mkLD(ly,
                sbX, frontTop + 5,
                sbX, topBottom - 5,
                projCol, projSW, 1);
        }

        return items;
    }

    // ═══════════════════════════════════════════════════════════════
    // VIEW LABEL CORNER MARKS
    // L-shaped corner marks on each view artboard in accent color
    // ═══════════════════════════════════════════════════════════════

    function drawViewMarkers() {
        var ly = projLayer;
        var markCol = sCol("accent");
        var markSW = sSW("structural");
        var len = CORNER_MARK_LEN;
        var inset = 8; // Inset from artboard edge

        // Front view corners
        drawCornerMark(ly, frontLeft + inset, frontTop - inset, "TL", len, markCol, markSW);
        drawCornerMark(ly, frontRight - inset, frontTop - inset, "TR", len, markCol, markSW);
        drawCornerMark(ly, frontLeft + inset, frontBottom + inset, "BL", len, markCol, markSW);
        drawCornerMark(ly, frontRight - inset, frontBottom + inset, "BR", len, markCol, markSW);

        // Side view corners
        drawCornerMark(ly, sideLeft + inset, sideTop - inset, "TL", len, markCol, markSW);
        drawCornerMark(ly, sideRight - inset, sideTop - inset, "TR", len, markCol, markSW);
        drawCornerMark(ly, sideLeft + inset, sideBottom + inset, "BL", len, markCol, markSW);
        drawCornerMark(ly, sideRight - inset, sideBottom + inset, "BR", len, markCol, markSW);

        // Top view corners
        drawCornerMark(ly, topLeft + inset, topTop - inset, "TL", len, markCol, markSW);
        drawCornerMark(ly, topRight - inset, topTop - inset, "TR", len, markCol, markSW);
        drawCornerMark(ly, topLeft + inset, topBottom + inset, "BL", len, markCol, markSW);
        drawCornerMark(ly, topRight - inset, topBottom + inset, "BR", len, markCol, markSW);
    }

    // ═══════════════════════════════════════════════════════════════
    // EXECUTE ALL DRAWING FUNCTIONS
    // ═══════════════════════════════════════════════════════════════
    drawOrthoFront();
    drawOrthoSide();
    drawOrthoTop();
    drawProjectionLines();
    drawViewMarkers();

    // ═══════════════════════════════════════════════════════════════
    // FINALIZE
    // ═══════════════════════════════════════════════════════════════
    app.redraw();
    doc.save();

    return "VOID_s" + SEED + " ortho: 3 projection views created (front, side, top)";
})();
