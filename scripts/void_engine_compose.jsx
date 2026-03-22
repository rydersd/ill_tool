// void_engine_compose.jsx — Axis-Locked Machine Composition
// Generates machine geometry aligned to STYLE.angle_grid
// All cylinders share primary axis, housings on secondary axis
// Composition fills STYLE.density of the artboard
// Depends on: void_engine_lib.jsx, void_style_*.jsx

// ═══════════════════════════════════════════════════════════════
// MACHINE COMPOSITION
// Generates a complete machine definition in LOCAL coordinates
// Local coords: (0,0) = top-left of artboard, Y increases downward
// Chunk runners convert to Illustrator coords: ill_x = abX + x, ill_y = abY - y
// ═══════════════════════════════════════════════════════════════

function composeMachine(seed, abW, abH) {
    var rng = PRNG(seed);
    var machine = {
        seed: seed,
        cylinders: [],
        housings: [],
        pipes: [],
        crossSections: [],
        dataPanels: [],
        dimensions: [],
        labels: []
    };

    var cx = abW / 2;
    var cy = abH / 2;
    var margin = Math.min(abW, abH) * STYLE.composition.fill_margin;
    var primaryAngle = STYLE.composition.primary_angle;
    var secondaryAngle = STYLE.composition.secondary_angle;
    var fs = sForeshorten();

    // ── Main Cylinder ──────────────────────────────────────────
    // Spans most of the artboard along the primary diagonal
    var diagLen = Math.sqrt(abW * abW + abH * abH);
    var mainHalfLen = diagLen * rng.range(0.26, 0.33) * STYLE.density;
    var baseR = rng.range(80, 140);

    // Generate sections with smooth Gaussian random-walk radius
    var secCount = rng.randInt(4, 6);
    var mainSections = [];
    var prevR = baseR * rng.range(0.55, 0.7);

    for (var si = 0; si < secCount; si++) {
        var tStart = si / secCount;
        var tEnd = (si + 1) / secCount;
        var radiusTop = prevR;
        var radiusBottom = clamp(
            prevR + rng.gaussian(0, 10),
            baseR * 0.5, baseR * 1.4
        );
        // Taper at intake and exhaust ends
        if (si === 0) radiusTop = radiusBottom * rng.range(0.6, 0.8);
        if (si === secCount - 1) radiusBottom = radiusTop * rng.range(0.5, 0.7);

        mainSections[mainSections.length] = {
            name: "sec_" + si,
            tStart: tStart,
            tEnd: tEnd,
            radiusTop: radiusTop,
            radiusBottom: radiusBottom
        };
        prevR = radiusBottom;
    }

    machine.cylinders[0] = {
        name: "main",
        cx: cx,
        cy: cy,
        axisAngle: primaryAngle,
        halfLength: mainHalfLen,
        foreshorten: fs,
        sections: mainSections,
        isTube: false
    };

    // ── Parallel Tubes ─────────────────────────────────────────
    // Run along the main cylinder body on the SAME axis (axis-locked)
    var tubeCount = rng.randInt(2, 4);
    for (var ti = 0; ti < tubeCount; ti++) {
        var tubeAngle = (360 / tubeCount) * ti + rng.range(0, 30);
        var tubeOff = baseR * rng.range(1.15, 1.5);
        var tubeR = rng.range(8, 18);
        var tubeFR = tubeR * rng.range(1.3, 1.6);

        // Offset perpendicular to cylinder axis
        var perpAng = (primaryAngle + 90 + tubeAngle) * DEG2RAD;
        var tubeOffX = Math.cos(perpAng) * tubeOff;
        var tubeOffY = Math.sin(perpAng) * tubeOff;

        var tubeHalfLen = mainHalfLen * rng.range(0.7, 0.9);

        machine.cylinders[machine.cylinders.length] = {
            name: "tube_" + ti,
            cx: cx + tubeOffX,
            cy: cy + tubeOffY,
            axisAngle: primaryAngle,  // LOCKED to same axis as main
            halfLength: tubeHalfLen,
            foreshorten: fs,
            sections: [{
                name: "tube_body",
                tStart: 0, tEnd: 1,
                radiusTop: tubeR, radiusBottom: tubeR
            }],
            isTube: true,
            flangeR: tubeFR
        };
    }

    // ── Housings ───────────────────────────────────────────────
    // Attached to main cylinder surface, oriented on secondary angle
    var housingCount = rng.randInt(3, 5);
    var usedPositions = [];

    // Precompute main cylinder axis endpoints in local coords
    var mainAxRad = primaryAngle * DEG2RAD;
    var mainAxDx = Math.cos(mainAxRad) * mainHalfLen;
    var mainAxDy = Math.sin(mainAxRad) * mainHalfLen;
    var mainBackPt = [cx - mainAxDx, cy - mainAxDy];
    var mainFrontPt = [cx + mainAxDx, cy + mainAxDy];

    for (var hi = 0; hi < housingCount; hi++) {
        var attachT = rng.range(0.15, 0.85);
        var attachPt = axPt(mainBackPt, mainFrontPt, attachT);

        // Get cylinder radius at attachment point
        var secIdx = Math.floor(attachT * mainSections.length);
        if (secIdx >= mainSections.length) secIdx = mainSections.length - 1;
        var secR = (mainSections[secIdx].radiusTop + mainSections[secIdx].radiusBottom) / 2;

        // Position above or below cylinder
        var side = rng.chance(0.5) ? 1 : -1;
        var hw = rng.range(40, 90);
        var hh = rng.range(30, 70);
        var hd = rng.range(20, 45);

        // Housing depth angle — uses secondary angle or slight variation
        var hAngle = (secondaryAngle === primaryAngle)
            ? rng.range(25, 45)   // if same angle, add variation for depth
            : Math.abs(secondaryAngle) || 30;

        var attachY = side * (secR * fs + hh * 0.3);
        var hx = attachPt[0] - hw / 2;
        var hy = attachPt[1] + attachY;

        // Collision avoidance with previous housings
        var collision = false;
        for (var ui = 0; ui < usedPositions.length; ui++) {
            if (Math.abs(hx - usedPositions[ui][0]) < hw * 0.8 &&
                Math.abs(hy - usedPositions[ui][1]) < hh * 0.8) {
                collision = true;
                break;
            }
        }
        if (collision) {
            hx += rng.range(-80, 80);
            hy += rng.range(-60, 60);
        }
        usedPositions[usedPositions.length] = [hx, hy];

        machine.housings[machine.housings.length] = {
            name: "housing_" + hi,
            x: hx, y: hy,
            w: hw, h: hh, d: hd,
            angle: hAngle,
            showHidden: rng.chance(0.6),
            attachCyl: 0,
            attachT: attachT
        };
    }

    // ── Pipes ──────────────────────────────────────────────────
    // Connect housings to each other or to cylinder surface
    var pipeCount = rng.randInt(2, Math.min(4, housingCount));
    for (var pi = 0; pi < pipeCount; pi++) {
        var pR = rng.range(6, 14);
        var pFR = pR * rng.range(1.3, 1.6);
        var startPt, endPt;

        if (pi < machine.housings.length - 1) {
            // Connect adjacent housings
            var h1 = machine.housings[pi];
            var h2 = machine.housings[pi + 1];
            startPt = [h1.x + h1.w, h1.y + h1.h / 2];
            endPt = [h2.x, h2.y + h2.h / 2];
        } else {
            // Connect to random point on cylinder surface
            var rT = rng.range(0.2, 0.8);
            var rPt = axPt(mainBackPt, mainFrontPt, rT);
            startPt = [rPt[0] + rng.range(-40, 40), rPt[1] + rng.range(30, 80)];
            endPt = [rPt[0] + rng.range(-80, 80), rPt[1] + rng.range(60, 160)];
        }

        machine.pipes[machine.pipes.length] = {
            name: "pipe_" + pi,
            startPt: startPt,
            endPt: endPt,
            radius: pR,
            flangeRadius: pFR
        };
    }

    // ── Cross-Sections ─────────────────────────────────────────
    // Turbine face at front end of main cylinder
    var lastSec = mainSections[mainSections.length - 1];
    machine.crossSections[0] = {
        name: "section_main",
        cx: mainFrontPt[0],
        cy: mainFrontPt[1],
        outerRadius: lastSec.radiusBottom,
        innerRadius: lastSec.radiusBottom * rng.range(0.25, 0.4),
        rings: rng.randInt(3, 5),
        spokes: rng.randInt(6, 10),
        blades: rng.chance(0.7) ? rng.randInt(8, 14) : 0,
        foreshorten: fs
    };

    // ── Data Panels ────────────────────────────────────────────
    // Technical readout boxes positioned at artboard corners/edges
    var dpCount = rng.randInt(3, 5);
    var corners = [
        { x: margin, y: margin },                        // top-left
        { x: abW - 180 - margin, y: margin },            // top-right
        { x: margin, y: abH - 120 - margin },            // bottom-left
        { x: abW - 180 - margin, y: abH - 120 - margin },// bottom-right
        { x: abW / 2 - 80, y: margin }                   // top-center
    ];
    for (var di = 0; di < dpCount; di++) {
        var corner = corners[di % corners.length];
        machine.dataPanels[machine.dataPanels.length] = {
            name: "data_" + di,
            x: corner.x,
            y: corner.y,
            w: rng.range(100, 170),
            h: rng.range(60, 110),
            scanLines: rng.randInt(6, 14),
            hasGauge: rng.chance(0.4)
        };
    }

    // ── Dimension Lines ────────────────────────────────────────
    // Engineering measurement annotations along main cylinder
    var dimCount = rng.randInt(3, 5);
    for (var dmi = 0; dmi < dimCount; dmi++) {
        var dt1 = rng.range(0, 0.4);
        var dt2 = rng.range(0.6, 1.0);
        machine.dimensions[machine.dimensions.length] = {
            name: "dim_" + dmi,
            startPt: axPt(mainBackPt, mainFrontPt, dt1),
            endPt: axPt(mainBackPt, mainFrontPt, dt2),
            offset: rng.range(15, 40) * (rng.chance(0.5) ? 1 : -1)
        };
    }

    // ── Labels ─────────────────────────────────────────────────
    // Section labels placed along the cylinder axis
    if (STYLE.typography.density === "high") {
        for (var li = 0; li < mainSections.length; li++) {
            var lT = (mainSections[li].tStart + mainSections[li].tEnd) / 2;
            var lPt = axPt(mainBackPt, mainFrontPt, lT);
            var lR = (mainSections[li].radiusTop + mainSections[li].radiusBottom) / 2;
            machine.labels[machine.labels.length] = {
                text: sSectionLabel(rng, li),
                x: lPt[0],
                y: lPt[1] - lR * fs - 15,
                size: STYLE.typography.label_size,
                type: "section"
            };
        }

        // Coordinate markers at housing positions
        if (STYLE.typography.coord_markers) {
            for (var cmi = 0; cmi < machine.housings.length; cmi++) {
                var hDef = machine.housings[cmi];
                machine.labels[machine.labels.length] = {
                    text: sCoordMarker(rng),
                    x: hDef.x + hDef.w + 5,
                    y: hDef.y,
                    size: STYLE.typography.micro_size,
                    type: "coord"
                };
            }
        }

        // System text in data panel areas
        for (var sti = 0; sti < 3; sti++) {
            machine.labels[machine.labels.length] = {
                text: sSystemText(rng),
                x: rng.range(margin, abW - 200),
                y: rng.chance(0.5) ? rng.range(margin, margin + 40) : rng.range(abH - margin - 40, abH - margin),
                size: STYLE.typography.heading_size,
                type: "system"
            };
        }
    }

    return machine;
}

