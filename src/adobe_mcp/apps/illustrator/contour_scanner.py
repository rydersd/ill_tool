"""Axis-guided contour scanner for extracting vector paths from reference images.

Given a reference image and an axis (center + angle), this module:
1. Walks along the main axis in incremental steps
2. At each step, scans perpendicular (cross-axis) for color transitions
3. Collects edge transition points (background->feature and feature->background)
4. Separates into left_edges and right_edges contour lists
5. Fits efficient bezier paths through each edge set via curve_fit
6. Returns contour data ready for AI path placement

Tier 1 (top): Pure Python scanning, edge detection, and path fitting.
Tier 2 (bottom): MCP tool registration for scan_feature and place_contour actions.
"""

import json
import math
import os
from typing import Optional

import cv2
import numpy as np

from adobe_mcp.apps.illustrator.curve_fit import fit_bezier_path
from adobe_mcp.apps.illustrator.landmark_axis import compute_transform, pixel_to_ai
from adobe_mcp.apps.illustrator.models import AiContourScannerInput
from adobe_mcp.apps.illustrator.rig_data import _load_rig
from adobe_mcp.engine import _async_run_jsx
from adobe_mcp.jsx.templates import escape_jsx_string


# ── Tier 1: Pure Python Edge Scanning ────────────────────────────────────


def _load_grayscale(image_path: str) -> Optional[np.ndarray]:
    """Load an image and convert to single-channel grayscale.

    Returns the grayscale image as a 2D numpy array (uint8), or None on failure.
    """
    img = cv2.imread(image_path)
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _pixel_in_bounds(x: int, y: int, width: int, height: int) -> bool:
    """Check whether a pixel coordinate is within image bounds."""
    return 0 <= x < width and 0 <= y < height


def scan_edges_along_axis(
    gray: np.ndarray,
    axis_center: tuple[float, float],
    axis_angle_deg: float,
    scan_start: float,
    scan_end: float,
    scan_step: float,
    cross_range: float,
    sample_step: float,
    bright_threshold: int = 80,
    dark_threshold: int = 30,
) -> dict:
    """Walk along the main axis and scan perpendicular for edge transitions.

    At each position along the main axis, we scan along the cross-axis direction
    from -cross_range to +cross_range looking for brightness transitions that
    indicate feature boundaries.

    Args:
        gray: Grayscale image as 2D numpy array.
        axis_center: (x, y) center of the axis in pixel coordinates.
        axis_angle_deg: Angle of the main axis in degrees. 0=right, 90=down
                        (standard image coordinates where Y increases downward).
        scan_start: Start distance along axis from center (can be negative).
        scan_end: End distance along axis from center.
        scan_step: Increment along the main axis per scan line.
        cross_range: Half-width of the perpendicular scan.
        sample_step: Increment along the cross-axis per sample.
        bright_threshold: Brightness above this = background (not feature).
        dark_threshold: Brightness below this = feature (dark region).

    Returns:
        Dict with keys:
            left_edges: list of [x, y] pixel positions (first transition per scan line)
            right_edges: list of [x, y] pixel positions (last transition per scan line)
            all_transitions: list of all transition points for debugging
            scan_line_count: number of scan lines processed
    """
    img_h, img_w = gray.shape[:2]

    # Main axis direction (in image coordinates, Y increases downward)
    angle_rad = math.radians(axis_angle_deg)
    dir_x = math.cos(angle_rad)
    dir_y = math.sin(angle_rad)

    # Cross-axis direction (perpendicular, 90 degrees clockwise in image coords)
    cross_x = -dir_y
    cross_y = dir_x

    left_edges = []
    right_edges = []
    all_transitions = []
    scan_line_count = 0

    # Walk along the main axis from scan_start to scan_end
    t = scan_start
    while t <= scan_end:
        # Compute the scan origin for this axis position
        origin_x = axis_center[0] + t * dir_x
        origin_y = axis_center[1] + t * dir_y

        # Scan along the cross-axis at this position
        line_transitions = []
        s = -cross_range
        prev_brightness = None

        while s <= cross_range:
            # Compute the sample point
            px = origin_x + s * cross_x
            py = origin_y + s * cross_y
            ix, iy = int(round(px)), int(round(py))

            if _pixel_in_bounds(ix, iy, img_w, img_h):
                brightness = int(gray[iy, ix])

                if prev_brightness is not None:
                    # Detect entering dark feature: background -> feature
                    if prev_brightness > bright_threshold and brightness < dark_threshold:
                        line_transitions.append({
                            "type": "enter",
                            "pos": [round(px, 2), round(py, 2)],
                            "axis_t": round(t, 2),
                            "cross_s": round(s, 2),
                        })
                    # Detect leaving dark feature: feature -> background
                    elif prev_brightness < dark_threshold and brightness > bright_threshold:
                        line_transitions.append({
                            "type": "exit",
                            "pos": [round(px, 2), round(py, 2)],
                            "axis_t": round(t, 2),
                            "cross_s": round(s, 2),
                        })

                prev_brightness = brightness

            s += sample_step

        # Separate first "enter" as left edge and last "exit" as right edge
        # This handles the common case of a single feature region per scan line
        enters = [tr for tr in line_transitions if tr["type"] == "enter"]
        exits = [tr for tr in line_transitions if tr["type"] == "exit"]

        if enters:
            left_edges.append(enters[0]["pos"])
        if exits:
            right_edges.append(exits[-1]["pos"])

        all_transitions.extend(line_transitions)
        scan_line_count += 1
        t += scan_step

    return {
        "left_edges": left_edges,
        "right_edges": right_edges,
        "all_transitions": all_transitions,
        "scan_line_count": scan_line_count,
    }


