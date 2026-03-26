"""Illustrator-specific input models."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AiNewDocInput(BaseModel):
    """Create new Illustrator document."""
    model_config = ConfigDict(str_strip_whitespace=True)
    width: float = Field(default=800, description="Width in points", ge=1)
    height: float = Field(default=600, description="Height in points", ge=1)
    name: str = Field(default="Untitled", description="Document name")
    color_mode: Optional[str] = Field(default="RGB", description="RGB or CMYK")
    artboard_count: int = Field(default=1, description="Number of artboards", ge=1, le=1000)


class AiShapeInput(BaseModel):
    """Create shapes in Illustrator."""
    model_config = ConfigDict(str_strip_whitespace=True)
    shape: str = Field(..., description="Shape: rectangle, ellipse, polygon, star, line, arc, spiral")
    x: float = Field(default=0, description="X position")
    y: float = Field(default=0, description="Y position")
    width: Optional[float] = Field(default=100, description="Width")
    height: Optional[float] = Field(default=100, description="Height")
    sides: Optional[int] = Field(default=5, description="Sides for polygon")
    points: Optional[int] = Field(default=5, description="Points for star")
    fill_r: Optional[int] = Field(default=None, ge=0, le=255, description="Fill red")
    fill_g: Optional[int] = Field(default=None, ge=0, le=255, description="Fill green")
    fill_b: Optional[int] = Field(default=None, ge=0, le=255, description="Fill blue")
    stroke_r: Optional[int] = Field(default=0, ge=0, le=255, description="Stroke red")
    stroke_g: Optional[int] = Field(default=0, ge=0, le=255, description="Stroke green")
    stroke_b: Optional[int] = Field(default=0, ge=0, le=255, description="Stroke blue")
    stroke_width: Optional[float] = Field(default=1, description="Stroke width", ge=0)


class AiTextInput(BaseModel):
    """Add text in Illustrator."""
    model_config = ConfigDict(str_strip_whitespace=True)
    text: str = Field(..., description="Text content")
    x: float = Field(default=0, description="X position")
    y: float = Field(default=0, description="Y position")
    font: Optional[str] = Field(default="ArialMT", description="Font name")
    size: Optional[float] = Field(default=24, description="Font size in points")
    color_r: Optional[int] = Field(default=0, ge=0, le=255)
    color_g: Optional[int] = Field(default=0, ge=0, le=255)
    color_b: Optional[int] = Field(default=0, ge=0, le=255)


class AiPathInput(BaseModel):
    """Create/manipulate paths in Illustrator."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: create, join, offset, simplify, smooth, outline_stroke, expand, compound")
    points: Optional[str] = Field(default=None, description="JSON array of [x,y] points for create action")
    closed: bool = Field(default=False, description="Close the path")
    fill_r: Optional[int] = Field(default=None, ge=0, le=255)
    fill_g: Optional[int] = Field(default=None, ge=0, le=255)
    fill_b: Optional[int] = Field(default=None, ge=0, le=255)
    stroke_width: Optional[float] = Field(default=1, ge=0)


class AiExportInput(BaseModel):
    """Export Illustrator document."""
    model_config = ConfigDict(str_strip_whitespace=True)
    file_path: str = Field(..., description="Output file path")
    format: str = Field(default="svg", description="Format: svg, png, pdf, eps, ai, jpg")
    artboard_index: Optional[int] = Field(default=None, description="Specific artboard to export")
    scale: Optional[float] = Field(default=1.0, description="Export scale factor")


class AiInspectInput(BaseModel):
    """Inspect Illustrator document — list items, layers, artboards, get details."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: list_all, list_layers, get_item, get_selection, get_artboards")
    name: Optional[str] = Field(default=None, description="Item name for get_item action")
    index: Optional[int] = Field(default=None, description="Item index for get_item action (0-based)")
    offset: Optional[int] = Field(default=0, description="Pagination offset for list_all", ge=0)
    limit: Optional[int] = Field(default=100, description="Max items to return for list_all", ge=1, le=500)


class AiModifyInput(BaseModel):
    """Modify existing Illustrator objects — move, resize, recolor, rename, delete, etc."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: select, move, resize, rotate, recolor_fill, recolor_stroke, rename, delete, opacity, arrange, duplicate, group, ungroup")
    name: Optional[str] = Field(default=None, description="Target item name (uses getByName)")
    index: Optional[int] = Field(default=None, description="Target item index (0-based, for unnamed items)")
    # Move params
    x: Optional[float] = Field(default=None, description="Absolute X position or delta X for move")
    y: Optional[float] = Field(default=None, description="Absolute Y position or delta Y for move")
    absolute: bool = Field(default=True, description="If true, x/y are absolute position; if false, they are deltas")
    # Resize params
    scale_x: Optional[float] = Field(default=None, description="Horizontal scale percentage for resize (100 = no change)", ge=1)
    scale_y: Optional[float] = Field(default=None, description="Vertical scale percentage for resize (100 = no change)", ge=1)
    # Rotate params
    angle: Optional[float] = Field(default=None, description="Rotation angle in degrees")
    # Color params
    fill_r: Optional[int] = Field(default=None, ge=0, le=255, description="Fill red (0-255)")
    fill_g: Optional[int] = Field(default=None, ge=0, le=255, description="Fill green (0-255)")
    fill_b: Optional[int] = Field(default=None, ge=0, le=255, description="Fill blue (0-255)")
    stroke_r: Optional[int] = Field(default=None, ge=0, le=255, description="Stroke red (0-255)")
    stroke_g: Optional[int] = Field(default=None, ge=0, le=255, description="Stroke green (0-255)")
    stroke_b: Optional[int] = Field(default=None, ge=0, le=255, description="Stroke blue (0-255)")
    stroke_width: Optional[float] = Field(default=None, ge=0, description="Stroke width in points")
    # Other params
    new_name: Optional[str] = Field(default=None, description="New name for rename action")
    opacity: Optional[float] = Field(default=None, ge=0, le=100, description="Opacity 0-100")
    arrange: Optional[str] = Field(default=None, description="Z-order: bring_to_front, bring_forward, send_backward, send_to_back")
    items: Optional[str] = Field(default=None, description="Comma-separated item names for group action")


