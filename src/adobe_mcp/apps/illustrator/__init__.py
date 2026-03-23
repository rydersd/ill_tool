"""Illustrator tools — 12 tools split by feature.

Registration chain:
    apps/__init__.py -> illustrator/__init__.py -> {new_document, shapes, text, paths, export, layers, modify, inspect, image_trace, analyze_reference, reference_underlay, vtrace}.py
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


def register_illustrator_tools(mcp):
    """Register all 12 Illustrator tools."""
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
