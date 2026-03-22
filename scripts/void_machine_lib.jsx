// void_machine_lib.jsx
// Component render library for procedural isometric machine generator
// Adobe Illustrator ExtendScript (ES3)

// ─────────────────────────────────────────────────────────────
// PRNG — seeded pseudo-random number generator (xorshift32)
// ─────────────────────────────────────────────────────────────
function PRNG(seed) {
    var s = seed | 0;
    if (s === 0) s = 1;
    var self = {};
    self.next = function () {
        s ^= s << 13;
        s ^= s >> 17;
        s ^= s << 5;
        return ((s < 0 ? s + 4294967296 : s) % 4294967296) / 4294967296;
    };
    self.range = function (mn, mx) {
        return mn + self.next() * (mx - mn);
    };
    self.randInt = function (mn, mx) {
        return Math.floor(self.range(mn, mx + 1));
    };
    self.pick = function (arr) {
        return arr[Math.floor(self.next() * arr.length)];
    };
    self.gaussian = function (mean, stddev) {
        var u1 = self.next();
        var u2 = self.next();
        if (u1 < 1e-10) u1 = 1e-10;
        var z = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
        return mean + z * stddev;
    };
    self.chance = function (p) {
        return self.next() < p;
    };
    return self;
}

// ─────────────────────────────────────────────────────────────
// Color helpers
// ─────────────────────────────────────────────────────────────
function rgb(r, g, b) {
    var c = new RGBColor();
    c.red = r;
    c.green = g;
    c.blue = b;
    return c;
}

var COL = {
    NEON:   rgb(255, 102, 0),
    SALMON: rgb(232, 115, 74),
    WARM:   rgb(212, 98, 59),
    DEEP:   rgb(184, 80, 48),
    DARK:   rgb(61, 26, 10),
    BLACK:  rgb(15, 15, 15)
};

// ─────────────────────────────────────────────────────────────
// Math utilities
// ─────────────────────────────────────────────────────────────
function lerp(a, b, t) {
    return a + (b - a) * t;
}

function clamp(val, mn, mx) {
    if (val < mn) return mn;
    if (val > mx) return mx;
    return val;
}

function ePt(cx, cy, a, b, angleDeg) {
    var rad = angleDeg * Math.PI / 180;
    return [cx + a * Math.cos(rad), cy + b * Math.sin(rad)];
}

// Rotated ellipse point — for ellipses oriented perpendicular to a given axis
function eRPt(cx, cy, a, b, angleDeg, rotDeg) {
    var rad = angleDeg * DEG2RAD;
    var rr = rotDeg * DEG2RAD;
    var px = a * Math.cos(rad);
    var py = b * Math.sin(rad);
    // Rotate point by rotDeg
    return [cx + px * Math.cos(rr) - py * Math.sin(rr),
            cy + px * Math.sin(rr) + py * Math.cos(rr)];
}

// Create a rotated ellipse (or arc) — samples points and rotates them
function mkER(layer, cx, cy, a, b, startAng, endAng, rotDeg, col, sw, dashed) {
    var sweep = endAng - startAng;
    var steps = Math.max(24, Math.round(Math.abs(sweep) / 5));
    var pts = [];
    for (var i = 0; i <= steps; i++) {
        var ang = startAng + (sweep * i / steps);
        var pt = eRPt(cx, cy, a, b, ang, rotDeg);
        pts[pts.length] = pt;
    }
    var p = layer.pathItems.add();
    p.setEntirePath(pts);
    p.closed = (startAng === 0 && endAng === 360);
    return _applyStroke(p, col, sw, dashed);
}

function axPt(backPt, frontPt, t) {
    return [lerp(backPt[0], frontPt[0], t), lerp(backPt[1], frontPt[1], t)];
}

var DEG2RAD = Math.PI / 180;

// ─────────────────────────────────────────────────────────────
// Layer helper
// ─────────────────────────────────────────────────────────────
function getOrCreateLayer(parent, name) {
    for (var i = 0; i < parent.layers.length; i++) {
        if (parent.layers[i].name === name) return parent.layers[i];
    }
    var lyr = parent.layers.add();
    lyr.name = name;
    return lyr;
}

// ─────────────────────────────────────────────────────────────
// Stroke helper — applies common stroke settings
// ─────────────────────────────────────────────────────────────
function _applyStroke(p, strokeColor, strokeWidth, dashed) {
    p.stroked = true;
    p.filled = false;
    p.strokeColor = strokeColor;
    p.strokeWidth = strokeWidth;
    if (dashed) {
        p.strokeDashes = [4, 3];
    }
    return p;
}

// ─────────────────────────────────────────────────────────────
// mkE — ellipse or arc
// ─────────────────────────────────────────────────────────────
function mkE(layer, cx, cy, a, b, startAng, endAng, strokeColor, strokeWidth, dashed) {
    var p;
    if (startAng === 0 && endAng === 360) {
        // Full ellipse — use built-in. Args: top, left, width, height
        p = layer.pathItems.ellipse(cy + b, cx - a, a * 2, b * 2);
    } else {
        // Arc — compute points parametrically
        var sweep = endAng - startAng;
        var steps = Math.max(12, Math.round(Math.abs(sweep) / 5));
        var pts = [];
        for (var i = 0; i <= steps; i++) {
            var ang = startAng + (sweep * i / steps);
            var rad = ang * DEG2RAD;
            pts[pts.length] = [cx + a * Math.cos(rad), cy + b * Math.sin(rad)];
        }
        p = layer.pathItems.add();
        p.setEntirePath(pts);
        p.closed = false;
    }
    return _applyStroke(p, strokeColor, strokeWidth, dashed);
}

// ─────────────────────────────────────────────────────────────
// mkL — line between two points
// ─────────────────────────────────────────────────────────────
function mkL(layer, x1, y1, x2, y2, strokeColor, strokeWidth, dashed) {
    var p = layer.pathItems.add();
    p.setEntirePath([[x1, y1], [x2, y2]]);
    p.closed = false;
    return _applyStroke(p, strokeColor, strokeWidth, dashed);
}

// ─────────────────────────────────────────────────────────────
// mkCirc — circle (optionally filled)
// ─────────────────────────────────────────────────────────────
function mkCirc(layer, cx, cy, r, strokeColor, strokeWidth, filled) {
    var p = layer.pathItems.ellipse(cy + r, cx - r, r * 2, r * 2);
    p.stroked = true;
    p.strokeColor = strokeColor;
    p.strokeWidth = strokeWidth;
    if (filled) {
        p.filled = true;
        p.fillColor = strokeColor;
    } else {
        p.filled = false;
    }
    return p;
}

