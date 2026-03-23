"""Compare Illustrator artboard against a reference image — gradient-descent feedback loop.

Exports the active artboard as PNG, loads both images with OpenCV, extracts and
matches contours, then computes per-point correction vectors. The result is a JSON
object that tells the LLM exactly how to adjust each shape to converge on the
reference — turning the illustration feedback loop into gradient descent.
"""

import json
import math
import os
import tempfile

import cv2
import numpy as np

from adobe_mcp.engine import _async_run_jsx
from adobe_mcp.jsx.templates import escape_jsx_string
from adobe_mcp.apps.common.models import CompareDrawingInput


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _resample_contour(contour: np.ndarray, num_points: int) -> np.ndarray:
    """Resample a contour to a fixed number of evenly-spaced points along its arc."""
    contour = contour.reshape(-1, 2).astype(np.float64)
    if len(contour) < 2:
        return np.tile(contour[0], (num_points, 1))

    # Cumulative arc length
    diffs = np.diff(contour, axis=0)
    segment_lengths = np.sqrt((diffs ** 2).sum(axis=1))
    cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])
    total_length = cumulative[-1]

    if total_length == 0:
        return np.tile(contour[0], (num_points, 1))

    # Interpolate at evenly-spaced arc-length positions
    sample_dists = np.linspace(0, total_length, num_points, endpoint=False)
    resampled = np.zeros((num_points, 2))
    for i, d in enumerate(sample_dists):
        idx = int(np.searchsorted(cumulative, d, side="right")) - 1
        idx = min(idx, len(contour) - 2)
        t = (d - cumulative[idx]) / max(segment_lengths[idx], 1e-8)
        resampled[i] = contour[idx] + t * (contour[idx + 1] - contour[idx])
    return resampled


def _contour_centroid(contour: np.ndarray) -> tuple[float, float]:
    """Return the (x, y) centroid of a contour."""
    pts = contour.reshape(-1, 2)
    return float(pts[:, 0].mean()), float(pts[:, 1].mean())