class AiLayerInput(BaseModel):
    """Manage Illustrator layers — list, create, delete, rename, show, hide, lock, unlock, reorder."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: list, create, delete, rename, show, hide, lock, unlock, reorder")
    name: Optional[str] = Field(default=None, description="Layer name (for targeting existing layer)")
    new_name: Optional[str] = Field(default=None, description="New name for create/rename")
    target: Optional[str] = Field(default=None, description="Target layer name for reorder (place before this layer)")


class AiImageTraceInput(BaseModel):
    """Trace a raster image to vector paths in Illustrator."""
    model_config = ConfigDict(str_strip_whitespace=True)
    image_path: str = Field(..., description="Absolute path to PNG/JPG image file")
    preset: str = Field(
        default="6 Colors",
        description=(
            "Trace preset: '3 Colors', '6 Colors', '16 Colors', "
            "'High Fidelity Photo', 'Low Fidelity Photo', "
            "'Black and White Logo', 'Shades of Gray', "
            "'Silhouettes', 'Line Art', 'Technical Drawing'"
        ),
    )
    max_colors: Optional[int] = Field(
        default=None, description="Override preset max colors (2-256)", ge=2, le=256
    )
    expand: bool = Field(default=True, description="Expand trace to editable vector paths")
    recolor_to_dna: bool = Field(
        default=False,
        description="Recolor traced paths to current design token palette",
    )
    layer_name: Optional[str] = Field(default="traced", description="Name for the result group/layer")
    x: Optional[float] = Field(default=None, description="X position after tracing")
    y: Optional[float] = Field(default=None, description="Y position after tracing")


class AiAnalyzeReferenceInput(BaseModel):
    """Analyze a reference image for geometric form — returns measured shapes, not guesses."""
    model_config = ConfigDict(str_strip_whitespace=True)
    image_path: str = Field(..., description="Absolute path to reference PNG/JPG image")
    min_area_pct: float = Field(default=0.5, description="Ignore contours smaller than this % of image area", ge=0.01, le=50)
    max_contours: int = Field(default=20, description="Maximum number of shapes to return", ge=1, le=100)
    canny_low: int = Field(default=50, description="Canny edge detection low threshold", ge=1, le=255)
    canny_high: int = Field(default=150, description="Canny edge detection high threshold", ge=1, le=255)
    multi_scale: bool = Field(default=False, description="Run at 3 Canny thresholds and merge results with scale tags (bold/medium/fine)")
    decompose: bool = Field(default=False, description="Use RETR_TREE to detect parent-child nesting, suggest layer structure and z-order")


class AiReferenceUnderlayInput(BaseModel):
    """Place a reference image as a locked background layer in Illustrator for tracing."""
    model_config = ConfigDict(str_strip_whitespace=True)
    image_path: str = Field(..., description="Absolute path to reference PNG/JPG image")
    opacity: float = Field(default=40, description="Reference layer opacity 0-100", ge=0, le=100)
    fit_to_artboard: bool = Field(default=True, description="Scale image to fit current artboard")
    drawing_layer_name: str = Field(default="Drawing", description="Name for the active drawing layer above reference")


class AiVtraceInput(BaseModel):
    """Trace a raster image to clean vector paths using vtracer (better than Image Trace for cartoon/graphic art)."""
    model_config = ConfigDict(str_strip_whitespace=True)
    image_path: str = Field(..., description="Absolute path to PNG/JPG image")
    mode: str = Field(default="polygon", description="Tracing mode: polygon or spline")
    color_precision: int = Field(default=6, description="Color quantization precision 1-8 (lower = fewer colors)", ge=1, le=8)
    filter_speckle: int = Field(default=4, description="Remove artifacts smaller than this many pixels", ge=0, le=100)
    corner_threshold: int = Field(default=60, description="Angle threshold for corner detection (degrees)", ge=0, le=180)
    path_precision: int = Field(default=3, description="Decimal places in SVG path coordinates", ge=1, le=8)
    place_in_ai: bool = Field(default=False, description="Place resulting paths directly in Illustrator")
    layer_name: str = Field(default="vtrace", description="Layer name when placing in Illustrator")


class AiAutoCorrectInput(BaseModel):
    """Closed-loop correction: compare drawing vs reference and apply anchor point adjustments automatically."""
    model_config = ConfigDict(str_strip_whitespace=True)
    reference_path: str = Field(..., description="Absolute path to reference PNG/JPG image")
    drawing_layer: str = Field(default="Drawing", description="Layer containing the drawing to correct")
    max_iterations: int = Field(default=1, description="Number of correction passes per call", ge=1, le=5)
    convergence_target: float = Field(default=0.85, description="Stop correcting when convergence exceeds this", ge=0, le=1)
    min_area_pct: float = Field(default=0.5, description="Ignore contours smaller than this % of image area", ge=0.01, le=50)
    correction_strength: float = Field(default=0.5, description="Damping factor 0-1 (1=full correction, 0.5=half step to avoid overshoot)", ge=0.1, le=1.0)


class AiAnchorEditInput(BaseModel):
    """Get or set individual anchor points and bezier handles on pathItems."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: get_points, set_point, set_handles, add_point, remove_point, simplify")
    name: Optional[str] = Field(default=None, description="Target pathItem name (uses getByName)")
    index: Optional[int] = Field(default=None, description="Target pathItem index (0-based, for unnamed items)")
    point_index: Optional[int] = Field(default=None, description="Anchor point index for set_point/set_handles/remove_point (0-based)")
    x: Optional[float] = Field(default=None, description="New X coordinate for set_point or add_point")
    y: Optional[float] = Field(default=None, description="New Y coordinate for set_point or add_point")
    left_x: Optional[float] = Field(default=None, description="Left bezier handle X for set_handles")
    left_y: Optional[float] = Field(default=None, description="Left bezier handle Y for set_handles")
    right_x: Optional[float] = Field(default=None, description="Right bezier handle X for set_handles")
    right_y: Optional[float] = Field(default=None, description="Right bezier handle Y for set_handles")
    tolerance: Optional[float] = Field(default=2.0, description="Simplification tolerance in points (for simplify action)", ge=0.1, le=50)


