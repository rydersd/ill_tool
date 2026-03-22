// void_v3_lib.jsx — 3D Isometric Engine for Adobe Illustrator
// All geometry defined in 3D, projected through isometric matrix to 2D curves
// ExtendScript (ES3)

var DEG = Math.PI / 180;

// ═══════════════════════════════════════════════════════════════
// PRNG (xorshift32)
// ═══════════════════════════════════════════════════════════════
function PRNG(seed) {
    var s = seed | 0; if (s === 0) s = 1;
    var self = {};
    self.next = function () { s ^= s << 13; s ^= s >> 17; s ^= s << 5; return ((s < 0 ? s + 4294967296 : s) % 4294967296) / 4294967296; };
    self.range = function (a, b) { return a + self.next() * (b - a); };
    self.randInt = function (a, b) { return Math.floor(self.range(a, b + 1)); };
    self.pick = function (arr) { return arr[Math.floor(self.next() * arr.length)]; };
    self.chance = function (p) { return self.next() < p; };
    self.gaussian = function (m, sd) { var u = self.next() || 1e-10; var v = self.next(); return m + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
    return self;
}

// ═══════════════════════════════════════════════════════════════
// 3D ISOMETRIC PROJECTION
// ═══════════════════════════════════════════════════════════════
// Coordinate system: X = right, Y = up, Z = toward viewer
// Isometric: X-axis at 30° below-right, Z-axis at 30° below-left

var ISO_A = 30 * DEG;  // axis angle from horizontal
var ISO_CA = Math.cos(ISO_A);
var ISO_SA = Math.sin(ISO_A);

// View direction (normalized) — for hidden-line computation
// In isometric, viewer looks along (-1, -1, -1) normalized
var VD = { x: -0.577, y: -0.577, z: -0.577 };

function iso(x, y, z) {
    // Project 3D to 2D screen (Y-up for Illustrator)
    return [
        x * ISO_CA - z * ISO_CA,
        y + (x + z) * ISO_SA
    ];
}

// Project with artboard offset
var _abCx = 0, _abCy = 0;
function setABOrigin(cx, cy) { _abCx = cx; _abCy = cy; }
function p3(x, y, z) {
    var s = iso(x, y, z);
    return [_abCx + s[0], _abCy + s[1]];
}

// ═══════════════════════════════════════════════════════════════
// 3D VECTOR MATH
// ═══════════════════════════════════════════════════════════════
function v3len(v) { return Math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]); }
function v3norm(v) { var l = v3len(v); return l > 0 ? [v[0]/l, v[1]/l, v[2]/l] : [0,0,0]; }
function v3dot(a, b) { return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]; }
function v3cross(a, b) { return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]; }
function v3add(a, b) { return [a[0]+b[0], a[1]+b[1], a[2]+b[2]]; }
function v3sub(a, b) { return [a[0]-b[0], a[1]-b[1], a[2]-b[2]]; }
function v3scale(v, s) { return [v[0]*s, v[1]*s, v[2]*s]; }
function v3lerp(a, b, t) { return [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, a[2]+(b[2]-a[2])*t]; }

// Compute perpendicular basis for a plane with given normal
function perpBasis(normal) {
    var n = v3norm(normal);
    // Pick a non-parallel seed vector
    var seed = (Math.abs(n[0]) < 0.9) ? [1,0,0] : [0,1,0];
    // Gram-Schmidt to get u perpendicular to n
    var d = v3dot(seed, n);
    var u = v3norm(v3sub(seed, v3scale(n, d)));
    // v = n × u
    var v = v3cross(n, u);
    return { u: u, v: v };
}

// Sample a 3D circle: center, radius, axis (normal to circle plane)
// Returns array of 3D points [[x,y,z], ...]
function circle3D(cx, cy, cz, radius, ax, ay, az, steps) {
    if (!steps) steps = 32;
    var basis = perpBasis([ax, ay, az]);
    var pts = [];
    for (var i = 0; i <= steps; i++) {
        var ang = (i / steps) * 2 * Math.PI;
        var ca = Math.cos(ang), sa = Math.sin(ang);
        pts[pts.length] = [
            cx + radius * (basis.u[0] * ca + basis.v[0] * sa),
            cy + radius * (basis.u[1] * ca + basis.v[1] * sa),
            cz + radius * (basis.u[2] * ca + basis.v[2] * sa)
        ];
    }
    return pts;
}

