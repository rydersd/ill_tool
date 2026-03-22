# Adobe MCP Server — Architecture

## Module Map

```
src/adobe_mcp/
├── __init__.py              # Package root — exports mcp, main
├── __main__.py              # python -m adobe_mcp entry point
├── server.py                # FastMCP init + register_all_tools + main()
├── config.py                # ADOBE_APPS registry, platform detection, SCRIPTS_DIR
├── enums.py                 # AdobeApp, PhotoshopBlendMode, ImageFormat, ColorSpace
├── engine.py                # _run_jsx, _run_powershell, _run_osascript + async wrappers
├── models/                  # Pydantic input models (one file per app)
│   ├── __init__.py          # Re-exports all models
│   ├── common.py            # 10 cross-app models
│   ├── photoshop.py         # 11 PS models
│   ├── illustrator.py       # 5 AI models
│   ├── premiere.py          # 6 PR models
│   ├── aftereffects.py      # 6 AE models
│   ├── indesign.py          # 3 ID models
│   ├── animate.py           # 2 AN models
│   └── media_encoder.py     # 1 AME model
├── tools/                   # Tool implementations (one file per app)
│   ├── __init__.py          # register_all_tools() — calls each app's register fn
│   ├── common.py            # 11 cross-app tools
│   ├── photoshop.py         # 11 PS tools
│   ├── illustrator.py       # 5 AI tools
│   ├── premiere.py          # 6 PR tools
│   ├── aftereffects.py      # 6 AE tools
│   ├── indesign.py          # 3 ID tools
│   ├── animate.py           # 2 AN tools
│   └── media_encoder.py     # 1 AME tool
├── jsx/                     # ExtendScript helpers
│   ├── __init__.py
│   ├── polyfills.py         # JSON polyfill for Illustrator ES3
│   └── templates.py         # escape_jsx_string(), escape_jsx_path()
└── scripts/                 # Generated/static JSX scripts
```

## Dependency Graph

```
server.py
  └─ tools/__init__.py (register_all_tools)
       ├─ tools/common.py ─────── engine.py ──── config.py
       ├─ tools/photoshop.py ──── engine.py      enums.py
       ├─ tools/illustrator.py ── engine.py
       ├─ tools/premiere.py ───── engine.py
       ├─ tools/aftereffects.py ─ engine.py
       ├─ tools/indesign.py ───── engine.py
       ├─ tools/animate.py ────── engine.py
       └─ tools/media_encoder.py ─ engine.py
                                    │
                               jsx/polyfills.py (lazy import for Illustrator)
```

- `engine.py` imports from `config.py` (ADOBE_APPS, IS_MACOS, IS_WINDOWS)
- `engine.py` lazy-imports `jsx/polyfills.py` only when running Illustrator code
- `models/` imports only from `enums.py` (no circular deps)
- `tools/` imports from `engine.py` and `models/`

## Registration Pattern

FastMCP has no router concept. Each tool file exports a `register_*_tools(mcp)` function:

```python
# tools/illustrator.py
def register_illustrator_tools(mcp):
    @mcp.tool(name="adobe_ai_shapes", ...)
    async def adobe_ai_shapes(params: AiShapeInput) -> str:
        ...

# tools/__init__.py
def register_all_tools(mcp):
    register_common_tools(mcp)
    register_photoshop_tools(mcp)
    ...
```

## Distribution

### pip (PyPI)
```
pyproject.toml → adobe_mcp.server:main
src/adobe_mcp/ → installed as package
```

### npm (npx)
```
scripts/build-npm.sh → copies src/adobe_mcp/ to npm/server/adobe_mcp/
npm/bin/adobe-mcp.js → spawns `python -m adobe_mcp` with PYTHONPATH=server/
```

Run `bash scripts/build-npm.sh` before npm publish.

## Tool Count: 45

| App | Tools | Module |
|-----|-------|--------|
| Cross-app | 11 | tools/common.py |
| Photoshop | 11 | tools/photoshop.py |
| Illustrator | 5 | tools/illustrator.py |
| Premiere Pro | 6 | tools/premiere.py |
| After Effects | 6 | tools/aftereffects.py |
| InDesign | 3 | tools/indesign.py |
| Animate | 2 | tools/animate.py |
| Media Encoder | 1 | tools/media_encoder.py |
