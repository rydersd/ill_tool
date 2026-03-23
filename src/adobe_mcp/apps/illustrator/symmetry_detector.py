"""Auto-detect bilateral and radial symmetry in images.

Analyzes an image for bilateral symmetry (horizontal flip similarity)
and radial symmetry (rotation by 360/N degrees), returning confidence
scores and detected axis positions.

Pure Python implementation using OpenCV and numpy.
"""

import json
import math
import os
from typing import Optional

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class AiSymmetryDetectorInput(BaseModel):
    """Detect bilateral and radial symmetry in an image."""
    model_config = ConfigDict(str_strip_whitespace=True)
    image_path: str = Field(..., description="Path to the image to analyze")
    max_radial_n: int = Field(
        default=8,
        description="Maximum N-fold radial symmetry to test (2..N)",
        ge=2, le=16,
    )
    bilateral_threshold: float = Field(
        default=0.7,
        description="SSIM threshold above which bilateral symmetry is detected",
        ge=0.0, le=1.0,
    )
    radial_threshold: float = Field(
        default=0.7,
        description="Similarity threshold for radial symmetry detection",
        ge=0.0, le=1.0,
    )


# ---------------------------------------------------------------------------
# Symmetry detection functions
# ---------------------------------------------------------------------------


def _compute_similarity(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """Compute normalized similarity between two images using correlation.

    Uses normalized cross-correlation which properly accounts for mean
    intensity and variance, returning 0 for uncorrelated images and 1
    for identical images. Robust against uniform-shift differences.

    Both images must have the same shape.
    """
    if img_a.shape != img_b.shape:
        img_b = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))

    a = img_a.astype(np.float64).ravel()
    b = img_b.astype(np.float64).ravel()

    a_mean = a.mean()
    b_mean = b.mean()
    a_centered = a - a_mean
    b_centered = b - b_mean

    a_std = np.sqrt(np.mean(a_centered ** 2))
    b_std = np.sqrt(np.mean(b_centered ** 2))

    # If either image is uniform (zero variance), similarity depends on
    # whether both are the same uniform value
    if a_std < 1e-6 or b_std < 1e-6:
        if a_std < 1e-6 and b_std < 1e-6:
            # Both uniform — similar only if same mean
            return 1.0 if abs(a_mean - b_mean) < 1.0 else 0.0
        return 0.0

    # Normalized cross-correlation (Pearson correlation coefficient)
    ncc = np.mean(a_centered * b_centered) / (a_std * b_std)
    # Map from [-1, 1] to [0, 1] where 1=identical, 0=uncorrelated
    similarity = (ncc + 1.0) / 2.0
    return max(0.0, min(1.0, float(similarity)))


