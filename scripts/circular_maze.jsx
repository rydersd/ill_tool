// Circular maze generator for Adobe Illustrator (ExtendScript ES3)
// Merged paths + grouped output — recursive backtracking on a polar grid

var numRings = 28;
var ringWidth = 12;
var centerRadius = 20;
var wallWeight = 1;
var margin = 40;
var THRESHOLD = 1.6;
var PI2 = Math.PI * 2;
var totalRadius = centerRadius + numRings * ringWidth;
var docSize = (totalRadius + margin) * 2;

var doc = app.documents.add(DocumentColorSpace.RGB, docSize, docSize);
var layer = doc.layers[0];
layer.name = "Circular Maze";
var cx = docSize / 2;
var cy = docSize / 2;

// --- Polar grid setup ---

var cellsPerRing = [];
cellsPerRing[0] = 8;
for (var r = 1; r < numRings; r++) {
    cellsPerRing[r] = cellsPerRing[r - 1];
    var oR = centerRadius + (r + 1) * ringWidth;
    if (PI2 * oR / cellsPerRing[r] > ringWidth * THRESHOLD) {
        cellsPerRing[r] *= 2;
    }
}

var innerWall = [], ccwWall = [], vis = [];
var totalCells = 0;
for (var r = 0; r < numRings; r++) {
    innerWall[r] = []; ccwWall[r] = []; vis[r] = [];
    for (var c = 0; c < cellsPerRing[r]; c++) {
        innerWall[r][c] = true;
        ccwWall[r][c] = true;
        vis[r][c] = false;
        totalCells++;
    }
}

// --- Maze generation (iterative backtracker) ---

function getNeighbors(r, c) {
    var n = cellsPerRing[r];
    var nb = [];
    nb.push([r, (c - 1 + n) % n, 0]); // CW
    nb.push([r, (c + 1) % n, 1]);      // CCW
    if (r > 0) {
        var pn = cellsPerRing[r - 1];
        nb.push([r - 1, (n == pn) ? c : Math.floor(c / 2), 2]); // inward
    }
    if (r < numRings - 1) {
        var cn = cellsPerRing[r + 1];
        if (cn == n) {
            nb.push([r + 1, c, 3]);
        } else {
            nb.push([r + 1, c * 2, 3]);
            nb.push([r + 1, c * 2 + 1, 3]);
        }
    }
    return nb;
}

function removeWall(r1, c1, r2, c2, dir) {
    if (dir == 0) { ccwWall[r1][(c1 - 1 + cellsPerRing[r1]) % cellsPerRing[r1]] = false; }
    else if (dir == 1) { ccwWall[r1][c1] = false; }
    else if (dir == 2) { innerWall[r1][c1] = false; }
    else { innerWall[r2][c2] = false; }
}

var stack = [], cr = 0, cc = 0;
vis[0][0] = true;
var vc = 1;
while (vc < totalCells) {
    var nbrs = getNeighbors(cr, cc);
    var unv = [];
    for (var i = 0; i < nbrs.length; i++) {
        if (!vis[nbrs[i][0]][nbrs[i][1]]) unv.push(nbrs[i]);
    }
    if (unv.length > 0) {
        var pick = unv[Math.floor(Math.random() * unv.length)];
        removeWall(cr, cc, pick[0], pick[1], pick[2]);
        stack.push([cr, cc]);
        cr = pick[0]; cc = pick[1];
        vis[cr][cc] = true;
        vc++;
    } else if (stack.length > 0) {
        var prev = stack.pop();
        cr = prev[0]; cc = prev[1];
    }
}

// --- Drawing helpers ---

var strokeColor = new RGBColor();
strokeColor.red = 25; strokeColor.green = 25; strokeColor.blue = 25;

function makeArc(grp, rad, a1, a2, segs) {
    var pts = [];
    for (var s = 0; s <= segs; s++) {
        var a = a1 + (a2 - a1) * s / segs;
        pts.push([cx + rad * Math.cos(a), cy + rad * Math.sin(a)]);
    }
    var p = grp.pathItems.add();
    p.setEntirePath(pts);
    p.filled = false; p.stroked = true;
    p.strokeWidth = wallWeight;
    p.strokeColor = strokeColor;
    p.strokeCap = StrokeCap.ROUNDENDCAP;
}