// Project 3D points to 2D screen array
function projectPts(pts3d) {
    var pts2d = [];
    for (var i = 0; i < pts3d.length; i++) {
        pts2d[pts2d.length] = p3(pts3d[i][0], pts3d[i][1], pts3d[i][2]);
    }
    return pts2d;
}

// Split circle into front-facing and back-facing halves
// based on view direction projected onto the circle's plane
function splitCircleFB(pts3d, center, axis) {
    var n = v3norm(axis);
    // Project view direction onto circle plane
    var vd = [VD.x, VD.y, VD.z];
    var vdDotN = v3dot(vd, n);
    var vdProj = v3norm(v3sub(vd, v3scale(n, vdDotN)));

    var front = [], back = [];
    for (var i = 0; i < pts3d.length; i++) {
        var disp = v3sub(pts3d[i], center);
        var facing = v3dot(disp, vdProj);
        if (facing < 0) {
            front[front.length] = pts3d[i];
        } else {
            back[back.length] = pts3d[i];
        }
    }
    return { front: front, back: back };
}

// ═══════════════════════════════════════════════════════════════
// COLORS & STYLES
// ═══════════════════════════════════════════════════════════════
function rgb(r, g, b) { var c = new RGBColor(); c.red = r; c.green = g; c.blue = b; return c; }
var COL = {
    NEON: rgb(255, 102, 0), SALMON: rgb(232, 115, 74), WARM: rgb(212, 98, 59),
    DEEP: rgb(184, 80, 48), DARK: rgb(61, 26, 10), BLACK: rgb(15, 15, 15)
};

function _style(p, col, sw, dashType) {
    p.stroked = true; p.filled = false;
    p.strokeColor = col; p.strokeWidth = sw;
    if (dashType === 1) p.strokeDashes = [4, 3];
    if (dashType === 2) p.strokeDashes = [18, 4, 2, 4];
    return p;
}

// ═══════════════════════════════════════════════════════════════
// 2D DRAWING PRIMITIVES
// ═══════════════════════════════════════════════════════════════
function getOrCreateLayer(parent, name) {
    for (var i = 0; i < parent.layers.length; i++) {
        if (parent.layers[i].name === name) return parent.layers[i];
    }
    var ly = parent.layers.add(); ly.name = name; return ly;
}

function mkL(layer, x1, y1, x2, y2, col, sw, dash) {
    var p = layer.pathItems.add(); p.setEntirePath([[x1,y1],[x2,y2]]); p.closed = false;
    return _style(p, col, sw, dash || 0);
}

function mkPoly(layer, pts, closed, col, sw, dash) {
    var p = layer.pathItems.add(); p.setEntirePath(pts); p.closed = !!closed;
    return _style(p, col, sw, dash || 0);
}

function mkCirc(layer, cx, cy, r, col, sw, filled) {
    var p = layer.pathItems.ellipse(cy + r, cx - r, r * 2, r * 2);
    p.stroked = true; p.strokeColor = col; p.strokeWidth = sw;
    p.filled = !!filled; if (filled) p.fillColor = col;
    return p;
}

function mkRect(layer, x, y, w, h, col, sw, dash) {
    var p = layer.pathItems.rectangle(y, x, w, h);
    return _style(p, col, sw, dash || 0);
}

function mkGroup(layer, name, items) {
    var g = layer.groupItems.add(); g.name = name;
    for (var i = items.length - 1; i >= 0; i--) items[i].move(g, ElementPlacement.PLACEATEND);
    return g;
}

// ═══════════════════════════════════════════════════════════════
// 3D → 2D PROJECTED DRAWING
// ═══════════════════════════════════════════════════════════════

// Draw a line between two 3D points
function draw3DLine(layer, p1, p2, col, sw, dash) {
    var s1 = p3(p1[0], p1[1], p1[2]);
    var s2 = p3(p2[0], p2[1], p2[2]);
    return mkL(layer, s1[0], s1[1], s2[0], s2[1], col, sw, dash);
}

