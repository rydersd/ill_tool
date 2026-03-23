"""Cross-app tools — 13 tools that work across all Adobe applications."""

import json
import os
import subprocess
import tempfile
import time

from adobe_mcp.config import ADOBE_APPS, IS_MACOS
from adobe_mcp.engine import (
    _async_run_jsx,
    _async_run_jsx_file,
    _async_run_powershell,
)
from adobe_mcp.apps.common.models import (
    AppStatusInput,
    BatchInput,
    CloseDocInput,
    ContextInput,
    DesignTokenInput,
    GetDocInfoInput,
    HealthCheckInput,
    LaunchAppInput,
    ListFontsInput,
    OpenFileInput,
    PipelineInput,
    PreviewInput,
    RelayStatusInput,
    RunJSXFileInput,
    RunJSXInput,
    RunPowerShellInput,
    SaveFileInput,
    SessionStateInput,
    SnippetInput,
    ToolDiscoveryInput,
    WorkflowInput,
)
from adobe_mcp.state import session
from adobe_mcp.context import context_card
from adobe_mcp.tokens import tokens as token_registry
from adobe_mcp.jsx.snippets import SNIPPETS, get_snippet, search_snippets, list_snippets


def register_common_tools(mcp):
    """Register 13 cross-app tools (including relay status)."""

    @mcp.tool(
        name="adobe_list_apps",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def adobe_list_apps() -> str:
        """List all supported Adobe applications and their status (running/stopped)."""
        if IS_MACOS:
            apps = {}
            for key, info in ADOBE_APPS.items():
                proc_name = info.get("mac_process", "")
                if not proc_name:
                    apps[info["display"]] = "unknown"
                    continue
                result = subprocess.run(
                    ["pgrep", "-f", proc_name],
                    capture_output=True, text=True
                )
                apps[info["display"]] = "running" if result.returncode == 0 else "stopped"
            return json.dumps(apps)

        ps = """
$apps = @{}
$procs = Get-Process -ErrorAction SilentlyContinue | Select-Object -Property Name
$mapping = @{
    'Photoshop'='Photoshop'; 'Illustrator'='Illustrator';
    'Adobe Premiere Pro'='Premiere Pro'; 'AfterFX'='After Effects';
    'InDesign'='InDesign'; 'Animate'='Animate';
    'Character Animator'='Character Animator'; 'Adobe Media Encoder'='Media Encoder'
}
foreach ($key in $mapping.Keys) {
    $running = $procs | Where-Object { $_.Name -like "*$key*" }
    $apps[$mapping[$key]] = if ($running) { 'running' } else { 'stopped' }
}
$apps | ConvertTo-Json
"""
        result = await _async_run_powershell(ps)
        if result["success"]:
            return result["stdout"]
        return json.dumps({"apps": {v["display"]: "unknown" for v in ADOBE_APPS.values()}, "note": result["stderr"]})

    @mcp.tool(
        name="adobe_app_status",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def adobe_app_status(params: AppStatusInput) -> str:
        """Check if a specific Adobe application is running and get its version."""
        info = ADOBE_APPS[params.app.value]

        if IS_MACOS:
            proc_name = info.get("mac_process", "")
            if not proc_name:
                return json.dumps({"status": "unknown", "version": None, "pid": None})
            result = subprocess.run(
                ["pgrep", "-f", proc_name],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                pids = result.stdout.strip().split("\n")
                pid = int(pids[0]) if pids[0] else None
                version = None
                bundle_id = info.get("bundle_id")
                if bundle_id:
                    ver_result = subprocess.run(
                        ["osascript", "-e", f'tell application id "{bundle_id}" to get version'],
                        capture_output=True, text=True, timeout=10
                    )
                    if ver_result.returncode == 0:
                        version = ver_result.stdout.strip()
                return json.dumps({"status": "running", "version": version, "pid": pid})
            return json.dumps({"status": "stopped", "version": None, "pid": None})

        ps = f"""
$proc = Get-Process -Name '{info["process"].replace(".exe", "")}' -ErrorAction SilentlyContinue
if ($proc) {{
    $version = $proc[0].FileVersion
    @{{ status='running'; version=$version; pid=$proc[0].Id }} | ConvertTo-Json
}} else {{
    @{{ status='stopped'; version=$null; pid=$null }} | ConvertTo-Json
}}
"""
        result = await _async_run_powershell(ps)
        return result["stdout"] if result["success"] else json.dumps({"status": "error", "error": result["stderr"]})

    @mcp.tool(
        name="adobe_launch_app",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def adobe_launch_app(params: LaunchAppInput) -> str:
        """Launch an Adobe application if not already running."""
        info = ADOBE_APPS[params.app.value]

        if IS_MACOS:
            proc_name = info.get("mac_process", info["display"])
            result = subprocess.run(
                ["open", "-a", proc_name],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return json.dumps({"success": True, "message": f"{info['display']} launched via open -a"})
            return json.dumps({"success": False, "error": result.stderr.strip()})

        if info["com_id"]:
            ps = f"""
try {{
    $app = New-Object -ComObject '{info["com_id"]}'
    @{{ success=$true; message='{info["display"]} launched/connected via COM' }} | ConvertTo-Json
}} catch {{
    $paths = @(
        'C:\\Program Files\\Adobe\\*\\{info["process"]}',
        'C:\\Program Files\\Adobe\\*\\Support Files\\{info["process"]}'
    )
    $exe = Get-ChildItem -Path $paths -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($exe) {{
        Start-Process $exe.FullName
        Start-Sleep -Seconds 3
        @{{ success=$true; message='{info["display"]} started via process' }} | ConvertTo-Json
    }} else {{
        @{{ success=$false; error='Could not find {info["process"]}' }} | ConvertTo-Json
    }}
}}
"""
        else:
            ps = f"""
$paths = @(
    'C:\\Program Files\\Adobe\\*\\{info["process"]}',
    'C:\\Program Files\\Adobe\\*\\Support Files\\{info["process"]}'
)
$exe = Get-ChildItem -Path $paths -ErrorAction SilentlyContinue | Select-Object -First 1
if ($exe) {{
    Start-Process $exe.FullName
    @{{ success=$true; message='{info["display"]} starting' }} | ConvertTo-Json
}} else {{
    @{{ success=$false; error='Could not find {info["process"]}' }} | ConvertTo-Json
}}
"""
        result = await _async_run_powershell(ps)
        return result["stdout"] if result["success"] else json.dumps({"success": False, "error": result["stderr"]})

    @mcp.tool(
        name="adobe_run_jsx",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def adobe_run_jsx(params: RunJSXInput) -> str:
        """Execute arbitrary ExtendScript/JSX code in any supported Adobe application.
        This is the most powerful tool — you can do ANYTHING the app supports via scripting.
        Returns the script result or error message."""
        result = await _async_run_jsx(params.app.value, params.code, params.timeout)
        if result["success"]:
            return result["stdout"] if result["stdout"] else "Script executed successfully (no output)"
        return f"Error: {result['stderr']}"

    @mcp.tool(
        name="adobe_run_jsx_file",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def adobe_run_jsx_file(params: RunJSXFileInput) -> str:
        """Execute a .jsx script file in any supported Adobe application."""
        # Bug #2 fix: use _async_run_jsx_file() which calls the app's native file
        # execution directly, instead of wrapping in $.evalFile() which has issues
        # with paths containing spaces and special characters.
        result = await _async_run_jsx_file(params.app.value, params.file_path, params.timeout)
        if result["success"]:
            return result["stdout"] if result["stdout"] else "Script file executed successfully"
        return f"Error: {result['stderr']}"

    @mcp.tool(
        name="adobe_run_powershell",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def adobe_run_powershell(params: RunPowerShellInput) -> str:
        """Execute arbitrary PowerShell for advanced Adobe COM automation.
        Use this when you need low-level COM access or complex multi-app workflows."""
        if IS_MACOS:
            return json.dumps({"error": "PowerShell COM automation is not available on macOS. Use adobe_run_jsx instead."})
        result = await _async_run_powershell(params.script, params.timeout)
        if result["success"]:
            return result["stdout"] if result["stdout"] else "PowerShell executed successfully"
        return f"Error: {result['stderr']}"

    @mcp.tool(
        name="adobe_open_file",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def adobe_open_file(params: OpenFileInput) -> str:
        """Open a file in any Adobe application."""
        path = params.file_path.replace("\\", "\\\\").replace("'", "\\'")

        if params.app.value == "photoshop":
            jsx = f'var f = new File("{path}"); app.open(f); app.activeDocument.name;'
        elif params.app.value == "illustrator":
            jsx = f'var f = new File("{path}"); app.open(f); app.activeDocument.name;'
        elif params.app.value == "aftereffects":
            jsx = f'var f = new File("{path}"); app.open(f); app.project.file.name;'
        elif params.app.value == "premierepro":
            jsx = f'app.openDocument("{path}");'
        elif params.app.value == "indesign":
            jsx = f'var f = new File("{path}"); app.open(f); app.activeDocument.name;'
        elif params.app.value == "animate":
            jsx = f'fl.openDocument("{path}"); fl.getDocumentDOM().name;'
        else:
            jsx = f'var f = new File("{path}"); app.open(f);'

        result = await _async_run_jsx(params.app.value, jsx)
        if result["success"]:
            return f"Opened: {result['stdout']}" if result["stdout"] else "File opened successfully"
        return f"Error: {result['stderr']}"

    @mcp.tool(
        name="adobe_save_file",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def adobe_save_file(params: SaveFileInput) -> str:
        """Save the active document in any Adobe application."""
        if params.file_path:
            path = params.file_path.replace("\\", "\\\\")
            if params.app.value == "photoshop":
                jsx = f'var f = new File("{path}"); app.activeDocument.saveAs(f); "Saved"'
            elif params.app.value == "illustrator":
                jsx = f'var f = new File("{path}"); app.activeDocument.saveAs(f); "Saved"'
            elif params.app.value == "indesign":
                jsx = f'var f = new File("{path}"); app.activeDocument.save(f); "Saved"'
            elif params.app.value == "animate":
                jsx = f'fl.saveDocument(fl.getDocumentDOM(), "{path}"); "Saved"'
            else:
                jsx = f'app.activeDocument.save(); "Saved"'
        else:
            if params.app.value == "animate":
                jsx = 'fl.saveDocument(fl.getDocumentDOM()); "Saved"'
            else:
                jsx = 'app.activeDocument.save(); "Saved"'

        result = await _async_run_jsx(params.app.value, jsx)
        return result["stdout"] if result["success"] else f"Error: {result['stderr']}"

    @mcp.tool(
        name="adobe_close_document",
        annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
    )
    async def adobe_close_document(params: CloseDocInput) -> str:
        """Close the active document in any Adobe application."""
        save_opt = "SaveOptions.YES" if params.save else "SaveOptions.NO"
        if params.app.value == "animate":
            jsx = f'fl.closeDocument(fl.getDocumentDOM(), {"true" if params.save else "false"}); "Closed"'
        else:
            jsx = f'app.activeDocument.close({save_opt}); "Closed"'
        result = await _async_run_jsx(params.app.value, jsx)
        return result["stdout"] if result["success"] else f"Error: {result['stderr']}"

    @mcp.tool(
        name="adobe_get_doc_info",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def adobe_get_doc_info(params: GetDocInfoInput) -> str:
        """Get detailed info about the active document in any Adobe app."""
        if params.app.value == "photoshop":
            jsx = """
var d = app.activeDocument;
var info = {
    name: d.name, path: d.path.fsName, width: d.width.value, height: d.height.value,
    resolution: d.resolution, colorMode: String(d.mode), bitDepth: d.bitsPerChannel,
    layerCount: d.layers.length, channels: d.channels.length,
    artLayerCount: d.artLayers.length, layerSetCount: d.layerSets.length
};
JSON.stringify(info, null, 2);
"""
        elif params.app.value == "illustrator":
            # With JSON polyfill auto-injected, we can use JSON.stringify cleanly
            jsx = """
var d = app.activeDocument;
var p = ''; try { p = d.path.fsName; } catch(e) { p = 'Unsaved'; }
var info = {
    name: d.name, path: p, width: d.width, height: d.height,
    colorMode: String(d.documentColorSpace), artboards: d.artboards.length,
    layers: d.layers.length, pathItems: d.pathItems.length,
    textFrames: d.textFrames.length, symbolItems: d.symbolItems.length
};
JSON.stringify(info);
"""
        elif params.app.value == "aftereffects":
            jsx = """
var p = app.project;
var c = p.activeItem;
var info = { projectName: p.file ? p.file.name : 'Unsaved', items: p.numItems };
if (c && c instanceof CompItem) {
    info.comp = { name: c.name, width: c.width, height: c.height,
        duration: c.duration, frameRate: c.frameRate, layers: c.numLayers };
}
JSON.stringify(info, null, 2);
"""
        elif params.app.value == "premierepro":
            jsx = """
var p = app.project;
var s = p.activeSequence;
var info = { projectName: p.name, sequences: p.sequences.numSequences };
if (s) {
    info.activeSequence = { name: s.name, id: s.sequenceID,
        videoTracks: s.videoTracks.numTracks, audioTracks: s.audioTracks.numTracks };
}
JSON.stringify(info, null, 2);
"""
        elif params.app.value == "indesign":
            jsx = """
var d = app.activeDocument;
var info = {
    name: d.name, path: d.filePath.fsName, pages: d.pages.length,
    spreads: d.spreads.length, stories: d.stories.length,
    textFrames: d.textFrames.length, images: d.allGraphics.length,
    layers: d.layers.length, masterSpreads: d.masterSpreads.length
};
JSON.stringify(info, null, 2);
"""
        elif params.app.value == "animate":
            jsx = """
var d = fl.getDocumentDOM();
var info = {
    name: d.name, width: d.width, height: d.height,
    frameRate: d.frameRate, currentTimeline: d.currentTimeline,
    layers: d.getTimeline().layerCount, frames: d.getTimeline().frameCount
};
JSON.stringify(info);
"""
        else:
            jsx = 'try { JSON.stringify({name: app.activeDocument.name}); } catch(e) { "No document open"; }'

        result = await _async_run_jsx(params.app.value, jsx)
        return result["stdout"] if result["success"] else f"Error: {result['stderr']}"

    @mcp.tool(
        name="adobe_list_fonts",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def adobe_list_fonts(params: ListFontsInput) -> str:
        """List available fonts in an Adobe application."""
        filter_str = params.filter or ""
        if params.app.value == "photoshop":
            jsx = f"""
var fonts = []; var filter = '{filter_str}'.toLowerCase();
for (var i = 0; i < app.fonts.length; i++) {{
    var f = app.fonts[i];
    if (!filter || f.name.toLowerCase().indexOf(filter) >= 0 || f.postScriptName.toLowerCase().indexOf(filter) >= 0) {{
        fonts.push({{ name: f.name, postScriptName: f.postScriptName, family: f.family, style: f.style }});
    }}
    if (fonts.length >= 100) break;
}}
JSON.stringify({{ count: fonts.length, fonts: fonts }}, null, 2);
"""
        elif params.app.value == "illustrator":
            jsx = f"""
var fonts = []; var filter = '{filter_str}'.toLowerCase();
for (var i = 0; i < app.textFonts.length; i++) {{
    var f = app.textFonts[i];
    if (!filter || f.name.toLowerCase().indexOf(filter) >= 0) {{
        fonts.push({{ name: f.name, family: f.family, style: f.style }});
    }}
    if (fonts.length >= 100) break;
}}
JSON.stringify({{ count: fonts.length, fonts: fonts }}, null, 2);
"""
        else:
            return json.dumps({"error": f"Font listing not available for {params.app.value}. Use Photoshop or Illustrator."})

        result = await _async_run_jsx(params.app.value, jsx)
        return result["stdout"] if result["success"] else f"Error: {result['stderr']}"

    @mcp.tool(
        name="adobe_preview",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def adobe_preview(params: PreviewInput) -> str:
        """Export a quick JPEG preview of the active document to a temp file for visual analysis.
        Returns the file path and dimensions. Use the Read tool on the returned path to see the image.
        Supports Illustrator, Photoshop, and After Effects."""
        max_size = params.max_size or 1200
        quality = params.quality or 72

        if params.app.value == "illustrator":
            jsx = f"""
var doc = app.activeDocument;
var maxSz = {max_size};
var w = doc.width; var h = doc.height;
var scale = (w >= h) ? (maxSz / w * 100) : (maxSz / h * 100);
if (scale > 100) scale = 100;
var opts = new ExportOptionsJPEG();
opts.qualitySetting = {quality};
opts.horizontalScale = scale; opts.verticalScale = scale;
opts.antiAliasing = true;
var tmpPath = Folder.temp.fsName + "/adobe_preview_" + new Date().getTime() + ".jpg";
doc.exportFile(new File(tmpPath), ExportType.JPEG, opts);
var aw = Math.round(w * scale / 100); var ah = Math.round(h * scale / 100);
JSON.stringify({{path: tmpPath, width: aw, height: ah, format: "jpeg"}});
"""
        elif params.app.value == "photoshop":
            # Duplicate, resize, flatten, save as JPEG, close duplicate — avoids polluting original
            jsx = f"""
var doc = app.activeDocument;
var maxSz = {max_size};
var w = doc.width.as("px"); var h = doc.height.as("px");
var scale = (w >= h) ? (maxSz / w) : (maxSz / h);
if (scale > 1) scale = 1;
var aw = Math.round(w * scale); var ah = Math.round(h * scale);
var dup = doc.duplicate("_preview_tmp");
dup.resizeImage(UnitValue(aw,"px"), UnitValue(ah,"px"), 72, ResampleMethod.BICUBIC);
dup.flatten();
var opts = new JPEGSaveOptions();
opts.quality = Math.round({quality} / 10);
opts.embedColorProfile = false;
var tmpPath = Folder.temp.fsName + "/adobe_preview_" + new Date().getTime() + ".jpg";
dup.saveAs(new File(tmpPath), opts, true, Extension.LOWERCASE);
dup.close(SaveOptions.DONOTSAVECHANGES);
JSON.stringify({{path: tmpPath, width: aw, height: ah, format: "jpeg"}});
"""
        elif params.app.value == "aftereffects":
            # Render single frame at current time via render queue
            jsx = f"""
var comp = app.project.activeItem;
if (comp && comp instanceof CompItem) {{
    var tmpPath = Folder.temp.fsName + "/adobe_preview_" + new Date().getTime() + ".jpg";
    var rq = app.project.renderQueue;
    var rqItem = rq.items.add(comp);
    rqItem.timeSpanStart = comp.time;
    rqItem.timeSpanDuration = comp.frameDuration;
    var om = rqItem.outputModule(1);
    try {{ om.applyTemplate("JPEG Sequence"); }} catch(e) {{}}
    om.file = new File(tmpPath);
    rq.render();
    JSON.stringify({{path: tmpPath, width: comp.width, height: comp.height, format: "jpeg"}});
}} else {{ JSON.stringify({{error: "No active composition"}}); }}
"""
        else:
            return json.dumps({
                "error": f"Preview not supported for {params.app.value}. Use Illustrator, Photoshop, or After Effects.",
                "suggestion": "Use the app's built-in export tools for other applications."
            })

        result = await _async_run_jsx(params.app.value, jsx)
        if result["success"]:
            try:
                preview_data = json.loads(result["stdout"])
                if "error" not in preview_data:
                    preview_data["app"] = params.app.value
                    preview_data["hint"] = "Use the Read tool to view this image for visual analysis"
                    return json.dumps(preview_data)
            except (json.JSONDecodeError, TypeError):
                pass  # Fall through to screencapture fallback

        # ── Screencapture fallback (macOS only) ───────────────────────
        # If JSX preview failed, try capturing the app's frontmost window
        if IS_MACOS:
            try:
                # Map tool app names to macOS process names
                process_names = {
                    "illustrator": "Adobe Illustrator",
                    "photoshop": "Adobe Photoshop",
                    "aftereffects": "After Effects",
                }
                process_name = process_names.get(params.app.value, "")
                if process_name:
                    capture_path = os.path.join(
                        tempfile.gettempdir(),
                        f"adobe_screencapture_{int(time.time())}.png",
                    )
                    # Get the frontmost window bounds via AppleScript
                    ascript = (
                        'tell application "System Events"\n'
                        f'    tell process "{process_name}"\n'
                        '        set frontWindow to front window\n'
                        '        set {x, y} to position of frontWindow\n'
                        '        set {w, h} to size of frontWindow\n'
                        '    end tell\n'
                        'end tell\n'
                        'return (x as text) & "," & (y as text) & "," & (w as text) & "," & (h as text)'
                    )
                    bounds_result = subprocess.run(
                        ["osascript", "-e", ascript],
                        capture_output=True, text=True, timeout=5,
                    )
                    if bounds_result.returncode == 0:
                        parts = bounds_result.stdout.strip().split(",")
                        if len(parts) == 4:
                            region = f"{parts[0]},{parts[1]},{parts[2]},{parts[3]}"
                            subprocess.run(
                                ["screencapture", "-x", "-R", region, capture_path],
                                timeout=5,
                            )
                            if os.path.exists(capture_path):
                                return json.dumps({
                                    "path": capture_path,
                                    "format": "png",
                                    "app": params.app.value,
                                    "method": "screencapture_fallback",
                                    "hint": "Used macOS screencapture fallback. Use the Read tool to view this image.",
                                })
            except Exception:
                pass  # Fall through to original error

        # Return the original JSX error if fallback also failed
        if result["success"]:
            return json.dumps({"error": "Unexpected response from preview export", "raw": result.get("stdout", "")})
        return json.dumps({"error": f"Preview failed: {result.get('stderr', 'unknown error')}", "app": params.app.value})

    # ── Session State Tool ────────────────────────────────────────────

    @mcp.tool(
        name="adobe_session_state",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def adobe_session_state(params: SessionStateInput) -> str:
        """Query or manage server-side session state. The server tracks document context
        (layers, artboards, recent actions) between tool calls. Use this instead of
        re-querying document info when you need to recall what you've done.

        Actions:
          summary — compact one-line-per-app overview (default, cheapest)
          full    — detailed JSON with all state + recent history
          history — last 20 actions across all apps
          reset   — clear state (optionally for one app only)
        """
        if params.action == "reset":
            app_name = params.app.value if params.app else None
            session.reset(app_name)
            target = f"for {app_name}" if app_name else "for all apps"
            return f"Session state reset {target}."

        if params.action == "full":
            return session.full_state()

        if params.action == "history":
            history = session.history
            if params.app:
                history = [h for h in history if h["app"] == params.app.value]
            recent = history[-20:]
            if not recent:
                return "No actions recorded yet."
            lines = [f"  {i+1}. [{h['app']}] {h['action']}" for i, h in enumerate(recent)]
            return f"Recent actions ({len(recent)} of {len(history)} total):\n" + "\n".join(lines)

        # Default: summary
        return session.summary()

    # ── Design Tokens Tool ─────────────────────────────────────────────

    @mcp.tool(
        name="adobe_design_tokens",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def adobe_design_tokens(params: DesignTokenInput) -> str:
        """Manage design tokens — named values for colors, typography, spacing, and effects.

        Design tokens create a consistent vocabulary across all operations. Instead of
        specifying fill_r=255 fill_g=0 fill_b=100 repeatedly, define color.primary once
        and reference it as $color.primary.r everywhere.

        Built-in presets: void (dark/technical), minimal (clean/white), brutalist (raw/bold)

        Example workflow:
          1. adobe_design_tokens(action='preset', name='void')
          2. adobe_design_tokens(action='resolve', params='{"fill_r":"$color.primary.r","fill_g":"$color.primary.g","fill_b":"$color.primary.b"}')
          3. Use resolved values in other tool calls
        """
        if params.action == "set":
            if not params.name:
                return "Error: 'name' required for set action"
            if params.value is None:
                return "Error: 'value' required for set action"
            try:
                value = json.loads(params.value)
            except json.JSONDecodeError:
                # Treat as raw string or number
                try:
                    value = float(params.value) if "." in params.value else int(params.value)
                except ValueError:
                    value = params.value

            token_registry.set(
                params.name, value,
                category=params.category or "custom",
                description=params.description or "",
            )
            return f"Token '{params.name}' set to {json.dumps(value)} ({params.category})"

        if params.action == "get":
            if not params.name:
                return "Error: 'name' required for get action"
            value = token_registry.get_nested(params.name)
            if value is None:
                return f"Token '{params.name}' not found. Use action='list' to see available tokens."
            return json.dumps({"name": params.name, "value": value})

        if params.action == "list":
            tokens_list = token_registry.list_tokens(category=params.category if params.category != "custom" else None)
            if not tokens_list:
                return "No tokens defined. Use action='preset' to load a built-in set, or action='set' to define custom tokens."
            lines = [f"Design Tokens ({len(tokens_list)}):"]
            by_cat: dict[str, list] = {}
            for t in tokens_list:
                by_cat.setdefault(t["category"], []).append(t)
            for cat in sorted(by_cat.keys()):
                lines.append(f"\n[{cat}]")
                for t in by_cat[cat]:
                    val = json.dumps(t["value"]) if isinstance(t["value"], dict) else str(t["value"])
                    desc = f" — {t['description']}" if t['description'] else ""
                    lines.append(f"  {t['name']} = {val}{desc}")
            return "\n".join(lines)

        if params.action == "preset":
            if not params.name:
                return "Error: 'name' required. Available presets: void, minimal, brutalist"
            result = token_registry.apply_preset(params.name)
            return result

        if params.action == "resolve":
            if not params.params:
                return "Error: 'params' (JSON object with $token references) required for resolve action"
            try:
                raw_params = json.loads(params.params)
            except json.JSONDecodeError as e:
                return f"Error: Invalid JSON in params: {e}"
            resolved = token_registry.resolve(raw_params)
            return json.dumps(resolved, indent=2)

        if params.action == "save":
            if not params.file_path and not params.name:
                return "Error: 'file_path' or 'name' required for save action"
            from pathlib import Path as _P
            if params.file_path:
                path = _P(params.file_path)
            else:
                tokens_dir = _P(__file__).parent.parent.parent / "tokens"
                path = tokens_dir / f"{params.name}.json"
            token_registry.save(path)
            return f"Saved {token_registry.count} tokens to {path}"

        if params.action == "load":
            if not params.file_path and not params.name:
                return "Error: 'file_path' or 'name' required for load action"
            from pathlib import Path as _P
            if params.file_path:
                path = _P(params.file_path)
            else:
                tokens_dir = _P(__file__).parent.parent.parent / "tokens"
                path = tokens_dir / f"{params.name}.json"
            if not path.exists():
                return f"Token file not found: {path}"
            count = token_registry.load(path)
            return f"Loaded {count} tokens from {path}"

        if params.action == "load_dna":
            if not params.file_path:
                return "Error: 'file_path' required for load_dna action (path to Design DNA JSON)"
            result = token_registry.load_dna_preset(params.file_path)
            return result

        if params.action == "font_audit":
            # Query Illustrator for installed/available text fonts, classify
            # them against DR-style design criteria, and auto-set typography tokens.
            font_jsx = """
            var fonts = [];
            for (var i = 0; i < app.textFonts.length && i < 500; i++) {
                var f = app.textFonts[i];
                fonts.push({name: f.name, family: f.family, style: f.style});
            }
            JSON.stringify({count: fonts.length, fonts: fonts});
            """

            font_result = await _async_run_jsx("illustrator", font_jsx)
            # _async_run_jsx returns a dict; the JSX JSON string is in the result
            font_data = json.loads(font_result) if isinstance(font_result, str) else font_result

            classified = token_registry.classify_fonts(font_data["fonts"])

            # Auto-set typography tokens from top picks in each role
            if classified["heading"]:
                top = classified["heading"][0]
                token_registry.set(
                    "type.heading.font", top["name"],
                    category="typography",
                    description=f"Auto: {top['family']} {top['style']}",
                )
            if classified["display"]:
                top = classified["display"][0]
                token_registry.set(
                    "type.display.font", top["name"],
                    category="typography",
                    description=f"Auto: {top['family']} {top['style']}",
                )
            if classified["label"]:
                top = classified["label"][0]
                token_registry.set(
                    "type.label.font", top["name"],
                    category="typography",
                    description=f"Auto: {top['family']} {top['style']}",
                )
            if classified["body"]:
                top = classified["body"][0]
                token_registry.set(
                    "type.body.font", top["name"],
                    category="typography",
                    description=f"Auto: {top['family']} {top['style']}",
                )

            return json.dumps(classified, indent=2)

        if params.action == "clear":
            token_registry.clear()
            return "All design tokens cleared."

        return f"Error: Unknown action '{params.action}'. Use: set, get, list, preset, resolve, save, load, load_dna, font_audit, clear"

    # ── Health Check Tool ──────────────────────────────────────────────

    @mcp.tool(
        name="adobe_health",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def adobe_health(params: HealthCheckInput) -> str:
        """Run diagnostics on the Adobe MCP server and connected applications.

        Use this to troubleshoot connectivity issues, verify which apps are ready
        for scripting, check system capabilities, and get server statistics.

        Start here when beginning a new session or encountering errors.
        """
        import sys
        import time as _time

        lines = []

        if params.action in ("full", "system"):
            lines.append("=== SYSTEM ===")
            lines.append(f"Platform: {'macOS' if IS_MACOS else 'Windows' if not IS_MACOS else 'Unknown'}")
            lines.append(f"Python: {sys.version.split()[0]}")
            lines.append(f"MCP Server: adobe_mcp v0.1.0")

            tool_registry = mcp._tool_manager._tools if hasattr(mcp, '_tool_manager') else {}
            lines.append(f"Registered tools: {len(tool_registry)}")
            lines.append(f"JSX snippets: {len(SNIPPETS)}")

            from pathlib import Path as _P
            workflows_dir = _P(__file__).parent.parent.parent / "workflows"
            wf_count = len(list(workflows_dir.glob("*.json"))) if workflows_dir.exists() else 0
            lines.append(f"Saved workflows: {wf_count}")

            state_apps = [n for n, s in session._apps.items() if s.action_count > 0]
            lines.append(f"Active session apps: {', '.join(state_apps) if state_apps else 'none'}")
            lines.append(f"Session operations: {len(session.history)}")
            lines.append("")

        if params.action in ("full", "apps", "connectivity"):
            lines.append("=== ADOBE APPS ===")

            apps_to_check = {}
            if params.app:
                apps_to_check = {params.app.value: ADOBE_APPS[params.app.value]}
            else:
                apps_to_check = ADOBE_APPS

            for app_key, info in apps_to_check.items():
                proc_name = info.get("mac_process", "")
                display = info["display"]
                supports_jsx = info.get("extendscript", False)
                mac_cmd = info.get("mac_script_cmd")

                # Check if running
                if IS_MACOS:
                    result = subprocess.run(
                        ["pgrep", "-f", proc_name] if proc_name else ["echo", ""],
                        capture_output=True, text=True
                    )
                    running = result.returncode == 0 and proc_name
                else:
                    running = False  # Windows check would use Get-Process

                status = "RUNNING" if running else "stopped"
                jsx_status = "jsx:yes" if supports_jsx else "jsx:no"
                script_status = f"script:{'yes' if mac_cmd else 'no'}"

                lines.append(f"  {display}: {status} | {jsx_status} | {script_status}")

                # Test connectivity for running apps
                if running and supports_jsx and mac_cmd and params.action in ("full", "connectivity"):
                    start = _time.time()
                    test_jsx = 'typeof app !== "undefined" ? app.name : "no app object"'
                    try:
                        test_result = await _async_run_jsx(app_key, test_jsx, timeout=10)
                        elapsed = round((_time.time() - start) * 1000)
                        if test_result["success"]:
                            lines.append(f"    Connectivity: OK ({elapsed}ms) — {test_result['stdout'][:50]}")
                        else:
                            lines.append(f"    Connectivity: FAIL — {test_result['stderr'][:80]}")
                    except Exception as e:
                        lines.append(f"    Connectivity: ERROR — {str(e)[:80]}")

            lines.append("")

        if params.action == "full":
            lines.append("=== TIPS ===")
            lines.append("  - Use adobe_discover to browse all tools")
            lines.append("  - Use adobe_context for a quick state overview")
            lines.append("  - Use adobe_batch to execute multiple operations at once")
            lines.append("  - Use adobe_jsx_snippets for ready-made ExtendScript patterns")

        return "\n".join(lines)

    # ── Context Card Tool ─────────────────────────────────────────────

    @mcp.tool(
        name="adobe_context",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def adobe_context(params: ContextInput) -> str:
        """Get a compact context card — the single cheapest way to know what's happening.

        Returns active documents, layer counts, recent actions, and smart suggestions
        for next steps — all in ~100 tokens. Call this instead of re-querying state
        or re-reading prior tool responses.

        Much cheaper than adobe_session_state(action='full') when you just need
        orientation. Includes contextual suggestions based on current app state.
        """
        return context_card(app=params.app)

    # ── JSX Snippet Library ────────────────────────────────────────────

    @mcp.tool(
        name="adobe_jsx_snippets",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def adobe_jsx_snippets(params: SnippetInput) -> str:
        """Browse, search, and compose reusable JSX code snippets.

        The snippet library contains tested ExtendScript patterns for common operations:
        gradients, clipping masks, grid layouts, halftones, duotones, wiggles, fades, etc.

        Actions:
          list    — browse all snippets (optionally filtered by app)
          search  — find snippets by keyword
          get     — view full code and parameters for a snippet
          compose — fill in parameters and get ready-to-execute JSX code
        """
        if params.action == "list":
            snippets = list_snippets(app=params.app)
            if not snippets:
                return f"No snippets found{' for ' + params.app if params.app else ''}."
            lines = [f"JSX Snippet Library ({len(snippets)} snippets):"]
            by_app: dict[str, list] = {}
            for s in snippets:
                by_app.setdefault(s["app"], []).append(s)
            for app_name in sorted(by_app.keys()):
                lines.append(f"\n[{app_name}]")
                for s in by_app[app_name]:
                    lines.append(f"  {s['name']} ({s['category']}) — {s['description'][:80]}")
            return "\n".join(lines)

        if params.action == "search":
            if not params.query:
                return "Error: 'query' required for search action"
            results = search_snippets(params.query, app=params.app)
            if not results:
                return f"No snippets matching '{params.query}'. Try: gradient, mask, grid, halftone, wiggle, fade"
            lines = [f"Snippets matching '{params.query}' ({len(results)}):"]
            for s in results:
                lines.append(f"  {s['name']} [{s['app']}] — {s['description'][:80]}")
            return "\n".join(lines)

        if params.action == "get":
            if not params.query:
                return "Error: 'query' (snippet name) required for get action"
            snippet = get_snippet(params.query)
            if not snippet:
                return f"Snippet '{params.query}' not found. Use action='list' to browse."
            lines = [
                f"Snippet: {snippet['name']}",
                f"App: {snippet['app']}",
                f"Category: {snippet['category']}",
                f"Description: {snippet['description']}",
                "Parameters:",
            ]
            for pname, pdesc in snippet["params"].items():
                lines.append(f"  {pname} — {pdesc}")
            if snippet["example_params"]:
                lines.append(f"Example params: {json.dumps(snippet['example_params'])}")
            lines.append("Code:")
            lines.append("```jsx")
            lines.append(snippet["code"])
            lines.append("```")
            return "\n".join(lines)

        if params.action == "compose":
            if not params.query:
                return "Error: 'query' (snippet name) required for compose action"
            if not params.params:
                return "Error: 'params' (JSON object) required for compose action"
            snippet = get_snippet(params.query)
            if not snippet:
                return f"Snippet '{params.query}' not found."
            try:
                values = json.loads(params.params)
            except json.JSONDecodeError as e:
                return f"Error: Invalid JSON in params: {e}"

            # Use the template engine to fill placeholders
            from adobe_mcp.engine import load_template
            import tempfile, os
            # Write snippet code to a temp file for the template engine
            td = tempfile.mkdtemp()
            tmp_path = os.path.join(td, f"{snippet['name']}.jsx")
            with open(tmp_path, "w") as f:
                f.write(snippet["code"])
            try:
                filled = load_template(f"{snippet['name']}.jsx", _caller_dir=td, **values)
                return f"Ready-to-execute JSX for '{snippet['name']}' (app: {snippet['app']}):\n```jsx\n{filled}\n```\nRun with: adobe_run_jsx(app=\"{snippet['app']}\", code=<above>)"
            except (ValueError, FileNotFoundError) as e:
                return f"Error composing snippet: {e}"

        return f"Error: Unknown action '{params.action}'. Use: list, search, get, compose"

    # ── Tool Discovery ─────────────────────────────────────────────────

    @mcp.tool(
        name="adobe_discover",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def adobe_discover(params: ToolDiscoveryInput) -> str:
        """Discover available tools, their parameters, and suggest tools for tasks.

        Use this instead of guessing tool names or parameters. Actions:
          list     — all tools grouped by app (default)
          search   — find tools matching a keyword (e.g. 'export', 'layer', 'text')
          describe — full parameter schema for a specific tool
          for_task — suggest which tools to use for a described task
        """
        import inspect as _inspect

        tool_registry = mcp._tool_manager._tools if hasattr(mcp, '_tool_manager') else {}

        # Build app groupings from tool name prefixes
        app_prefixes = {
            "adobe_ps_": "photoshop",
            "adobe_ai_": "illustrator",
            "adobe_pr_": "premiere",
            "adobe_ae_": "aftereffects",
            "adobe_id_": "indesign",
            "adobe_an_": "animate",
            "adobe_ame_": "media_encoder",
        }

        def _get_app(tool_name: str) -> str:
            for prefix, app in app_prefixes.items():
                if tool_name.startswith(prefix):
                    return app
            return "common"

        def _describe_tool(name: str) -> str:
            """Get full description and parameter schema for a tool."""
            if name not in tool_registry:
                return f"Unknown tool: {name}"
            tool = tool_registry[name]
            lines = [f"Tool: {name}", f"Description: {tool.description or 'N/A'}", "Parameters:"]

            # Extract parameter info from the Pydantic model
            sig = _inspect.signature(tool.fn)
            param_types = list(sig.parameters.values())
            if param_types:
                model_cls = param_types[0].annotation
                if hasattr(model_cls, 'model_fields'):
                    for field_name, field_info in model_cls.model_fields.items():
                        if field_name == 'model_config':
                            continue
                        required = field_info.is_required()
                        default = field_info.default if not required else "(required)"
                        desc = field_info.description or ""
                        type_name = str(field_info.annotation).replace("typing.", "")
                        lines.append(f"  {field_name}: {type_name} = {default} — {desc}")
            else:
                lines.append("  (no parameters)")
            return "\n".join(lines)

        if params.action == "list":
            grouped: dict[str, list[str]] = {}
            for name in sorted(tool_registry.keys()):
                app = _get_app(name)
                if params.app and app != params.app:
                    continue
                grouped.setdefault(app, []).append(name)

            lines = [f"Available tools ({len(tool_registry)} total):"]
            for app in ["common", "photoshop", "illustrator", "premiere", "aftereffects", "indesign", "animate", "media_encoder"]:
                tools_list = grouped.get(app, [])
                if tools_list:
                    lines.append(f"\n[{app}] ({len(tools_list)} tools):")
                    for t in tools_list:
                        desc = (tool_registry[t].description or "")[:80]
                        lines.append(f"  {t} — {desc}")
            return "\n".join(lines)

        if params.action == "search":
            if not params.query:
                return "Error: 'query' required for search action"
            query = params.query.lower()
            matches = []
            for name, tool in tool_registry.items():
                desc = (tool.description or "").lower()
                if query in name.lower() or query in desc:
                    matches.append(f"  {name} — {(tool.description or '')[:100]}")
            if not matches:
                return f"No tools matching '{params.query}'. Try: list, export, layer, text, shape, effect, render"
            return f"Tools matching '{params.query}' ({len(matches)}):\n" + "\n".join(matches)

        if params.action == "describe":
            if not params.query:
                return "Error: 'query' (tool name) required for describe action"
            return _describe_tool(params.query)

        if params.action == "for_task":
            if not params.query:
                return "Error: 'query' (task description) required for for_task action"
            task = params.query.lower()

            # Keyword-to-tool mapping for intelligent suggestion
            suggestions = []
            keyword_tools = {
                "create document": ["adobe_ai_new_document", "adobe_ps_new_document", "adobe_id_document"],
                "new document": ["adobe_ai_new_document", "adobe_ps_new_document", "adobe_id_document"],
                "shape": ["adobe_ai_shapes"],
                "rectangle": ["adobe_ai_shapes"],
                "circle": ["adobe_ai_shapes"],
                "text": ["adobe_ai_text", "adobe_ps_text", "adobe_id_text"],
                "typography": ["adobe_ai_text", "adobe_ps_text"],
                "export": ["adobe_ai_export", "adobe_ps_export", "adobe_pr_export", "adobe_ame_encode"],
                "save": ["adobe_save_file"],
                "layer": ["adobe_ps_layers", "adobe_ai_layers", "adobe_ae_layer"],
                "filter": ["adobe_ps_filter"],
                "effect": ["adobe_ps_filter", "adobe_ae_effect", "adobe_pr_effects"],
                "adjustment": ["adobe_ps_adjustment"],
                "color": ["adobe_ps_adjustment", "adobe_ai_modify"],
                "transform": ["adobe_ps_transform", "adobe_ai_modify"],
                "resize": ["adobe_ps_transform", "adobe_ai_modify"],
                "move": ["adobe_ps_layers", "adobe_ai_modify"],
                "animate": ["adobe_ae_layer", "adobe_ae_expression", "adobe_an_timeline"],
                "render": ["adobe_ae_render", "adobe_ame_encode"],
                "video": ["adobe_pr_project", "adobe_pr_sequence", "adobe_pr_timeline"],
                "sequence": ["adobe_pr_sequence", "adobe_pr_timeline"],
                "composition": ["adobe_ae_comp"],
                "keyframe": ["adobe_ae_property"],
                "expression": ["adobe_ae_expression"],
                "path": ["adobe_ai_path"],
                "selection": ["adobe_ps_selection"],
                "smart object": ["adobe_ps_smart_object"],
                "batch": ["adobe_batch"],
                "workflow": ["adobe_workflow"],
                "pipeline": ["adobe_pipeline"],
                "inspect": ["adobe_ai_inspect", "adobe_ps_inspect", "adobe_get_doc_info"],
                "preview": ["adobe_preview"],
                "poster": ["adobe_ai_new_document", "adobe_ai_shapes", "adobe_ai_text", "adobe_ai_export"],
                "photo edit": ["adobe_ps_adjustment", "adobe_ps_filter", "adobe_ps_layers"],
                "motion graphics": ["adobe_ae_comp", "adobe_ae_layer", "adobe_ae_expression"],
                "print layout": ["adobe_id_document", "adobe_id_text", "adobe_id_image"],
            }

            seen = set()
            for keywords, tools_list in keyword_tools.items():
                if any(kw in task for kw in keywords.split()):
                    for t in tools_list:
                        if t not in seen and t in tool_registry:
                            seen.add(t)
                            desc = (tool_registry[t].description or "")[:80]
                            suggestions.append(f"  {t} — {desc}")

            if not suggestions:
                return (
                    f"No specific suggestions for '{params.query}'. "
                    "Try using action='search' with individual keywords, or action='list' to browse all tools."
                )

            lines = [f"Suggested tools for '{params.query}' ({len(suggestions)}):"]
            lines.extend(suggestions)
            lines.append("\nTip: Use action='describe' with a tool name to see its full parameters.")
            return "\n".join(lines)

        return f"Error: Unknown action '{params.action}'. Use: list, search, describe, for_task"

    # ── Batch Operations Tool ─────────────────────────────────────────

    @mcp.tool(
        name="adobe_batch",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def adobe_batch(params: BatchInput) -> str:
        """Execute multiple Adobe tool operations in a single call.

        Instead of making 7 separate tool calls (burning ~3,500 tokens of accumulated
        context), send them all at once and get a compact summary back (~200 tokens).

        Example operations JSON:
        [
          {"tool": "adobe_ai_new_document", "params": {"width": 800, "height": 600, "name": "poster"}},
          {"tool": "adobe_ai_shapes", "params": {"shape": "rectangle", "x": 0, "y": 0, "width": 800, "height": 600, "fill_r": 0, "fill_g": 0, "fill_b": 0}},
          {"tool": "adobe_ai_text", "params": {"text": "VOID", "x": 400, "y": 300, "size": 72}}
        ]
        """
        try:
            operations = json.loads(params.operations)
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in operations: {e}"

        if not isinstance(operations, list) or not operations:
            return "Error: operations must be a non-empty JSON array"

        # Get all registered tool functions from the MCP server
        tool_registry = mcp._tool_manager._tools if hasattr(mcp, '_tool_manager') else {}

        results = []
        errors = []

        for i, op in enumerate(operations):
            tool_name = op.get("tool", "")
            tool_params = op.get("params", {})
            step_label = f"Step {i+1}/{len(operations)} [{tool_name}]"

            if tool_name not in tool_registry:
                error_msg = f"{step_label}: Unknown tool '{tool_name}'"
                errors.append(error_msg)
                if params.stop_on_error:
                    results.append(f"FAIL: {error_msg}")
                    break
                results.append(f"SKIP: {error_msg}")
                continue

            try:
                # Get the tool's function and call it with parsed params
                tool_func = tool_registry[tool_name].fn
                # Get the model class from the function's type hints
                import inspect as _inspect
                sig = _inspect.signature(tool_func)
                param_types = list(sig.parameters.values())

                if param_types:
                    # The tool expects a Pydantic model parameter
                    model_cls = param_types[0].annotation
                    model_instance = model_cls(**tool_params)
                    result = await tool_func(model_instance)
                else:
                    # No-arg tool (like adobe_list_apps)
                    result = await tool_func()

                # Truncate long results for batch summary
                result_str = str(result)
                if len(result_str) > 200:
                    result_str = result_str[:197] + "..."
                results.append(f"OK: {step_label} -> {result_str}")

            except Exception as e:
                error_msg = f"{step_label}: {type(e).__name__}: {e}"
                errors.append(error_msg)
                if params.stop_on_error:
                    results.append(f"FAIL: {error_msg}")
                    break
                results.append(f"ERROR: {error_msg}")

        # Compact summary
        ok_count = sum(1 for r in results if r.startswith("OK:"))
        fail_count = len(errors)
        header = f"Batch: {ok_count}/{len(operations)} succeeded"
        if fail_count:
            header += f", {fail_count} failed"

        # Include session state summary if any apps were touched
        state_line = session.summary() if session._apps else ""

        summary_lines = [header, "---"] + results
        if state_line:
            summary_lines.append("---")
            summary_lines.append(state_line)

        return "\n".join(summary_lines)

    # ── Workflow Tool ─────────────────────────────────────────────────

    @mcp.tool(
        name="adobe_workflow",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def adobe_workflow(params: WorkflowInput) -> str:
        """Save, list, describe, or run named multi-step workflows.

        Workflows are persistent operation sequences (saved to disk) that can be
        replayed with parameter overrides. Perfect for complex multi-step pipelines
        like VOID poster generation — save once, replay with different seeds.

        Save:   adobe_workflow(action="save", name="my_flow", operations="[...]", description="...")
        List:   adobe_workflow(action="list")
        Describe: adobe_workflow(action="describe", name="my_flow")
        Run:    adobe_workflow(action="run", name="my_flow", overrides='{"0": {"name": "new_poster"}}')
        """
        import os
        from pathlib import Path as _Path

        workflows_dir = _Path(__file__).parent.parent.parent / "workflows"
        workflows_dir.mkdir(exist_ok=True)

        if params.action == "list":
            files = sorted(workflows_dir.glob("*.json"))
            if not files:
                return "No saved workflows. Use action='save' to create one."
            listing = []
            for f in files:
                try:
                    data = json.loads(f.read_text())
                    desc = data.get("description", "")
                    steps = len(data.get("operations", []))
                    listing.append(f"  {f.stem}: {steps} steps — {desc}")
                except Exception:
                    listing.append(f"  {f.stem}: (corrupted)")
            return f"Saved workflows ({len(files)}):\n" + "\n".join(listing)

        if params.action == "save":
            if not params.name:
                return "Error: 'name' required for save action"
            if not params.operations:
                return "Error: 'operations' required for save action"
            try:
                ops = json.loads(params.operations)
            except json.JSONDecodeError as e:
                return f"Error: Invalid JSON in operations: {e}"

            workflow_data = {
                "name": params.name,
                "description": params.description or "",
                "operations": ops,
                "version": 1,
            }
            path = workflows_dir / f"{params.name}.json"
            path.write_text(json.dumps(workflow_data, indent=2))
            return f"Workflow '{params.name}' saved ({len(ops)} steps) at {path}"

        if params.action == "describe":
            if not params.name:
                return "Error: 'name' required for describe action"
            path = workflows_dir / f"{params.name}.json"
            if not path.exists():
                return f"Error: Workflow '{params.name}' not found"
            data = json.loads(path.read_text())
            lines = [f"Workflow: {data['name']}", f"Description: {data.get('description', 'N/A')}", f"Steps ({len(data['operations'])}):", "---"]
            for i, op in enumerate(data["operations"]):
                tool = op.get("tool", "unknown")
                p = op.get("params", {})
                param_summary = ", ".join(f"{k}={v}" for k, v in list(p.items())[:4])
                if len(p) > 4:
                    param_summary += ", ..."
                lines.append(f"  {i+1}. {tool}({param_summary})")
            return "\n".join(lines)

        if params.action == "run":
            if not params.name:
                return "Error: 'name' required for run action"
            path = workflows_dir / f"{params.name}.json"
            if not path.exists():
                return f"Error: Workflow '{params.name}' not found"
            data = json.loads(path.read_text())
            operations = data["operations"]

            # Apply overrides if provided
            if params.overrides:
                try:
                    overrides = json.loads(params.overrides)
                except json.JSONDecodeError as e:
                    return f"Error: Invalid JSON in overrides: {e}"

                for i, op in enumerate(operations):
                    # Apply step-specific overrides
                    step_key = str(i)
                    if step_key in overrides:
                        op.setdefault("params", {}).update(overrides[step_key])
                    # Apply "all" overrides to every step
                    if "all" in overrides:
                        op.setdefault("params", {}).update(overrides["all"])

            # Execute via batch
            batch_params = BatchInput(
                operations=json.dumps(operations),
                stop_on_error=True,
            )
            result = await adobe_batch(batch_params)
            return f"Workflow '{params.name}' executed:\n{result}"

        return f"Error: Unknown action '{params.action}'. Use: save, list, describe, run"

    # ── Cross-App Pipeline Tool ───────────────────────────────────────

    @mcp.tool(
        name="adobe_pipeline",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def adobe_pipeline(params: PipelineInput) -> str:
        """Execute a cross-app pipeline — chain operations across multiple Adobe applications.

        This is the most powerful automation tool: create in Illustrator, composite in
        Photoshop, animate in After Effects, render in Media Encoder — all in one call.

        Special placeholders in params:
          {{prev_output}}   — replaced with previous step's output file path
          {{step_N_output}} — replaced with step N's output path (0-based)

        Output paths are extracted from step results that contain JSON with 'path' or
        'file_path' keys, or from export tool results.

        Example:
        [
          {"tool": "adobe_ai_export", "params": {"file_path": "/tmp/logo.svg", "format": "svg"}},
          {"tool": "adobe_ps_layers", "params": {"action": "create", "new_name": "imported_logo"}},
          {"tool": "adobe_open_file", "params": {"app": "photoshop", "file_path": "{{prev_output}}"}}
        ]
        """
        try:
            steps = json.loads(params.steps)
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in steps: {e}"

        if not isinstance(steps, list) or not steps:
            return "Error: steps must be a non-empty JSON array"

        tool_registry = mcp._tool_manager._tools if hasattr(mcp, '_tool_manager') else {}
        step_outputs: list[str] = []  # File paths extracted from each step
        results: list[str] = []

        desc = params.description or "Cross-app pipeline"

        for i, step in enumerate(steps):
            tool_name = step.get("tool", "")
            tool_params = step.get("params", {})
            app = step.get("app", "")
            step_label = f"Step {i+1}/{len(steps)}"
            if app:
                step_label += f" [{app}]"
            step_label += f" {tool_name}"

            # Replace placeholders in parameter values
            def _replace_placeholders(val):
                if not isinstance(val, str):
                    return val
                if "{{prev_output}}" in val and step_outputs:
                    val = val.replace("{{prev_output}}", step_outputs[-1])
                for j, out_path in enumerate(step_outputs):
                    val = val.replace(f"{{{{step_{j}_output}}}}", out_path)
                return val

            tool_params = {k: _replace_placeholders(v) for k, v in tool_params.items()}

            if tool_name not in tool_registry:
                results.append(f"FAIL: {step_label}: Unknown tool '{tool_name}'")
                break

            try:
                import inspect as _inspect
                tool_func = tool_registry[tool_name].fn
                sig = _inspect.signature(tool_func)
                param_types = list(sig.parameters.values())

                if param_types:
                    model_cls = param_types[0].annotation
                    model_instance = model_cls(**tool_params)
                    result = await tool_func(model_instance)
                else:
                    result = await tool_func()

                # Extract output path for pipeline chaining
                output_path = ""
                try:
                    result_data = json.loads(result)
                    output_path = result_data.get("path", result_data.get("file_path", ""))
                except (json.JSONDecodeError, TypeError, AttributeError):
                    # Check if result contains a file path
                    if isinstance(result, str):
                        for token in result.split():
                            if "/" in token and "." in token.split("/")[-1]:
                                output_path = token.strip('"').strip("'")
                                break

                step_outputs.append(output_path)

                result_str = str(result)
                if len(result_str) > 150:
                    result_str = result_str[:147] + "..."
                results.append(f"OK: {step_label} -> {result_str}")

            except Exception as e:
                step_outputs.append("")
                results.append(f"FAIL: {step_label}: {type(e).__name__}: {e}")
                break

        ok_count = sum(1 for r in results if r.startswith("OK:"))
        header = f"Pipeline '{desc}': {ok_count}/{len(steps)} steps completed"
        state_line = session.summary() if session._apps else ""

        lines = [header, "---"] + results
        if state_line:
            lines.append("---")
            lines.append(state_line)
        return "\n".join(lines)

    # ── Relay Status Tool ──────────────────────────────────────────────

    @mcp.tool(
        name="adobe_relay_status",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def adobe_relay_status(params: RelayStatusInput) -> str:
        """Check the status of the WebSocket relay server and connected CEP panels.

        Returns which Adobe apps are connected via WebSocket, heartbeat freshness
        per app, operation cache statistics, and recording buffer count.

        Use this to verify that CEP panels are connected before running tool calls
        that benefit from the persistent WebSocket path (lower latency, no timeouts).
        """
        import time as _time

        # Access the relay singleton from the engine module
        try:
            from adobe_mcp.engine import get_relay
            relay = get_relay()
        except ImportError:
            relay = None

        # Access the operation cache
        try:
            from adobe_mcp.relay.cache import OperationCache
            cache = OperationCache()
        except ImportError:
            cache = None

        lines = ["=== RELAY STATUS ==="]

        if relay is None:
            lines.append("Relay: not initialized (engine.set_relay() not called)")
            lines.append("All tool calls use osascript/PowerShell fallback path.")
            return "\n".join(lines)

        # Server status
        if relay._started:
            lines.append(f"Server: running on ws://{relay.host}:{relay.port}")
        else:
            lines.append("Server: not started")
            lines.append("Hint: relay starts automatically with 'uv run adobe-mcp'")

        # Connected apps with heartbeat freshness
        lines.append("")
        lines.append("=== CONNECTED APPS ===")
        connected = relay.connected_apps
        if not connected:
            lines.append("  (no apps connected)")
            lines.append("  Install CEP panels: ./scripts/install-cep-panels.sh")
        else:
            now = _time.time()
            for app_name in sorted(connected):
                last_beat = relay._last_heartbeat.get(app_name, 0)
                freshness = now - last_beat
                if freshness < 10:
                    status = "fresh"
                elif freshness < 15:
                    status = "aging"
                else:
                    status = "stale"
                lines.append(f"  {app_name}: connected ({status}, {freshness:.1f}s since heartbeat)")

        # Apps registered but possibly stale
        all_registered = list(relay._connections.keys())
        stale = [a for a in all_registered if a not in connected]
        if stale:
            lines.append("")
            lines.append("Stale connections (no recent heartbeat):")
            for app_name in stale:
                lines.append(f"  {app_name}: stale")

        # Pending requests
        pending_count = len(relay._pending)
        if pending_count > 0:
            lines.append(f"\nPending JSX requests: {pending_count}")

        # Recording buffer
        recording_count = len(relay._recording)
        lines.append(f"\nRecording buffer: {recording_count} entries")

        # Cache statistics
        lines.append("")
        lines.append("=== CACHE ===")
        if cache is not None:
            ops_file = cache._ops_file
            if ops_file.exists():
                # Count lines in the JSONL file for total operation count
                try:
                    with open(ops_file, "r", encoding="utf-8") as f:
                        op_count = sum(1 for line in f if line.strip())
                    file_size = ops_file.stat().st_size
                    size_label = f"{file_size}" if file_size < 1024 else f"{file_size / 1024:.1f}KB"
                    lines.append(f"  Operations logged: {op_count}")
                    lines.append(f"  Cache file: {ops_file} ({size_label})")
                except OSError:
                    lines.append("  Operations logged: (read error)")
            else:
                lines.append("  Operations logged: 0 (no cache file yet)")

            # Check for snapshots
            snapshots = list(cache._snapshots_dir.glob("*_latest.json")) if cache._snapshots_dir.exists() else []
            if snapshots:
                snap_names = [s.stem.replace("_latest", "") for s in snapshots]
                lines.append(f"  App snapshots: {', '.join(snap_names)}")
            else:
                lines.append("  App snapshots: none")
        else:
            lines.append("  Cache module not available")

        return "\n".join(lines)