class AiProportionGridInput(BaseModel):
    """Place a measurement grid on the artboard based on reference analysis or manual key positions."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="from_manifest", description="Action: from_manifest (auto from shape data), manual (from positions), clear (remove grid)")
    shape_manifest: Optional[str] = Field(default=None, description="JSON shape manifest from analyze_reference (for from_manifest action)")
    h_positions: Optional[str] = Field(default=None, description="JSON array of Y positions as % of artboard height for manual horizontal guides")
    v_positions: Optional[str] = Field(default=None, description="JSON array of X positions as % of artboard width for manual vertical guides")
    show_bounding_boxes: bool = Field(default=True, description="Draw bounding rectangles for each shape in the manifest")
    grid_opacity: float = Field(default=30, description="Grid layer opacity 0-100", ge=0, le=100)


class AiSilhouetteInput(BaseModel):
    """Extract the overall silhouette from a reference image as a single clean closed path."""
    model_config = ConfigDict(str_strip_whitespace=True)
    image_path: str = Field(..., description="Absolute path to reference PNG/JPG image")
    simplification: float = Field(default=0.01, description="approxPolyDP epsilon as fraction of arc length (lower=more points, higher=simpler)", ge=0.001, le=0.1)
    place_in_ai: bool = Field(default=True, description="Place the silhouette path in Illustrator")
    layer_name: str = Field(default="Drawing", description="Layer to place the silhouette on")
    stroke_width: float = Field(default=2.0, description="Stroke width for the placed path", ge=0.1)


class AiStyleTransferInput(BaseModel):
    """Copy visual style (stroke, fill, opacity, effects) from one pathItem to others."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="transfer", description="Action: transfer (copy style), extract (get style JSON), apply (apply style JSON)")
    source_name: Optional[str] = Field(default=None, description="Source pathItem name to extract style from (for transfer/extract)")
    target_names: Optional[str] = Field(default=None, description="Comma-separated target pathItem names (for transfer/apply)")
    style_json: Optional[str] = Field(default=None, description="JSON style spec for apply action")


class AiContourToPathInput(BaseModel):
    """Create an Illustrator path from an analyze_reference shape manifest entry."""
    model_config = ConfigDict(str_strip_whitespace=True)
    shape_json: str = Field(..., description="JSON object of a single shape from analyze_reference manifest (with approx_points, center, etc.)")
    image_size: Optional[str] = Field(default=None, description="JSON [width, height] of the source image for coordinate transform")
    path_name: str = Field(default="shape", description="Name for the created path")
    layer_name: str = Field(default="Drawing", description="Target layer")
    closed: bool = Field(default=True, description="Close the path")
    stroke_width: float = Field(default=2.0, description="Stroke width", ge=0.1)
    smooth: bool = Field(default=False, description="Auto-smooth corners to curves after placement")


class AiBezierOptimizeInput(BaseModel):
    """Smooth a jagged polygon path into clean bezier curves while preserving shape fidelity."""
    model_config = ConfigDict(str_strip_whitespace=True)
    name: Optional[str] = Field(default=None, description="Target pathItem name")
    index: Optional[int] = Field(default=None, description="Target pathItem index (0-based)")
    smoothness: float = Field(default=50, description="Smoothness 0-100 (0=keep corners, 100=maximum smoothing)", ge=0, le=100)
    preserve_corners: bool = Field(default=True, description="Keep sharp corners sharp (angle threshold)")
    corner_angle: float = Field(default=60, description="Angle below which a point is considered a corner (degrees)", ge=0, le=180)


class AiPathBooleanInput(BaseModel):
    """Pathfinder boolean operations — unite, subtract, intersect, divide paths."""
    model_config = ConfigDict(str_strip_whitespace=True)
    operation: str = Field(..., description="Operation: unite, minus_front, minus_back, intersect, exclude, divide")
    front_name: Optional[str] = Field(default=None, description="Front pathItem name")
    back_name: Optional[str] = Field(default=None, description="Back pathItem name")
    result_name: str = Field(default="boolean_result", description="Name for the resulting path")


class AiSmartShapeInput(BaseModel):
    """Create a shape from high-level description — type, center, dimensions, rotation."""
    model_config = ConfigDict(str_strip_whitespace=True)
    shape_type: str = Field(..., description="Shape: hexagon, pentagon, triangle, rectangle, ellipse, star, polygon")
    center_x: float = Field(..., description="Center X position in AI coordinates")
    center_y: float = Field(..., description="Center Y position in AI coordinates")
    width: float = Field(..., description="Width in points")
    height: float = Field(..., description="Height in points")
    rotation: float = Field(default=0, description="Rotation in degrees (positive = counterclockwise)")
    sides: int = Field(default=6, description="Number of sides for polygon shapes", ge=3, le=36)
    name: str = Field(default="smart_shape", description="Name for the created shape")
    layer_name: str = Field(default="Drawing", description="Target layer")
    stroke_width: float = Field(default=2.0, description="Stroke width", ge=0.1)


class AiArtboardFromRefInput(BaseModel):
    """Create or resize artboard to match reference image aspect ratio."""
    model_config = ConfigDict(str_strip_whitespace=True)
    image_path: str = Field(..., description="Absolute path to reference image")
    target_width: float = Field(default=800, description="Target artboard width in points", ge=72)
    margin: float = Field(default=0, description="Margin around the image area in points", ge=0)


class AiCurveFitInput(BaseModel):
    """Fit smooth cubic bezier curves through a path's anchor points using least-squares optimization."""
    model_config = ConfigDict(str_strip_whitespace=True)
    name: Optional[str] = Field(default=None, description="Target pathItem name")
    index: Optional[int] = Field(default=None, description="Target pathItem index (0-based)")
    error_threshold: float = Field(default=2.0, description="Max allowed deviation from original points in pts", ge=0.1, le=50)
    max_segments: Optional[int] = Field(default=None, description="Max bezier segments (None=auto)")


