// void_engine_lib.jsx — Core 2D Drawing Engine for VOID procedural illustration
// Style-agnostic primitives: PRNG, math, color, drawing, layer management
// ExtendScript (ES3) — no modern JS features
// Concatenated FIRST in chunk pipeline: lib → style → compose → chunk

var DEG2RAD = Math.PI / 180;

// ═══════════════════════════════════════════════════════════════
// PRNG — Seeded pseudo-random number generator (xorshift32)
// Same seed always produces same sequence — enables reproducible machines
// ═══════════════════════════════════════════════════════════════
function PRNG(seed) {
    var s = seed | 0;
    if (s === 0) s = 1;
    var self = {};
    self.next = function () {
        s ^= s << 13; s ^= s >> 17; s ^= s << 5;
        return ((s < 0 ? s + 4294967296 : s) % 4294967296) / 4294967296;
    };
    self.range = function (a, b) { return a + self.next() * (b - a); };
    self.randInt = function (a, b) { return Math.floor(self.range(a, b + 1)); };
    self.pick = function (arr) { return arr[Math.floor(self.next() * arr.length)]; };
    self.chance = function (p) { return self.next() < p; };
    self.gaussian = function (m, sd) {
        var u = self.next() || 1e-10; var v = self.next();
        return m + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    };
    self.shuffle = function (arr) {
        var a = arr.slice();
        for (var i = a.length - 1; i > 0; i--) {
            var j = Math.floor(self.next() * (i + 1));
            var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
        }
        return a;
    };
    return self;
}

// ═══════════════════════════════════════════════════════════════
// MATH UTILITIES
// ═══════════════════════════════════════════════════════════════
function lerp(a, b, t) { return a + (b - a) * t; }
function clamp(v, mn, mx) { return v < mn ? mn : (v > mx ? mx : v); }

// Point on axis-aligned ellipse at parametric angle (degrees)
function ePt(cx, cy, a, b, deg) {
    var r = deg * DEG2RAD;
    return [cx + a * Math.cos(r), cy + b * Math.sin(r)];
}

// Point on ROTATED ellipse — samples ellipse then rotates by rotDeg
// This is the core function for drawing isometric ellipses perpendicular to any axis
function eRPt(cx, cy, a, b, deg, rotDeg) {
    var r = deg * DEG2RAD;
    var rr = rotDeg * DEG2RAD;
    var px = a * Math.cos(r);
    var py = b * Math.sin(r);
    return [cx + px * Math.cos(rr) - py * Math.sin(rr),
            cy + px * Math.sin(rr) + py * Math.cos(rr)];
}

// Interpolate between two 2D points
function axPt(p0, p1, t) {
    return [lerp(p0[0], p1[0], t), lerp(p0[1], p1[1], t)];
}

// Distance between two 2D points
function dist2D(p0, p1) {
    var dx = p1[0] - p0[0], dy = p1[1] - p0[1];
    return Math.sqrt(dx * dx + dy * dy);
}

// Angle between two 2D points (degrees)
function angle2D(p0, p1) {
    return Math.atan2(p1[1] - p0[1], p1[0] - p0[0]) / DEG2RAD;
}

// ═══════════════════════════════════════════════════════════════
// COLOR
// ═══════════════════════════════════════════════════════════════
function rgb(r, g, b) {
    var c = new RGBColor();
    c.red = r; c.green = g; c.blue = b;
    return c;
}

// Parse hex string (#FF0000 or FF0000) to RGBColor
function hexRgb(hex) {
    if (hex.charAt(0) === "#") hex = hex.substring(1);
    var r = parseInt(hex.substring(0, 2), 16);
    var g = parseInt(hex.substring(2, 4), 16);
    var b = parseInt(hex.substring(4, 6), 16);
    return rgb(r, g, b);
}

// ═══════════════════════════════════════════════════════════════
// LAYER HELPERS
// ═══════════════════════════════════════════════════════════════

// Find or create a sub-layer by name
function getOrCreateLayer(parent, name) {
    for (var i = 0; i < parent.layers.length; i++) {
        if (parent.layers[i].name === name) return parent.layers[i];
    }
    var ly = parent.layers.add();
    ly.name = name;
    return ly;
}

// Find existing layer by name — returns null if not found (never creates)
function findLayer(parent, name) {
    for (var i = 0; i < parent.layers.length; i++) {
        if (parent.layers[i].name === name) return parent.layers[i];
    }
    return null;
}

// Find artboard by name prefix — returns {index, rect, name} or null
function findArtboard(doc, prefix) {
    for (var i = 0; i < doc.artboards.length; i++) {
        if (doc.artboards[i].name.indexOf(prefix) === 0) {
            return {
                index: i,
                rect: doc.artboards[i].artboardRect,
                name: doc.artboards[i].name
            };
        }
    }
    return null;
}

// ═══════════════════════════════════════════════════════════════
// STROKE / FILL HELPERS
// ═══════════════════════════════════════════════════════════════

// Apply stroke to a path item
// dashType: 0=solid, 1=short dash [4,3], 2=dash-dot [18,4,2,4]
function _applyStroke(p, col, sw, dashType) {
    p.stroked = true;
    p.filled = false;
    p.strokeColor = col;
    p.strokeWidth = sw;
    if (dashType === 1) p.strokeDashes = [4, 3];
    if (dashType === 2) p.strokeDashes = [18, 4, 2, 4];
    return p;
}

// ═══════════════════════════════════════════════════════════════
// DRAWING PRIMITIVES
// All functions take: layer, geometry params, color, strokeWidth, dashed
// ═══════════════════════════════════════════════════════════════