// ─────────────────────────────────────────────────────────────
// mkPoly — polyline / polygon from point array
// ─────────────────────────────────────────────────────────────
function mkPoly(layer, pointsArray, closed, strokeColor, strokeWidth, dashed) {
    var p = layer.pathItems.add();
    p.setEntirePath(pointsArray);
    p.closed = closed;
    return _applyStroke(p, strokeColor, strokeWidth, dashed);
}

// ─────────────────────────────────────────────────────────────
// mkRect — rectangle (top-left x,y then w,h)
// ─────────────────────────────────────────────────────────────
function mkRect(layer, x, y, w, h, strokeColor, strokeWidth, dashed) {
    // Illustrator Y-up: y is the top edge, bottom edge is y-h
    var p = layer.pathItems.rectangle(y, x, w, h);
    return _applyStroke(p, strokeColor, strokeWidth, dashed);
}

// ─────────────────────────────────────────────────────────────
// mkGroup — group items under a name
// ─────────────────────────────────────────────────────────────
function mkGroup(layer, name, itemsArray) {
    var g = layer.groupItems.add();
    g.name = name;
    // Move items into group in reverse so stacking order is preserved
    for (var i = itemsArray.length - 1; i >= 0; i--) {
        itemsArray[i].move(g, ElementPlacement.PLACEATEND);
    }
    return g;
}

// ─────────────────────────────────────────────────────────────
// _ellipseArc — helper to draw front or back half of ellipse
// Returns the path item
// ─────────────────────────────────────────────────────────────
function _ellipseArc(layer, cx, cy, a, b, fromDeg, toDeg, strokeColor, strokeWidth, dashed) {
    return mkE(layer, cx, cy, a, b, fromDeg, toDeg, strokeColor, strokeWidth, dashed);
}

// ─────────────────────────────────────────────────────────────
// COMPONENT: makeCylinder
// ─────────────────────────────────────────────────────────────
function makeCylinder(layer, def, rng) {
    var items = [];
    var axAng = def.axisAngle || -40;
    var axRad = axAng * DEG2RAD;
    var dx = Math.cos(axRad) * def.halfLength;
    var dy = Math.sin(axRad) * def.halfLength;
    var backPt  = [def.cx - dx, def.cy - dy];
    var frontPt = [def.cx + dx, def.cy + dy];
    var fs = def.foreshorten || 0.6;
    var secs = def.sections;
    // Ellipse rotation: perpendicular to cylinder axis
    var eRot = axAng + 90;

    for (var si = 0; si < secs.length; si++) {
        var sec = secs[si];
        var t0 = sec.tStart;
        var t1 = sec.tEnd;
        var rTop = sec.radiusTop;
        var rBot = sec.radiusBottom;

        var cBack  = axPt(backPt, frontPt, t0);
        var cFront = axPt(backPt, frontPt, t1);

        // Rotated ellipses — perpendicular to the cylinder axis
        // Back: hidden half dashed, visible half solid
        items[items.length] = mkER(layer, cBack[0], cBack[1], rTop, rTop * fs, 0, 180, eRot, COL.DEEP, 0.35, true);
        items[items.length] = mkER(layer, cBack[0], cBack[1], rTop, rTop * fs, 180, 360, eRot, COL.SALMON, 1.5, false);

        // Front: bold visible ring
        items[items.length] = mkER(layer, cFront[0], cFront[1], rBot, rBot * fs, 0, 360, eRot, COL.NEON, 2.0, false);

        // Silhouette lines — connect tangent points of rotated ellipses
        var topBack  = eRPt(cBack[0], cBack[1], rTop, rTop * fs, 90, eRot);
        var topFront = eRPt(cFront[0], cFront[1], rBot, rBot * fs, 90, eRot);
        var botBack  = eRPt(cBack[0], cBack[1], rTop, rTop * fs, 270, eRot);
        var botFront = eRPt(cFront[0], cFront[1], rBot, rBot * fs, 270, eRot);
        items[items.length] = mkL(layer, topBack[0], topBack[1], topFront[0], topFront[1], COL.NEON, 2.5, false);
        items[items.length] = mkL(layer, botBack[0], botBack[1], botFront[0], botFront[1], COL.NEON, 2.5, false);

        // Band rings (intermediate structural rings)
        var bandCount = rng.randInt(2, 4);
        for (var bi = 1; bi <= bandCount; bi++) {
            var bt = bi / (bandCount + 1);
            var bCenter = axPt(cBack, cFront, bt);
            var bRad = lerp(rTop, rBot, bt);
            items[items.length] = mkER(layer, bCenter[0], bCenter[1], bRad, bRad * fs, 180, 360, eRot, COL.SALMON, 1.0, false);
            items[items.length] = mkER(layer, bCenter[0], bCenter[1], bRad, bRad * fs, 0, 180, eRot, COL.DEEP, 0.3, true);
        }

        // Rib rings
        var ribCount = rng.randInt(1, 2);
        for (var ri = 0; ri < ribCount; ri++) {
            var rt = rng.range(0.15, 0.85);
            var rCenter = axPt(cBack, cFront, rt);
            var rRad = lerp(rTop, rBot, rt) * (1.0 + rng.range(0.02, 0.06));
            items[items.length] = mkER(layer, rCenter[0], rCenter[1], rRad, rRad * fs, 180, 360, eRot, COL.WARM, 0.6, false);
        }

        // Panel lines — surface detail connecting rotated ellipse tangents
        var panelCount = rng.randInt(3, 6);
        for (var pi = 0; pi < panelCount; pi++) {
            var pAng = 200 + (140 * (pi + 1) / (panelCount + 1));
            var pBack  = eRPt(cBack[0], cBack[1], rTop, rTop * fs, pAng, eRot);
            var pFront = eRPt(cFront[0], cFront[1], rBot, rBot * fs, pAng, eRot);
            items[items.length] = mkL(layer, pBack[0], pBack[1], pFront[0], pFront[1], COL.WARM, 0.4, false);
        }

        // Hidden panel lines (dashed, back face)
        var hiddenPanels = rng.randInt(1, 3);
        for (var hp = 0; hp < hiddenPanels; hp++) {
            var hAng = 30 + (120 * (hp + 1) / (hiddenPanels + 1));
            var hpBack  = eRPt(cBack[0], cBack[1], rTop, rTop * fs, hAng, eRot);
            var hpFront = eRPt(cFront[0], cFront[1], rBot, rBot * fs, hAng, eRot);
            items[items.length] = mkL(layer, hpBack[0], hpBack[1], hpFront[0], hpFront[1], COL.DEEP, 0.25, true);
        }

        // Section boundary ring (bold)
        if (si < secs.length - 1) {
            var ringPt = axPt(backPt, frontPt, t1);
            var ringR = rBot;
            items[items.length] = mkER(layer, ringPt[0], ringPt[1], ringR * 1.05, ringR * 1.05 * fs, 0, 360, eRot, COL.NEON, 1.75, false);
            items[items.length] = mkER(layer, ringPt[0], ringPt[1], ringR * 0.92, ringR * 0.92 * fs, 0, 360, eRot, COL.SALMON, 0.75, false);
        }
    }

    // Axis center line
    items[items.length] = mkL(layer, backPt[0], backPt[1], frontPt[0], frontPt[1], COL.DEEP, 0.4, false);
    items[items.length - 1].strokeDashes = [18, 4, 2, 4];

    return mkGroup(layer, def.name || "cylinder", items);
}

