// void_style_dr.jsx — Designers Republic Style Preset
// All visual decisions for the DR aesthetic flow from this object
// Depends on: void_engine_lib.jsx (rgb function must be loaded first)
//
// References: Pinterest board synthesis of 11 DR works
// Key invariants: high contrast, black structural, saturated accents,
// geometric sans, asymmetric composition, dense element spacing

var STYLE = {
    name: "designers-republic",

    // ── 5 Functional Color Roles ──
    // Every drawn element maps to exactly one of these roles
    palette: {
        bg:         rgb(15, 15, 15),       // #0F0F0F — near-black background
        structural: rgb(255, 255, 255),    // #FFFFFF — white primary structure
        accent:     rgb(255, 0, 0),        // #FF0000 — pure red punctuation
        secondary:  rgb(128, 128, 128),    // #808080 — grey detail
        ghost:      rgb(42, 42, 42)        // #2A2A2A — barely visible construction
    },

    // Fraction of elements that use accent color instead of structural (0.0–1.0)
    // DR uses red sparingly — it's punctuation, not base color (~5-8% of surface)
    accent_ratio: 0.08,

    // ── Allowed Component Angles (degrees) ──
    // ALL elements must align to one of these — no random skewing
    // Primary: isometric diagonal for main cylinders
    // Secondary: horizontal for housings/connections
    // Tertiary: vertical for typography and accents
    angle_grid: [-30, 0, 90],

    // ── Frame Fill Target (0.0–1.0) ──
    // DR compositions are dense — 85% of frame occupied
    density: 0.85,

    // ── Stroke Weight Hierarchy ──
    // Bold silhouettes vs. hairline detail creates visual depth
    // Ratio: silhouette/construction = 3.0/0.15 = 20:1
    strokes: {
        silhouette:   3.0,    // bold outer contours, defining edges
        structural:   1.5,    // visible edges, section rings, boundaries
        detail:       0.5,    // panel lines, surface texture, ribs
        hidden:       0.25,   // hidden/occluded lines (ghost color)
        construction: 0.15    // grid lines, guidelines, annotations
    },

    // ── Hidden Line Treatment ──
    // "ghost" = very faint solid (DR aesthetic — everything visible but hierarchical)
    // "dashed" = traditional engineering dashed
    // "none" = omit hidden lines entirely
    hidden_line_style: "ghost",

    // ── Ellipse Foreshorten Ratio ──
    // minor_axis = major_axis * foreshorten
    // 0.5 gives moderate depth; lower = flatter/more oblique
    foreshorten: 0.5,

    // ── Typography Settings ──
    typography: {
        density: "high",     // labels everywhere — typography IS the design
        heading_size: 14,    // section headers, system titles
        label_size: 8,       // coordinate markers, dimension values
        micro_size: 5,       // tiny data readouts, serial numbers
        // Text pools for procedural label generation
        system_text: [
            "EXPERIMENTAL.DESIGN.SERIES",
            "VOID.ENGINE.MK",
            "PRESSURE.VESSEL.ASSEMBLY",
            "THERMAL.EXCHANGE.UNIT",
            "FLOW.DYNAMICS.MODULE",
            "STRUCTURAL.INTEGRITY.SYS",
            "SYSTEM.STATUS.NOMINAL",
            "COOLANT.CIRCUIT.PRIMARY",
            "PRIMARY.INTAKE.MANIFOLD",
            "SECONDARY.OUTPUT.STAGE"
        ],
        section_labels: [
            "SEC.", "INTAKE", "COMPRESSOR", "CHAMBER",
            "TURBINE", "EXHAUST", "NOZZLE", "CONDUIT"
        ],
        coord_markers: true,     // 00.XX coordinate labels at intersections
        dimension_labels: true   // measurement annotations on dimension lines
    },

    // ── Composition Rules ──
    composition: {
        primary_angle: -30,       // main cylinder axis (isometric diagonal)
        secondary_angle: 0,       // housings, connections (horizontal)
        tertiary_angle: 90,       // vertical accents, typography alignment
        fill_margin: 0.08,        // 8% margin from artboard edges
        negative_space_fill: true // fill remaining space with construction lines
    }
};

// ═══════════════════════════════════════════════════════════════
// STYLE HELPER FUNCTIONS
// Convenience API for accessing STYLE properties in renderers
// ═══════════════════════════════════════════════════════════════

// Get RGBColor by functional role name
// Roles: "bg", "structural", "accent", "secondary", "ghost"
function sCol(role) {
    if (STYLE.palette[role]) return STYLE.palette[role];
    return STYLE.palette.structural; // safe fallback
}

// Get stroke weight by hierarchy role name
// Roles: "silhouette", "structural", "detail", "hidden", "construction"
function sSW(role) {
    if (STYLE.strokes[role] !== undefined) return STYLE.strokes[role];
    return STYLE.strokes.detail; // safe fallback
}

// Decide accent vs structural color using PRNG
// Maintains consistent per-seed coloring — same seed = same accent placement
function sAccentOrStructural(rng) {
    return rng.chance(STYLE.accent_ratio) ? sCol("accent") : sCol("structural");
}

// Get dash type for hidden lines based on style setting
// Returns: 0 (solid/ghost), 1 (dashed), or -1 (none/skip)
function sHiddenDash() {
    if (STYLE.hidden_line_style === "ghost") return 0;
    if (STYLE.hidden_line_style === "dashed") return 1;
    if (STYLE.hidden_line_style === "none") return -1;
    return 0;
}

// Compute ellipse rotation angle for a cylinder at given axis angle
// Ellipses are always perpendicular to the cylinder axis
function sEllipseRot(axisAngle) {
    return axisAngle + 90;
}

// Get the foreshorten ratio from style
function sForeshorten() {
    return STYLE.foreshorten;
}

// Pick a random text from the system text pool
function sSystemText(rng) {
    return rng.pick(STYLE.typography.system_text);
}

// Pick a random section label
function sSectionLabel(rng, index) {
    var labels = STYLE.typography.section_labels;
    var label = labels[index % labels.length];
    // Add numeric suffix: SEC.01, INTAKE.03, etc.
    var num = (index < 10) ? "0" + index : "" + index;
    return label + num;
}

// Generate a coordinate marker string: "00.XX"
function sCoordMarker(rng) {
    var n = rng.randInt(10, 99);
    return "00." + n;
}