class AiLayerAutoOrganizeInput(BaseModel):
    """Auto-sort paths into named layers based on spatial position and decomposition hierarchy."""
    model_config = ConfigDict(str_strip_whitespace=True)
    source_layer: str = Field(default="Drawing", description="Layer containing paths to organize")
    strategy: str = Field(default="spatial", description="Strategy: spatial (by Y position), hierarchy (by containment), manifest (from shape manifest)")
    shape_manifest: Optional[str] = Field(default=None, description="JSON shape manifest with decomposition for manifest strategy")
    prefix: str = Field(default="", description="Prefix for created layer names")


class AiSymmetryInput(BaseModel):
    """Mirror/reflect a path across an axis."""
    model_config = ConfigDict(str_strip_whitespace=True)
    name: Optional[str] = Field(default=None, description="Source pathItem name to mirror")
    index: Optional[int] = Field(default=None, description="Source pathItem index (0-based)")
    axis: str = Field(default="vertical", description="Mirror axis: vertical (left-right), horizontal (top-bottom)")
    axis_position: Optional[float] = Field(default=None, description="Axis position in pts (None=center of artboard)")
    duplicate: bool = Field(default=True, description="Create a mirrored copy (True) or mirror in place (False)")
    mirror_name: str = Field(default="", description="Name for the mirrored copy (auto-generated if empty)")


class AiColorSamplerInput(BaseModel):
    """Sample RGB color values from a reference image at specific positions."""
    model_config = ConfigDict(str_strip_whitespace=True)
    image_path: str = Field(..., description="Absolute path to reference image")
    positions: str = Field(..., description="JSON array of [x,y] pixel positions to sample, or 'grid' for auto-grid sampling")
    radius: int = Field(default=3, description="Averaging radius around each sample point in pixels", ge=0, le=20)


class AiStrokeProfileInput(BaseModel):
    """Apply variable-width stroke profiles to paths for expressive line art."""
    model_config = ConfigDict(str_strip_whitespace=True)
    name: Optional[str] = Field(default=None, description="Target pathItem name")
    index: Optional[int] = Field(default=None, description="Target pathItem index (0-based)")
    profile: str = Field(default="taper", description="Profile: taper (thick→thin), swell (thin→thick→thin), pressure (variable), uniform")
    min_width: float = Field(default=0.5, description="Minimum stroke width in points", ge=0.1)
    max_width: float = Field(default=4.0, description="Maximum stroke width in points", ge=0.1)


class AiPathOffsetInput(BaseModel):
    """Create offset/parallel path at a specified distance."""
    model_config = ConfigDict(str_strip_whitespace=True)
    name: Optional[str] = Field(default=None, description="Source pathItem name")
    index: Optional[int] = Field(default=None, description="Source pathItem index (0-based)")
    offset: float = Field(..., description="Offset distance in points (positive=outward, negative=inward)")
    joins: str = Field(default="miter", description="Join style: miter, round, bevel")
    result_name: str = Field(default="offset_path", description="Name for the offset path")


class AiGroupAndNameInput(BaseModel):
    """Auto-group paths by spatial proximity and name groups by body region."""
    model_config = ConfigDict(str_strip_whitespace=True)
    source_layer: str = Field(default="Drawing", description="Layer containing paths to group")
    proximity_threshold: float = Field(default=50, description="Max distance between path centers to group together (points)", ge=1)
    shape_manifest: Optional[str] = Field(default=None, description="JSON shape manifest for informed naming")


class AiPathWeldInput(BaseModel):
    """Join adjacent path endpoints into continuous paths."""
    model_config = ConfigDict(str_strip_whitespace=True)
    names: Optional[str] = Field(default=None, description="Comma-separated pathItem names to consider for welding")
    layer_name: str = Field(default="Drawing", description="Layer to search for paths")
    tolerance: float = Field(default=5.0, description="Max distance between endpoints to weld (points)", ge=0.1)
    result_name: str = Field(default="welded_path", description="Name for welded result")


class AiSnapToGridInput(BaseModel):
    """Snap anchor points to the nearest proportion grid positions."""
    model_config = ConfigDict(str_strip_whitespace=True)
    name: Optional[str] = Field(default=None, description="Target pathItem name (None=all on layer)")
    layer_name: str = Field(default="Drawing", description="Layer to process")
    snap_distance: float = Field(default=5.0, description="Max distance to snap (points)", ge=0.5, le=50)
    grid_spacing: Optional[float] = Field(default=None, description="Grid spacing in points (None=use proportion grid positions)")


class AiUndoCheckpointInput(BaseModel):
    """Save or restore named snapshots of the drawing state."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: save, restore, list, delete")
    checkpoint_name: str = Field(default="auto", description="Name for the checkpoint")
    layer_name: str = Field(default="Drawing", description="Layer to snapshot/restore")


class AiReferenceCropInput(BaseModel):
    """Crop and re-analyze a specific region of the reference image at higher detail."""
    model_config = ConfigDict(str_strip_whitespace=True)
    image_path: str = Field(..., description="Absolute path to reference image")
    x: int = Field(..., description="Crop region left X in pixels")
    y: int = Field(..., description="Crop region top Y in pixels")
    width: int = Field(..., description="Crop region width in pixels", ge=10)
    height: int = Field(..., description="Crop region height in pixels", ge=10)
    min_area_pct: float = Field(default=0.3, description="Min contour area % (lower for detail regions)", ge=0.01)
    save_crop: bool = Field(default=True, description="Save cropped image for reference")


# ── Character Rigging & Posing Models ──────────────────────────


class AiSkeletonAnnotateInput(BaseModel):
    """Mark joint positions on a character for skeleton-based posing."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="add", description="Action: add (mark joint), list (show all joints), remove, clear, auto_detect (estimate joints from contour analysis)")
    joint_name: Optional[str] = Field(default=None, description="Joint name: head, neck, shoulder_l, shoulder_r, elbow_l, elbow_r, wrist_l, wrist_r, hip_l, hip_r, knee_l, knee_r, ankle_l, ankle_r, spine_top, spine_mid, spine_base")
    x: Optional[float] = Field(default=None, description="Joint X position in AI coordinates")
    y: Optional[float] = Field(default=None, description="Joint Y position in AI coordinates")
    image_path: Optional[str] = Field(default=None, description="Reference image for auto_detect action")
    character_name: str = Field(default="character", description="Character identifier for multi-character scenes")