// ─────────────────────────────────────────────────────────────
// COMPONENT: makeHousing
// ─────────────────────────────────────────────────────────────
function makeHousing(layer, def, rng) {
    var items = [];
    var x = def.x;
    var y = def.y;
    var w = def.w;
    var h = def.h;
    var d = def.d;
    var ang = (def.angle || 30) * DEG2RAD;
    var dxOff = d * Math.cos(ang);
    var dyOff = d * Math.sin(ang);

    // Front face corners (bottom-left origin, Y-up)
    var fl = [x, y];          // front-left-bottom
    var fr = [x + w, y];      // front-right-bottom
    var frt = [x + w, y + h]; // front-right-top
    var flt = [x, y + h];     // front-left-top

    // Back face corners (offset by depth)
    var bl = [fl[0] + dxOff, fl[1] + dyOff];
    var br = [fr[0] + dxOff, fr[1] + dyOff];
    var brt = [frt[0] + dxOff, frt[1] + dyOff];
    var blt = [flt[0] + dxOff, flt[1] + dyOff];

    // Front face
    var front = mkPoly(layer, [fl, fr, frt, flt], true, COL.SALMON, 1.0, false);
    items[items.length] = front;

    // Top face
    var top = mkPoly(layer, [flt, frt, brt, blt], true, COL.SALMON, 1.0, false);
    items[items.length] = top;

    // Side face (right side)
    var side = mkPoly(layer, [fr, br, brt, frt], true, COL.SALMON, 1.0, false);
    items[items.length] = side;

    // Bold outlines on visible silhouette edges
    var sil1 = mkL(layer, fl[0], fl[1], fr[0], fr[1], COL.NEON, 2.0, false);
    var sil2 = mkL(layer, fl[0], fl[1], flt[0], flt[1], COL.NEON, 2.0, false);
    var sil3 = mkL(layer, flt[0], flt[1], blt[0], blt[1], COL.NEON, 2.0, false);
    var sil4 = mkL(layer, blt[0], blt[1], brt[0], brt[1], COL.NEON, 2.0, false);
    var sil5 = mkL(layer, brt[0], brt[1], br[0], br[1], COL.NEON, 2.0, false);
    var sil6 = mkL(layer, br[0], br[1], fr[0], fr[1], COL.NEON, 2.0, false);
    items[items.length] = sil1;
    items[items.length] = sil2;
    items[items.length] = sil3;
    items[items.length] = sil4;
    items[items.length] = sil5;
    items[items.length] = sil6;

    // Panel lines on front face
    var panelCount = rng.randInt(2, 4);
    for (var pi = 0; pi < panelCount; pi++) {
        var px = x + w * (pi + 1) / (panelCount + 1);
        var panelLine = mkL(layer, px, y, px, y + h, COL.WARM, 0.5, false);
        items[items.length] = panelLine;
    }

    // Hidden edges (dashed)
    if (def.showHidden) {
        var hid1 = mkL(layer, fl[0], fl[1], bl[0], bl[1], COL.DEEP, 0.35, true);
        var hid2 = mkL(layer, bl[0], bl[1], blt[0], blt[1], COL.DEEP, 0.35, true);
        var hid3 = mkL(layer, bl[0], bl[1], br[0], br[1], COL.DEEP, 0.35, true);
        items[items.length] = hid1;
        items[items.length] = hid2;
        items[items.length] = hid3;
    }

    // Bracket / mounting detail on bottom edge
    var bracketInset = w * 0.15;
    var bracketDrop = h * 0.06;
    var bk1 = mkL(layer, x + bracketInset, y, x + bracketInset, y - bracketDrop, COL.WARM, 0.75, false);
    var bk2 = mkL(layer, x + bracketInset, y - bracketDrop, x + w - bracketInset, y - bracketDrop, COL.WARM, 0.75, false);
    var bk3 = mkL(layer, x + w - bracketInset, y - bracketDrop, x + w - bracketInset, y, COL.WARM, 0.75, false);
    items[items.length] = bk1;
    items[items.length] = bk2;
    items[items.length] = bk3;

    return mkGroup(layer, def.name || "housing", items);
}