// Draw a 3D circle (full) projected to 2D
function draw3DCircle(layer, cx, cy, cz, radius, ax, ay, az, col, sw, dash) {
    var pts3d = circle3D(cx, cy, cz, radius, ax, ay, az, 48);
    var pts2d = projectPts(pts3d);
    return mkPoly(layer, pts2d, true, col, sw, dash);
}

// Draw front-facing half of a 3D circle (visible part of cylinder ring)
function draw3DCircleFront(layer, cx, cy, cz, radius, ax, ay, az, col, sw) {
    var pts3d = circle3D(cx, cy, cz, radius, ax, ay, az, 32);
    var split = splitCircleFB(pts3d, [cx, cy, cz], [ax, ay, az]);
    if (split.front.length < 2) return null;
    return mkPoly(layer, projectPts(split.front), false, col, sw, 0);
}

// Draw back-facing half (hidden, dashed)
function draw3DCircleBack(layer, cx, cy, cz, radius, ax, ay, az, col, sw) {
    var pts3d = circle3D(cx, cy, cz, radius, ax, ay, az, 32);
    var split = splitCircleFB(pts3d, [cx, cy, cz], [ax, ay, az]);
    if (split.back.length < 2) return null;
    return mkPoly(layer, projectPts(split.back), false, col, sw, 1);
}

// Draw a complete cylinder between two 3D points
// Returns items array
function draw3DCylinder(layer, startPt, endPt, radius, rng) {
    var items = [];
    var axis = v3sub(endPt, startPt);
    var axDir = v3norm(axis);
    var axLen = v3len(axis);
    var basis = perpBasis(axDir);

    // Front/back end ellipses
    items[items.length] = draw3DCircleBack(layer, startPt[0], startPt[1], startPt[2], radius, axDir[0], axDir[1], axDir[2], COL.DEEP, 0.35);
    items[items.length] = draw3DCircleFront(layer, startPt[0], startPt[1], startPt[2], radius, axDir[0], axDir[1], axDir[2], COL.SALMON, 1.25);
    items[items.length] = draw3DCircle(layer, endPt[0], endPt[1], endPt[2], radius, axDir[0], axDir[1], axDir[2], COL.NEON, 2.0, 0);

    // Silhouette lines (tangent lines along cylinder surface)
    // Two lines at ±90° from view-facing direction on the circle
    var pts3dStart = circle3D(startPt[0], startPt[1], startPt[2], radius, axDir[0], axDir[1], axDir[2], 32);
    var pts3dEnd = circle3D(endPt[0], endPt[1], endPt[2], radius, axDir[0], axDir[1], axDir[2], 32);

    // Find the two silhouette points (where surface turns from front to back)
    var silIdx = findSilhouetteIndices(pts3dStart, [startPt[0], startPt[1], startPt[2]], axDir);
    if (silIdx[0] >= 0 && silIdx[1] >= 0) {
        var s1s = p3(pts3dStart[silIdx[0]][0], pts3dStart[silIdx[0]][1], pts3dStart[silIdx[0]][2]);
        var s1e = p3(pts3dEnd[silIdx[0]][0], pts3dEnd[silIdx[0]][1], pts3dEnd[silIdx[0]][2]);
        items[items.length] = mkL(layer, s1s[0], s1s[1], s1e[0], s1e[1], COL.NEON, 2.5, 0);

        var s2s = p3(pts3dStart[silIdx[1]][0], pts3dStart[silIdx[1]][1], pts3dStart[silIdx[1]][2]);
        var s2e = p3(pts3dEnd[silIdx[1]][0], pts3dEnd[silIdx[1]][1], pts3dEnd[silIdx[1]][2]);
        items[items.length] = mkL(layer, s2s[0], s2s[1], s2e[0], s2e[1], COL.NEON, 2.5, 0);
    }

    return items;
}

// Find indices where circle transitions from front-facing to back-facing (silhouette points)
function findSilhouetteIndices(pts3d, center, axis) {
    var n = v3norm(axis);
    var vd = [VD.x, VD.y, VD.z];
    var vdDotN = v3dot(vd, n);
    var vdProj = v3norm(v3sub(vd, v3scale(n, vdDotN)));

    var idx1 = -1, idx2 = -1;
    var prevSign = 0;
    for (var i = 0; i < pts3d.length - 1; i++) {
        var disp = v3sub(pts3d[i], center);
        var facing = v3dot(disp, vdProj);
        var sign = facing < 0 ? -1 : 1;
        if (prevSign !== 0 && sign !== prevSign) {
            if (idx1 < 0) idx1 = i;
            else idx2 = i;
        }
        prevSign = sign;
    }
    return [idx1, idx2];
}