function makeLine(grp, r1, r2, ang) {
    var p = grp.pathItems.add();
    p.setEntirePath([
        [cx + r1 * Math.cos(ang), cy + r1 * Math.sin(ang)],
        [cx + r2 * Math.cos(ang), cy + r2 * Math.sin(ang)]
    ]);
    p.filled = false; p.stroked = true;
    p.strokeWidth = wallWeight;
    p.strokeColor = strokeColor;
    p.strokeCap = StrokeCap.ROUNDENDCAP;
}

// --- Create groups ---

var mazeGroup = layer.groupItems.add();
mazeGroup.name = "Maze";
var arcGroup = mazeGroup.groupItems.add();
arcGroup.name = "Arc Walls";
var radialGroup = mazeGroup.groupItems.add();
radialGroup.name = "Radial Walls";
var boundaryGroup = mazeGroup.groupItems.add();
boundaryGroup.name = "Outer Boundary";

var pathCount = 0;

// --- Draw merged arc walls ---
// For each ring, find consecutive runs of innerWall=true and draw as single arcs

for (var r = 0; r < numRings; r++) {
    var n = cellsPerRing[r];
    var iR = centerRadius + r * ringWidth;
    var cellAngle = PI2 / n;
    var spc = Math.max(2, Math.round(cellAngle / (Math.PI / 16))); // segments per cell

    // Find first gap to handle wraparound
    var hasGap = false;
    var gapIdx = 0;
    for (var c = 0; c < n; c++) {
        if (!innerWall[r][c]) { gapIdx = c; hasGap = true; break; }
    }

    if (!hasGap) {
        // Full ring — one arc
        makeArc(arcGroup, iR, 0, PI2, spc * n);
        pathCount++;
    } else {
        // Scan from first gap, merge consecutive wall cells
        var scanned = 0;
        while (scanned < n) {
            var idx = (gapIdx + scanned) % n;
            if (!innerWall[r][idx]) { scanned++; continue; }
            // Start of a run
            var runStart = idx;
            var runLen = 0;
            while (scanned < n && innerWall[r][(gapIdx + scanned) % n]) {
                scanned++; runLen++;
            }
            makeArc(arcGroup, iR, runStart * cellAngle, (runStart + runLen) * cellAngle, spc * runLen);
            pathCount++;
        }
    }
}

// --- Draw merged radial walls ---
// Map each angle index to the list of rings with a wall there, then merge consecutive spans

var maxCells = cellsPerRing[numRings - 1];
var radialMap = {};

for (var r = 0; r < numRings; r++) {
    var n = cellsPerRing[r];
    var ratio = maxCells / n;
    for (var c = 0; c < n; c++) {
        if (ccwWall[r][c]) {
            var aIdx = ((c + 1) * ratio) % maxCells;
            if (!radialMap[aIdx]) radialMap[aIdx] = [];
            radialMap[aIdx].push(r);
        }
    }
}

for (var aIdx in radialMap) {
    if (!radialMap.hasOwnProperty(aIdx)) continue;
    var rings = radialMap[aIdx];
    rings.sort(function(a, b) { return a - b; });
    var angle = parseInt(aIdx, 10) * PI2 / maxCells;

    var spanStart = rings[0];
    for (var i = 1; i <= rings.length; i++) {
        if (i < rings.length && rings[i] == rings[i - 1] + 1) continue;
        // End of consecutive span — draw one merged radial
        var r1 = centerRadius + spanStart * ringWidth;
        var r2 = centerRadius + (rings[i - 1] + 1) * ringWidth;
        makeLine(radialGroup, r1, r2, angle);
        pathCount++;
        if (i < rings.length) spanStart = rings[i];
    }
}

// --- Outer boundary (one arc with exit gap) ---

var outerN = cellsPerRing[numRings - 1];
var outerAngle = PI2 / outerN;
var outerSpc = Math.max(2, Math.round(outerAngle / (Math.PI / 16)));
var exitCell = Math.floor(outerN * 3 / 4); // gap at bottom

// Single arc from exitCell+1 around to exitCell (skipping exit)
var bStart = (exitCell + 1) % outerN;
var bLen = outerN - 1;
makeArc(boundaryGroup, totalRadius, bStart * outerAngle, bStart * outerAngle + bLen * outerAngle, outerSpc * bLen);
pathCount++;

// --- Title ---
var title = layer.textFrames.add();
title.contents = "CIRCULAR MAZE";
title.position = [margin, docSize - 15];
title.textRange.characterAttributes.size = 14;
title.textRange.characterAttributes.fillColor = strokeColor;

"Circular maze: " + numRings + " rings, " + totalCells + " cells, " + pathCount + " paths (merged & grouped)";