// ─────────────────────────────────────────────────────────────
// COMPONENT: makePipe
// ─────────────────────────────────────────────────────────────
function makePipe(layer, def, rng) {
    var items = [];
    var sp = def.startPt;
    var ep = def.endPt;
    var r  = def.radius;
    var fr = def.flangeRadius || r * 1.4;
    var fs = 0.35; // foreshorten

    // Direction perpendicular to pipe axis (simplified: assume mostly horizontal)
    var adx = ep[0] - sp[0];
    var ady = ep[1] - sp[1];
    var alen = Math.sqrt(adx * adx + ady * ady);
    if (alen < 0.01) alen = 1;
    // Perpendicular in 2D
    var nx = -ady / alen;
    var ny = adx / alen;

    // Silhouette lines along pipe body
    var s1 = mkL(layer, sp[0] + nx * r, sp[1] + ny * r, ep[0] + nx * r, ep[1] + ny * r, COL.NEON, 2.0, false);
    var s2 = mkL(layer, sp[0] - nx * r, sp[1] - ny * r, ep[0] - nx * r, ep[1] - ny * r, COL.NEON, 2.0, false);
    items[items.length] = s1;
    items[items.length] = s2;

    // End ellipses (pipe openings)
    var eStart = mkE(layer, sp[0], sp[1], r, r * fs, 0, 360, COL.SALMON, 1.25, false);
    var eEnd   = mkE(layer, ep[0], ep[1], r, r * fs, 0, 360, COL.SALMON, 1.25, false);
    items[items.length] = eStart;
    items[items.length] = eEnd;

    // Flanges — wider ellipses at each end
    var fStart = mkE(layer, sp[0], sp[1], fr, fr * fs, 0, 360, COL.SALMON, 1.0, false);
    var fEnd   = mkE(layer, ep[0], ep[1], fr, fr * fs, 0, 360, COL.SALMON, 1.0, false);
    items[items.length] = fStart;
    items[items.length] = fEnd;

    // Center line (dash-dot)
    var cl = mkL(layer, sp[0], sp[1], ep[0], ep[1], COL.DEEP, 0.4, false);
    cl.strokeDashes = [18, 4, 2, 4];
    items[items.length] = cl;

    // Bolt circles on flanges
    var boltStartGroup = makeBoltCircle(layer, {
        name: def.name + "_bolts_s",
        cx: sp[0], cy: sp[1],
        radius: (r + fr) * 0.5,
        count: 6,
        boltRadius: r * 0.08,
        foreshorten: fs
    }, rng);
    var boltEndGroup = makeBoltCircle(layer, {
        name: def.name + "_bolts_e",
        cx: ep[0], cy: ep[1],
        radius: (r + fr) * 0.5,
        count: 6,
        boltRadius: r * 0.08,
        foreshorten: fs
    }, rng);
    items[items.length] = boltStartGroup;
    items[items.length] = boltEndGroup;

    return mkGroup(layer, def.name || "pipe", items);
}

// ─────────────────────────────────────────────────────────────
// COMPONENT: makeCrossSection
// ─────────────────────────────────────────────────────────────
function makeCrossSection(layer, def, rng) {
    var items = [];
    var cx = def.cx;
    var cy = def.cy;
    var outerR = def.outerRadius;
    var innerR = def.innerRadius;
    var rings  = def.rings || 3;
    var spokes = def.spokes || 8;
    var blades = def.blades || 0;
    var fs = def.foreshorten || 0.35;

    // Outer ring — bold
    var outerEl = mkE(layer, cx, cy, outerR, outerR * fs, 0, 360, COL.NEON, 2.5, false);
    items[items.length] = outerEl;

    // Concentric rings
    for (var ri = 1; ri < rings; ri++) {
        var rr = lerp(innerR, outerR, ri / rings);
        var ringEl = mkE(layer, cx, cy, rr, rr * fs, 0, 360, COL.SALMON, 0.75, false);
        items[items.length] = ringEl;
    }

    // Inner ring
    var innerEl = mkE(layer, cx, cy, innerR, innerR * fs, 0, 360, COL.SALMON, 1.0, false);
    items[items.length] = innerEl;

    // Hub circle (filled)
    var hubR = innerR * 0.35;
    var hub = mkCirc(layer, cx, cy, hubR, COL.SALMON, 1.0, true);
    items[items.length] = hub;

    // Spokes — radial lines from hub to outer ring
    for (var si = 0; si < spokes; si++) {
        var ang = (360 / spokes) * si;
        var sInner = ePt(cx, cy, hubR, hubR * fs, ang);
        var sOuter = ePt(cx, cy, outerR * 0.95, outerR * 0.95 * fs, ang);
        var spoke = mkL(layer, sInner[0], sInner[1], sOuter[0], sOuter[1], COL.WARM, 0.6, false);
        items[items.length] = spoke;
    }

    // Turbine blades between rings
    if (blades > 0) {
        var bladeInnerR = innerR * 1.2;
        var bladeOuterR = outerR * 0.85;
        for (var bi = 0; bi < blades; bi++) {
            var bAng = (360 / blades) * bi;
            var bladePts = [];
            var bladeSteps = 8;
            for (var bs = 0; bs <= bladeSteps; bs++) {
                var t = bs / bladeSteps;
                var curR = lerp(bladeInnerR, bladeOuterR, t);
                var curAng = bAng + t * 25; // twist
                var bp = ePt(cx, cy, curR, curR * fs, curAng);
                bladePts[bladePts.length] = bp;
            }
            var blade = mkPoly(layer, bladePts, false, COL.WARM, 0.5, false);
            items[items.length] = blade;
        }
    }

    // Cross-hatching between first and second ring
    var hatchInnerR = innerR * 1.05;
    var hatchOuterR = lerp(innerR, outerR, 1.0 / rings) * 0.95;
    var hatchCount = 16;
    for (var hi = 0; hi < hatchCount; hi++) {
        var hAng1 = (360 / hatchCount) * hi;
        var hAng2 = hAng1 + (360 / hatchCount) * 0.5;
        var hp1 = ePt(cx, cy, hatchInnerR, hatchInnerR * fs, hAng1);
        var hp2 = ePt(cx, cy, hatchOuterR, hatchOuterR * fs, hAng2);
        var hLine = mkL(layer, hp1[0], hp1[1], hp2[0], hp2[1], COL.DARK, 0.25, false);
        items[items.length] = hLine;
    }

    return mkGroup(layer, def.name || "crossSection", items);
}

// ─────────────────────────────────────────────────────────────
// COMPONENT: makeBoltCircle
// ─────────────────────────────────────────────────────────────
function makeBoltCircle(layer, def, rng) {
    var items = [];
    var cx = def.cx;
    var cy = def.cy;
    var r  = def.radius;
    var n  = def.count || 6;
    var br = def.boltRadius || 2;
    var fs = def.foreshorten || 0.35;

    for (var i = 0; i < n; i++) {
        var ang = (360 / n) * i;
        var pt = ePt(cx, cy, r, r * fs, ang);
        var bolt = mkCirc(layer, pt[0], pt[1], br, COL.WARM, 0.5, true);
        items[items.length] = bolt;
    }

    return mkGroup(layer, def.name || "boltCircle", items);
}