class AiBodyPartLabelInput(BaseModel):
    """Assign semantic body part labels to path groups."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="label", description="Action: label (assign label to item/group), auto_label (infer from skeleton positions), list (show current labels)")
    item_name: Optional[str] = Field(default=None, description="pathItem or group name to label")
    body_part: Optional[str] = Field(default=None, description="Body part: head, torso, upper_arm_l, upper_arm_r, forearm_l, forearm_r, hand_l, hand_r, upper_leg_l, upper_leg_r, lower_leg_l, lower_leg_r, foot_l, foot_r")
    character_name: str = Field(default="character", description="Character identifier")


class AiSkeletonBuildInput(BaseModel):
    """Create a connected bone structure from annotated joints."""
    model_config = ConfigDict(str_strip_whitespace=True)
    character_name: str = Field(default="character", description="Character to build skeleton for")
    preset: str = Field(default="biped", description="Skeleton preset: biped, quadruped, custom")
    show_bones: bool = Field(default=True, description="Draw bone visualization on a Skeleton layer")
    bone_color_r: int = Field(default=0, ge=0, le=255)
    bone_color_g: int = Field(default=200, ge=0, le=255)
    bone_color_b: int = Field(default=100, ge=0, le=255)


class AiPartBindInput(BaseModel):
    """Bind path groups to skeleton bones for pose-driven deformation."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="bind", description="Action: bind (associate part to bone), unbind, auto_bind (infer from proximity), list")
    part_name: Optional[str] = Field(default=None, description="Body part label or group name")
    bone_name: Optional[str] = Field(default=None, description="Bone name (e.g. upper_arm_l, torso)")
    character_name: str = Field(default="character", description="Character identifier")


class AiJointRotateInput(BaseModel):
    """Rotate a body part and its children around a joint pivot point."""
    model_config = ConfigDict(str_strip_whitespace=True)
    joint_name: str = Field(..., description="Joint to rotate around (e.g. shoulder_l, elbow_r, hip_l)")
    angle: float = Field(..., description="Rotation angle in degrees (positive=counterclockwise)")
    character_name: str = Field(default="character", description="Character identifier")
    cascade: bool = Field(default=True, description="Also rotate child joints and their bound parts")


class AiPoseSnapshotInput(BaseModel):
    """Capture or apply a named pose (all joint angles)."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: capture (save current pose), apply (set pose), list, delete")
    pose_name: str = Field(default="pose_1", description="Name for the pose")
    character_name: str = Field(default="character", description="Character identifier")


class AiPoseInterpolateInput(BaseModel):
    """Interpolate between two saved poses to create in-between frames."""
    model_config = ConfigDict(str_strip_whitespace=True)
    pose_a: str = Field(..., description="Start pose name")
    pose_b: str = Field(..., description="End pose name")
    t: float = Field(default=0.5, description="Interpolation factor 0.0-1.0 (0=pose_a, 1=pose_b)", ge=0, le=1)
    character_name: str = Field(default="character", description="Character identifier")
    apply: bool = Field(default=True, description="Apply the interpolated pose immediately")


class AiIKSolverInput(BaseModel):
    """Inverse kinematics — move an end effector (hand/foot) and compute joint angles."""
    model_config = ConfigDict(str_strip_whitespace=True)
    end_effector: str = Field(..., description="End joint to position: wrist_l, wrist_r, ankle_l, ankle_r")
    target_x: float = Field(..., description="Target X position in AI coordinates")
    target_y: float = Field(..., description="Target Y position in AI coordinates")
    character_name: str = Field(default="character", description="Character identifier")
    apply: bool = Field(default=True, description="Apply the solution immediately")


class AiOnionSkinInput(BaseModel):
    """Show ghost frames of adjacent poses for animation planning."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="show", description="Action: show (create onion skin), clear (remove)")
    pose_names: Optional[str] = Field(default=None, description="Comma-separated pose names to show as ghosts")
    opacity_step: float = Field(default=15, description="Opacity decrease per frame from current (0-100)", ge=5, le=50)
    color_before_r: int = Field(default=100, ge=0, le=255, description="Tint for previous frames (red)")
    color_before_g: int = Field(default=100, ge=0, le=255)
    color_before_b: int = Field(default=255, ge=0, le=255)
    color_after_r: int = Field(default=255, ge=0, le=255, description="Tint for next frames (green)")
    color_after_g: int = Field(default=100, ge=0, le=255)
    color_after_b: int = Field(default=100, ge=0, le=255)
    character_name: str = Field(default="character", description="Character identifier")


class AiCharacterTemplateInput(BaseModel):
    """Save or load a complete posable character (paths + skeleton + bindings)."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: save, load, list, delete")
    template_name: str = Field(default="character", description="Template name")
    character_name: str = Field(default="character", description="Character identifier")
    template_path: Optional[str] = Field(default=None, description="Custom path for template file (default: ~/.claude/memory/illustration/characters/)")


class AiPoseFromImageInput(BaseModel):
    """Estimate pose joint angles from a reference photo or sketch."""
    model_config = ConfigDict(str_strip_whitespace=True)
    image_path: str = Field(..., description="Path to reference pose image")
    character_name: str = Field(default="character", description="Character to apply pose to")
    apply: bool = Field(default=False, description="Apply extracted pose immediately")
    method: str = Field(default="contour", description="Method: contour (shape analysis), manual (guided annotation)")


class AiKeyframeTimelineInput(BaseModel):
    """Define animation keyframes at frame numbers with pose data."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: add_keyframe, remove_keyframe, list, clear, set_fps, set_duration")
    frame: Optional[int] = Field(default=None, description="Frame number for add/remove", ge=0)
    pose_name: Optional[str] = Field(default=None, description="Pose name for add_keyframe")
    fps: Optional[int] = Field(default=None, description="Frames per second for set_fps", ge=1, le=120)
    duration_frames: Optional[int] = Field(default=None, description="Total duration in frames for set_duration", ge=1)
    character_name: str = Field(default="character", description="Character identifier")
    easing: str = Field(default="ease_in_out", description="Easing: linear, ease_in, ease_out, ease_in_out")