// ═══════════════════════════════════════════════════════════════
// HIGH-LEVEL 3D COMPONENT RENDERERS
// ═══════════════════════════════════════════════════════════════

// Multi-section cylinder with bands and detail
function renderCylinder3D(layer, sections, axStart, axDir, rng) {
    var items = [];
    var axN = v3norm(axDir);

    for (var si = 0; si < sections.length; si++) {
        var sec = sections[si];
        var secStart = v3add(axStart, v3scale(axN, sec.tStart));
        var secEnd = v3add(axStart, v3scale(axN, sec.tEnd));
        var rS = sec.rStart;
        var rE = sec.rEnd;

        // Section end rings
        items[items.length] = draw3DCircleBack(layer, secStart[0], secStart[1], secStart[2], rS, axN[0], axN[1], axN[2], COL.DEEP, 0.35);
        items[items.length] = draw3DCircleFront(layer, secStart[0], secStart[1], secStart[2], rS, axN[0], axN[1], axN[2], COL.SALMON, 1.25);
        items[items.length] = draw3DCircle(layer, secEnd[0], secEnd[1], secEnd[2], rE, axN[0], axN[1], axN[2], COL.NEON, 2.0, 0);

        // Silhouette lines
        var pts3dS = circle3D(secStart[0], secStart[1], secStart[2], rS, axN[0], axN[1], axN[2], 32);
        var pts3dE = circle3D(secEnd[0], secEnd[1], secEnd[2], rE, axN[0], axN[1], axN[2], 32);
        var silIdx = findSilhouetteIndices(pts3dS, [secStart[0], secStart[1], secStart[2]], axN);
        if (silIdx[0] >= 0 && silIdx[1] >= 0) {
            var s1s = p3(pts3dS[silIdx[0]][0], pts3dS[silIdx[0]][1], pts3dS[silIdx[0]][2]);
            var s1e = p3(pts3dE[silIdx[0]][0], pts3dE[silIdx[0]][1], pts3dE[silIdx[0]][2]);
            items[items.length] = mkL(layer, s1s[0], s1s[1], s1e[0], s1e[1], COL.NEON, 2.5, 0);
            var s2s = p3(pts3dS[silIdx[1]][0], pts3dS[silIdx[1]][1], pts3dS[silIdx[1]][2]);
            var s2e = p3(pts3dE[silIdx[1]][0], pts3dE[silIdx[1]][1], pts3dE[silIdx[1]][2]);
            items[items.length] = mkL(layer, s2s[0], s2s[1], s2e[0], s2e[1], COL.NEON, 2.5, 0);
        }

        // Band rings along section
        var bandCount = rng.randInt(2, 4);
        for (var bi = 1; bi <= bandCount; bi++) {
            var bt = bi / (bandCount + 1);
            var bPos = v3lerp(secStart, secEnd, bt);
            var bRad = rS + (rE - rS) * bt;
            items[items.length] = draw3DCircleFront(layer, bPos[0], bPos[1], bPos[2], bRad, axN[0], axN[1], axN[2], COL.SALMON, 0.75);
            items[items.length] = draw3DCircleBack(layer, bPos[0], bPos[1], bPos[2], bRad, axN[0], axN[1], axN[2], COL.DEEP, 0.25);
        }

        // Panel lines (surface detail along cylinder length)
        var panelCount = rng.randInt(3, 5);
        var basisS = perpBasis(axN);
        for (var pi = 0; pi < panelCount; pi++) {
            var pAng = (2 * Math.PI / panelCount) * pi + rng.range(0, 0.3);
            var offU = Math.cos(pAng);
            var offV = Math.sin(pAng);
            // Check if this panel line is front-facing
            var testPt = v3add(secStart, v3add(v3scale(basisS.u, rS * offU), v3scale(basisS.v, rS * offV)));
            var disp = v3sub(testPt, [secStart[0], secStart[1], secStart[2]]);
            var vdN = v3dot([VD.x, VD.y, VD.z], axN);
            var vdP = v3norm(v3sub([VD.x, VD.y, VD.z], v3scale(axN, vdN)));
            var facing = v3dot(v3norm(disp), vdP);

            var pStart = v3add(secStart, v3add(v3scale(basisS.u, rS * offU), v3scale(basisS.v, rS * offV)));
            var pEnd = v3add(secEnd, v3add(v3scale(basisS.u, rE * offU), v3scale(basisS.v, rE * offV)));

            if (facing < 0) {
                // Front-facing: solid
                items[items.length] = draw3DLine(layer, pStart, pEnd, COL.WARM, 0.4, 0);
            } else {
                // Back-facing: dashed hidden line
                items[items.length] = draw3DLine(layer, pStart, pEnd, COL.DEEP, 0.25, 1);
            }
        }

        // Section joint ring (bold, at transition between sections)
        if (si < sections.length - 1) {
            items[items.length] = draw3DCircle(layer, secEnd[0], secEnd[1], secEnd[2], rE * 1.05, axN[0], axN[1], axN[2], COL.NEON, 1.75, 0);
        }
    }

    // Axis center line
    var axEnd = v3add(axStart, axDir);
    var ext = v3scale(axN, v3len(axDir) * 0.1);
    items[items.length] = draw3DLine(layer, v3sub(axStart, ext), v3add(axEnd, ext), COL.DEEP, 0.4, 2);

    return items;
}