// ─────────────────────────────────────────────────────────────
// COMPONENT: makeDataPanel
// ─────────────────────────────────────────────────────────────
function makeDataPanel(layer, def, rng) {
    var items = [];
    var x = def.x;
    var y = def.y;
    var w = def.w;
    var h = def.h;
    var scanCount = def.scanLines || 12;

    // Outer border
    var outer = mkRect(layer, x, y, w, h, COL.SALMON, 1.0, false);
    items[items.length] = outer;

    // Inner margin
    var margin = 4;
    var inner = mkRect(layer, x + margin, y - margin, w - margin * 2, h - margin * 2, COL.WARM, 0.5, false);
    items[items.length] = inner;

    // Scan lines
    var innerTop = y - margin;
    var innerBot = y - h + margin;
    var innerLeft = x + margin;
    var innerRight = x + w - margin;
    for (var si = 0; si < scanCount; si++) {
        var sy = lerp(innerTop, innerBot, (si + 1) / (scanCount + 1));
        var scanLine = mkL(layer, innerLeft + 2, sy, innerRight - 2, sy, COL.DARK, 0.2, false);
        items[items.length] = scanLine;
    }

    // Corner tick marks
    var tickLen = 5;
    // Top-left
    items[items.length] = mkL(layer, x, y, x + tickLen, y, COL.NEON, 0.75, false);
    items[items.length] = mkL(layer, x, y, x, y - tickLen, COL.NEON, 0.75, false);
    // Top-right
    items[items.length] = mkL(layer, x + w, y, x + w - tickLen, y, COL.NEON, 0.75, false);
    items[items.length] = mkL(layer, x + w, y, x + w, y - tickLen, COL.NEON, 0.75, false);
    // Bottom-left
    items[items.length] = mkL(layer, x, y - h, x + tickLen, y - h, COL.NEON, 0.75, false);
    items[items.length] = mkL(layer, x, y - h, x, y - h + tickLen, COL.NEON, 0.75, false);
    // Bottom-right
    items[items.length] = mkL(layer, x + w, y - h, x + w - tickLen, y - h, COL.NEON, 0.75, false);
    items[items.length] = mkL(layer, x + w, y - h, x + w, y - h + tickLen, COL.NEON, 0.75, false);

    // Optional gauge
    if (def.hasGauge) {
        var gaugeCx = x + w * 0.7;
        var gaugeCy = y - h * 0.65;
        var gaugeR = Math.min(w, h) * 0.15;
        var gaugeCircle = mkCirc(layer, gaugeCx, gaugeCy, gaugeR, COL.SALMON, 0.75, false);
        items[items.length] = gaugeCircle;
        // Needle
        var needleAng = rng.range(200, 340);
        var needleTip = ePt(gaugeCx, gaugeCy, gaugeR * 0.8, gaugeR * 0.8, needleAng);
        var needle = mkL(layer, gaugeCx, gaugeCy, needleTip[0], needleTip[1], COL.NEON, 0.6, false);
        items[items.length] = needle;
        // Hub dot
        var hubDot = mkCirc(layer, gaugeCx, gaugeCy, 1.5, COL.NEON, 0.5, true);
        items[items.length] = hubDot;
    }

    return mkGroup(layer, def.name || "dataPanel", items);
}

// ─────────────────────────────────────────────────────────────
// COMPONENT: makeAntennaArray
// ─────────────────────────────────────────────────────────────
function makeAntennaArray(layer, def, rng) {
    var items = [];
    var bx = def.baseX;
    var by = def.baseY;
    var masts = def.masts;
    var spacing = 18;

    // Base mounting bracket
    var baseW = masts.length * spacing + 10;
    var bracketL = mkL(layer, bx - 5, by, bx + baseW - 5, by, COL.WARM, 1.0, false);
    items[items.length] = bracketL;
    var bracketL2 = mkL(layer, bx - 5, by - 3, bx + baseW - 5, by - 3, COL.WARM, 0.5, false);
    items[items.length] = bracketL2;

    for (var mi = 0; mi < masts.length; mi++) {
        var mx = bx + mi * spacing;
        var mh = masts[mi].height;
        var hasCross = masts[mi].hasCross;

        // Vertical mast
        var mast = mkL(layer, mx, by, mx, by + mh, COL.SALMON, 1.0, false);
        items[items.length] = mast;

        // Sensor node at tip
        var node = mkCirc(layer, mx, by + mh, 2.5, COL.NEON, 0.75, true);
        items[items.length] = node;

        // Cross piece
        if (hasCross) {
            var crossY = by + mh * 0.65;
            var crossW = spacing * 0.4;
            var crossH = mkL(layer, mx - crossW, crossY, mx + crossW, crossY, COL.WARM, 0.6, false);
            items[items.length] = crossH;
            // Small nodes at cross ends
            items[items.length] = mkCirc(layer, mx - crossW, crossY, 1.5, COL.WARM, 0.4, true);
            items[items.length] = mkCirc(layer, mx + crossW, crossY, 1.5, COL.WARM, 0.4, true);
        }

        // Cross-bracing to next mast
        if (mi < masts.length - 1) {
            var nx = bx + (mi + 1) * spacing;
            var nh = masts[mi + 1].height;
            var braceBot = by + Math.min(mh, nh) * 0.2;
            var braceTop = by + Math.min(mh, nh) * 0.55;
            // X brace
            var xb1 = mkL(layer, mx, braceBot, nx, braceTop, COL.DARK, 0.3, false);
            var xb2 = mkL(layer, mx, braceTop, nx, braceBot, COL.DARK, 0.3, false);
            items[items.length] = xb1;
            items[items.length] = xb2;
        }
    }

    return mkGroup(layer, def.name || "antennaArray", items);
}

