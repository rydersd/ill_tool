"""Illustrator tools — 130 tools split by feature.

Registration chain:
    apps/__init__.py -> illustrator/__init__.py -> {new_document, shapes, text, paths, export, layers, modify, inspect, image_trace, analyze_reference, reference_underlay, vtrace, anchor_edit, silhouette, auto_correct, proportion_grid, style_transfer, shape_recipes, contour_to_path, smart_shape, bezier_optimize, curve_fit, artboard_from_ref, path_boolean, symmetry, layer_auto_organize, group_and_name, color_sampler, stroke_profiles, path_offset, path_weld, snap_to_grid, undo_checkpoint, reference_crop, drawing_orchestrator, skeleton_annotate, body_part_label, skeleton_build, part_bind, joint_rotate, pose_snapshot, pose_interpolate, ik_solver, onion_skin, character_template, pose_from_image, keyframe_timeline, motion_path, storyboard_panel, scene_manager, background_layer, multi_character, shot_list_gen, beat_sheet, production_notes, continuity_check, asset_registry, pdf_export, animatic_preview, prop_manager, lighting_notation, transition_planner, audio_sync, sequence_assembler, rig_controllers, storyboard_template, panel_text, camera_notation, character_turnaround, landmark_axis, construction_draw, gesture_line, proportion_check, negative_space, line_weight, form_volume, thumbnail_grid, scene_composition, character_expression, batch_pose, staging_system, revision_tracker, edl_export, thumbnail_promote, environment, continuity_enhanced, director_markup, audio_sync_enhanced, cross_section, shading_inference, color_region_cluster, contour_nesting, symmetry_detector, part_size_ranker, joint_geometry, object_classifier, template_inheritance, template_scaling, template_export, template_library_search, scene_graph, interaction_zones, lod_system, asset_versioning, batch_rig, cv_confidence, correction_learning, cross_object_patterns, failure_detection, active_learning, object_hierarchy, part_segmenter, part_questioner, connection_detector, hierarchy_builder, relationship_types, constraint_system, chain_detector, hierarchy_templates, template_matcher, ik_chain_auto, motion_range_from_shape, deformation_zones, secondary_motion, weight_zones, pose_library_generic, physics_hints, timing_curves, anticipation_markers, motion_path_from_hierarchy}.py
"""