// 3D Box (housing) — defined by origin corner + 3 edge vectors
function renderBox3D(layer, origin, edgeX, edgeY, edgeZ, rng) {
    var items = [];
    // 8 corners
    var c = [];
    c[0] = origin;
    c[1] = v3add(origin, edgeX);
    c[2] = v3add(v3add(origin, edgeX), edgeZ);
    c[3] = v3add(origin, edgeZ);
    c[4] = v3add(origin, edgeY);
    c[5] = v3add(v3add(origin, edgeX), edgeY);
    c[6] = v3add(v3add(v3add(origin, edgeX), edgeY), edgeZ);
    c[7] = v3add(v3add(origin, edgeY), edgeZ);

    // 6 faces — determine which face normals point toward viewer (visible)
    var faces = [
        { pts: [c[0],c[1],c[5],c[4]], normal: v3cross(edgeX, edgeY) },     // front (XY)
        { pts: [c[3],c[2],c[6],c[7]], normal: v3scale(v3cross(edgeX, edgeY), -1) }, // back
        { pts: [c[4],c[5],c[6],c[7]], normal: edgeY },                      // top
        { pts: [c[0],c[1],c[2],c[3]], normal: v3scale(edgeY, -1) },         // bottom
        { pts: [c[0],c[3],c[7],c[4]], normal: v3scale(edgeX, -1) },         // left
        { pts: [c[1],c[2],c[6],c[5]], normal: edgeX }                       // right
    ];

    for (var fi = 0; fi < faces.length; fi++) {
        var f = faces[fi];
        var nDot = v3dot(v3norm(f.normal), [VD.x, VD.y, VD.z]);
        var col = nDot < 0 ? COL.NEON : COL.DEEP;
        var sw = nDot < 0 ? 1.5 : 0.35;
        var dash = nDot < 0 ? 0 : 1;
        var pts2d = projectPts(f.pts);
        items[items.length] = mkPoly(layer, pts2d, true, col, sw, dash);
    }

    // Visible edges (bold silhouette on visible face boundaries)
    var edges = [
        [c[0],c[1]], [c[1],c[5]], [c[5],c[4]], [c[4],c[0]],
        [c[1],c[2]], [c[2],c[6]], [c[6],c[5]],
        [c[4],c[7]], [c[7],c[6]],
        [c[0],c[3]], [c[3],c[2]], [c[3],c[7]]
    ];
    for (var ei = 0; ei < edges.length; ei++) {
        items[items.length] = draw3DLine(layer, edges[ei][0], edges[ei][1], COL.SALMON, 0.75, 0);
    }

    // Panel lines on largest visible face
    var panelCount = rng.randInt(1, 3);
    for (var pli = 1; pli <= panelCount; pli++) {
        var t = pli / (panelCount + 1);
        var pl1 = v3lerp(c[0], c[1], t);
        var pl2 = v3lerp(c[4], c[5], t);
        items[items.length] = draw3DLine(layer, pl1, pl2, COL.WARM, 0.4, 0);
    }

    return items;
}

