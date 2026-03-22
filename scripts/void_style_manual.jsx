// void_style_manual.jsx — Instruction Manual Style Preset
// Original orange-on-black technical illustration aesthetic
// Depends on: void_engine_lib.jsx (rgb function must be loaded first)
//
// Traditional engineering drawing feel — single isometric axis,
// warm monochromatic palette, sparse labeling, dashed hidden lines

var STYLE = {
    name: "instruction-manual",

    // ── 5 Functional Color Roles ──
    // Warm monochromatic palette — all colors in the orange family
    palette: {
        bg:         rgb(15, 15, 15),       // #0F0F0F — near-black background
        structural: rgb(255, 102, 0),      // #FF6600 — neon orange primary
        accent:     rgb(232, 115, 74),     // #E8734A — salmon highlight
        secondary:  rgb(212, 98, 59),      // #D4623B — warm detail
        ghost:      rgb(61, 26, 10)        // #3D1A0A — dark brown hidden
    },

    // Higher accent ratio than DR — more color variation within orange family
    accent_ratio: 0.3,

    // ── Single Isometric Axis ──
    // Everything aligned to the same -40° angle — classic technical illustration
    angle_grid: [-40, -40, -40],

    // ── Moderate Density ──
    // Engineering drawings have more white space than graphic posters
    density: 0.5,

    // ── Stroke Weight Hierarchy ──
    strokes: {
        silhouette:   2.5,
        structural:   1.25,
        detail:       0.4,
        hidden:       0.3,
        construction: 0.15
    },

    // Traditional dashed hidden lines
    hidden_line_style: "dashed",

    // Slightly higher foreshorten than DR — deeper perspective
    foreshorten: 0.6,

    // ── Typography Settings ──
    typography: {
        density: "low",       // sparse, functional labels only
        heading_size: 12,
        label_size: 7,
        micro_size: 5,
        system_text: [
            "ENGINEERING.SPEC",
            "ASSEMBLY.GUIDE",
            "PART.NO.",
            "REV.A",
            "SCALE 1:1",
            "MATERIAL.SPEC",
            "TOLERANCE.CLASS.B",
            "SURFACE.FINISH.RA"
        ],
        section_labels: ["SEC.", "STAGE", "MODULE", "ASSY."],
        coord_markers: false,    // no coordinate markers in manual style
        dimension_labels: true   // engineering dimensions always labeled
    },

    // ── Composition Rules ──
    composition: {
        primary_angle: -40,
        secondary_angle: -40,     // same angle — unified direction
        tertiary_angle: -40,
        fill_margin: 0.15,        // more margin — engineering drawing breathing room
        negative_space_fill: false // clean white space, no construction grid overlay
    }
};

// ═══════════════════════════════════════════════════════════════
// STYLE HELPER FUNCTIONS
// Same API as void_style_dr.jsx — interchangeable via concatenation
// ═══════════════════════════════════════════════════════════════

function sCol(role) {
    if (STYLE.palette[role]) return STYLE.palette[role];
    return STYLE.palette.structural;
}

function sSW(role) {
    if (STYLE.strokes[role] !== undefined) return STYLE.strokes[role];
    return STYLE.strokes.detail;
}

function sAccentOrStructural(rng) {
    return rng.chance(STYLE.accent_ratio) ? sCol("accent") : sCol("structural");
}

function sHiddenDash() {
    if (STYLE.hidden_line_style === "ghost") return 0;
    if (STYLE.hidden_line_style === "dashed") return 1;
    if (STYLE.hidden_line_style === "none") return -1;
    return 0;
}

function sEllipseRot(axisAngle) {
    return axisAngle + 90;
}

function sForeshorten() {
    return STYLE.foreshorten;
}

function sSystemText(rng) {
    return rng.pick(STYLE.typography.system_text);
}

function sSectionLabel(rng, index) {
    var labels = STYLE.typography.section_labels;
    var label = labels[index % labels.length];
    var num = (index < 10) ? "0" + index : "" + index;
    return label + num;
}

function sCoordMarker(rng) {
    var n = rng.randInt(10, 99);
    return "00." + n;
}