// ─────────────────────────────────────────────────────────────
// COMPONENT: makeHatching
// ─────────────────────────────────────────────────────────────
function makeHatching(layer, def, rng) {
    var items = [];
    var pts = def.points;
    var ang = (def.angle || 45) * DEG2RAD;
    var sp  = def.spacing || 4;
    var sc  = def.strokeColor || COL.DARK;
    var sw  = def.strokeWidth || 0.25;

    // Compute bounding box of polygon
    var minX = pts[0][0], maxX = pts[0][0];
    var minY = pts[0][1], maxY = pts[0][1];
    for (var i = 1; i < pts.length; i++) {
        if (pts[i][0] < minX) minX = pts[i][0];
        if (pts[i][0] > maxX) maxX = pts[i][0];
        if (pts[i][1] < minY) minY = pts[i][1];
        if (pts[i][1] > maxY) maxY = pts[i][1];
    }

    // Extend bounding box diagonal for hatch coverage
    var diag = Math.sqrt((maxX - minX) * (maxX - minX) + (maxY - minY) * (maxY - minY));
    var cx = (minX + maxX) / 2;
    var cy = (minY + maxY) / 2;

    // Direction along hatch lines
    var dx = Math.cos(ang);
    var dy = Math.sin(ang);
    // Perpendicular direction for stepping
    var px = -dy;
    var py = dx;

    var halfDiag = diag * 0.75;
    var count = Math.ceil(diag / sp);

    for (var hi = -count; hi <= count; hi++) {
        var offX = cx + px * hi * sp;
        var offY = cy + py * hi * sp;
        var x1 = offX - dx * halfDiag;
        var y1 = offY - dy * halfDiag;
        var x2 = offX + dx * halfDiag;
        var y2 = offY + dy * halfDiag;
        var hLine = mkL(layer, x1, y1, x2, y2, sc, sw, false);
        items[items.length] = hLine;
    }

    return mkGroup(layer, def.name || "hatching", items);
}

// ─────────────────────────────────────────────────────────────
// COMPONENT: makeDimensionLine
// ─────────────────────────────────────────────────────────────
function makeDimensionLine(layer, def, rng) {
    var items = [];
    var sp = def.startPt;
    var ep = def.endPt;
    var off = def.offset || 20;

    // Direction from start to end
    var adx = ep[0] - sp[0];
    var ady = ep[1] - sp[1];
    var alen = Math.sqrt(adx * adx + ady * ady);
    if (alen < 0.01) alen = 1;

    // Perpendicular offset direction
    var nx = -ady / alen;
    var ny = adx / alen;

    // Offset points for dimension line
    var dsp = [sp[0] + nx * off, sp[1] + ny * off];
    var dep = [ep[0] + nx * off, ep[1] + ny * off];

    // Extension lines from original points to dimension line
    var ext1 = mkL(layer, sp[0], sp[1], dsp[0] + nx * 4, dsp[1] + ny * 4, COL.DARK, 0.2, false);
    var ext2 = mkL(layer, ep[0], ep[1], dep[0] + nx * 4, dep[1] + ny * 4, COL.DARK, 0.2, false);
    items[items.length] = ext1;
    items[items.length] = ext2;

    // Dimension line itself
    var dimLine = mkL(layer, dsp[0], dsp[1], dep[0], dep[1], COL.DARK, 0.2, false);
    items[items.length] = dimLine;

    // Tick marks at each end (perpendicular to dimension line)
    var tickLen = 4;
    // Ticks are perpendicular to the dimension line direction
    var tdx = adx / alen;
    var tdy = ady / alen;
    // Start tick (angled slash)
    var t1 = mkL(layer,
        dsp[0] - nx * tickLen * 0.5 - tdx * tickLen * 0.5,
        dsp[1] - ny * tickLen * 0.5 - tdy * tickLen * 0.5,
        dsp[0] + nx * tickLen * 0.5 + tdx * tickLen * 0.5,
        dsp[1] + ny * tickLen * 0.5 + tdy * tickLen * 0.5,
        COL.DARK, 0.3, false
    );
    // End tick
    var t2 = mkL(layer,
        dep[0] - nx * tickLen * 0.5 - tdx * tickLen * 0.5,
        dep[1] - ny * tickLen * 0.5 - tdy * tickLen * 0.5,
        dep[0] + nx * tickLen * 0.5 + tdx * tickLen * 0.5,
        dep[1] + ny * tickLen * 0.5 + tdy * tickLen * 0.5,
        COL.DARK, 0.3, false
    );
    items[items.length] = t1;
    items[items.length] = t2;

    return mkGroup(layer, def.name || "dimensionLine", items);
}

// ─────────────────────────────────────────────────────────────
// Construction grid (isometric)
// ─────────────────────────────────────────────────────────────
function makeConstructionGrid(layer, abX, abY, abW, abH, spacing) {
    var items = [];
    // Horizontal reference lines
    for (var gy = abY; gy >= abY - abH; gy -= spacing) {
        items[items.length] = mkL(layer, abX, gy, abX + abW, gy, COL.DARK, 0.15, false);
    }
    // 30-degree rising lines
    var diag = abW + abH;
    var angR = 30 * DEG2RAD;
    var stepX = spacing / Math.cos(angR);
    for (var gx = abX - diag; gx < abX + abW + diag; gx += stepX) {
        var ly1 = abY - abH;
        var ly2 = abY;
        var lx1 = gx;
        var lx2 = gx + (ly2 - ly1) * Math.cos(angR) / Math.sin(angR);
        items[items.length] = mkL(layer, lx1, ly1, lx2, ly2, COL.DARK, 0.15, false);
    }
    // 150-degree lines (mirror)
    var angR2 = 150 * DEG2RAD;
    for (var gx2 = abX - diag; gx2 < abX + abW + diag; gx2 += stepX) {
        var ly3 = abY - abH;
        var ly4 = abY;
        var lx3 = gx2;
        var lx4 = gx2 + (ly4 - ly3) * Math.cos(angR2) / Math.sin(angR2);
        items[items.length] = mkL(layer, lx3, ly3, lx4, ly4, COL.DARK, 0.15, false);
    }
    return mkGroup(layer, "grid_construction", items);
}

// ═════════════════════════════════════════════════════════════
// ORTHOGRAPHIC PROJECTION RENDERERS
// Standard engineering drawing layout:
//   Top view above front view (aligned X)
//   Side view right of front view (aligned Y)
//   Projection lines connecting corresponding features
// ═════════════════════════════════════════════════════════════

