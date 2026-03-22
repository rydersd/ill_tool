// void_v3_compose.jsx — Define machine geometry in 3D space
// All coordinates in 3D: X = right, Y = up, Z = toward viewer

function composeMachine3D(seed) {
    var rng = PRNG(seed);
    var m = { seed: seed, cylinders: [], housings: [], pipes: [], crossSections: [], tubes: [] };

    // ── Main cylinder axis: runs diagonally in 3D space ──
    // axis direction roughly (1, 0.15, 0.5) → projects nicely in isometric
    var mainDir = v3norm([1.0, 0.15, 0.4]);
    var mainLen = rng.range(600, 900);
    var mainStart = v3scale(mainDir, -mainLen / 2);  // centered at origin

    // Generate sections along main cylinder
    var secCount = rng.randInt(4, 6);
    var baseR = rng.range(80, 130);
    var sections = [];
    var prevR = baseR * rng.range(0.5, 0.7);  // tapered intake
    for (var si = 0; si < secCount; si++) {
        var tS = (si / secCount) * mainLen;
        var tE = ((si + 1) / secCount) * mainLen;
        var nextR = (si === secCount - 1)
            ? prevR * rng.range(0.5, 0.7)  // tapered exhaust
            : prevR + rng.gaussian(0, 10);
        nextR = Math.max(baseR * 0.4, Math.min(baseR * 1.4, nextR));
        sections[sections.length] = { tStart: tS, tEnd: tE, rStart: prevR, rEnd: nextR, name: "sec_" + si };
        prevR = nextR;
    }
    m.cylinders[0] = { name: "main", start: mainStart, dir: mainDir, length: mainLen, sections: sections };

    // ── Secondary cylinder: offset and at different angle ──
    var sec2Dir = v3norm([rng.range(0.8, 1.2), rng.range(-0.3, 0.3), rng.range(0.2, 0.8)]);
    var sec2Len = rng.range(350, 550);
    var sec2Off = v3add(v3scale(mainDir, mainLen * rng.range(-0.1, 0.2)), [rng.range(-80, 80), rng.range(-60, 60), rng.range(-60, 60)]);
    var sec2Start = v3add(sec2Off, v3scale(sec2Dir, -sec2Len / 2));
    var sec2BaseR = rng.range(50, 90);
    var sec2Secs = [];
    var sec2PrevR = sec2BaseR * 0.6;
    var sec2SecCount = rng.randInt(3, 5);
    for (var s2i = 0; s2i < sec2SecCount; s2i++) {
        var s2tS = (s2i / sec2SecCount) * sec2Len;
        var s2tE = ((s2i + 1) / sec2SecCount) * sec2Len;
        var s2nextR = (s2i === sec2SecCount - 1) ? sec2PrevR * 0.6 : sec2PrevR + rng.gaussian(0, 8);
        s2nextR = Math.max(sec2BaseR * 0.4, Math.min(sec2BaseR * 1.3, s2nextR));
        sec2Secs[sec2Secs.length] = { tStart: s2tS, tEnd: s2tE, rStart: sec2PrevR, rEnd: s2nextR, name: "s2_" + s2i };
        sec2PrevR = s2nextR;
    }
    m.cylinders[1] = { name: "secondary", start: sec2Start, dir: sec2Dir, length: sec2Len, sections: sec2Secs };

    // ── Parallel tubes running along main cylinder body ──
    var tubeCount = rng.randInt(2, 4);
    var mainBasis = perpBasis(mainDir);
    for (var ti = 0; ti < tubeCount; ti++) {
        var tubeAngle = (2 * Math.PI / tubeCount) * ti + rng.range(0, 0.5);
        var tubeOff = rng.range(baseR * 1.1, baseR * 1.5);
        var tubeR = rng.range(8, 18);
        var offset = v3add(v3scale(mainBasis.u, tubeOff * Math.cos(tubeAngle)), v3scale(mainBasis.v, tubeOff * Math.sin(tubeAngle)));
        // Tube runs parallel to main cylinder, slightly shorter
        var tStart = rng.range(0.05, 0.2);
        var tEnd = rng.range(0.8, 0.95);
        var tubeStart = v3add(v3add(mainStart, v3scale(mainDir, mainLen * tStart)), offset);
        var tubeEnd = v3add(v3add(mainStart, v3scale(mainDir, mainLen * tEnd)), offset);
        m.tubes[m.tubes.length] = { name: "tube_" + ti, start: tubeStart, end: tubeEnd, radius: tubeR, flangeR: tubeR * 1.4 };
    }

    // ── Housings: 3D boxes attached to cylinder surface ──
    var housingCount = rng.randInt(2, 4);
    for (var hi = 0; hi < housingCount; hi++) {
        var hAttachT = rng.range(0.2, 0.8);
        var hCenter = v3add(mainStart, v3scale(mainDir, mainLen * hAttachT));
        // Get the cylinder radius at attachment point
        var hSecIdx = Math.floor(hAttachT * sections.length);
        if (hSecIdx >= sections.length) hSecIdx = sections.length - 1;
        var hSecR = (sections[hSecIdx].rStart + sections[hSecIdx].rEnd) / 2;

        // Place housing on surface of cylinder
        var hAngle = rng.range(0, 2 * Math.PI);
        var hSurfaceOff = v3add(v3scale(mainBasis.u, hSecR * Math.cos(hAngle)), v3scale(mainBasis.v, hSecR * Math.sin(hAngle)));
        var hOrigin = v3add(hCenter, hSurfaceOff);

        // Box edges aligned with isometric axes (so they sit on correct planes)
        var hW = rng.range(30, 70);
        var hH = rng.range(25, 55);
        var hD = rng.range(20, 40);
        // Use the surface normal direction for depth, world Y for height, and axis tangent for width
        var hNorm = v3norm(hSurfaceOff);
        var hUp = [0, 1, 0];
        var hRight = v3norm(v3cross(hUp, hNorm));
        if (v3len(hRight) < 0.01) hRight = v3norm(v3cross([0, 0, 1], hNorm));

        m.housings[m.housings.length] = {
            name: "housing_" + hi,
            origin: hOrigin,
            edgeX: v3scale(hRight, hW),
            edgeY: v3scale(hUp, hH),
            edgeZ: v3scale(hNorm, hD)
        };
    }

    // ── Pipes connecting components ──
    var pipeCount = rng.randInt(2, 4);
    for (var pi = 0; pi < pipeCount; pi++) {
        var pR = rng.range(6, 14);
        var pStart, pEnd;
        if (pi < m.housings.length) {
            // Connect housing to a point on secondary cylinder
            var h = m.housings[pi];
            pStart = v3add(h.origin, v3scale(h.edgeY, 0.5));
            var pEndT = rng.range(0.2, 0.8);
            pEnd = v3add(sec2Start, v3scale(sec2Dir, sec2Len * pEndT));
            pEnd = v3add(pEnd, [0, rng.range(20, 60), 0]);
        } else {
            // Connect between random points
            var pt1 = rng.range(0.1, 0.4) * mainLen;
            var pt2 = rng.range(0.6, 0.9) * mainLen;
            pStart = v3add(mainStart, v3scale(mainDir, pt1));
            pStart = v3add(pStart, v3add(v3scale(mainBasis.u, baseR * 1.2), [0, rng.range(-30, 30), 0]));
            pEnd = v3add(mainStart, v3scale(mainDir, pt2));
            pEnd = v3add(pEnd, v3add(v3scale(mainBasis.v, baseR * 1.2), [0, rng.range(-30, 30), 0]));
        }
        m.pipes[m.pipes.length] = { name: "pipe_" + pi, start: pStart, end: pEnd, radius: pR, flangeR: pR * 1.5 };
    }

    // ── Cross-section at main cylinder front end ──
    var csEnd = v3add(mainStart, v3scale(mainDir, mainLen));
    var lastSec = sections[sections.length - 1];
    m.crossSections[0] = {
        name: "section_main",
        center: csEnd,
        radius: lastSec.rEnd,
        axis: [mainDir[0], mainDir[1], mainDir[2]],
        rings: rng.randInt(3, 5),
        spokes: rng.randInt(6, 10),
        blades: rng.chance(0.7) ? rng.randInt(8, 14) : 0
    };

    return m;
}