def _extract_contours(img: np.ndarray, min_area: float) -> list[np.ndarray]:
    """Edge-detect and return external contours above *min_area* pixels."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [c for c in contours if cv2.contourArea(c) > min_area]


def _compute_corrections(
    ref_contour: np.ndarray,
    draw_contour: np.ndarray,
    num_sample_points: int = 32,
) -> tuple[list[dict], float]:
    """Resample both contours, compute displacement vectors and Hausdorff distance."""
    ref_pts = _resample_contour(ref_contour, num_sample_points)
    draw_pts = _resample_contour(draw_contour, num_sample_points)

    # Per-point displacement (reference minus drawing = correction vector)
    corrections: list[dict] = []
    for i in range(num_sample_points):
        dx = float(ref_pts[i][0] - draw_pts[i][0])
        dy = float(ref_pts[i][1] - draw_pts[i][1])
        corrections.append({"idx": i, "dx": round(dx, 1), "dy": round(dy, 1)})

    # Hausdorff distance — worst-case mismatch between the two point sets
    fwd = max(
        float(min(np.linalg.norm(r - d) for d in draw_pts))
        for r in ref_pts
    )
    bwd = max(
        float(min(np.linalg.norm(d - r) for r in ref_pts))
        for d in draw_pts
    )
    hausdorff = max(fwd, bwd)

    return corrections, hausdorff


def _severity(hausdorff: float) -> str:
    """Classify correction severity by Hausdorff distance."""
    if hausdorff > 20:
        return "critical"
    if hausdorff > 10:
        return "high"
    if hausdorff > 5:
        return "medium"
    return "low"


def _match_contours(
    ref_contours: list[np.ndarray],
    draw_contours: list[np.ndarray],
) -> list[tuple[int, int]]:
    """Greedy nearest-centroid + area-ratio matching between two contour sets.

    For each reference contour, finds the best unmatched drawing contour using
    a cost function of normalised centroid distance plus log-area-ratio.
    Drawing contours are consumed once matched.
    """
    if not ref_contours or not draw_contours:
        return []

    ref_info = []
    for i, c in enumerate(ref_contours):
        cx, cy = _contour_centroid(c)
        area = max(cv2.contourArea(c), 1.0)
        ref_info.append((i, cx, cy, area))

    draw_info = []
    for j, c in enumerate(draw_contours):
        cx, cy = _contour_centroid(c)
        area = max(cv2.contourArea(c), 1.0)
        draw_info.append((j, cx, cy, area))

    # Normalise distance by image diagonal so cost is scale-independent
    all_pts = np.concatenate(
        [c.reshape(-1, 2) for c in ref_contours + draw_contours]
    )
    diag = float(np.linalg.norm(all_pts.max(axis=0) - all_pts.min(axis=0)))
    diag = max(diag, 1.0)

    matched: list[tuple[int, int]] = []
    available = set(range(len(draw_info)))

    for ri, rcx, rcy, rarea in ref_info:
        best_j: int | None = None
        best_cost = float("inf")
        for j in available:
            dj, dcx, dcy, darea = draw_info[j]
            # Reject if areas differ by more than 3x
            area_ratio = rarea / darea
            if area_ratio > 3.0 or area_ratio < 1.0 / 3.0:
                continue
            norm_dist = math.hypot(rcx - dcx, rcy - dcy) / diag
            log_area = abs(math.log(area_ratio))
            cost = norm_dist + log_area
            if cost < best_cost:
                best_cost = cost
                best_j = j
        if best_j is not None:
            matched.append((ri, draw_info[best_j][0]))
            available.discard(best_j)

    return matched


def _draw_overlay(
    ref_img: np.ndarray,
    draw_img: np.ndarray,
    matches: list[dict],
) -> np.ndarray:
    """Blend the two images 50/50 and draw correction arrows for significant displacements."""
    overlay = cv2.addWeighted(ref_img, 0.5, draw_img, 0.5, 0)

    for match in matches:
        draw_cx = match["draw_centroid"]
        for corr in match["point_corrections"]:
            mag = abs(corr["dx"]) + abs(corr["dy"])
            if mag <= 5:
                continue  # skip negligible corrections
            # Arrow origin = drawing point (centroid + offset approximation)
            # For simplicity, draw from draw_centroid shifted by point index spread
            ox = int(draw_cx[0])
            oy = int(draw_cx[1])
            ex = ox + int(corr["dx"])
            ey = oy + int(corr["dy"])
            # Colour by severity
            sev = match.get("severity", "low")
            colour = {
                "critical": (0, 0, 255),
                "high": (0, 128, 255),
                "medium": (0, 255, 255),
                "low": (0, 255, 0),
            }.get(sev, (255, 255, 255))
            cv2.arrowedLine(overlay, (ox, oy), (ex, ey), colour, 1, tipLength=0.3)
            break  # one representative arrow per shape keeps the overlay readable

    return overlay


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register_compare_tool(mcp):
    """Register the adobe_ai_compare_drawing tool."""

    @mcp.tool(
        name="adobe_ai_compare_drawing",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_compare_drawing(params: CompareDrawingInput) -> str:
        """Compare the active Illustrator artboard against a reference image.

        Returns per-shape correction vectors, a convergence score, and an
        overlay image showing the delta. Use this to iteratively refine a
        drawing toward a reference — each call tells you exactly what to nudge.
        """
        # ── Step 1: Validate reference image exists ──────────────────
        if not os.path.isfile(params.reference_path):
            return json.dumps({"error": f"Reference image not found: {params.reference_path}"})

        # ── Step 2: Export current artboard as PNG via JSX ───────────
        tmp_export = tempfile.mktemp(suffix=".png", prefix="ai_compare_")
        tmp_export_escaped = escape_jsx_string(tmp_export)

        jsx = f"""