class AiMotionPathInput(BaseModel):
    """Define arc-based motion paths for character movement across frames."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="create", description="Action: create, edit, delete, list")
    path_name: str = Field(default="motion_1", description="Motion path name")
    points: Optional[str] = Field(default=None, description="JSON array of [x, y, frame] waypoints")
    character_name: str = Field(default="character", description="Character to move along path")
    show_path: bool = Field(default=True, description="Visualize the motion path on a Motion layer")


class AiStoryboardPanelInput(BaseModel):
    """Generate storyboard panels with character in specified pose and camera framing."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="create", description="Action: create (new panel), duplicate, reorder, list, export")
    panel_number: Optional[int] = Field(default=None, description="Panel number (auto-increment if None)")
    pose_name: Optional[str] = Field(default=None, description="Character pose for this panel")
    camera: str = Field(default="medium", description="Camera framing: wide, medium, close_up, extreme_close_up, over_shoulder")
    description: Optional[str] = Field(default=None, description="Action/dialogue description for the panel")
    duration_frames: int = Field(default=24, description="Panel duration in frames", ge=1)
    character_name: str = Field(default="character", description="Character identifier")


# ── Rig Controllers & Storyboard Pipeline Models ──────────────


class AiRigControllersInput(BaseModel):
    """Create visual control handles on skeleton joints for intuitive posing."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="create", description="Action: create (generate controllers), update (refresh positions), clear (remove), list")
    character_name: str = Field(default="character", description="Character identifier")
    controller_style: str = Field(default="circle", description="Handle shape: circle, diamond, square, arrow")
    controller_size: float = Field(default=12, description="Controller handle size in points", ge=4, le=50)
    color_r: int = Field(default=255, ge=0, le=255, description="Controller color red")
    color_g: int = Field(default=100, ge=0, le=255, description="Controller color green")
    color_b: int = Field(default=0, ge=0, le=255, description="Controller color orange/blue")
    show_labels: bool = Field(default=True, description="Show joint name labels next to controllers")


class AiStoryboardTemplateInput(BaseModel):
    """Create a storyboard template with configurable panel grid layout."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="create", description="Action: create, clear, list_presets")
    preset: str = Field(default="standard", description="Preset: standard (2x3), widescreen (2x2), vertical (1x4), cinematic (3x3), custom")
    columns: int = Field(default=2, description="Columns for custom preset", ge=1, le=6)
    rows: int = Field(default=3, description="Rows for custom preset", ge=1, le=8)
    page_width: float = Field(default=792, description="Page width in points (792=11in)", ge=100)
    page_height: float = Field(default=612, description="Page height in points (612=8.5in)", ge=100)
    panel_ratio: str = Field(default="16:9", description="Panel aspect ratio: 16:9, 4:3, 2.39:1, 1:1, custom")
    gutter: float = Field(default=18, description="Space between panels in points", ge=0)
    margin: float = Field(default=36, description="Page margin in points", ge=0)
    title: Optional[str] = Field(default=None, description="Storyboard title (shown at top)")
    include_fields: bool = Field(default=True, description="Add description/dialogue/duration fields below each panel")


class AiPanelTextInput(BaseModel):
    """Add dialogue, action descriptions, and SFX text to storyboard panels."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="set", description="Action: set (add/update text), clear, list")
    panel_number: int = Field(..., description="Target panel number", ge=1)
    text_type: str = Field(default="dialogue", description="Text type: dialogue, action, sfx, note")
    text: Optional[str] = Field(default=None, description="Text content")
    speaker: Optional[str] = Field(default=None, description="Speaker name for dialogue")


class AiCameraNotationInput(BaseModel):
    """Add camera movement notation (pan, zoom, truck, dolly) to storyboard panels."""
    model_config = ConfigDict(str_strip_whitespace=True)
    panel_number: int = Field(..., description="Target panel number", ge=1)
    movement: str = Field(..., description="Camera movement: pan_left, pan_right, tilt_up, tilt_down, zoom_in, zoom_out, truck_left, truck_right, dolly_in, dolly_out, crane_up, crane_down, static, handheld")
    intensity: str = Field(default="medium", description="Movement intensity: subtle, medium, dramatic")


class AiCharacterTurnaroundInput(BaseModel):
    """Generate front/side/3-4/back views from a rigged character."""
    model_config = ConfigDict(str_strip_whitespace=True)
    character_name: str = Field(default="character", description="Character identifier")
    views: str = Field(default="front,3-4,side,back", description="Comma-separated views to generate")
    spacing: float = Field(default=100, description="Horizontal spacing between views in points")
    include_guidelines: bool = Field(default=True, description="Add horizontal proportion guidelines across views")


class AiSceneManagerInput(BaseModel):
    """Group storyboard panels into numbered scenes with headers."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="create", description="Action: create, add_panel, remove_panel, reorder, list, delete")
    scene_number: Optional[int] = Field(default=None, description="Scene number")
    scene_name: Optional[str] = Field(default=None, description="Scene name/description")
    panel_numbers: Optional[str] = Field(default=None, description="Comma-separated panel numbers to include")
    location: Optional[str] = Field(default=None, description="Scene location (INT/EXT)")
    time_of_day: Optional[str] = Field(default=None, description="Time: DAY, NIGHT, DAWN, DUSK")


