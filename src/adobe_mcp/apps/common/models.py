"""Cross-app input models shared by multiple tools."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from adobe_mcp.enums import AdobeApp, ImageFormat


class AppStatusInput(BaseModel):
    """Check if an Adobe app is running."""
    model_config = ConfigDict(str_strip_whitespace=True)
    app: AdobeApp = Field(..., description="Adobe application to check")


class RunJSXInput(BaseModel):
    """Execute arbitrary ExtendScript/JSX code in any Adobe app."""
    model_config = ConfigDict(str_strip_whitespace=True)
    app: AdobeApp = Field(..., description="Target Adobe application")
    code: str = Field(..., description="ExtendScript/JSX code to execute", min_length=1)
    timeout: Optional[int] = Field(default=120, description="Timeout in seconds", ge=5, le=600)


class RunJSXFileInput(BaseModel):
    """Execute a .jsx file in an Adobe app."""
    model_config = ConfigDict(str_strip_whitespace=True)
    app: AdobeApp = Field(..., description="Target Adobe application")
    file_path: str = Field(..., description="Full path to the .jsx file", min_length=1)
    timeout: Optional[int] = Field(default=120, description="Timeout in seconds", ge=5, le=600)


class LaunchAppInput(BaseModel):
    """Launch an Adobe application."""
    model_config = ConfigDict(str_strip_whitespace=True)
    app: AdobeApp = Field(..., description="Adobe application to launch")


class OpenFileInput(BaseModel):
    """Open a file in an Adobe application."""
    model_config = ConfigDict(str_strip_whitespace=True)
    app: AdobeApp = Field(..., description="Target Adobe application")
    file_path: str = Field(..., description="Full path to the file to open", min_length=1)


class SaveFileInput(BaseModel):
    """Save the active document in an Adobe application."""
    model_config = ConfigDict(str_strip_whitespace=True)
    app: AdobeApp = Field(..., description="Target Adobe application")
    file_path: Optional[str] = Field(default=None, description="Save path (None = save in place)")
    format: Optional[ImageFormat] = Field(default=None, description="Export format")


class CloseDocInput(BaseModel):
    """Close a document in an Adobe app."""
    model_config = ConfigDict(str_strip_whitespace=True)
    app: AdobeApp = Field(..., description="Target Adobe application")
    save: bool = Field(default=True, description="Save before closing")


class RunPowerShellInput(BaseModel):
    """Execute arbitrary PowerShell for Adobe COM automation."""
    model_config = ConfigDict(str_strip_whitespace=True)
    script: str = Field(..., description="PowerShell script to execute", min_length=1)
    timeout: Optional[int] = Field(default=120, description="Timeout in seconds", ge=5, le=600)


class GetDocInfoInput(BaseModel):
    """Get info about the active document in any Adobe app."""
    model_config = ConfigDict(str_strip_whitespace=True)
    app: AdobeApp = Field(..., description="Target Adobe application")


class ListFontsInput(BaseModel):
    """List available fonts in an Adobe app."""
    model_config = ConfigDict(str_strip_whitespace=True)
    app: AdobeApp = Field(..., description="Target Adobe application")
    filter: Optional[str] = Field(default=None, description="Filter fonts by name substring")


class PreviewInput(BaseModel):
    """Generate a quick preview image of the active document for visual analysis."""
    model_config = ConfigDict(str_strip_whitespace=True)
    app: AdobeApp = Field(..., description="Target Adobe application")
    max_size: Optional[int] = Field(default=1200, description="Max dimension in pixels (longest edge)", ge=100, le=4096)
    quality: Optional[int] = Field(default=72, description="JPEG quality 1-100", ge=1, le=100)


class BatchInput(BaseModel):
    """Execute multiple tool operations in a single call.

    Each operation specifies a tool name and its parameters.
    Operations execute sequentially. On error, stops and reports which step failed.
    Returns a compact summary of all results instead of individual verbose responses.
    """
    model_config = ConfigDict(str_strip_whitespace=True)
    operations: str = Field(
        ...,
        description=(
            "JSON array of operations. Each item: {\"tool\": \"adobe_ai_shapes\", \"params\": {...}}. "
            "Operations execute sequentially. On error, stops and reports which step failed."
        ),
    )
    stop_on_error: bool = Field(
        default=True,
        description="If true, stop executing on first error. If false, continue and report all errors."
    )


class WorkflowInput(BaseModel):
    """Save, list, or run named multi-step workflows.

    Workflows are saved operation sequences that can be replayed with parameter overrides.
    The VOID engine's 7-step poster pipeline becomes a single tool call.
    """
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ...,
        description="Action: 'save' (persist workflow), 'run' (execute saved workflow), 'list' (show available), 'describe' (show steps of a workflow)"
    )
    name: Optional[str] = Field(
        default=None,
        description="Workflow name for save/run/describe (e.g. 'void_poster')"
    )
    operations: Optional[str] = Field(
        default=None,
        description="JSON array of operations for 'save' action (same format as batch)"
    )
    overrides: Optional[str] = Field(
        default=None,
        description="JSON object of parameter overrides for 'run' action. Keys are step indices (0-based) or 'all'. Values are param dicts to merge."
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description for 'save' action"
    )


class DesignTokenInput(BaseModel):
    """Manage design tokens — named values for colors, typography, spacing, and effects.

    Tokens enable consistent design across operations. Define once, reference by name.
    Supports presets (void, minimal, brutalist) and save/load to files.
    """
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        ...,
        description=(
            "Action: 'set' (define a token), 'get' (get a token value), "
            "'list' (show all tokens), 'preset' (apply a built-in preset), "
            "'resolve' (resolve $token references in params), "
            "'save' (save tokens to file), 'load' (load tokens from file), "
            "'clear' (remove all tokens)"
        )
    )
    name: Optional[str] = Field(
        default=None,
        description="Token name (e.g. 'color.primary') for set/get, or preset name for preset action"
    )
    value: Optional[str] = Field(
        default=None,
        description="Token value as JSON for set action (e.g. '{\"r\":255,\"g\":0,\"b\":100}' or '48')"
    )
    category: Optional[str] = Field(
        default="custom",
        description="Token category: color, typography, spacing, effect, custom"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description for set action"
    )
    params: Optional[str] = Field(
        default=None,
        description="JSON object with $token references for resolve action"
    )
    file_path: Optional[str] = Field(
        default=None,
        description="File path for save/load actions"
    )


class HealthCheckInput(BaseModel):
    """Run diagnostics on the Adobe MCP server and connected applications.

    Tests connectivity to Adobe apps, verifies scripting capabilities,
    reports system status, and diagnoses common issues.
    """
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        default="full",
        description=(
            "Action: 'full' (comprehensive check), 'apps' (which apps are running), "
            "'connectivity' (test scripting connection to each running app), "
            "'system' (platform info and server stats)"
        )
    )
    app: Optional[AdobeApp] = Field(
        default=None,
        description="Test a specific app only (None = test all)"
    )


class ContextInput(BaseModel):
    """Get a compact context card — everything the LLM needs to know in ~100 tokens.

    Use this instead of re-querying document state after every tool call.
    Returns active documents, recent actions, and suggested next steps.
    """
    model_config = ConfigDict(str_strip_whitespace=True)
    app: Optional[str] = Field(
        default=None,
        description="Filter to specific app (None = overview of all active apps)"
    )


class SnippetInput(BaseModel):
    """Browse, search, and compose JSX code snippets from the snippet library.

    The snippet library contains tested, reusable ExtendScript patterns for
    common operations across all Adobe apps.
    """
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        default="list",
        description=(
            "Action: 'list' (browse all snippets), 'search' (find by keyword), "
            "'get' (full code for a snippet), 'compose' (fill params and return ready-to-run JSX)"
        )
    )
    query: Optional[str] = Field(
        default=None,
        description="Snippet name (for get/compose) or search keyword (for search)"
    )
    app: Optional[str] = Field(
        default=None,
        description="Filter by app: illustrator, photoshop, aftereffects, premierepro"
    )
    params: Optional[str] = Field(
        default=None,
        description="JSON object of parameter values for 'compose' action"
    )


class ToolDiscoveryInput(BaseModel):
    """Discover available tools, their parameters, and usage examples.

    This is a meta-tool: it helps the LLM understand what tools exist and how
    to use them without needing to hold all tool descriptions in context.
    """
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        default="list",
        description=(
            "Action: 'list' (all tools grouped by app), 'search' (find tools by keyword), "
            "'describe' (full params for one tool), 'examples' (usage examples for a tool), "
            "'for_task' (suggest tools for a described task)"
        )
    )
    query: Optional[str] = Field(
        default=None,
        description="Search keyword, tool name, or task description depending on action"
    )
    app: Optional[str] = Field(
        default=None,
        description="Filter by app: photoshop, illustrator, premiere, aftereffects, indesign, animate, common"
    )


class PipelineInput(BaseModel):
    """Execute a cross-app pipeline — chain operations across multiple Adobe apps.

    Supports automatic file passing between apps: the output path of one step
    can feed into the input of the next via {{prev_output}} placeholder.
    """
    model_config = ConfigDict(str_strip_whitespace=True)
    steps: str = Field(
        ...,
        description=(
            "JSON array of pipeline steps. Each: {\"app\": \"illustrator\", \"tool\": \"adobe_ai_export\", \"params\": {...}}. "
            "Use '{{prev_output}}' in params to reference previous step's output file path. "
            "Use '{{step_N_output}}' to reference step N's output (0-based)."
        )
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of what this pipeline does"
    )


class RelayStatusInput(BaseModel):
    """Check the status of the WebSocket relay server and connected CEP panels."""
    model_config = ConfigDict(str_strip_whitespace=True)
    # No required fields — returns full status overview by default


class SessionStateInput(BaseModel):
    """Query or reset server-side session state."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(
        default="summary",
        description="Action: 'summary' (compact overview), 'full' (detailed JSON), 'reset' (clear state), 'history' (recent actions)"
    )
    app: Optional[AdobeApp] = Field(
        default=None,
        description="Filter to specific app (None = all apps). For reset, clears only that app."
    )


class CompareDrawingInput(BaseModel):
    """Compare current Illustrator artboard against a reference image — returns contour-matched correction vectors."""
    model_config = ConfigDict(str_strip_whitespace=True)
    reference_path: str = Field(..., description="Absolute path to reference PNG/JPG image")
    export_path: str = Field(default="", description="Where to save overlay image (auto-generated in /tmp if empty)")
    artboard_index: int = Field(default=0, description="Which artboard to export for comparison (0-based)", ge=0)
    min_area_pct: float = Field(default=0.5, description="Ignore contours smaller than this % of image area", ge=0.01, le=50)