// Front elevation: longitudinal cross-section (X = along axis, Y = up)
function drawOrthoFront(layer, machine, ox, oy, scale, projLayer) {
    var items = [];
    var projItems = [];
    var cyls = machine.cylinders;
    // Use primary cylinder for all views
    var mainCyl = cyls[0];
    var secs = mainCyl.sections;
    var totalLen = mainCyl.halfLength * 2 * scale;
    var startX = ox - totalLen / 2;

    // Draw each section as tapered rectangle profile
    for (var si = 0; si < secs.length; si++) {
        var sec = secs[si];
        var x1 = startX + sec.tStart * totalLen;
        var x2 = startX + sec.tEnd * totalLen;
        var rT = sec.radiusTop * scale;
        var rB = sec.radiusBottom * scale;

        // Top silhouette
        items[items.length] = mkL(layer, x1, oy + rT, x2, oy + rB, COL.NEON, 2.0, false);
        // Bottom silhouette
        items[items.length] = mkL(layer, x1, oy - rT, x2, oy - rB, COL.NEON, 2.0, false);
        // Section boundary
        items[items.length] = mkL(layer, x1, oy - rT, x1, oy + rT, COL.SALMON, 1.25, false);

        // Internal structure: wall thickness
        var wall = rT * 0.12;
        items[items.length] = mkL(layer, x1, oy + rT - wall, x2, oy + rB - wall, COL.WARM, 0.5, false);
        items[items.length] = mkL(layer, x1, oy - rT + wall, x2, oy - rB + wall, COL.WARM, 0.5, false);

        // Hidden center bore (dashed)
        var boreR = rT * 0.3;
        var boreR2 = rB * 0.3;
        items[items.length] = mkL(layer, x1, oy + boreR, x2, oy + boreR2, COL.DEEP, 0.3, true);
        items[items.length] = mkL(layer, x1, oy - boreR, x2, oy - boreR2, COL.DEEP, 0.3, true);

        // Cross-hatching on cut face (first section)
        if (si === 0) {
            var hatchSpacing = 5;
            for (var hy = oy - rT + wall; hy < oy + rT - wall; hy += hatchSpacing) {
                items[items.length] = mkL(layer, x1 - 2, hy, x1 + 8, hy + 4, COL.DARK, 0.2, false);
            }
        }
    }

    // End cap
    var last = secs[secs.length - 1];
    var endX = startX + last.tEnd * totalLen;
    var endR = last.radiusBottom * scale;
    items[items.length] = mkL(layer, endX, oy - endR, endX, oy + endR, COL.SALMON, 1.25, false);

    // Center line (full length, extends past ends)
    var clExt = totalLen * 0.08;
    items[items.length] = mkL(layer, startX - clExt, oy, endX + clExt, oy, COL.DEEP, 0.4, false);
    items[items.length - 1].strokeDashes = [18, 4, 2, 4];

    // Housings attached to main cylinder
    var housings = machine.housings;
    for (var hi = 0; hi < housings.length; hi++) {
        var hd = housings[hi];
        if (hd.attachCyl !== 0) continue;
        var hx = startX + (hd.attachT || 0.5) * totalLen;
        var attachR = secs[0].radiusTop * scale;
        var hSide = (hd.attachY || 0) > 0 ? 1 : -1;
        var hw = hd.w * scale;
        var hh = hd.h * scale;
        var hy2 = oy + hSide * attachR;
        items[items.length] = mkRect(layer, hx - hw / 2, hy2 + (hSide > 0 ? hh : 0), hw, hh, COL.SALMON, 1.0, false);
        // Hidden internal line
        items[items.length] = mkL(layer, hx - hw / 2 + 3, hy2 + hSide * hh * 0.5,
            hx + hw / 2 - 3, hy2 + hSide * hh * 0.5, COL.DEEP, 0.3, true);
    }

    // Secondary cylinders as hidden outlines
    for (var ci = 1; ci < cyls.length; ci++) {
        var sc = cyls[ci];
        var scLen = sc.halfLength * 2 * scale;
        var scStart = ox - scLen / 2;
        var scMaxR = sc.sections[0].radiusTop * scale;
        // Dashed outline
        items[items.length] = mkL(layer, scStart, oy + scMaxR * 0.7, scStart + scLen, oy + scMaxR * 0.7, COL.DEEP, 0.35, true);
        items[items.length] = mkL(layer, scStart, oy - scMaxR * 0.7, scStart + scLen, oy - scMaxR * 0.7, COL.DEEP, 0.35, true);
    }

    // Dimension: overall length
    var dimOff = endR + 25;
    items[items.length] = mkL(layer, startX, oy - dimOff, endX, oy - dimOff, COL.DARK, 0.2, false);
    items[items.length] = mkL(layer, startX, oy - endR - 5, startX, oy - dimOff - 5, COL.DARK, 0.2, false);
    items[items.length] = mkL(layer, endX, oy - endR - 5, endX, oy - dimOff - 5, COL.DARK, 0.2, false);
    // Tick marks
    items[items.length] = mkL(layer, startX - 3, oy - dimOff - 3, startX + 3, oy - dimOff + 3, COL.DARK, 0.3, false);
    items[items.length] = mkL(layer, endX - 3, oy - dimOff - 3, endX + 3, oy - dimOff + 3, COL.DARK, 0.3, false);

    return mkGroup(layer, "ortho_front", items);
}