// 3D Pipe with flanges
function renderPipe3D(layer, startPt, endPt, radius, flangeR, rng) {
    var items = [];
    var axis = v3sub(endPt, startPt);
    var axN = v3norm(axis);

    // Pipe body silhouette
    var cylItems = draw3DCylinder(layer, startPt, endPt, radius, rng);
    for (var ci = 0; ci < cylItems.length; ci++) {
        if (cylItems[ci]) items[items.length] = cylItems[ci];
    }

    // Flanges
    items[items.length] = draw3DCircle(layer, startPt[0], startPt[1], startPt[2], flangeR, axN[0], axN[1], axN[2], COL.SALMON, 1.0, 0);
    items[items.length] = draw3DCircle(layer, endPt[0], endPt[1], endPt[2], flangeR, axN[0], axN[1], axN[2], COL.SALMON, 1.0, 0);

    // Center line
    var ext = v3scale(axN, v3len(axis) * 0.15);
    items[items.length] = draw3DLine(layer, v3sub(startPt, ext), v3add(endPt, ext), COL.DEEP, 0.4, 2);

    // Bolt circle hint (single ring, not individual bolts)
    items[items.length] = draw3DCircle(layer, startPt[0], startPt[1], startPt[2], flangeR * 0.75, axN[0], axN[1], axN[2], COL.WARM, 0.4, 0);
    items[items.length] = draw3DCircle(layer, endPt[0], endPt[1], endPt[2], flangeR * 0.75, axN[0], axN[1], axN[2], COL.WARM, 0.4, 0);

    return items;
}

// Cross-section face (turbine face)
function renderCrossSection3D(layer, center, radius, axis, rings, spokes, blades, rng) {
    var items = [];
    var axN = v3norm(axis);
    var basis = perpBasis(axN);
    var innerR = radius * 0.25;

    // Outer ring (bold)
    items[items.length] = draw3DCircle(layer, center[0], center[1], center[2], radius, axN[0], axN[1], axN[2], COL.NEON, 2.5, 0);

    // Concentric rings
    for (var ri = 1; ri < rings; ri++) {
        var rr = innerR + (radius - innerR) * (ri / rings);
        items[items.length] = draw3DCircle(layer, center[0], center[1], center[2], rr, axN[0], axN[1], axN[2], COL.SALMON, 0.75, 0);
    }

    // Hub
    items[items.length] = draw3DCircle(layer, center[0], center[1], center[2], innerR, axN[0], axN[1], axN[2], COL.SALMON, 1.0, 0);

    // Spokes
    for (var si = 0; si < spokes; si++) {
        var sAng = (2 * Math.PI / spokes) * si;
        var sInner = v3add(center, v3add(v3scale(basis.u, innerR * Math.cos(sAng)), v3scale(basis.v, innerR * Math.sin(sAng))));
        var sOuter = v3add(center, v3add(v3scale(basis.u, radius * 0.95 * Math.cos(sAng)), v3scale(basis.v, radius * 0.95 * Math.sin(sAng))));
        items[items.length] = draw3DLine(layer, sInner, sOuter, COL.WARM, 0.5, 0);
    }

    // Blades
    if (blades > 0) {
        var bladeInR = innerR * 1.3;
        var bladeOutR = radius * 0.8;
        for (var bi = 0; bi < blades; bi++) {
            var bAng1 = (2 * Math.PI / blades) * bi;
            var bAng2 = bAng1 + (2 * Math.PI / blades) * 0.6;
            var bIn = v3add(center, v3add(v3scale(basis.u, bladeInR * Math.cos(bAng1)), v3scale(basis.v, bladeInR * Math.sin(bAng1))));
            var bOut = v3add(center, v3add(v3scale(basis.u, bladeOutR * Math.cos(bAng2)), v3scale(basis.v, bladeOutR * Math.sin(bAng2))));
            items[items.length] = draw3DLine(layer, bIn, bOut, COL.WARM, 0.4, 0);
        }
    }

    return items;
}
