// void_machine_generate.jsx
// Main entry point — generates a procedural isometric machine
// Creates a NEW artboard below the existing row
// Orthographic views (front/side/top) arranged in standard projection
// Adobe Illustrator ExtendScript (ES3)

#include "/tmp/void_machine_lib.jsx"
#include "/tmp/void_machine_composer.jsx"

// ── Configuration ─────────────────────────────────────────────
var SEED = 77;  // Change for different machines. -1 = random
if (SEED < 0) SEED = Math.floor(Math.random() * 999999);

var AB_W = 1728;
var AB_H = 2592;

// ── Setup ─────────────────────────────────────────────────────
var doc = app.activeDocument;

// ── Create new artboard on the NEXT ROW below existing ones ───
// Find the lowest Y of all existing artboards
var lowestY = 99999;
for (var abi = 0; abi < doc.artboards.length; abi++) {
    var abr = doc.artboards[abi].artboardRect;
    if (abr[3] < lowestY) lowestY = abr[3];  // abr[3] = bottom (lowest Y)
}
var newRowY = lowestY - 120;  // Gap below lowest existing artboard
var newAbX = 0;

// Create the isometric artboard
var isoRect = [newAbX, newRowY, newAbX + AB_W, newRowY - AB_H];
var isoAB = doc.artboards.add(isoRect);
isoAB.name = "VOID_engine_s" + SEED;
var isoAbIndex = doc.artboards.length - 1;

var abX = isoRect[0];
var abY = isoRect[1];

// ── Create root layer for this generation ─────────────────────
var rootLayer = doc.layers.add();
rootLayer.name = "ENGINE_s" + SEED;

// ── Create layer hierarchy ────────────────────────────────────
var layerNames = [
    "TYPO_labels",
    "DATA_panels",
    "DETAIL_dimensions",
    "DETAIL_fasteners",
    "ANTENNAS",
    "PIPES",
    "HOUSINGS",
    "SECTIONS",
    "CYLINDERS",
    "AXES",
    "GRID_construction",
    "BG_fill"
];
var layers = {};
// Create in reverse so first = topmost in panel
for (var lni = layerNames.length - 1; lni >= 0; lni--) {
    var newLy = rootLayer.layers.add();
    newLy.name = layerNames[lni];
    layers[layerNames[lni]] = newLy;
}

// ── Background fill ──────────────────────────────────────────
var bgPath = layers["BG_fill"].pathItems.rectangle(abY, abX, AB_W, AB_H);
bgPath.stroked = false;
bgPath.filled = true;
bgPath.fillColor = COL.BLACK;

// ── Compose the machine ───────────────────────────────────────
var machine = composeMachine(SEED, AB_W, AB_H);
var rng = PRNG(SEED + 7);

// ── Render construction grid ──────────────────────────────────
makeConstructionGrid(layers["GRID_construction"], abX, abY, AB_W, AB_H, 200);

// ── Render cylinders ──────────────────────────────────────────
var cyls = machine.cylinders;
for (var ci = 0; ci < cyls.length; ci++) {
    var cylDef = cyls[ci];
    var cylDefCopy = {
        name: cylDef.name,
        cx: abX + cylDef.cx,
        cy: abY - cylDef.cy,
        axisAngle: cylDef.axisAngle,
        halfLength: cylDef.halfLength,
        foreshorten: cylDef.foreshorten,
        sections: cylDef.sections
    };
    makeCylinder(layers["CYLINDERS"], cylDefCopy, rng);
}

// ── Render cross-sections ─────────────────────────────────────
var crossSecs = machine.crossSections;
for (var csi = 0; csi < crossSecs.length; csi++) {
    var csDef = crossSecs[csi];
    var csDefCopy = {
        name: csDef.name,
        cx: abX + csDef.cx,
        cy: abY - csDef.cy,
        outerRadius: csDef.outerRadius,
        innerRadius: csDef.innerRadius,
        rings: csDef.rings,
        spokes: csDef.spokes,
        blades: csDef.blades,
        foreshorten: csDef.foreshorten
    };
    makeCrossSection(layers["SECTIONS"], csDefCopy, rng);
}