from adobe_mcp.apps.illustrator.new_document import register as _reg_new_document
from adobe_mcp.apps.illustrator.shapes import register as _reg_shapes
from adobe_mcp.apps.illustrator.text import register as _reg_text
from adobe_mcp.apps.illustrator.paths import register as _reg_paths
from adobe_mcp.apps.illustrator.export import register as _reg_export
from adobe_mcp.apps.illustrator.layers import register as _reg_layers
from adobe_mcp.apps.illustrator.modify import register as _reg_modify
from adobe_mcp.apps.illustrator.inspect import register as _reg_inspect
from adobe_mcp.apps.illustrator.image_trace import register as _reg_image_trace
from adobe_mcp.apps.illustrator.analyze_reference import register as _reg_analyze_reference
from adobe_mcp.apps.illustrator.reference_underlay import register as _reg_reference_underlay
from adobe_mcp.apps.illustrator.vtrace import register as _reg_vtrace
from adobe_mcp.apps.illustrator.anchor_edit import register as _reg_anchor_edit
from adobe_mcp.apps.illustrator.silhouette import register as _reg_silhouette
from adobe_mcp.apps.illustrator.auto_correct import register as _reg_auto_correct
from adobe_mcp.apps.illustrator.proportion_grid import register as _reg_proportion_grid
from adobe_mcp.apps.illustrator.style_transfer import register as _reg_style_transfer
from adobe_mcp.apps.illustrator.shape_recipes import register as _reg_shape_recipes
from adobe_mcp.apps.illustrator.contour_to_path import register as _reg_contour_to_path
from adobe_mcp.apps.illustrator.smart_shape import register as _reg_smart_shape
from adobe_mcp.apps.illustrator.bezier_optimize import register as _reg_bezier_optimize
from adobe_mcp.apps.illustrator.curve_fit import register as _reg_curve_fit
from adobe_mcp.apps.illustrator.artboard_from_ref import register as _reg_artboard_from_ref
from adobe_mcp.apps.illustrator.path_boolean import register as _reg_path_boolean
from adobe_mcp.apps.illustrator.symmetry import register as _reg_symmetry
from adobe_mcp.apps.illustrator.layer_auto_organize import register as _reg_layer_auto_organize
from adobe_mcp.apps.illustrator.group_and_name import register as _reg_group_and_name
from adobe_mcp.apps.illustrator.color_sampler import register as _reg_color_sampler
from adobe_mcp.apps.illustrator.stroke_profiles import register as _reg_stroke_profiles
from adobe_mcp.apps.illustrator.path_offset import register as _reg_path_offset
from adobe_mcp.apps.illustrator.path_weld import register as _reg_path_weld
from adobe_mcp.apps.illustrator.snap_to_grid import register as _reg_snap_to_grid
from adobe_mcp.apps.illustrator.undo_checkpoint import register as _reg_undo_checkpoint
from adobe_mcp.apps.illustrator.reference_crop import register as _reg_reference_crop
from adobe_mcp.apps.illustrator.drawing_orchestrator import register as _reg_drawing_orchestrator
from adobe_mcp.apps.illustrator.skeleton_annotate import register as _reg_skeleton_annotate
from adobe_mcp.apps.illustrator.body_part_label import register as _reg_body_part_label
from adobe_mcp.apps.illustrator.skeleton_build import register as _reg_skeleton_build
from adobe_mcp.apps.illustrator.part_bind import register as _reg_part_bind
from adobe_mcp.apps.illustrator.joint_rotate import register as _reg_joint_rotate
from adobe_mcp.apps.illustrator.pose_snapshot import register as _reg_pose_snapshot
from adobe_mcp.apps.illustrator.pose_interpolate import register as _reg_pose_interpolate
from adobe_mcp.apps.illustrator.ik_solver import register as _reg_ik_solver
from adobe_mcp.apps.illustrator.onion_skin import register as _reg_onion_skin
from adobe_mcp.apps.illustrator.character_template import register as _reg_character_template
from adobe_mcp.apps.illustrator.pose_from_image import register as _reg_pose_from_image
from adobe_mcp.apps.illustrator.keyframe_timeline import register as _reg_keyframe_timeline
from adobe_mcp.apps.illustrator.motion_path import register as _reg_motion_path
from adobe_mcp.apps.illustrator.storyboard_panel import register as _reg_storyboard_panel
from adobe_mcp.apps.illustrator.scene_manager import register as _reg_scene_manager
from adobe_mcp.apps.illustrator.background_layer import register as _reg_background_layer
from adobe_mcp.apps.illustrator.multi_character import register as _reg_multi_character
from adobe_mcp.apps.illustrator.shot_list_gen import register as _reg_shot_list_gen
from adobe_mcp.apps.illustrator.beat_sheet import register as _reg_beat_sheet
from adobe_mcp.apps.illustrator.production_notes import register as _reg_production_notes
from adobe_mcp.apps.illustrator.continuity_check import register as _reg_continuity_check
from adobe_mcp.apps.illustrator.asset_registry import register as _reg_asset_registry
from adobe_mcp.apps.illustrator.pdf_export import register as _reg_pdf_export
from adobe_mcp.apps.illustrator.animatic_preview import register as _reg_animatic_preview
from adobe_mcp.apps.illustrator.prop_manager import register as _reg_prop_manager
from adobe_mcp.apps.illustrator.lighting_notation import register as _reg_lighting_notation
from adobe_mcp.apps.illustrator.transition_planner import register as _reg_transition_planner
from adobe_mcp.apps.illustrator.audio_sync import register as _reg_audio_sync
from adobe_mcp.apps.illustrator.sequence_assembler import register as _reg_sequence_assembler
from adobe_mcp.apps.illustrator.rig_controllers import register as _reg_rig_controllers
from adobe_mcp.apps.illustrator.storyboard_template import register as _reg_storyboard_template
from adobe_mcp.apps.illustrator.panel_text import register as _reg_panel_text
from adobe_mcp.apps.illustrator.camera_notation import register as _reg_camera_notation
from adobe_mcp.apps.illustrator.character_turnaround import register as _reg_character_turnaround
from adobe_mcp.apps.illustrator.landmark_axis import register as _reg_landmark_axis
from adobe_mcp.apps.illustrator.construction_draw import register as _reg_construction_draw
from adobe_mcp.apps.illustrator.gesture_line import register as _reg_gesture_line
from adobe_mcp.apps.illustrator.proportion_check import register as _reg_proportion_check
from adobe_mcp.apps.illustrator.negative_space import register as _reg_negative_space
from adobe_mcp.apps.illustrator.line_weight import register as _reg_line_weight
from adobe_mcp.apps.illustrator.form_volume import register as _reg_form_volume
from adobe_mcp.apps.illustrator.thumbnail_grid import register as _reg_thumbnail_grid
from adobe_mcp.apps.illustrator.scene_composition import register as _reg_scene_composition
from adobe_mcp.apps.illustrator.character_expression import register as _reg_character_expression
from adobe_mcp.apps.illustrator.batch_pose import register as _reg_batch_pose
from adobe_mcp.apps.illustrator.staging_system import register as _reg_staging_system
from adobe_mcp.apps.illustrator.revision_tracker import register as _reg_revision_tracker
from adobe_mcp.apps.illustrator.edl_export import register as _reg_edl_export
from adobe_mcp.apps.illustrator.thumbnail_promote import register as _reg_thumbnail_promote
from adobe_mcp.apps.illustrator.environment import register as _reg_environment
from adobe_mcp.apps.illustrator.continuity_enhanced import register as _reg_continuity_enhanced
from adobe_mcp.apps.illustrator.director_markup import register as _reg_director_markup
from adobe_mcp.apps.illustrator.audio_sync_enhanced import register as _reg_audio_sync_enhanced
from adobe_mcp.apps.illustrator.cross_section import register as _reg_cross_section
from adobe_mcp.apps.illustrator.shading_inference import register as _reg_shading_inference
from adobe_mcp.apps.illustrator.color_region_cluster import register as _reg_color_region_cluster
from adobe_mcp.apps.illustrator.contour_nesting import register as _reg_contour_nesting
from adobe_mcp.apps.illustrator.symmetry_detector import register as _reg_symmetry_detector
from adobe_mcp.apps.illustrator.part_size_ranker import register as _reg_part_size_ranker
from adobe_mcp.apps.illustrator.joint_geometry import register as _reg_joint_geometry
from adobe_mcp.apps.illustrator.object_classifier import register as _reg_object_classifier
from adobe_mcp.apps.illustrator.template_inheritance import register as _reg_template_inheritance
from adobe_mcp.apps.illustrator.template_scaling import register as _reg_template_scaling
from adobe_mcp.apps.illustrator.template_export import register as _reg_template_export
from adobe_mcp.apps.illustrator.template_library_search import register as _reg_template_library_search
from adobe_mcp.apps.illustrator.scene_graph import register as _reg_scene_graph
from adobe_mcp.apps.illustrator.interaction_zones import register as _reg_interaction_zones
from adobe_mcp.apps.illustrator.lod_system import register as _reg_lod_system
from adobe_mcp.apps.illustrator.asset_versioning import register as _reg_asset_versioning
from adobe_mcp.apps.illustrator.batch_rig import register as _reg_batch_rig
from adobe_mcp.apps.illustrator.cv_confidence import register as _reg_cv_confidence
from adobe_mcp.apps.illustrator.correction_learning import register as _reg_correction_learning
from adobe_mcp.apps.illustrator.cross_object_patterns import register as _reg_cross_object_patterns
from adobe_mcp.apps.illustrator.failure_detection import register as _reg_failure_detection
from adobe_mcp.apps.illustrator.active_learning import register as _reg_active_learning
from adobe_mcp.apps.illustrator.object_hierarchy import register as _reg_object_hierarchy
from adobe_mcp.apps.illustrator.part_segmenter import register as _reg_part_segmenter
from adobe_mcp.apps.illustrator.part_questioner import register as _reg_part_questioner
from adobe_mcp.apps.illustrator.connection_detector import register as _reg_connection_detector
from adobe_mcp.apps.illustrator.hierarchy_builder import register as _reg_hierarchy_builder
from adobe_mcp.apps.illustrator.relationship_types import register as _reg_relationship_types
from adobe_mcp.apps.illustrator.constraint_system import register as _reg_constraint_system
from adobe_mcp.apps.illustrator.chain_detector import register as _reg_chain_detector
from adobe_mcp.apps.illustrator.hierarchy_templates import register as _reg_hierarchy_templates
from adobe_mcp.apps.illustrator.template_matcher import register as _reg_template_matcher
from adobe_mcp.apps.illustrator.ik_chain_auto import register as _reg_ik_chain_auto
from adobe_mcp.apps.illustrator.motion_range_from_shape import register as _reg_motion_range_from_shape
from adobe_mcp.apps.illustrator.deformation_zones import register as _reg_deformation_zones
from adobe_mcp.apps.illustrator.secondary_motion import register as _reg_secondary_motion
from adobe_mcp.apps.illustrator.weight_zones import register as _reg_weight_zones
from adobe_mcp.apps.illustrator.pose_library_generic import register as _reg_pose_library_generic
from adobe_mcp.apps.illustrator.physics_hints import register as _reg_physics_hints
from adobe_mcp.apps.illustrator.timing_curves import register as _reg_timing_curves
from adobe_mcp.apps.illustrator.anticipation_markers import register as _reg_anticipation_markers
from adobe_mcp.apps.illustrator.motion_path_from_hierarchy import register as _reg_motion_path_from_hierarchy