class AiBackgroundLayerInput(BaseModel):
    """Set up a background/environment for a storyboard panel or scene."""
    model_config = ConfigDict(str_strip_whitespace=True)
    panel_number: Optional[int] = Field(default=None, description="Target panel (None=active artboard)")
    bg_type: str = Field(default="solid", description="Background type: solid, gradient, image, none")
    color_r: int = Field(default=230, ge=0, le=255)
    color_g: int = Field(default=230, ge=0, le=255)
    color_b: int = Field(default=230, ge=0, le=255)
    gradient_end_r: Optional[int] = Field(default=None, ge=0, le=255)
    gradient_end_g: Optional[int] = Field(default=None, ge=0, le=255)
    gradient_end_b: Optional[int] = Field(default=None, ge=0, le=255)
    image_path: Optional[str] = Field(default=None, description="Background image path for image type")
    opacity: float = Field(default=100, description="Background opacity 0-100", ge=0, le=100)


class AiMultiCharacterInput(BaseModel):
    """Place multiple rigged characters in one panel with independent poses."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="place", description="Action: place, repose, remove, list")
    panel_number: int = Field(..., description="Target panel number", ge=1)
    character_name: str = Field(..., description="Character to place")
    pose_name: Optional[str] = Field(default=None, description="Pose to apply")
    position_x: Optional[float] = Field(default=None, description="X position in panel")
    position_y: Optional[float] = Field(default=None, description="Y position in panel")
    scale: float = Field(default=100, description="Character scale percentage", ge=10, le=500)


class AiShotListInput(BaseModel):
    """Generate a production shot list from storyboard data."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="generate", description="Action: generate, export_csv, export_json")
    include_timing: bool = Field(default=True, description="Include duration and cumulative time")
    include_camera: bool = Field(default=True, description="Include camera framing and movement")
    include_notes: bool = Field(default=True, description="Include production notes")


class AiBeatSheetInput(BaseModel):
    """Map story beats to panel timing for narrative structure."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="add", description="Action: add, remove, list, auto_assign")
    beat_name: Optional[str] = Field(default=None, description="Beat name: opening, inciting_incident, rising_action, climax, resolution, etc.")
    panel_number: Optional[int] = Field(default=None, description="Panel where this beat occurs", ge=1)
    description: Optional[str] = Field(default=None, description="Beat description")


class AiProductionNotesInput(BaseModel):
    """Per-panel director's notes, technical requirements, and VFX flags."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="set", description="Action: set, clear, list, export")
    panel_number: int = Field(..., description="Target panel number", ge=1)
    note_type: str = Field(default="direction", description="Note type: direction, vfx, audio, technical, continuity")
    note: Optional[str] = Field(default=None, description="Note content")
    priority: str = Field(default="normal", description="Priority: low, normal, high, critical")


class AiContinuityCheckInput(BaseModel):
    """Verify character appearance consistency across storyboard panels."""
    model_config = ConfigDict(str_strip_whitespace=True)
    character_name: str = Field(default="character", description="Character to check")
    check_type: str = Field(default="full", description="Check type: full, colors_only, proportions_only, costume_only")


class AiAssetRegistryInput(BaseModel):
    """Track all characters, props, and backgrounds used in each panel."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="register", description="Action: register, remove, list, list_by_panel, list_by_asset, summary")
    asset_type: Optional[str] = Field(default=None, description="Asset type: character, prop, background, effect")
    asset_name: Optional[str] = Field(default=None, description="Asset name/identifier")
    panel_number: Optional[int] = Field(default=None, description="Panel number for register/remove", ge=1)


class AiPdfExportInput(BaseModel):
    """Export storyboard as formatted PDF with all annotations."""
    model_config = ConfigDict(str_strip_whitespace=True)
    output_path: str = Field(..., description="Output PDF file path")
    include_descriptions: bool = Field(default=True, description="Include panel descriptions")
    include_dialogue: bool = Field(default=True, description="Include dialogue text")
    include_camera: bool = Field(default=True, description="Include camera notation")
    include_timing: bool = Field(default=True, description="Include timing information")
    include_notes: bool = Field(default=True, description="Include production notes")
    layout: str = Field(default="panels", description="Layout: panels (grid), list (sequential), presentation (one per page)")


class AiAnimaticPreviewInput(BaseModel):
    """Generate an HTML-based panel timing preview (animatic without AE)."""
    model_config = ConfigDict(str_strip_whitespace=True)
    output_path: str = Field(default="", description="Output HTML path (auto-generated if empty)")
    auto_play: bool = Field(default=True, description="Auto-play on open")
    show_timing: bool = Field(default=True, description="Show timing bar")
    show_descriptions: bool = Field(default=True, description="Show panel descriptions during playback")


class AiPropManagerInput(BaseModel):
    """Create, place, and track props that characters interact with."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="create", description="Action: create, place, remove, list, attach_to_joint")
    prop_name: str = Field(default="prop", description="Prop identifier")
    panel_number: Optional[int] = Field(default=None, description="Panel to place prop in", ge=1)
    x: Optional[float] = Field(default=None, description="X position")
    y: Optional[float] = Field(default=None, description="Y position")
    joint_name: Optional[str] = Field(default=None, description="Joint to attach prop to (for attach_to_joint)")
    character_name: Optional[str] = Field(default=None, description="Character for joint attachment")
    prop_path: Optional[str] = Field(default=None, description="Path to prop AI/SVG file for create")


class AiLightingNotationInput(BaseModel):
    """Add key/fill/rim light direction indicators to storyboard panels."""
    model_config = ConfigDict(str_strip_whitespace=True)
    panel_number: int = Field(..., description="Target panel number", ge=1)
    action: str = Field(default="set", description="Action: set, clear")
    key_direction: Optional[str] = Field(default=None, description="Key light: top_left, top_right, left, right, front, back")
    fill_direction: Optional[str] = Field(default=None, description="Fill light direction")
    rim: bool = Field(default=False, description="Add rim/back light indicator")
    mood: Optional[str] = Field(default=None, description="Lighting mood: bright, moody, dramatic, silhouette, noir")