// ── Render housings ───────────────────────────────────────────
var hDefs = machine.housings;
for (var hi = 0; hi < hDefs.length; hi++) {
    var hDef = hDefs[hi];
    var hDefCopy = {
        name: hDef.name,
        x: abX + hDef.x,
        y: abY - hDef.y,
        w: hDef.w,
        h: hDef.h,
        d: hDef.d,
        angle: hDef.angle,
        showHidden: hDef.showHidden
    };
    makeHousing(layers["HOUSINGS"], hDefCopy, rng);
}

// ── Render pipes ──────────────────────────────────────────────
var pipes = machine.pipes;
for (var pi = 0; pi < pipes.length; pi++) {
    var pDef = pipes[pi];
    var pDefCopy = {
        name: pDef.name,
        startPt: [abX + pDef.startPt[0], abY - pDef.startPt[1]],
        endPt: [abX + pDef.endPt[0], abY - pDef.endPt[1]],
        radius: pDef.radius,
        flangeRadius: pDef.flangeRadius
    };
    makePipe(layers["PIPES"], pDefCopy, rng);
}

// ── Render antennas ───────────────────────────────────────────
var antennas = machine.antennas;
for (var ai = 0; ai < antennas.length; ai++) {
    var aDef = antennas[ai];
    var aDefCopy = {
        name: aDef.name,
        baseX: abX + aDef.baseX,
        baseY: abY - aDef.baseY,
        masts: aDef.masts
    };
    makeAntennaArray(layers["ANTENNAS"], aDefCopy, rng);
}

// ── Render data panels ────────────────────────────────────────
var dataPanels = machine.dataPanels;
for (var di = 0; di < dataPanels.length; di++) {
    var dpDef = dataPanels[di];
    var dpDefCopy = {
        name: dpDef.name,
        x: abX + dpDef.x,
        y: abY - dpDef.y,
        w: dpDef.w,
        h: dpDef.h,
        scanLines: dpDef.scanLines,
        hasGauge: dpDef.hasGauge
    };
    makeDataPanel(layers["DATA_panels"], dpDefCopy, rng);
}

// ── Render dimension lines ────────────────────────────────────
var dims = machine.dimensions;
for (var dmi = 0; dmi < dims.length; dmi++) {
    var dmDef = dims[dmi];
    var dmDefCopy = {
        name: dmDef.name,
        startPt: [abX + dmDef.startPt[0], abY - dmDef.startPt[1]],
        endPt: [abX + dmDef.endPt[0], abY - dmDef.endPt[1]],
        offset: dmDef.offset
    };
    makeDimensionLine(layers["DETAIL_dimensions"], dmDefCopy, rng);
}

// ═══════════════════════════════════════════════════════════════
// ORTHOGRAPHIC VIEWS — standard third-angle projection layout
// Front view bottom-right of isometric poster
// Side (end) view to the RIGHT of front
// Top (plan) view ABOVE the front view
// Projection lines connect corresponding features
// ═══════════════════════════════════════════════════════════════

var orthoScale = 0.7;
var orthoGap = 60;

// Front view: right of the isometric artboard
var frontW = 700;
var frontH = 450;
var frontX = abX + AB_W + orthoGap;
var frontY = abY - AB_H + frontH + 200;  // Lower portion of poster height
var frontRect = [frontX, frontY, frontX + frontW, frontY - frontH];
var frontAB = doc.artboards.add(frontRect);
frontAB.name = "ORTHO_front_s" + SEED;

// Side (end) view: to the right of front view
var sideW = 400;
var sideH = frontH;  // Same height — aligned Y with front
var sideX = frontX + frontW + orthoGap;
var sideY = frontY;
var sideRect = [sideX, sideY, sideX + sideW, sideY - sideH];
var sideAB = doc.artboards.add(sideRect);
sideAB.name = "ORTHO_side_s" + SEED;

// Top (plan) view: above front view
var topW = frontW;  // Same width — aligned X with front
var topH = 300;
var topX = frontX;
var topY = frontY + orthoGap + topH;
var topRect = [topX, topY, topX + topW, topY - topH];
var topAB = doc.artboards.add(topRect);
topAB.name = "ORTHO_top_s" + SEED;

// ── Ortho layers ──────────────────────────────────────────────
var orthoRoot = doc.layers.add();
orthoRoot.name = "ORTHO_s" + SEED;