# ── Gradient-based edge scanning ──────────────────────────────────────


def _compute_gradient_magnitude(gray: np.ndarray) -> np.ndarray:
    """Compute gradient magnitude using Sobel operator.

    Returns a float64 array of the same shape as input, where each pixel
    value represents the magnitude of the local brightness gradient.
    """
    grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    return np.sqrt(grad_x ** 2 + grad_y ** 2)


def _find_gradient_peaks(
    signal: np.ndarray,
    threshold: float,
    min_distance: int = 3,
) -> list[int]:
    """Find local maxima in a 1D gradient signal that exceed a threshold.

    Args:
        signal: 1D array of gradient magnitudes along a scan line.
        threshold: Minimum gradient value to qualify as an edge peak.
        min_distance: Minimum index separation between consecutive peaks.

    Returns:
        List of indices into signal where peaks were found, sorted by position.
    """
    peaks = []
    for i in range(1, len(signal) - 1):
        if (
            signal[i] >= threshold
            and signal[i] >= signal[i - 1]
            and signal[i] >= signal[i + 1]
        ):
            if not peaks or (i - peaks[-1]) >= min_distance:
                peaks.append(i)
    return peaks


def scan_edges_gradient(
    gray: np.ndarray,
    axis_center: tuple[float, float],
    axis_angle_deg: float,
    scan_start: float,
    scan_end: float,
    scan_step: float,
    cross_range: float,
    sample_step: float,
    gradient_threshold: float = 30.0,
    min_peak_distance: int = 3,
) -> dict:
    """Walk along the main axis and detect edges using gradient magnitude peaks.

    Unlike scan_edges_along_axis which relies on brightness transitions between
    a bright background and dark feature, this function finds edges by detecting
    peaks in the Sobel gradient magnitude. This works for high-fill regions where
    the feature fills most of the scan window and there are no clean bright/dark
    transitions to detect.

    Args:
        gray: Grayscale image as 2D numpy array.
        axis_center: (x, y) center of the axis in pixel coordinates.
        axis_angle_deg: Angle of the main axis in degrees.
        scan_start: Start distance along axis from center.
        scan_end: End distance along axis from center.
        scan_step: Increment along the main axis per scan line.
        cross_range: Half-width of the perpendicular scan.
        sample_step: Increment along the cross-axis per sample.
        gradient_threshold: Minimum gradient magnitude to count as an edge.
        min_peak_distance: Minimum sample spacing between consecutive peaks.

    Returns:
        Dict with left_edges, right_edges, all_transitions, scan_line_count.
    """
    img_h, img_w = gray.shape[:2]
    grad_mag = _compute_gradient_magnitude(gray)

    angle_rad = math.radians(axis_angle_deg)
    dir_x = math.cos(angle_rad)
    dir_y = math.sin(angle_rad)
    cross_x = -dir_y
    cross_y = dir_x

    left_edges = []
    right_edges = []
    all_transitions = []
    scan_line_count = 0

    t = scan_start
    while t <= scan_end:
        origin_x = axis_center[0] + t * dir_x
        origin_y = axis_center[1] + t * dir_y

        # Sample gradient magnitude along the cross-axis
        samples = []
        positions = []
        s = -cross_range
        while s <= cross_range:
            px = origin_x + s * cross_x
            py = origin_y + s * cross_y
            ix, iy = int(round(px)), int(round(py))

            if _pixel_in_bounds(ix, iy, img_w, img_h):
                samples.append(float(grad_mag[iy, ix]))
                positions.append((round(px, 2), round(py, 2), round(s, 2)))

            s += sample_step

        if len(samples) >= 3:
            signal = np.array(samples)
            peak_indices = _find_gradient_peaks(
                signal, gradient_threshold, min_peak_distance
            )

            if peak_indices:
                # Outermost peaks are the feature boundary edges
                first_peak = peak_indices[0]
                last_peak = peak_indices[-1]

                left_edges.append(list(positions[first_peak][:2]))
                right_edges.append(list(positions[last_peak][:2]))

                for pi in peak_indices:
                    all_transitions.append({
                        "type": "gradient_peak",
                        "pos": list(positions[pi][:2]),
                        "axis_t": round(t, 2),
                        "cross_s": positions[pi][2],
                        "gradient_value": round(samples[pi], 2),
                    })

        scan_line_count += 1
        t += scan_step

    return {
        "left_edges": left_edges,
        "right_edges": right_edges,
        "all_transitions": all_transitions,
        "scan_line_count": scan_line_count,
    }


