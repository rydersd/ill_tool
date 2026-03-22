// void_machine_composer.jsx
// Random machine definition generator with plausibility constraints
// Adobe Illustrator ExtendScript (ES3)

function composeMachine(seed, abW, abH) {
    var rng = PRNG(seed);
    var machine = {
        seed: seed,
        cylinders: [],
        housings: [],
        pipes: [],
        crossSections: [],
        antennas: [],
        dataPanels: [],
        dimensions: []
    };

    var cx = abW / 2;
    var cy = abH / 2;

    // ── Generate main cylinders (1-3) ─────────────────────────
    var cylCount = rng.randInt(2, 3);
    var sectionNames = ["intake", "stage_1", "compressor", "chamber", "combustion",
                        "turbine", "expansion", "condenser", "exhaust", "nozzle"];

    for (var ci = 0; ci < cylCount; ci++) {
        var axAngle = rng.range(-55, -25);
        var halfLen = rng.range(350, 650);
        var foreshorten = rng.range(0.55, 0.65);

        // Offset secondary cylinders from center
        var offX = ci === 0 ? 0 : rng.range(-250, 250);
        var offY = ci === 0 ? 0 : rng.range(-200, 200);

        // Generate sections with smooth radius variation
        var secCount = rng.randInt(4, 6);
        var sections = [];
        var baseRadius = rng.range(80, 160);
        var prevRadius = baseRadius;

        for (var si = 0; si < secCount; si++) {
            var tStart = si / secCount;
            var tEnd = (si + 1) / secCount;
            // Gaussian random walk for radius (smooth variation)
            var radiusTop = prevRadius;
            var radiusBottom = clamp(
                prevRadius + rng.gaussian(0, 12),
                baseRadius * 0.5, baseRadius * 1.5
            );
            // First and last sections taper
            if (si === 0) radiusTop = radiusBottom * rng.range(0.6, 0.85);
            if (si === secCount - 1) radiusBottom = radiusTop * rng.range(0.5, 0.75);

            var nameIdx = Math.floor((si / secCount) * sectionNames.length);
            if (nameIdx >= sectionNames.length) nameIdx = sectionNames.length - 1;

            sections[sections.length] = {
                name: sectionNames[nameIdx],
                tStart: tStart,
                tEnd: tEnd,
                radiusTop: radiusTop,
                radiusBottom: radiusBottom
            };
            prevRadius = radiusBottom;
        }

        machine.cylinders[machine.cylinders.length] = {
            name: ci === 0 ? "main" : "cyl_" + (ci + 1),
            cx: cx + offX,
            cy: cy + offY,
            axisAngle: axAngle,
            halfLength: halfLen,
            foreshorten: foreshorten,
            sections: sections
        };
    }

    // ── Generate housings (2-5) attached to cylinders ─────────
    var housingCount = rng.randInt(3, 6);
    var housingNames = ["control", "regulator", "conduit", "manifold", "accumulator",
                        "exchanger", "relay", "amplifier"];
    var usedPositions = [];

    for (var hi = 0; hi < housingCount; hi++) {
        var attachCyl = rng.randInt(0, machine.cylinders.length - 1);
        var cyl = machine.cylinders[attachCyl];
        var attachT = rng.range(0.15, 0.85);

        var hw = rng.range(40, 100);
        var hh = rng.range(30, 80);
        var hd = rng.range(20, 50);
        var hAngle = rng.range(25, 45);

        // Attachment position on cylinder surface
        var axRad = cyl.axisAngle * DEG2RAD;
        var axDx = Math.cos(axRad) * cyl.halfLength;
        var axDy = Math.sin(axRad) * cyl.halfLength;
        var backPt = [cyl.cx - axDx, cyl.cy - axDy];
        var frontPt = [cyl.cx + axDx, cyl.cy + axDy];
        var attachPt = axPt(backPt, frontPt, attachT);

        // Side offset: top or bottom
        var side = rng.chance(0.5) ? 1 : -1;
        var attachSec = cyl.sections[Math.floor(attachT * cyl.sections.length)];
        var secRadius = attachSec ? (attachSec.radiusTop + attachSec.radiusBottom) / 2 : 80;
        var attachY = side * (secRadius * cyl.foreshorten + hh * 0.3);

        var hx = attachPt[0] - hw / 2;
        var hy = attachPt[1] + attachY;

        // Simple collision check
        var collision = false;
        for (var ui = 0; ui < usedPositions.length; ui++) {
            var up = usedPositions[ui];
            if (Math.abs(hx - up[0]) < hw * 0.8 && Math.abs(hy - up[1]) < hh * 0.8) {
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
            name: housingNames[hi % housingNames.length] + "_" + (hi + 1),
            x: hx,
            y: hy,
            w: hw,
            h: hh,
            d: hd,
            angle: hAngle,
            showHidden: rng.chance(0.6),
            attachCyl: attachCyl,
            attachT: attachT,
            attachX: hx - cx,
            attachY: hy - cy
        };
    }

    // ── Generate pipes (2-6) connecting housings/cylinders ────
    var pipeCount = rng.randInt(2, Math.min(5, housingCount + 1));
    for (var pi = 0; pi < pipeCount; pi++) {
        var pRadius = rng.range(6, 16);
        var pFlangeR = pRadius * rng.range(1.3, 1.6);
        var startPt, endPt;

        if (pi < machine.housings.length && pi + 1 < machine.housings.length) {
            // Connect adjacent housings
            var h1 = machine.housings[pi];
            var h2 = machine.housings[(pi + 1) % machine.housings.length];
            startPt = [h1.x + h1.w, h1.y + h1.h / 2];
            endPt = [h2.x, h2.y + h2.h / 2];
        } else {
            // Connect to random positions on cylinder surface
            var rCyl = machine.cylinders[rng.randInt(0, machine.cylinders.length - 1)];
            var rT = rng.range(0.2, 0.8);
            var rAxRad = rCyl.axisAngle * DEG2RAD;
            var rAxDx = Math.cos(rAxRad) * rCyl.halfLength;
            var rAxDy = Math.sin(rAxRad) * rCyl.halfLength;
            var rBack = [rCyl.cx - rAxDx, rCyl.cy - rAxDy];
            var rFront = [rCyl.cx + rAxDx, rCyl.cy + rAxDy];
            var rPt = axPt(rBack, rFront, rT);

            startPt = [rPt[0] + rng.range(-40, 40), rPt[1] + rng.range(30, 80)];
            endPt = [rPt[0] + rng.range(-100, 100), rPt[1] + rng.range(80, 200)];
        }

        machine.pipes[machine.pipes.length] = {
            name: "pipe_" + (pi + 1),
            startPt: startPt,
            endPt: endPt,
            radius: pRadius,
            flangeRadius: pFlangeR
        };
    }

    // ── Cross-sections (1-2) at cylinder ends ────────────────
    var csCount = rng.randInt(1, 2);
    for (var csi = 0; csi < csCount; csi++) {
        var csCyl = machine.cylinders[csi % machine.cylinders.length];
        // Position at front end
        var csAxRad = csCyl.axisAngle * DEG2RAD;
        var csAxDx = Math.cos(csAxRad) * csCyl.halfLength;
        var csAxDy = Math.sin(csAxRad) * csCyl.halfLength;
        var csFront = [csCyl.cx + csAxDx, csCyl.cy + csAxDy];
        var lastSec = csCyl.sections[csCyl.sections.length - 1];
        var csRadius = lastSec.radiusBottom;

        machine.crossSections[machine.crossSections.length] = {
            name: "section_" + csCyl.name,
            cx: csFront[0],
            cy: csFront[1],
            outerRadius: csRadius,
            innerRadius: csRadius * rng.range(0.25, 0.4),
            rings: rng.randInt(3, 5),
            spokes: rng.randInt(6, 12),
            blades: rng.chance(0.7) ? rng.randInt(8, 16) : 0,
            foreshorten: csCyl.foreshorten
        };
    }

    // ── Antennas (2-4 arrays) above assembly ─────────────────
    var antCount = rng.randInt(2, 4);
    for (var ai = 0; ai < antCount; ai++) {
        var antX = cx + rng.range(-abW * 0.35, abW * 0.35);
        var antY = cy + rng.range(100, 300);
        var mastCount = rng.randInt(2, 5);
        var masts = [];
        for (var mi = 0; mi < mastCount; mi++) {
            masts[masts.length] = {
                height: rng.range(40, 120),
                hasCross: rng.chance(0.6)
            };
        }
        machine.antennas[machine.antennas.length] = {
            name: "antenna_" + (ai + 1),
            baseX: antX,
            baseY: antY,
            masts: masts
        };
    }

    // ── Data panels (3-5) in corners/edges ───────────────────
    var dpCount = rng.randInt(3, 5);
    var corners = [
        { x: 40, y: abH - 40 },           // top-left
        { x: abW - 200, y: abH - 40 },     // top-right
        { x: 40, y: 200 },                  // bottom-left
        { x: abW - 200, y: 200 },           // bottom-right
        { x: abW / 2 - 80, y: abH - 40 }   // top-center
    ];
    for (var di = 0; di < dpCount; di++) {
        var corner = corners[di % corners.length];
        var dpW = rng.range(100, 180);
        var dpH = rng.range(60, 120);
        machine.dataPanels[machine.dataPanels.length] = {
            name: "data_" + (di + 1),
            x: corner.x,
            y: corner.y,
            w: dpW,
            h: dpH,
            scanLines: rng.randInt(6, 16),
            hasGauge: rng.chance(0.4)
        };
    }

    // ── Dimension lines (3-6) on key measurements ────────────
    var dimCount = rng.randInt(3, 6);
    for (var dmi = 0; dmi < dimCount; dmi++) {
        var dimCyl = machine.cylinders[dmi % machine.cylinders.length];
        var dimAxRad = dimCyl.axisAngle * DEG2RAD;
        var dimAxDx = Math.cos(dimAxRad) * dimCyl.halfLength;
        var dimAxDy = Math.sin(dimAxRad) * dimCyl.halfLength;
        var dimBack = [dimCyl.cx - dimAxDx, dimCyl.cy - dimAxDy];
        var dimFront = [dimCyl.cx + dimAxDx, dimCyl.cy + dimAxDy];

        var dimT1 = rng.range(0, 0.4);
        var dimT2 = rng.range(0.6, 1.0);
        machine.dimensions[machine.dimensions.length] = {
            name: "dim_" + (dmi + 1),
            startPt: axPt(dimBack, dimFront, dimT1),
            endPt: axPt(dimBack, dimFront, dimT2),
            offset: rng.range(15, 40) * (rng.chance(0.5) ? 1 : -1)
        };
    }

    return machine;
}