(function() {{
    var doc = app.activeDocument;
    var opts = new ExportOptionsPNG24();
    opts.horizontalScale = 100;
    opts.verticalScale = 100;
    opts.transparency = false;
    opts.antiAliasing = true;
    opts.artBoardClipping = true;
    doc.artboards.setActiveArtboardIndex({params.artboard_index});
    doc.exportFile(new File("{tmp_export_escaped}"), ExportType.PNG24, opts);
    return "exported";
}})();
"""
        result = await _async_run_jsx("illustrator", jsx)
        if not result["success"]:
            return json.dumps({"error": f"Failed to export artboard: {result['stderr']}"})

        # ── Step 3: Load both images ─────────────────────────────────
        ref_img = cv2.imread(params.reference_path)
        if ref_img is None:
            return json.dumps({"error": f"Could not decode reference image: {params.reference_path}"})

        draw_img = cv2.imread(tmp_export)
        if draw_img is None:
            return json.dumps({"error": f"Could not decode exported artboard image: {tmp_export}"})

        # Clean up temp export now that it is loaded into memory
        try:
            os.remove(tmp_export)
        except OSError:
            pass

        # Resize drawing to match reference dimensions for fair comparison
        draw_img = cv2.resize(draw_img, (ref_img.shape[1], ref_img.shape[0]))

        # ── Step 4: Compute minimum contour area from image size ─────
        img_area = ref_img.shape[0] * ref_img.shape[1]
        min_area = img_area * (params.min_area_pct / 100.0)

        # ── Step 5: Extract contours from both images ────────────────
        ref_contours = _extract_contours(ref_img, min_area)
        draw_contours = _extract_contours(draw_img, min_area)

        # ── Step 6: Match contours between reference and drawing ─────
        matched_pairs = _match_contours(ref_contours, draw_contours)
        matched_ref_idxs = {ri for ri, _ in matched_pairs}
        matched_draw_idxs = {di for _, di in matched_pairs}

        # ── Step 7: Compute per-match correction vectors ─────────────
        matches: list[dict] = []
        for shape_idx, (ri, di) in enumerate(matched_pairs):
            corrections, hausdorff = _compute_corrections(ref_contours[ri], draw_contours[di])
            rcx, rcy = _contour_centroid(ref_contours[ri])
            dcx, dcy = _contour_centroid(draw_contours[di])
            matches.append({
                "shape_idx": shape_idx,
                "ref_centroid": [round(rcx, 1), round(rcy, 1)],
                "draw_centroid": [round(dcx, 1), round(dcy, 1)],
                "centroid_offset": [round(rcx - dcx, 1), round(rcy - dcy, 1)],
                "ref_area": int(cv2.contourArea(ref_contours[ri])),
                "draw_area": int(cv2.contourArea(draw_contours[di])),
                "hausdorff_dist": round(hausdorff, 1),
                "severity": _severity(hausdorff),
                "point_corrections": corrections,
            })

        # ── Step 8: Pixel-level similarity (0-1) ────────────────────
        gray_ref = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)
        gray_draw = cv2.cvtColor(draw_img, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(gray_ref, gray_draw)
        pixel_similarity = 1.0 - (float(np.mean(diff)) / 255.0)

        # ── Step 9: Convergence score ────────────────────────────────
        match_ratio = len(matched_pairs) / max(len(ref_contours), 1)
        convergence = 0.5 * pixel_similarity + 0.5 * match_ratio

        # ── Step 10: Generate overlay image ──────────────────────────
        overlay = _draw_overlay(ref_img, draw_img, matches)
        overlay_path = params.export_path or tempfile.mktemp(
            suffix="_overlay.png", prefix="ai_compare_"
        )
        cv2.imwrite(overlay_path, overlay)

        # ── Step 11: Build result payload ────────────────────────────
        payload = {
            "convergence_score": round(convergence, 3),
            "pixel_similarity": round(pixel_similarity, 3),
            "contour_match_ratio": round(match_ratio, 3),
            "overlay_path": overlay_path,
            "reference_contours": len(ref_contours),
            "drawing_contours": len(draw_contours),
            "matched_shapes": len(matched_pairs),
            "unmatched_reference": len(ref_contours) - len(matched_ref_idxs),
            "unmatched_drawing": len(draw_contours) - len(matched_draw_idxs),
            "corrections": matches,
        }

        return json.dumps(payload)