// BG first (bottom), then content on top
var orthoBGLayer = orthoRoot.layers.add();
orthoBGLayer.name = "ORTHO_BG";
var orthoProjLayer = orthoRoot.layers.add();
orthoProjLayer.name = "ORTHO_projections";
var orthoTopLayer = orthoRoot.layers.add();
orthoTopLayer.name = "ORTHO_top";
var orthoSideLayer = orthoRoot.layers.add();
orthoSideLayer.name = "ORTHO_side";
var orthoFrontLayer = orthoRoot.layers.add();
orthoFrontLayer.name = "ORTHO_front";

// ── BG fills ──────────────────────────────────────────────────
var orthoRects = [frontRect, sideRect, topRect];
for (var bgi = 0; bgi < 3; bgi++) {
    var br = orthoRects[bgi];
    var bp = orthoBGLayer.pathItems.rectangle(br[1], br[0], br[2] - br[0], br[1] - br[3]);
    bp.stroked = false;
    bp.filled = true;
    bp.fillColor = COL.BLACK;
}

// ── Render orthographic views ─────────────────────────────────
var frontCx = frontX + frontW / 2;
var frontCy = frontY - frontH / 2;
drawOrthoFront(orthoFrontLayer, machine, frontCx, frontCy, orthoScale, orthoProjLayer);

var sideCx = sideX + sideW / 2;
var sideCy = sideY - sideH / 2;  // Same vertical center as front (aligned)
drawOrthoSide(orthoSideLayer, machine, sideCx, sideCy, orthoScale, orthoProjLayer, frontCy);

var topCx = topX + topW / 2;  // Same horizontal center as front (aligned)
var topCy = topY - topH / 2;
drawOrthoTop(orthoTopLayer, machine, topCx, topCy, orthoScale, orthoProjLayer, frontCx, frontX);

// ── Projection lines connecting views ─────────────────────────
// Horizontal lines from front → side (at cylinder extents)
var mainR = machine.cylinders[0].sections[0].radiusTop * orthoScale;
// Top extent
mkL(orthoProjLayer, frontX + frontW, frontCy + mainR, sideX, sideCy + mainR, COL.DARK, 0.2, false);
// Center
mkL(orthoProjLayer, frontX + frontW, frontCy, sideX, sideCy, COL.DARK, 0.2, false);
// Bottom extent
mkL(orthoProjLayer, frontX + frontW, frontCy - mainR, sideX, sideCy - mainR, COL.DARK, 0.2, false);

// Vertical lines from front → top (at section boundaries)
var mainLen = machine.cylinders[0].halfLength * 2 * orthoScale;
var mainStart = frontCx - mainLen / 2;
// Start boundary
mkL(orthoProjLayer, mainStart, frontY, mainStart, topY - topH, COL.DARK, 0.2, false);
// End boundary
mkL(orthoProjLayer, mainStart + mainLen, frontY, mainStart + mainLen, topY - topH, COL.DARK, 0.2, false);
// Center
mkL(orthoProjLayer, frontCx, frontY, topCx, topY - topH, COL.DARK, 0.2, false);

// ── View label markers ────────────────────────────────────────
// Front
mkL(orthoFrontLayer, frontX + 10, frontY - 12, frontX + 50, frontY - 12, COL.NEON, 1.5, false);
mkL(orthoFrontLayer, frontX + 10, frontY - 12, frontX + 10, frontY - 22, COL.NEON, 1.5, false);
// Side
mkL(orthoSideLayer, sideX + 10, sideY - 12, sideX + 50, sideY - 12, COL.NEON, 1.5, false);
mkL(orthoSideLayer, sideX + 10, sideY - 12, sideX + 10, sideY - 22, COL.NEON, 1.5, false);
// Top
mkL(orthoTopLayer, topX + 10, topY - 12, topX + 50, topY - 12, COL.NEON, 1.5, false);
mkL(orthoTopLayer, topX + 10, topY - 12, topX + 10, topY - 22, COL.NEON, 1.5, false);

// ── Finalize ──────────────────────────────────────────────────
app.redraw();
doc.save();

"VOID Machine Generator v2 complete. Seed: " + SEED +
    ", Cylinders: " + machine.cylinders.length +
    ", Housings: " + machine.housings.length +
    ", Pipes: " + machine.pipes.length +
    ", Cross-sections: " + machine.crossSections.length +
    ", Antennas: " + machine.antennas.length +
    ", Data panels: " + machine.dataPanels.length +
    ", Ortho views: 3 (front/side/top) with projection lines" +
    ", Total artboards: " + doc.artboards.length;