def _check_boundary_clipping(
    edges: dict,
    cross_range: float,
    axis_center: tuple[float, float],
    axis_angle_deg: float,
    margin: float = 5.0,
) -> float:
    """Check what fraction of detected edges sit at the scan boundary.

    When left/right edges cluster near ±cross_range, the feature likely fills
    the scan window and threshold detection produced clipped rectangles.

    Args:
        edges: Output from scan_edges_along_axis.
        cross_range: Half-width of the cross-axis scan.
        axis_center: Axis center for reconstructing cross_s values.
        axis_angle_deg: Axis angle for reconstructing cross_s values.
        margin: Distance from boundary to count as "clipped".

    Returns:
        Ratio (0–1) of edges that are clipped at the scan boundary.
        High ratio = high fill = threshold detection unreliable.
    """
    if not edges["all_transitions"]:
        # No transitions at all — either no feature or entire cross-axis is feature
        # Check if the scan region is fully dark by returning 1.0 to trigger gradient mode
        return 1.0

    clipped = 0
    total = 0
    for tr in edges["all_transitions"]:
        total += 1
        s = abs(tr["cross_s"])
        if s >= (cross_range - margin):
            clipped += 1

    return clipped / total if total > 0 else 0.0


def scan_feature_adaptive(
    image_path: str,
    axis_center: tuple[float, float],
    axis_angle_deg: float,
    scan_start: float = -100.0,
    scan_end: float = 100.0,
    scan_step: float = 2.0,
    cross_range: float = 80.0,
    sample_step: float = 1.0,
    bright_threshold: int = 80,
    dark_threshold: int = 30,
    gradient_threshold: float = 30.0,
    error_threshold: float = 2.0,
    max_segments: Optional[int] = None,
    closed: bool = True,
    fill_limit: float = 0.85,
) -> dict:
    """Adaptive scanning: tries threshold first, falls back to gradient for high-fill.

    The fill ratio is computed from how many edges sit at the scan boundary.
    If fill_ratio > fill_limit, the feature fills the scan window and threshold
    detection is unreliable — switches to gradient-based edge detection.

    Returns the same dict as scan_feature, plus:
        mode: "threshold" or "gradient" — which method produced the result.
        fill_clipped: ratio of boundary-clipped edges from threshold pass.
    """
    gray = _load_grayscale(image_path)
    if gray is None:
        return {"error": f"Could not read image: {image_path}"}

    # Pass 1: threshold-based scanning
    edges = scan_edges_along_axis(
        gray, axis_center, axis_angle_deg,
        scan_start, scan_end, scan_step,
        cross_range, sample_step,
        bright_threshold, dark_threshold,
    )

    fill_clipped = _check_boundary_clipping(
        edges, cross_range, axis_center, axis_angle_deg,
    )

    mode = "threshold"
    no_edges = not edges["left_edges"] and not edges["right_edges"]

    # Sparsity check: if threshold found very few edges relative to scan lines,
    # the result is too sparse for a meaningful contour — switch to gradient.
    # A good contour needs edges on at least 30% of scan lines.
    edge_count = max(len(edges["left_edges"]), len(edges["right_edges"]))
    sparse = (
        edges["scan_line_count"] > 5
        and edge_count < edges["scan_line_count"] * 0.3
    )

    if fill_clipped > fill_limit or no_edges or sparse:
        # High fill, no edges, or too sparse — switch to gradient mode
        edges = scan_edges_gradient(
            gray, axis_center, axis_angle_deg,
            scan_start, scan_end, scan_step,
            cross_range, sample_step,
            gradient_threshold,
        )
        mode = "gradient"

    if not edges["left_edges"] and not edges["right_edges"]:
        return {
            "error": "No edges found in either threshold or gradient mode",
            "scan_line_count": edges["scan_line_count"],
            "mode": mode,
            "fill_clipped": fill_clipped,
            "left_edges": [],
            "right_edges": [],
        }

    # Fit bezier contour through the detected edges
    contour = fit_contour_from_edges(
        edges["left_edges"],
        edges["right_edges"],
        error_threshold=error_threshold,
        max_segments=max_segments,
        closed=closed,
    )

    return {
        "contour_points": contour["contour_points"],
        "left_edges": edges["left_edges"],
        "right_edges": edges["right_edges"],
        "left_anchors": contour["left_anchors"],
        "right_anchors": contour["right_anchors"],
        "anchor_count": contour["anchor_count"],
        "scan_line_count": edges["scan_line_count"],
        "all_transitions": edges["all_transitions"],
        "mode": mode,
        "fill_clipped": fill_clipped,
    }