// Line between two points
function mkL(layer, x1, y1, x2, y2, col, sw, dashed) {
    var p = layer.pathItems.add();
    p.setEntirePath([[x1, y1], [x2, y2]]);
    p.closed = false;
    return _applyStroke(p, col, sw, dashed ? 1 : 0);
}

// Line with specific dash type (0=solid, 1=dash, 2=dash-dot)
function mkLD(layer, x1, y1, x2, y2, col, sw, dashType) {
    var p = layer.pathItems.add();
    p.setEntirePath([[x1, y1], [x2, y2]]);
    p.closed = false;
    return _applyStroke(p, col, sw, dashType);
}

// Axis-aligned ellipse (full) or arc (partial)
function mkE(layer, cx, cy, a, b, startAng, endAng, col, sw, dashed) {
    var p;
    if (startAng === 0 && endAng === 360) {
        // Full ellipse — use built-in for best quality
        p = layer.pathItems.ellipse(cy + b, cx - a, a * 2, b * 2);
    } else {
        // Arc — sample points parametrically
        var sweep = endAng - startAng;
        var steps = Math.max(12, Math.round(Math.abs(sweep) / 5));
        var pts = [];
        for (var i = 0; i <= steps; i++) {
            var ang = startAng + (sweep * i / steps);
            pts[pts.length] = ePt(cx, cy, a, b, ang);
        }
        p = layer.pathItems.add();
        p.setEntirePath(pts);
        p.closed = false;
    }
    return _applyStroke(p, col, sw, dashed ? 1 : 0);
}

// Rotated ellipse (or arc) — the CORE isometric drawing function
// Samples points on ellipse(a,b) then rotates entire shape by rotDeg
// Use for cylinder end-caps perpendicular to any axis angle
function mkER(layer, cx, cy, a, b, startAng, endAng, rotDeg, col, sw, dashed) {
    var sweep = endAng - startAng;
    var steps = Math.max(24, Math.round(Math.abs(sweep) / 5));
    var pts = [];
    for (var i = 0; i <= steps; i++) {
        var ang = startAng + (sweep * i / steps);
        pts[pts.length] = eRPt(cx, cy, a, b, ang, rotDeg);
    }
    var p = layer.pathItems.add();
    p.setEntirePath(pts);
    p.closed = (startAng === 0 && endAng === 360);
    return _applyStroke(p, col, sw, dashed ? 1 : 0);
}

// Circle (optionally filled)
function mkCirc(layer, cx, cy, r, col, sw, filled) {
    var p = layer.pathItems.ellipse(cy + r, cx - r, r * 2, r * 2);
    p.stroked = true;
    p.strokeColor = col;
    p.strokeWidth = sw;
    p.filled = !!filled;
    if (filled) p.fillColor = col;
    return p;
}

// Polyline (open) or polygon (closed) from point array
function mkPoly(layer, pts, closed, col, sw, dashed) {
    var p = layer.pathItems.add();
    p.setEntirePath(pts);
    p.closed = !!closed;
    return _applyStroke(p, col, sw, dashed ? 1 : 0);
}

// Rectangle — x,y is top-left in Illustrator Y-up coordinates
function mkRect(layer, x, y, w, h, col, sw, dashed) {
    var p = layer.pathItems.rectangle(y, x, w, h);
    return _applyStroke(p, col, sw, dashed ? 1 : 0);
}

// Filled rectangle (no stroke) — for backgrounds and solid fills
function mkFilledRect(layer, x, y, w, h, col) {
    var p = layer.pathItems.rectangle(y, x, w, h);
    p.stroked = false;
    p.filled = true;
    p.fillColor = col;
    return p;
}

// Group items under a named group — preserves stacking order
function mkGroup(layer, name, items) {
    var g = layer.groupItems.add();
    g.name = name;
    for (var i = items.length - 1; i >= 0; i--) {
        if (items[i]) items[i].move(g, ElementPlacement.PLACEATEND);
    }
    return g;
}

// Text frame — uses default font (no textFonts.getByName)
// position is [x, y] in Illustrator coordinates (Y-up)
function mkText(layer, x, y, text, size, col) {
    var tf = layer.textFrames.add();
    tf.contents = text;
    tf.position = [x, y];
    var attrs = tf.textRange.characterAttributes;
    attrs.size = size;
    attrs.fillColor = col;
    return tf;
}

// ═══════════════════════════════════════════════════════════════
// GRID DRAWING UTILITY
// Draws parallel lines at a given angle across a rectangular area
// Used for construction grids and hatching
// ═══════════════════════════════════════════════════════════════
function drawGridLines(layer, abX, abY, abW, abH, angle, spacing, col, sw) {
    var items = [];
    var angR = angle * DEG2RAD;
    var dx = Math.cos(angR);
    var dy = Math.sin(angR);
    // Perpendicular direction for stepping between lines
    var px = -dy;
    var py = dx;
    // Diagonal of area — maximum line length needed
    var diag = Math.sqrt(abW * abW + abH * abH);
    var halfDiag = diag * 0.6;
    // Center of area
    var cx = abX + abW / 2;
    var cy = abY - abH / 2;
    // Number of lines to cover the area
    var count = Math.ceil(diag / spacing);

    for (var i = -count; i <= count; i++) {
        var ox = cx + px * i * spacing;
        var oy = cy + py * i * spacing;
        items[items.length] = mkL(layer,
            ox - dx * halfDiag, oy - dy * halfDiag,
            ox + dx * halfDiag, oy + dy * halfDiag,
            col, sw, false);
    }
    return items;
}