def detect_bilateral_symmetry(image_path: str) -> dict:
    """Detect bilateral (left-right) symmetry by flipping and comparing.

    Also scans for the optimal vertical axis position that maximizes
    symmetry score.

    Args:
        image_path: path to the image

    Returns:
        dict with detected (bool), confidence (float), axis_x (int).
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return {"error": f"Could not read image: {image_path}"}

    h, w = img.shape[:2]

    # Full-image flip comparison
    flipped = cv2.flip(img, 1)  # horizontal flip
    full_score = _compute_similarity(img, flipped)

    # Find best axis position by testing different vertical lines.
    # The score is penalized when the axis is far from center, to avoid
    # degenerate matches at extreme positions where one side is tiny.
    best_score = full_score
    best_axis = w // 2

    # Test axis positions at 10% intervals around center
    step = max(1, w // 20)
    for offset in range(-5, 6):
        axis_x = w // 2 + offset * step
        if axis_x < 10 or axis_x > w - 10:
            continue

        # Compare left half (mirrored) with right half
        left = img[:, :axis_x]
        right = img[:, axis_x:]

        # Use the larger side as reference to avoid degenerate small-side matches.
        # Pad the shorter comparison region with zeros (unmatched pixels count as
        # differences).
        max_half = max(left.shape[1], right.shape[1])
        left_flipped = cv2.flip(left, 1)

        # Create padded arrays of size max_half
        left_padded = np.zeros((h, max_half), dtype=np.uint8)
        right_padded = np.zeros((h, max_half), dtype=np.uint8)
        left_padded[:, :left_flipped.shape[1]] = left_flipped
        right_padded[:, :right.shape[1]] = right

        score = _compute_similarity(left_padded, right_padded)

        # Penalize axes far from center — perfect symmetry should be centered
        center_distance = abs(axis_x - w // 2) / (w // 2)
        score *= (1.0 - 0.3 * center_distance)

        if score > best_score:
            best_score = score
            best_axis = axis_x

    return {
        "detected": bool(best_score > 0.7),
        "confidence": round(float(best_score), 4),
        "axis_x": int(best_axis),
        "image_width": w,
        "image_height": h,
    }


def detect_radial_symmetry(image_path: str, max_n: int = 8) -> dict:
    """Detect N-fold radial symmetry by rotating and comparing.

    Tests rotations of 360/N degrees for N=2..max_n. If the rotated image
    closely matches the original, radial symmetry of order N is detected.

    Args:
        image_path: path to the image
        max_n: maximum fold count to test

    Returns:
        dict with detected (bool), best_n (int), confidence (float), all_scores.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return {"error": f"Could not read image: {image_path}"}

    h, w = img.shape[:2]
    center = (w / 2, h / 2)

    # Use the largest inscribed circle region to avoid rotation edge artifacts
    radius = min(w, h) // 2
    # Create circular mask
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, (w // 2, h // 2), radius, 255, -1)

    img_masked = cv2.bitwise_and(img, img, mask=mask)

    scores = {}
    best_n = 0
    best_score = 0.0

    for n in range(2, max_n + 1):
        angle = 360.0 / n
        rot_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(img_masked, rot_matrix, (w, h))
        rotated_masked = cv2.bitwise_and(rotated, rotated, mask=mask)

        score = _compute_similarity(img_masked, rotated_masked)
        scores[n] = round(score, 4)

        if score > best_score:
            best_score = score
            best_n = n

    return {
        "detected": bool(best_score > 0.7),
        "best_n": best_n,
        "confidence": round(float(best_score), 4),
        "all_scores": scores,
        "image_size": [w, h],
    }


def get_symmetry_axis(image_path: str) -> dict:
    """Return the primary symmetry axis position and angle.

    For bilateral symmetry, returns the vertical axis.
    For radial symmetry, returns the center point.

    Args:
        image_path: path to the image

    Returns:
        dict with axis_x, axis_y, angle, symmetry_type.
    """
    bilateral = detect_bilateral_symmetry(image_path)
    if "error" in bilateral:
        return bilateral

    w = bilateral["image_width"]
    h = bilateral["image_height"]

    if bilateral["detected"]:
        return {
            "symmetry_type": "bilateral",
            "axis_x": bilateral["axis_x"],
            "axis_y": h // 2,
            "angle": 90.0,  # vertical axis
            "confidence": bilateral["confidence"],
        }

    # Check radial as fallback
    radial = detect_radial_symmetry(image_path, max_n=8)
    if "error" in radial:
        return radial

    if radial["detected"]:
        return {
            "symmetry_type": f"radial_{radial['best_n']}-fold",
            "axis_x": w // 2,
            "axis_y": h // 2,
            "angle": 0.0,  # center point, no single axis
            "confidence": radial["confidence"],
        }

    return {
        "symmetry_type": "none",
        "axis_x": w // 2,
        "axis_y": h // 2,
        "angle": 0.0,
        "confidence": 0.0,
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register(mcp):
    """Register the adobe_ai_symmetry_detector tool."""

    @mcp.tool(
        name="adobe_ai_symmetry_detector",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def adobe_ai_symmetry_detector(params: AiSymmetryDetectorInput) -> str:
        """Detect bilateral and radial symmetry in an image.

        Checks for left-right (bilateral) symmetry via horizontal flip comparison,
        and N-fold radial symmetry via rotation comparison. Returns confidence
        scores and axis positions.
        """
        if not os.path.isfile(params.image_path):
            return json.dumps({"error": f"Image not found: {params.image_path}"})

        bilateral = detect_bilateral_symmetry(params.image_path)
        if "error" in bilateral:
            return json.dumps(bilateral)

        radial = detect_radial_symmetry(
            params.image_path, max_n=params.max_radial_n
        )
        if "error" in radial:
            return json.dumps(radial)

        # Apply user thresholds
        bilateral["detected"] = bilateral["confidence"] >= params.bilateral_threshold
        radial["detected"] = radial["confidence"] >= params.radial_threshold

        return json.dumps({
            "bilateral": bilateral,
            "radial": radial,
        }, indent=2)
