"""Tests for form_3d_projection — 3D orientation inference and projection."""

import math
import pytest
from adobe_mcp.apps.illustrator.form_3d_projection import (
    infer_orientation_from_axis,
    place_feature_on_surface,
    mirror_point_3d,
    mirror_points_3d,
    continue_feature_line,
    estimate_form_dimensions,
    rotation_matrix_z,
    rotation_matrix_y,
)
import numpy as np


class TestInferOrientation:
    def test_vertical_axis_no_tilt(self):
        """Perfectly vertical axis → 0 roll."""
        o = infer_orientation_from_axis([400, -200], [400, -600])
        assert abs(o["roll_deg"]) < 0.1

    def test_tilted_axis(self):
        """Axis tilted right → positive roll."""
        o = infer_orientation_from_axis([400, -200], [430, -600])
        assert o["roll_deg"] > 0
        assert o["roll_deg"] < 15

    def test_axis_length(self):
        o = infer_orientation_from_axis([0, 0], [300, -400])
        assert abs(o["axis_length"] - 500) < 1

    def test_axis_center(self):
        o = infer_orientation_from_axis([100, -200], [300, -400])
        assert o["axis_center"] == [200.0, -300.0]

    def test_yaw_from_widths(self):
        """Near side wider than far → positive yaw."""
        o = infer_orientation_from_axis([400, -200], [400, -600],
                                        near_side_width=200, far_side_width=150)
        assert o["yaw_deg"] > 0

    def test_symmetric_widths_no_yaw(self):
        o = infer_orientation_from_axis([400, -200], [400, -600],
                                        near_side_width=200, far_side_width=200)
        assert abs(o["yaw_deg"]) < 0.1


class TestPlaceFeature:
    def test_center_front(self):
        o = infer_orientation_from_axis([400, -200], [400, -600])
        r = place_feature_on_surface(o, [0.5, 0.5], [200, 400, 100], "front")
        assert r["visible"] is True
        assert abs(r["position_2d"][0] - 400) < 5
        assert abs(r["position_2d"][1] - (-400)) < 5

    def test_back_face_hidden(self):
        o = infer_orientation_from_axis([400, -200], [400, -600])
        r = place_feature_on_surface(o, [0.5, 0.5], [200, 400, 100], "back")
        assert r["visible"] is False


class TestMirror3D:
    def test_mirror_center_stays(self):
        """Point on the centerline stays on the centerline."""
        o = infer_orientation_from_axis([400, -200], [400, -600])
        r = mirror_point_3d(o, [400, -400], [200, 400, 100], "front")
        assert abs(r["mirrored_2d"][0] - 400) < 5

    def test_mirror_left_goes_right(self):
        """Point left of center mirrors to the right."""
        o = infer_orientation_from_axis([400, -200], [400, -600])
        r = mirror_point_3d(o, [300, -400], [200, 400, 100], "front")
        assert r["mirrored_2d"][0] > 400

    def test_mirror_multiple(self):
        o = infer_orientation_from_axis([400, -200], [400, -600])
        pts = [[300, -400], [350, -350]]
        results = mirror_points_3d(o, pts, [200, 400, 100], "front")
        assert len(results) == 2
        assert all(r["mirrored_2d"][0] > 400 for r in results)

    def test_tilted_mirror_differs_from_flat(self):
        """Tilted axis should produce different mirror than vertical."""
        o_vertical = infer_orientation_from_axis([400, -200], [400, -600])
        o_tilted = infer_orientation_from_axis([400, -200], [430, -600])
        r_v = mirror_point_3d(o_vertical, [300, -400], [200, 400, 100])
        r_t = mirror_point_3d(o_tilted, [300, -400], [200, 400, 100])
        # Tilted should give different result
        assert abs(r_v["mirrored_2d"][0] - r_t["mirrored_2d"][0]) > 0.5 or \
               abs(r_v["mirrored_2d"][1] - r_t["mirrored_2d"][1]) > 0.5


class TestContinueLine:
    def test_extends_past_edge(self):
        o = infer_orientation_from_axis([400, -200], [400, -600])
        r = continue_feature_line(o, [300, -400], [500, -400], [200, 400, 100])
        assert r["extended_point_2d"][0] > 500

    def test_wraps_direction(self):
        o = infer_orientation_from_axis([400, -200], [400, -600])
        r = continue_feature_line(o, [300, -400], [500, -400], [200, 400, 100])
        assert r["wraps_to_surface"] == "right"


class TestEstimateDimensions:
    def test_basic(self):
        dims = estimate_form_dimensions(400, 200)
        assert len(dims) == 3
        assert dims[0] == 200  # width
        assert dims[1] == 400  # height

    def test_with_far_width(self):
        dims = estimate_form_dimensions(400, 200, 150)
        assert dims[2] > 0  # depth estimated


class TestRotationMatrices:
    def test_identity_z(self):
        r = rotation_matrix_z(0)
        np.testing.assert_array_almost_equal(r, np.eye(3))

    def test_identity_y(self):
        r = rotation_matrix_y(0)
        np.testing.assert_array_almost_equal(r, np.eye(3))

    def test_90_z(self):
        r = rotation_matrix_z(math.pi / 2)
        result = r @ np.array([1, 0, 0])
        np.testing.assert_array_almost_equal(result, [0, 1, 0])