// End view (side elevation): looking down the cylinder axis
function drawOrthoSide(layer, machine, ox, oy, scale, projLayer, frontOY) {
    var items = [];
    var mainCyl = machine.cylinders[0];
    var secs = mainCyl.sections;

    // End face: concentric circles for each section radius
    // Use the front-most (smallest) section
    var maxSec = secs[0];
    var maxR = maxSec.radiusTop * scale;
    // Outer silhouette
    items[items.length] = mkCirc(layer, ox, oy, maxR, COL.NEON, 2.0, false);

    // Section rings
    for (var si = 0; si < secs.length; si++) {
        var sec = secs[si];
        var rAvg = ((sec.radiusTop + sec.radiusBottom) / 2) * scale;
        if (Math.abs(rAvg - maxR) > 3) {
            items[items.length] = mkCirc(layer, ox, oy, rAvg, COL.SALMON, 0.75, false);
        }
    }

    // Wall thickness circle
    var wall = maxR * 0.12;
    items[items.length] = mkCirc(layer, ox, oy, maxR - wall, COL.WARM, 0.5, false);

    // Center bore
    var boreR = maxR * 0.3;
    items[items.length] = mkCirc(layer, ox, oy, boreR, COL.SALMON, 1.0, false);
    items[items.length] = mkCirc(layer, ox, oy, boreR * 0.4, COL.WARM, 0.5, true);

    // Spokes / internal structure
    var spokeCount = 6;
    for (var sp = 0; sp < spokeCount; sp++) {
        var spAng = (360 / spokeCount) * sp;
        var spIn = ePt(ox, oy, boreR, boreR, spAng);
        var spOut = ePt(ox, oy, maxR - wall, maxR - wall, spAng);
        items[items.length] = mkL(layer, spIn[0], spIn[1], spOut[0], spOut[1], COL.WARM, 0.4, false);
    }

    // Cross-hair center lines
    var clExt = maxR * 1.25;
    items[items.length] = mkL(layer, ox - clExt, oy, ox + clExt, oy, COL.DEEP, 0.4, false);
    items[items.length - 1].strokeDashes = [18, 4, 2, 4];
    items[items.length] = mkL(layer, ox, oy - clExt, ox, oy + clExt, COL.DEEP, 0.4, false);
    items[items.length - 1].strokeDashes = [18, 4, 2, 4];

    // Cross-hatching in cut section (upper-right quadrant)
    var hatchSpacing = 5;
    for (var hx = 2; hx < maxR - wall; hx += hatchSpacing) {
        var hLen = Math.sqrt(Math.max(0, (maxR - wall) * (maxR - wall) - hx * hx));
        if (hLen > 3) {
            items[items.length] = mkL(layer, ox + hx, oy + 2, ox + hx + 3, oy + hLen * 0.8, COL.DARK, 0.2, false);
        }
    }

    // Housing projections (circles/squares for housing cross-sections)
    var housings = machine.housings;
    for (var hi = 0; hi < housings.length; hi++) {
        var hd = housings[hi];
        if (hd.attachCyl !== 0) continue;
        var hSide = (hd.attachY || 0) > 0 ? 1 : -1;
        var hOff = maxR + hd.h * scale * 0.5;
        items[items.length] = mkRect(layer, ox - hd.w * scale * 0.3, oy + hSide * hOff,
            hd.w * scale * 0.6, hd.d * scale * 0.6, COL.SALMON, 0.75, false);
    }

    // Projection lines connecting to front view (horizontal)
    if (projLayer && frontOY) {
        // Top and bottom extent lines from front → side
        var projStartX = ox - maxR * 1.4;
        mkL(projLayer, projStartX - 200, frontOY + maxR, projStartX, oy + maxR, COL.DARK, 0.15, false);
        mkL(projLayer, projStartX - 200, frontOY - maxR, projStartX, oy - maxR, COL.DARK, 0.15, false);
        mkL(projLayer, projStartX - 200, frontOY, projStartX, oy, COL.DARK, 0.15, false);
    }

    return mkGroup(layer, "ortho_side", items);
}

// Plan view (top): looking straight down
function drawOrthoTop(layer, machine, ox, oy, scale, projLayer, frontOX, frontStartX) {
    var items = [];
    var mainCyl = machine.cylinders[0];
    var secs = mainCyl.sections;
    var totalLen = mainCyl.halfLength * 2 * scale;
    var startX = ox - totalLen / 2;

    // Main cylinder plan view: rectangle with rounded ends
    var maxR = secs[0].radiusTop * scale;
    for (var si = 0; si < secs.length; si++) {
        var sec = secs[si];
        var x1 = startX + sec.tStart * totalLen;
        var x2 = startX + sec.tEnd * totalLen;
        var rT = sec.radiusTop * scale;
        var rB = sec.radiusBottom * scale;
        // Plan rectangle
        var pts = [
            [x1, oy + rT], [x2, oy + rB],
            [x2, oy - rB], [x1, oy - rT]
        ];
        items[items.length] = mkPoly(layer, pts, true, COL.NEON, 1.5, false);

        // Wall thickness
        var wT = rT * 0.12;
        var wB = rB * 0.12;
        var ipts = [
            [x1, oy + rT - wT], [x2, oy + rB - wB],
            [x2, oy - rB + wB], [x1, oy - rT + wT]
        ];
        items[items.length] = mkPoly(layer, ipts, true, COL.WARM, 0.5, false);

        // Center bore in plan
        var bT = rT * 0.3;
        var bB = rB * 0.3;
        items[items.length] = mkL(layer, x1, oy + bT, x2, oy + bB, COL.DEEP, 0.3, true);
        items[items.length] = mkL(layer, x1, oy - bT, x2, oy - bB, COL.DEEP, 0.3, true);
    }

    // Center line
    var clExt = totalLen * 0.08;
    items[items.length] = mkL(layer, startX - clExt, oy, startX + totalLen + clExt, oy, COL.DEEP, 0.4, false);
    items[items.length - 1].strokeDashes = [18, 4, 2, 4];

    // Secondary cylinders in plan
    for (var ci = 1; ci < machine.cylinders.length; ci++) {
        var sc = machine.cylinders[ci];
        var scLen = sc.halfLength * 2 * scale;
        var scR = sc.sections[0].radiusTop * scale;
        var scStart = ox - scLen / 2;
        var scPts = [
            [scStart, oy + scR * 0.6], [scStart + scLen, oy + scR * 0.6],
            [scStart + scLen, oy - scR * 0.6], [scStart, oy - scR * 0.6]
        ];
        items[items.length] = mkPoly(layer, scPts, true, COL.SALMON, 0.75, false);
    }

    // Housings in plan
    var housings = machine.housings;
    for (var hi = 0; hi < housings.length; hi++) {
        var hd = housings[hi];
        if (hd.attachCyl !== 0) continue;
        var hx = startX + (hd.attachT || 0.5) * totalLen;
        var hw = hd.w * scale;
        var hd2 = hd.d * scale;
        var hSide = (hd.attachY || 0) > 0 ? 1 : -1;
        var hBase = maxR;
        items[items.length] = mkRect(layer, hx - hw / 2, oy + hSide * (hBase + hd2), hw, hd2, COL.SALMON, 0.75, false);
    }

    // Projection lines from front view (vertical alignment)
    if (projLayer && frontStartX) {
        // Vertical projection lines at section boundaries
        for (var pi = 0; pi < secs.length; pi++) {
            var px = startX + secs[pi].tStart * totalLen;
            mkL(projLayer, px, oy + maxR * 1.5, px, oy + maxR * 3, COL.DARK, 0.15, false);
        }
        // End boundary
        var pxEnd = startX + totalLen;
        mkL(projLayer, pxEnd, oy + maxR * 1.5, pxEnd, oy + maxR * 3, COL.DARK, 0.15, false);
    }

    return mkGroup(layer, "ortho_top", items);
}