def register_illustrator_tools(mcp):
    """Register all 130 Illustrator tools."""
    _reg_new_document(mcp)
    _reg_shapes(mcp)
    _reg_text(mcp)
    _reg_paths(mcp)
    _reg_export(mcp)
    _reg_layers(mcp)
    _reg_modify(mcp)
    _reg_inspect(mcp)
    _reg_image_trace(mcp)
    _reg_analyze_reference(mcp)
    _reg_reference_underlay(mcp)
    _reg_vtrace(mcp)
    _reg_anchor_edit(mcp)
    _reg_silhouette(mcp)
    _reg_auto_correct(mcp)
    _reg_proportion_grid(mcp)
    _reg_style_transfer(mcp)
    _reg_shape_recipes(mcp)
    _reg_contour_to_path(mcp)
    _reg_smart_shape(mcp)
    _reg_bezier_optimize(mcp)
    _reg_curve_fit(mcp)
    _reg_artboard_from_ref(mcp)
    _reg_path_boolean(mcp)
    _reg_symmetry(mcp)
    _reg_layer_auto_organize(mcp)
    _reg_group_and_name(mcp)
    _reg_color_sampler(mcp)
    _reg_stroke_profiles(mcp)
    _reg_path_offset(mcp)
    _reg_path_weld(mcp)
    _reg_snap_to_grid(mcp)
    _reg_undo_checkpoint(mcp)
    _reg_reference_crop(mcp)
    _reg_drawing_orchestrator(mcp)
    _reg_skeleton_annotate(mcp)
    _reg_body_part_label(mcp)
    _reg_skeleton_build(mcp)
    _reg_part_bind(mcp)
    _reg_joint_rotate(mcp)
    _reg_pose_snapshot(mcp)
    _reg_pose_interpolate(mcp)
    _reg_ik_solver(mcp)
    _reg_onion_skin(mcp)
    _reg_character_template(mcp)
    _reg_pose_from_image(mcp)
    _reg_keyframe_timeline(mcp)
    _reg_motion_path(mcp)
    _reg_storyboard_panel(mcp)
    _reg_scene_manager(mcp)
    _reg_background_layer(mcp)
    _reg_multi_character(mcp)
    _reg_shot_list_gen(mcp)
    _reg_beat_sheet(mcp)
    _reg_production_notes(mcp)
    _reg_continuity_check(mcp)
    _reg_asset_registry(mcp)
    _reg_pdf_export(mcp)
    _reg_animatic_preview(mcp)
    _reg_prop_manager(mcp)
    _reg_lighting_notation(mcp)
    _reg_transition_planner(mcp)
    _reg_audio_sync(mcp)
    _reg_sequence_assembler(mcp)
    _reg_rig_controllers(mcp)
    _reg_storyboard_template(mcp)
    _reg_panel_text(mcp)
    _reg_camera_notation(mcp)
    _reg_character_turnaround(mcp)
    _reg_landmark_axis(mcp)
    _reg_construction_draw(mcp)
    _reg_gesture_line(mcp)
    _reg_proportion_check(mcp)
    _reg_negative_space(mcp)
    _reg_line_weight(mcp)
    _reg_form_volume(mcp)
    _reg_thumbnail_grid(mcp)
    _reg_scene_composition(mcp)
    _reg_character_expression(mcp)
    _reg_batch_pose(mcp)
    _reg_staging_system(mcp)
    _reg_revision_tracker(mcp)
    _reg_edl_export(mcp)
    _reg_thumbnail_promote(mcp)
    _reg_environment(mcp)
    _reg_continuity_enhanced(mcp)
    _reg_director_markup(mcp)
    _reg_audio_sync_enhanced(mcp)
    _reg_cross_section(mcp)
    _reg_shading_inference(mcp)
    _reg_color_region_cluster(mcp)
    _reg_contour_nesting(mcp)
    _reg_symmetry_detector(mcp)
    _reg_part_size_ranker(mcp)
    _reg_joint_geometry(mcp)
    _reg_object_classifier(mcp)
    _reg_template_inheritance(mcp)
    _reg_template_scaling(mcp)
    _reg_template_export(mcp)
    _reg_template_library_search(mcp)
    _reg_scene_graph(mcp)
    _reg_interaction_zones(mcp)
    _reg_lod_system(mcp)
    _reg_asset_versioning(mcp)
    _reg_batch_rig(mcp)
    _reg_cv_confidence(mcp)
    _reg_correction_learning(mcp)
    _reg_cross_object_patterns(mcp)
    _reg_failure_detection(mcp)
    _reg_active_learning(mcp)
    _reg_object_hierarchy(mcp)
    _reg_part_segmenter(mcp)
    _reg_part_questioner(mcp)
    _reg_connection_detector(mcp)
    _reg_hierarchy_builder(mcp)
    _reg_relationship_types(mcp)
    _reg_constraint_system(mcp)
    _reg_chain_detector(mcp)
    _reg_hierarchy_templates(mcp)
    _reg_template_matcher(mcp)
    _reg_ik_chain_auto(mcp)
    _reg_motion_range_from_shape(mcp)
    _reg_deformation_zones(mcp)
    _reg_secondary_motion(mcp)
    _reg_weight_zones(mcp)
    _reg_pose_library_generic(mcp)
    _reg_physics_hints(mcp)
    _reg_timing_curves(mcp)
    _reg_anticipation_markers(mcp)
    _reg_motion_path_from_hierarchy(mcp)
