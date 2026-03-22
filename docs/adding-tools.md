# Adding New Tools

Step-by-step guide for adding a new tool to the Adobe MCP server.

## 1. Create the input model

Add a Pydantic model to the appropriate `models/<app>.py` file:

```python
# models/illustrator.py

class AiLayerInput(BaseModel):
    """Manipulate Illustrator layers."""
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: list, rename, delete, hide, show, lock, unlock, reorder")
    layer_name: Optional[str] = Field(default=None, description="Target layer name")
    new_name: Optional[str] = Field(default=None, description="New name for rename")
```

Then add it to `models/__init__.py`:

```python
from adobe_mcp.models.illustrator import (
    AiExportInput,
    AiLayerInput,      # ← add here
    AiNewDocInput,
    ...
)
```

## 2. Implement the tool

Add the tool function inside the `register_*_tools()` function in the appropriate `tools/<app>.py`:

```python
# tools/illustrator.py

def register_illustrator_tools(mcp):
    # ... existing tools ...

    @mcp.tool(
        name="adobe_ai_layers",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def adobe_ai_layers(params: AiLayerInput) -> str:
        """Manage Illustrator layers — list, rename, delete, hide, show, lock, unlock, reorder."""
        if params.action == "list":
            jsx = """
var doc = app.activeDocument;
var layers = [];
for (var i = 0; i < doc.layers.length; i++) {
    var l = doc.layers[i];
    layers.push({ name: l.name, visible: l.visible, locked: l.locked });
}
JSON.stringify({ count: layers.length, layers: layers });
"""
        # ... more actions ...
        result = await _async_run_jsx("illustrator", jsx)
        return result["stdout"] if result["success"] else f"Error: {result['stderr']}"
```

## 3. Verify

Run the smoke test:

```bash
uv run python -c "
from adobe_mcp.server import mcp
tools = mcp._tool_manager._tools
print(f'Tools: {len(tools)}')
assert 'adobe_ai_layers' in tools
print('OK')
"
```

## 4. Rebuild npm (if publishing)

```bash
bash scripts/build-npm.sh
```

## Key Patterns

- **JSON polyfill**: Illustrator JSX can use `JSON.stringify()` freely — the polyfill is auto-injected by `engine._prepare_jsx()`.
- **Async execution**: Always use `await _async_run_jsx(app, jsx)` in tool functions (never the sync `_run_jsx` directly).
- **Tool naming**: `adobe_{app}_{noun}` — e.g. `adobe_ai_layers`, `adobe_ps_filter`.
- **Model naming**: `{AppPrefix}{Noun}Input` — e.g. `AiLayerInput`, `PsFilterInput`.
- **Annotations**: Set `readOnlyHint: True` for read-only tools, `destructiveHint: True` for delete/close operations.
