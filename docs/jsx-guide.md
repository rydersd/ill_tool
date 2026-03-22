# ExtendScript / JSX Guide

Working with Adobe's ExtendScript across different apps.

## Per-App Differences

### Photoshop
- **AppleScript**: `tell application "Adobe Photoshop 2026" to do javascript of file "<path>"`
- **JSON**: Native `JSON.stringify()` / `JSON.parse()` supported
- **Entry point**: `app.activeDocument`
- **Units**: Uses UnitValue — `UnitValue(100, 'px')`

### Illustrator
- **AppleScript**: `tell application "Adobe Illustrator" to do javascript file "<path>"` (no "of")
- **JSON**: ES3 engine — **no native JSON**. The polyfill in `jsx/polyfills.py` is auto-prepended by `engine._prepare_jsx()`, so all Illustrator JSX can use `JSON.stringify()` transparently.
- **Entry point**: `app.activeDocument`
- **Units**: Points by default
- **Coordinates**: Y-axis is inverted (positive = up from bottom-left)

### After Effects
- **AppleScript**: `tell application "Adobe After Effects 2026" to DoScriptFile "<path>"`
- **JSON**: Native JSON supported
- **Entry point**: `app.project.activeItem` (comp), `app.project` (project)
- **Indexing**: 1-based (layers, items)

### InDesign
- **AppleScript**: `tell application id "com.adobe.InDesign" to do script (POSIX file "<path>") language javascript`
- **JSON**: Native JSON supported
- **Entry point**: `app.activeDocument`
- **Units**: Points, configurable via document preferences

### Premiere Pro
- **AppleScript**: Not supported via `mac_script_cmd` (null)
- **Scripting**: Uses CEP/ExtendScript via file execution only
- **Entry point**: `app.project`, `app.project.activeSequence`

### Animate
- **AppleScript**: Not supported via `mac_script_cmd` (null)
- **Scripting**: JSFL (JavaScript Flash) — uses `fl.getDocumentDOM()` not `app`
- **Entry point**: `fl.getDocumentDOM()`

### Media Encoder
- **AppleScript**: Not supported via `mac_script_cmd` (null)
- **Entry point**: `app` (the encoder application)

## JSON Polyfill

Illustrator's ExtendScript engine is ES3, which lacks native JSON. The polyfill in `jsx/polyfills.py` provides:

- `JSON.stringify(obj)` — serializes objects, arrays, strings, numbers, booleans, null
- `JSON.parse(str)` — parses JSON strings (uses `eval()` — safe in ExtendScript context)

The polyfill is automatically prepended to all Illustrator JSX by `engine._prepare_jsx()`. You never need to add it manually.

## String Escaping

Use `jsx/templates.py` helpers:

```python
from adobe_mcp.jsx.templates import escape_jsx_string, escape_jsx_path

# For text content inside JSX string literals
escaped = escape_jsx_string(user_text)  # handles ", \, \n, \r, \t
jsx = f'tf.contents = "{escaped}";'

# For file paths in File() constructors
safe_path = escape_jsx_path(file_path)  # \ → /, ' → \'
jsx = f'var f = new File("{safe_path}");'
```

## Common Patterns

### Getting document info (all apps)
```javascript
// Most apps:
var d = app.activeDocument;
JSON.stringify({ name: d.name, /* ... */ });

// Animate:
var d = fl.getDocumentDOM();

// After Effects (comp):
var c = app.project.activeItem;
```

### Error handling in JSX
```javascript
try {
    // risky operation
    result;
} catch(e) {
    "Error: " + e.message;
}
```

### Iterating collections
```javascript
// Most apps (0-based):
for (var i = 0; i < collection.length; i++) { ... }

// After Effects (1-based):
for (var i = 1; i <= collection.numItems; i++) { ... }
```