// ═══════════════════════════════════════════════════════════════
// CHUNK INITIALIZATION
// Called at the start of every chunk runner (02-07)
// Finds existing artboard/layers created by chunk 01, regenerates machine
// ═══════════════════════════════════════════════════════════════

var AB_W = 1728;   // Standard poster width
var AB_H = 2592;   // Standard poster height

function chunkInit() {
    var doc = app.activeDocument;

    // Find the artboard created by chunk 01
    var ab = findArtboard(doc, "VOID_s" + SEED);
    if (!ab) {
        // If no artboard found, fail with helpful message
        return null;
    }

    var abX = ab.rect[0];
    var abY = ab.rect[1];
    var w = ab.rect[2] - ab.rect[0];
    var h = ab.rect[1] - ab.rect[3];

    // Find root layer
    var root = findLayer(doc, "VOID_s" + SEED);
    if (!root) return null;

    // Regenerate the same machine definition (PRNG is deterministic)
    var machine = composeMachine(SEED, w, h);
    // Offset seed for rendering variation (different from composition)
    var rng = PRNG(SEED + 7);

    return {
        doc: doc,
        root: root,
        abX: abX,
        abY: abY,
        AB_W: w,
        AB_H: h,
        machine: machine,
        rng: rng,
        // Coordinate conversion: local (Y-down) → Illustrator (Y-up)
        toX: function (x) { return abX + x; },
        toY: function (y) { return abY - y; },
        // Convert a local point [x, y] to Illustrator coordinates
        toPt: function (pt) { return [abX + pt[0], abY - pt[1]]; }
    };
}
