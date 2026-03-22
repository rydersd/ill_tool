# ill-tool Feature Tracker

## Known Bugs

### BUG-001: JSON.stringify undefined in Illustrator ExtendScript
- **Severity**: High — affects multiple tools
- **Affected tools**: `adobe_list_fonts`, `adobe_ai_new_document`, `adobe_ai_path` (return values)
- **Symptom**: `Error 2: JSON is undefined` when tools try to return structured results
- **Root cause**: Illustrator's ExtendScript engine (ES3) does not include a native `JSON` object. Tools that use `JSON.stringify()` to format return values fail.
- **Workaround**: Use `adobe_run_jsx` directly with string concatenation for return values, or use tools where the action succeeds even if the return errors (e.g., `adobe_ai_new_document` creates the doc but errors on the result string)
- **Fix**: Add a JSON polyfill at the top of every JSX script that checks `if (typeof JSON === 'undefined')` and defines `JSON.stringify`/`JSON.parse`. This should be injected by the server automatically.
- **Status**: Open

### BUG-002: adobe_ai_path create action fails
- **Severity**: Medium — workaround available via `adobe_run_jsx`
- **Affected tools**: `adobe_ai_path` with `action: "create"`
- **Symptom**: `Error 24: path.setEntirePath is not a function`
- **Root cause**: The path item may not be properly initialized before calling `setEntirePath`. In ExtendScript, `pathItems.add()` returns a valid path item, but the tool's JSX wrapper may be calling the method incorrectly.
- **Workaround**: Use `adobe_run_jsx` to create paths directly: `layer.pathItems.add()` then `.setEntirePath([[x,y], ...])`
- **Fix**: Review the `adobe_ai_path` tool's JSX template for the `create` action. Ensure `pathItems.add()` is used before `setEntirePath()`.
- **Status**: Open

### BUG-003: adobe_ai_export doesn't write to expected path
- **Severity**: Low — workaround available
- **Affected tools**: `adobe_ai_export`
- **Symptom**: Reports "Exported PNG" but file not found at specified path
- **Root cause**: Illustrator's `exportFile` may resolve paths differently than expected, or the tool's path handling doesn't match the OS path format
- **Workaround**: Use `adobe_run_jsx` with `new File('~/Desktop/filename.png')` and `doc.exportFile()` directly
- **Fix**: Verify path resolution in the export tool's JSX. Use `new File()` constructor with absolute paths.
- **Status**: Open

## Implemented Features

### Phase 1: Core Adobe MCP Tools (51 tools)
- Illustrator: document, shapes, text, path, export
- Photoshop: layers, text, filters, adjustments, selection, export, smart objects, batch
- After Effects: comp, layer, effect, expression, property, render
- Premiere Pro: project, sequence, timeline, media, effects, export
- InDesign: document, text, image
- Animate: document, timeline
- Media Encoder: encode
- Cross-app: app status, launch, open/close/save, list fonts, run JSX/PowerShell, get doc info

### Phase 2: Mad Designer Agent
- **Extract**: Vision-based DNA extraction from any image
- **Transplant**: Apply DNA to target Adobe documents
- **Mutate**: Create N variants along a mutation axis
- **Cross-Pollinate**: Merge DNA from multiple sources

### Phase 3: Full Creative Pipeline (current)
- **Synthesize**: Multi-reference DNA extraction from Pinterest/galleries with confidence scoring, invariants, variants, mutation axes
- **Create**: Generate new Illustrator designs driven by composite DNA
- **Prompt**: Generate Midjourney prompts from DNA vocabulary
- **Integrate**: Compose AI renders into Illustrator designs
- **Self-Learning**: Session log, prompt patterns, integration patterns — each session improves future sessions
- **Image Scraper**: `scripts/fetch_reference_images.py` — httpx-based fetcher with Pinterest dedup and RSS fallback

## Planned Features

- JSON polyfill injection for all ExtendScript tools (fixes BUG-001)
- Coordinate system normalization (top-left origin for all positioning tools)
- Preview tool (`adobe_preview`) for vision-in-the-loop feedback
- Batch processing across multiple files
- Design token extraction from Illustrator documents