# ── Multi-exposure edge voting ─────────────────────────────────────────


def multi_exposure_edge_vote(
    gray: np.ndarray,
    n_levels: int = 10,
    canny_low: int = 30,
    canny_high: int = 100,
    gamma_range: tuple[float, float] = (0.2, 1.5),
) -> np.ndarray:
    """Generate a vote map showing which edges persist across exposure changes.

    Form edges (where the surface actually turns away) persist regardless of
    brightness. Shadow edges (where light stops reaching) appear/disappear as
    exposure changes. The vote count distinguishes them.

    Args:
        gray: Grayscale image as 2D numpy array.
        n_levels: Number of gamma levels to test.
        canny_low: Canny low threshold.
        canny_high: Canny high threshold.
        gamma_range: (min_gamma, max_gamma) range to sweep.

    Returns:
        2D float array same shape as input. Each pixel value = number of
        exposure levels (0 to n_levels) that detected an edge there.
        High values (>=8) = likely form edge. Low values (<=3) = likely shadow.
    """
    h, w = gray.shape[:2]
    vote_map = np.zeros((h, w), dtype=np.float64)

    # Build a lookup table for each gamma level and run Canny on each
    gamma_min, gamma_max = gamma_range
    gammas = np.linspace(gamma_min, gamma_max, n_levels)

    for gamma in gammas:
        # Apply gamma correction: output = 255 * (input / 255) ^ gamma
        # Build LUT for fast per-pixel mapping
        inv_gamma = 1.0 / gamma if gamma > 0 else 1.0
        lut = np.array(
            [np.clip(pow(i / 255.0, inv_gamma) * 255.0, 0, 255) for i in range(256)],
            dtype=np.uint8,
        )
        corrected = cv2.LUT(gray, lut)

        # Run Canny edge detection on the gamma-corrected image
        edges = cv2.Canny(corrected, canny_low, canny_high)

        # Accumulate votes: each nonzero pixel in the edge map adds 1 vote
        vote_map += (edges > 0).astype(np.float64)

    return vote_map