class AiTransitionPlannerInput(BaseModel):
    """Visual indicators for panel-to-panel transitions."""
    model_config = ConfigDict(str_strip_whitespace=True)
    panel_number: int = Field(..., description="Source panel number", ge=1)
    transition: str = Field(default="cut", description="Transition: cut, dissolve, wipe_left, wipe_right, wipe_up, wipe_down, match_cut, smash_cut, fade_in, fade_out, iris")
    duration_frames: int = Field(default=12, description="Transition duration in frames", ge=1)


class AiAudioSyncInput(BaseModel):
    """Dialogue timing, music cues, and SFX placement per panel."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="add", description="Action: add, remove, list, export_markers")
    panel_number: int = Field(..., description="Target panel number", ge=1)
    cue_type: str = Field(default="dialogue", description="Cue type: dialogue, music, sfx, ambience")
    cue_name: Optional[str] = Field(default=None, description="Cue identifier or description")
    start_frame: int = Field(default=0, description="Start frame within the panel", ge=0)
    duration_frames: Optional[int] = Field(default=None, description="Cue duration in frames")


class AiSequenceAssemblerInput(BaseModel):
    """Combine scenes into acts and complete sequences."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="create_act", description="Action: create_act, add_scene, reorder, list, summary, export_outline")
    act_number: Optional[int] = Field(default=None, description="Act number")
    act_name: Optional[str] = Field(default=None, description="Act name (e.g. 'Setup', 'Confrontation', 'Resolution')")
    scene_numbers: Optional[str] = Field(default=None, description="Comma-separated scene numbers to include")


# ── Landmark-Axis Drawing Model ──────────────────────────────


class AiLandmarkAxisInput(BaseModel):
    """Landmark-and-axis-first drawing: detect landmarks, compute axes, draw in axis-relative coordinates."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: detect_landmarks, add_landmark, compute_axis, draw_on_axis, validate_placement, infer_occluded")
    character_name: str = Field(default="character", description="Character identifier")
    image_path: Optional[str] = Field(default=None, description="Reference image path (for detect_landmarks)")
    landmark_name: Optional[str] = Field(default=None, description="Landmark name")
    landmark_type: Optional[str] = Field(default="structural", description="Landmark type: structural or feature")
    x: Optional[float] = Field(default=None, description="X position in AI coordinates")
    y: Optional[float] = Field(default=None, description="Y position in AI coordinates")
    px_x: Optional[float] = Field(default=None, description="X in pixel coordinates")
    px_y: Optional[float] = Field(default=None, description="Y in pixel coordinates")
    axis_name: Optional[str] = Field(default=None, description="Name for the axis")
    from_landmark: Optional[str] = Field(default=None, description="Start landmark for axis")
    to_landmark: Optional[str] = Field(default=None, description="End landmark for axis")
    points_json: Optional[str] = Field(default=None, description="JSON array of [along_pct, across_pct] for shape points")
    cross_width: Optional[float] = Field(default=None, description="Cross-axis width in AI points")
    near_cross_width: Optional[float] = Field(default=None, description="Near-side cross width for perspective")
    far_cross_width: Optional[float] = Field(default=None, description="Far-side cross width for perspective")
    path_name: str = Field(default="axis_shape", description="Name for created path")
    layer_name: str = Field(default="Drawing", description="Target layer")
    closed: bool = Field(default=True, description="Close the path")
    stroke_width: float = Field(default=2.0, ge=0.1)
    placed_name: Optional[str] = Field(default=None, description="Name of placed path to validate")
    tolerance: float = Field(default=2.0, ge=0.1, description="Validation tolerance in AI points")
    visible_landmarks: Optional[str] = Field(default=None, description="JSON array of visible landmark names")
    view_angle: Optional[float] = Field(default=None, description="View rotation degrees (0=front, 90=side)")
    symmetric: bool = Field(default=True, description="Assume bilateral symmetry for inference")


# ── Contour Scanner Model ────────────────────────────────────


class AiContourScannerInput(BaseModel):
    """Axis-guided contour scanner: scan a reference image along an axis to extract edge contour paths."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: scan_feature, place_contour")
    image_path: str = Field(..., description="Absolute path to reference image")
    # Axis definition
    axis_center_x: float = Field(default=0.0, description="Axis center X in pixel coordinates")
    axis_center_y: float = Field(default=0.0, description="Axis center Y in pixel coordinates")
    axis_angle: float = Field(default=90.0, description="Axis angle in degrees (0=right, 90=up in AI / down in pixel)")
    # Scan parameters
    scan_start: float = Field(default=-100.0, description="Start distance along axis from center (pixels)")
    scan_end: float = Field(default=100.0, description="End distance along axis from center (pixels)")
    scan_step: float = Field(default=2.0, description="Step size along axis (pixels)", gt=0)
    cross_range: float = Field(default=80.0, description="Half-width of cross-axis scan (pixels)", gt=0)
    sample_step: float = Field(default=1.0, description="Step size along cross-axis (pixels)", gt=0)
    # Edge detection thresholds
    bright_threshold: int = Field(default=80, description="Pixel brightness above which is 'background'", ge=0, le=255)
    dark_threshold: int = Field(default=30, description="Pixel brightness below which is 'feature'", ge=0, le=255)
    # Curve fitting
    error_threshold: float = Field(default=2.0, description="Bezier fitting error threshold (pixels)", gt=0)
    max_segments: Optional[int] = Field(default=None, description="Max bezier segments for curve fitting")
    # Place contour params
    contour_json: Optional[str] = Field(default=None, description="JSON contour data from scan_feature (for place_contour)")
    character_name: str = Field(default="character", description="Character identifier for rig transform lookup")
    path_name: str = Field(default="scanned_contour", description="Name for created path")
    layer_name: str = Field(default="Drawing", description="Target layer in Illustrator")
    closed: bool = Field(default=True, description="Close the contour path")
    stroke_width: float = Field(default=2.0, ge=0.1, description="Stroke width for placed path")