def classify_edge_votes(
    vote_map: np.ndarray,
    n_levels: int = 10,
    form_threshold: float = 0.7,
    shadow_threshold: float = 0.3,
) -> dict:
    """Classify voted edges into form, ambiguous, and shadow categories.

    Args:
        vote_map: Output from multi_exposure_edge_vote.
        n_levels: Total number of levels used in voting.
        form_threshold: Fraction of votes needed to classify as form edge.
        shadow_threshold: Below this fraction = shadow edge.

    Returns:
        Dict with:
            form_edges: Binary mask of high-confidence form edges
            ambiguous_edges: Binary mask of ambiguous edges
            shadow_edges: Binary mask of likely shadow edges
            form_count: Number of form edge pixels
            shadow_count: Number of shadow edge pixels
    """
    form_min_votes = form_threshold * n_levels
    shadow_max_votes = shadow_threshold * n_levels

    # A pixel must have at least 1 vote to be considered an edge at all
    any_edge = vote_map > 0

    form_edges = (vote_map >= form_min_votes).astype(np.uint8)
    shadow_edges = (any_edge & (vote_map <= shadow_max_votes)).astype(np.uint8)
    ambiguous_edges = (
        any_edge
        & (vote_map > shadow_max_votes)
        & (vote_map < form_min_votes)
    ).astype(np.uint8)

    return {
        "form_edges": form_edges,
        "ambiguous_edges": ambiguous_edges,
        "shadow_edges": shadow_edges,
        "form_count": int(np.sum(form_edges)),
        "shadow_count": int(np.sum(shadow_edges)),
    }


def generate_exposure_gif(
    gray: np.ndarray,
    output_path: str,
    n_frames: int = 20,
    gamma_range: tuple[float, float] = (0.2, 1.5),
    duration_ms: int = 100,
) -> str:
    """Generate a GIF sweeping through exposure levels with Canny edge overlays.

    Shadow edges appear/disappear across frames while form edges stay constant.
    Useful for visual verification of form-vs-shadow calls.

    Each frame shows the gamma-corrected image with Canny edges overlaid in
    green. The GIF is saved using PIL. If PIL is not available, individual
    frames are saved as numbered PNGs in the same directory.

    Args:
        gray: Grayscale image.
        output_path: Where to save the GIF.
        n_frames: Number of frames in the animation.
        gamma_range: Exposure sweep range.
        duration_ms: Duration per frame in milliseconds.

    Returns:
        Path to the saved GIF file (or directory of PNGs on fallback).
    """
    gamma_min, gamma_max = gamma_range
    gammas = np.linspace(gamma_min, gamma_max, n_frames)

    frames = []
    for gamma in gammas:
        # Gamma correction
        inv_gamma = 1.0 / gamma if gamma > 0 else 1.0
        lut = np.array(
            [np.clip(pow(i / 255.0, inv_gamma) * 255.0, 0, 255) for i in range(256)],
            dtype=np.uint8,
        )
        corrected = cv2.LUT(gray, lut)

        # Run Canny on corrected frame
        edges = cv2.Canny(corrected, 30, 100)

        # Compose: grayscale background with green edge overlay
        rgb = cv2.cvtColor(corrected, cv2.COLOR_GRAY2RGB)
        rgb[edges > 0] = [0, 255, 0]  # Green overlay for edges

        frames.append(rgb)

    # Try to save as animated GIF via PIL
    try:
        from PIL import Image as PILImage

        pil_frames = [PILImage.fromarray(f) for f in frames]
        pil_frames[0].save(
            output_path,
            save_all=True,
            append_images=pil_frames[1:],
            duration=duration_ms,
            loop=0,
        )
        return output_path
    except ImportError:
        # Fallback: save individual frames as numbered PNGs
        base, _ = os.path.splitext(output_path)
        out_dir = os.path.dirname(output_path) or "."
        paths_saved = []
        for i, frame in enumerate(frames):
            frame_path = f"{base}_frame{i:03d}.png"
            cv2.imwrite(frame_path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            paths_saved.append(frame_path)
        return out_dir


def vote_map_to_contour_candidates(
    vote_map: np.ndarray,
    min_votes: int = 6,
    min_contour_length: int = 20,
) -> list[np.ndarray]:
    """Extract contour candidates from high-vote regions of the vote map.

    Thresholds the vote map, finds connected components, extracts contours,
    and filters by minimum length.

    Args:
        vote_map: Output from multi_exposure_edge_vote.
        min_votes: Minimum votes to include in contour extraction.
        min_contour_length: Minimum contour perimeter in pixels.

    Returns:
        List of contour arrays (each is Nx1x2 int array from cv2.findContours).
    """
    # Threshold the vote map to a binary mask
    binary = (vote_map >= min_votes).astype(np.uint8) * 255

    # Find contours in the binary mask
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter by minimum perimeter length
    filtered = []
    for contour in contours:
        perimeter = cv2.arcLength(contour, closed=True)
        if perimeter >= min_contour_length:
            filtered.append(contour)

    return filtered


def assign_contours_to_skeleton(
    contours: list[np.ndarray],
    skeleton_joints: dict[str, tuple[float, float]],
    max_distance: float = 100.0,
) -> dict[str, list[np.ndarray]]:
    """Assign extracted contours to the nearest skeleton joint.

    Each contour is assigned to the skeleton joint closest to its centroid.
    Contours further than max_distance from any joint are unassigned.

    Args:
        contours: List of contour arrays from vote_map_to_contour_candidates.
        skeleton_joints: Dict mapping joint name to (x, y) pixel coordinates.
        max_distance: Maximum distance to assign a contour to a joint.

    Returns:
        Dict mapping joint name to list of contour arrays assigned to it.
        Includes special key '_unassigned' for orphan contours.
    """
    result: dict[str, list[np.ndarray]] = {"_unassigned": []}
    for name in skeleton_joints:
        result[name] = []

    for contour in contours:
        # Compute contour centroid via moments
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            # Degenerate contour (zero area) — use mean of points instead
            pts = contour.reshape(-1, 2).astype(np.float64)
            cx = float(np.mean(pts[:, 0]))
            cy = float(np.mean(pts[:, 1]))
        else:
            cx = moments["m10"] / moments["m00"]
            cy = moments["m01"] / moments["m00"]

        # Find nearest joint
        best_name = None
        best_dist = float("inf")

        for name, (jx, jy) in skeleton_joints.items():
            dist = math.sqrt((cx - jx) ** 2 + (cy - jy) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_name = name

        if best_name is not None and best_dist <= max_distance:
            result[best_name].append(contour)
        else:
            result["_unassigned"].append(contour)

    return result


def fit_contour_from_edges(
    left_edges: list[list[float]],
    right_edges: list[list[float]],
    error_threshold: float = 2.0,
    max_segments: Optional[int] = None,
    closed: bool = True,
) -> dict:
    """Fit bezier paths through left and right edge point sets, then combine.

    For a closed contour, the path goes: left_edges (top to bottom) then
    right_edges reversed (bottom to top), forming a loop around the feature.

    For an open contour, returns separate left and right edge paths.

    Args:
        left_edges: List of [x, y] pixel positions for the left boundary.
        right_edges: List of [x, y] pixel positions for the right boundary.
        error_threshold: Max error for bezier curve fitting.
        max_segments: Optional cap on bezier segments.
        closed: Whether to combine edges into a closed contour.

    Returns:
        Dict with:
            contour_points: combined ordered point list (pixel coords)
            left_segments: bezier segments for left edge
            right_segments: bezier segments for right edge
            anchor_count: total number of anchor points in the fitted path
    """
    result = {
        "contour_points": [],
        "left_segments": [],
        "right_segments": [],
        "left_anchors": [],
        "right_anchors": [],
        "anchor_count": 0,
    }

    if not left_edges and not right_edges:
        return result

    # Fit bezier paths through each edge set
    left_anchors = []
    right_anchors = []

    if len(left_edges) >= 2:
        left_pts = np.array(left_edges, dtype=np.float64)
        left_segs = fit_bezier_path(left_pts, error_threshold, max_segments)
        result["left_segments"] = [
            [[float(v) for v in p] for p in seg] for seg in left_segs
        ]
        # Extract anchor points from segments for the contour
        if left_segs:
            left_anchors.append([float(left_segs[0][0][0]), float(left_segs[0][0][1])])
            for seg in left_segs:
                left_anchors.append([float(seg[3][0]), float(seg[3][1])])
    elif len(left_edges) == 1:
        left_anchors = [list(left_edges[0])]

    if len(right_edges) >= 2:
        right_pts = np.array(right_edges, dtype=np.float64)
        right_segs = fit_bezier_path(right_pts, error_threshold, max_segments)
        result["right_segments"] = [
            [[float(v) for v in p] for p in seg] for seg in right_segs
        ]
        if right_segs:
            right_anchors.append([float(right_segs[0][0][0]), float(right_segs[0][0][1])])
            for seg in right_segs:
                right_anchors.append([float(seg[3][0]), float(seg[3][1])])
    elif len(right_edges) == 1:
        right_anchors = [list(right_edges[0])]

    result["left_anchors"] = left_anchors
    result["right_anchors"] = right_anchors

    # Combine into contour: left top->bottom, then right bottom->top (reversed)
    if closed and left_anchors and right_anchors:
        contour = left_anchors + list(reversed(right_anchors))
    else:
        contour = left_anchors + right_anchors

    result["contour_points"] = contour
    result["anchor_count"] = len(contour)

    return result


def pixels_to_ai_coords(
    points: list[list[float]],
    transform: Optional[dict] = None,
) -> list[list[float]]:
    """Convert a list of pixel coordinate points to AI coordinates.

    If a transform dict is provided (from landmark_axis.compute_transform),
    uses the full scale+offset+flip pipeline. Otherwise falls back to
    simple (x, -y) mapping for a 1:1 reference placed at origin.

    Args:
        points: List of [px_x, px_y] pixel coordinates.
        transform: Optional transform dict with scale, offset_x, offset_y.

    Returns:
        List of [ai_x, ai_y] Illustrator coordinates.
    """
    ai_points = []
    for pt in points:
        if transform:
            ai_x, ai_y = pixel_to_ai(pt[0], pt[1], transform)
        else:
            # Fallback: 1:1 placement at origin, Y-flip only
            ai_x = pt[0]
            ai_y = -pt[1]
        ai_points.append([round(ai_x, 2), round(ai_y, 2)])
    return ai_points


def scan_feature(
    image_path: str,
    axis_center: tuple[float, float],
    axis_angle_deg: float,
    scan_start: float = -100.0,
    scan_end: float = 100.0,
    scan_step: float = 2.0,
    cross_range: float = 80.0,
    sample_step: float = 1.0,
    bright_threshold: int = 80,
    dark_threshold: int = 30,
    error_threshold: float = 2.0,
    max_segments: Optional[int] = None,
    closed: bool = True,
) -> dict:
    """Full pipeline: load image, scan edges, fit contour.

    This is the main entry point for programmatic use (not via MCP).

    Returns a dict with:
        contour_points: List of [x, y] pixel coords forming the contour.
        left_edges: Raw left edge points detected.
        right_edges: Raw right edge points detected.
        anchor_count: Number of anchors after bezier fitting.
        scan_line_count: Number of cross-axis scan lines run.
        error: Optional error message if something failed.
    """
    gray = _load_grayscale(image_path)
    if gray is None:
        return {"error": f"Could not read image: {image_path}"}

    # Scan edges along the axis
    edges = scan_edges_along_axis(
        gray,
        axis_center=axis_center,
        axis_angle_deg=axis_angle_deg,
        scan_start=scan_start,
        scan_end=scan_end,
        scan_step=scan_step,
        cross_range=cross_range,
        sample_step=sample_step,
        bright_threshold=bright_threshold,
        dark_threshold=dark_threshold,
    )

    if not edges["left_edges"] and not edges["right_edges"]:
        return {
            "error": "No edge transitions found in scan region",
            "scan_line_count": edges["scan_line_count"],
            "left_edges": [],
            "right_edges": [],
        }

    # Fit bezier contour through detected edges
    contour = fit_contour_from_edges(
        edges["left_edges"],
        edges["right_edges"],
        error_threshold=error_threshold,
        max_segments=max_segments,
        closed=closed,
    )

    return {
        "contour_points": contour["contour_points"],
        "left_edges": edges["left_edges"],
        "right_edges": edges["right_edges"],
        "left_anchors": contour["left_anchors"],
        "right_anchors": contour["right_anchors"],
        "anchor_count": contour["anchor_count"],
        "scan_line_count": edges["scan_line_count"],
        "all_transitions": edges["all_transitions"],
    }


# ── Tier 2: MCP Tool Registration ───────────────────────────────────────


def register(mcp):
    """Register the adobe_ai_contour_scanner tool."""

    @mcp.tool(
        name="adobe_ai_contour_scanner",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_contour_scanner(params: AiContourScannerInput) -> str:
        """Axis-guided contour scanner for extracting vector paths from reference images.

        Actions:
        - scan_feature: scan a region along an axis and return edge contour points
        - place_contour: place a scanned contour as a path in Illustrator
        """

        if params.action == "scan_feature":
            # ── Scan feature edges from the reference image ──
            if not os.path.exists(params.image_path):
                return json.dumps({"error": f"Image not found: {params.image_path}"})

            result = scan_feature(
                image_path=params.image_path,
                axis_center=(params.axis_center_x, params.axis_center_y),
                axis_angle_deg=params.axis_angle,
                scan_start=params.scan_start,
                scan_end=params.scan_end,
                scan_step=params.scan_step,
                cross_range=params.cross_range,
                sample_step=params.sample_step,
                bright_threshold=params.bright_threshold,
                dark_threshold=params.dark_threshold,
                error_threshold=params.error_threshold,
                max_segments=params.max_segments,
                closed=params.closed,
            )

            if "error" in result and not result.get("contour_points"):
                return json.dumps(result)

            return json.dumps({
                "action": "scan_feature",
                "contour_points": result["contour_points"],
                "anchor_count": result["anchor_count"],
                "left_edge_count": len(result["left_edges"]),
                "right_edge_count": len(result["right_edges"]),
                "scan_line_count": result["scan_line_count"],
                "left_edges": result["left_edges"],
                "right_edges": result["right_edges"],
            })

        elif params.action == "place_contour":
            # ── Place a scanned contour as a path in Illustrator ──
            if not params.contour_json:
                return json.dumps({"error": "place_contour requires contour_json"})

            try:
                contour_data = json.loads(params.contour_json)
            except (json.JSONDecodeError, TypeError) as exc:
                return json.dumps({"error": f"Invalid contour_json: {exc}"})

            # Extract contour points from the scan result
            contour_points = contour_data.get("contour_points", [])
            if not contour_points:
                return json.dumps({"error": "contour_json has no contour_points"})

            # Convert pixel coords to AI coords using rig transform if available
            rig = _load_rig(params.character_name)
            transform = rig.get("transform")
            ai_points = pixels_to_ai_coords(contour_points, transform)

            # Build JSX to create the path
            escaped_layer = escape_jsx_string(params.layer_name)
            escaped_name = escape_jsx_string(params.path_name)
            points_json = json.dumps(ai_points)
            closed_js = "true" if params.closed else "false"

            jsx = f"""
(function() {{
    var doc = app.activeDocument;
    var layer = null;
    for (var i = 0; i < doc.layers.length; i++) {{
        if (doc.layers[i].name === "{escaped_layer}") {{
            layer = doc.layers[i];
            break;
        }}
    }}
    if (!layer) {{
        layer = doc.layers.add();
        layer.name = "{escaped_layer}";
    }}
    doc.activeLayer = layer;

    var path = layer.pathItems.add();
    path.setEntirePath({points_json});
    path.closed = {closed_js};
    path.filled = false;
    path.stroked = true;
    path.strokeWidth = {params.stroke_width};
    path.name = "{escaped_name}";

    var black = new RGBColor();
    black.red = 0;
    black.green = 0;
    black.blue = 0;
    path.strokeColor = black;

    var result = [];
    for (var i = 0; i < path.pathPoints.length; i++) {{
        var a = path.pathPoints[i].anchor;
        result.push([Math.round(a[0] * 100) / 100, Math.round(a[1] * 100) / 100]);
    }}
    return JSON.stringify({{
        name: path.name,
        layer: layer.name,
        pointCount: path.pathPoints.length,
        bounds: path.geometricBounds,
        placed_points: result
    }});
}})();
"""
            jsx_result = await _async_run_jsx("illustrator", jsx)

            if not jsx_result["success"]:
                return json.dumps({
                    "error": f"Path creation failed: {jsx_result['stderr']}",
                    "ai_points": ai_points,
                    "point_count": len(ai_points),
                })

            try:
                placed = json.loads(jsx_result["stdout"])
            except (json.JSONDecodeError, TypeError):
                placed = {"raw": jsx_result["stdout"]}

            return json.dumps({
                "action": "place_contour",
                "name": placed.get("name", params.path_name),
                "layer": placed.get("layer", params.layer_name),
                "point_count": placed.get("pointCount", len(ai_points)),
                "bounds": placed.get("bounds", []),
                "ai_points": ai_points,
                "transform_used": "rig" if transform else "fallback_y_flip",
            })

        else:
            return json.dumps({
                "error": f"Unknown action: {params.action}. Valid: scan_feature, place_contour"
            })
