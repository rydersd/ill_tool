"""Design Token System — define and apply consistent design vocabularies.

Design tokens are named values for colors, typography, spacing, and effects
that can be referenced by name across all Adobe tools. Instead of specifying
`fill_r=255, fill_g=0, fill_b=100` everywhere, define a token `color.primary`
once and reference it by name.

This enables:
1. Consistent design across operations (no color drift)
2. Rapid theme switching (change token values, everything updates)
3. Design system enforcement (tokens = your brand guidelines)
4. Compact tool calls (token names instead of raw values)

Architecture:
    - Tokens are stored in a global TokenRegistry (per server process)
    - Token sets can be saved to / loaded from JSON files
    - Tools can resolve token references via `resolve_tokens(params)`
    - The adobe_design_tokens tool lets the LLM manage tokens interactively
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DesignToken:
    """A single design token — a named, typed design value."""
    name: str
    value: Any
    category: str  # color, typography, spacing, effect
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "category": self.category,
            "description": self.description,
        }


class TokenRegistry:
    """Global design token registry. One per MCP server process.

    Usage:
        from adobe_mcp.tokens import tokens

        # Define tokens
        tokens.set("color.primary", {"r": 255, "g": 0, "b": 100}, category="color")
        tokens.set("color.bg", {"r": 10, "g": 10, "b": 10}, category="color")
        tokens.set("type.heading", {"font": "HelveticaNeue-Bold", "size": 72}, category="typography")
        tokens.set("spacing.margin", 40, category="spacing")

        # Resolve tokens in params
        params = {"fill_r": "$color.primary.r", "fill_g": "$color.primary.g", "fill_b": "$color.primary.b"}
        resolved = tokens.resolve(params)
        # -> {"fill_r": 255, "fill_g": 0, "fill_b": 100}
    """

    def __init__(self) -> None:
        self._tokens: dict[str, DesignToken] = {}

    def set(self, name: str, value: Any, category: str = "custom", description: str = "") -> None:
        """Set a design token value."""
        self._tokens[name] = DesignToken(
            name=name, value=value, category=category, description=description
        )

    def get(self, name: str) -> Any | None:
        """Get a token value by name. Returns None if not found."""
        token = self._tokens.get(name)
        return token.value if token else None

    def get_nested(self, path: str) -> Any | None:
        """Get a nested value from a token using dot notation.

        Examples:
            get_nested("color.primary.r") -> looks up token "color.primary", returns value["r"]
            get_nested("spacing.margin") -> returns the token value directly if not a dict
        """
        parts = path.split(".")

        # Try progressively longer prefixes
        for i in range(len(parts), 0, -1):
            token_name = ".".join(parts[:i])
            token = self._tokens.get(token_name)
            if token is not None:
                remaining = parts[i:]
                value = token.value
                for key in remaining:
                    if isinstance(value, dict):
                        value = value.get(key)
                    else:
                        return None
                return value
        return None

    def resolve(self, params: dict[str, Any]) -> dict[str, Any]:
        """Resolve token references in parameter dict.

        Token references start with '$': "$color.primary.r" -> 255
        Non-token values pass through unchanged.
        """
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$"):
                token_path = value[1:]  # Strip $
                token_value = self.get_nested(token_path)
                if token_value is not None:
                    resolved[key] = token_value
                else:
                    resolved[key] = value  # Keep original if not found
            else:
                resolved[key] = value
        return resolved

    def list_tokens(self, category: str | None = None) -> list[dict]:
        """List all tokens, optionally filtered by category."""
        results = []
        for token in self._tokens.values():
            if category and token.category != category:
                continue
            results.append(token.to_dict())
        return results

    def save(self, path: str | Path) -> None:
        """Save all tokens to a JSON file."""
        path = Path(path)
        data = {
            "version": 1,
            "tokens": [t.to_dict() for t in self._tokens.values()],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    def load(self, path: str | Path) -> int:
        """Load tokens from a JSON file. Returns number loaded."""
        path = Path(path)
        if not path.exists():
            return 0
        data = json.loads(path.read_text())
        count = 0
        for t in data.get("tokens", []):
            self.set(
                name=t["name"],
                value=t["value"],
                category=t.get("category", "custom"),
                description=t.get("description", ""),
            )
            count += 1
        return count

    def clear(self) -> None:
        """Clear all tokens."""
        self._tokens.clear()

    def apply_preset(self, preset_name: str) -> str:
        """Apply a built-in design preset. Returns description of what was set."""
        presets = {
            "void": {
                "description": "VOID engine aesthetic — dark, technical, high contrast",
                "tokens": {
                    "color.bg": ({"r": 10, "g": 10, "b": 10}, "color", "Background — near-black"),
                    "color.primary": ({"r": 255, "g": 0, "b": 100}, "color", "Primary — hot pink"),
                    "color.secondary": ({"r": 0, "g": 200, "b": 255}, "color", "Secondary — electric cyan"),
                    "color.accent": ({"r": 255, "g": 220, "b": 0}, "color", "Accent — warning yellow"),
                    "color.text": ({"r": 230, "g": 230, "b": 230}, "color", "Text — off-white"),
                    "type.heading": ({"font": "HelveticaNeue-Bold", "size": 72}, "typography", "Heading"),
                    "type.subheading": ({"font": "HelveticaNeue-Medium", "size": 36}, "typography", "Subheading"),
                    "type.body": ({"font": "InputMono-Regular", "size": 11}, "typography", "Body/code"),
                    "type.label": ({"font": "HelveticaNeue-Light", "size": 8}, "typography", "Labels"),
                    "spacing.margin": (40, "spacing", "Outer margin"),
                    "spacing.gutter": (20, "spacing", "Column gutter"),
                    "spacing.padding": (12, "spacing", "Inner padding"),
                    "effect.stroke_width": (0.5, "effect", "Default stroke weight"),
                    "effect.corner_radius": (2, "effect", "Default corner radius"),
                },
            },
            "minimal": {
                "description": "Clean minimalist — white space, subtle grays, sharp typography",
                "tokens": {
                    "color.bg": ({"r": 255, "g": 255, "b": 255}, "color", "Background — pure white"),
                    "color.primary": ({"r": 20, "g": 20, "b": 20}, "color", "Primary — near-black"),
                    "color.secondary": ({"r": 120, "g": 120, "b": 120}, "color", "Secondary — mid gray"),
                    "color.accent": ({"r": 0, "g": 100, "b": 255}, "color", "Accent — clean blue"),
                    "color.text": ({"r": 30, "g": 30, "b": 30}, "color", "Text — dark gray"),
                    "type.heading": ({"font": "HelveticaNeue-Light", "size": 48}, "typography", "Heading"),
                    "type.body": ({"font": "Georgia", "size": 14}, "typography", "Body text"),
                    "spacing.margin": (60, "spacing", "Generous outer margin"),
                    "spacing.gutter": (30, "spacing", "Column gutter"),
                },
            },
            "brutalist": {
                "description": "Brutalist web aesthetic — raw, bold, unfinished",
                "tokens": {
                    "color.bg": ({"r": 245, "g": 245, "b": 230}, "color", "Background — off-white"),
                    "color.primary": ({"r": 0, "g": 0, "b": 0}, "color", "Primary — pure black"),
                    "color.accent": ({"r": 255, "g": 0, "b": 0}, "color", "Accent — raw red"),
                    "color.text": ({"r": 0, "g": 0, "b": 0}, "color", "Text — black"),
                    "type.heading": ({"font": "Courier-Bold", "size": 96}, "typography", "Heading — oversized mono"),
                    "type.body": ({"font": "Times-Roman", "size": 18}, "typography", "Body — serif"),
                    "spacing.margin": (20, "spacing", "Tight margin"),
                    "effect.stroke_width": (3, "effect", "Heavy stroke"),
                    "effect.border": (2, "effect", "Border width"),
                },
            },
        }

        preset = presets.get(preset_name)
        if not preset:
            available = ", ".join(presets.keys())
            return f"Unknown preset '{preset_name}'. Available: {available}"

        for name, (value, category, desc) in preset["tokens"].items():
            self.set(name, value, category=category, description=desc)

        return f"Applied '{preset_name}' preset: {preset['description']} ({len(preset['tokens'])} tokens set)"

    def load_dna_preset(self, dna_path: str | Path) -> str:
        """Load a Design DNA JSON and convert its palette/typography/spacing to design tokens.

        Reads a DNA file (e.g., designers-republic.json) and maps its structured
        aesthetic data into the token registry so composition tools can reference
        design values by token name ($color.primary, $type.heading, etc.).

        Conversions performed:
            - palette.colors[role] -> color.{role} with hex->rgb conversion
            - typography.heading/body -> type.heading, type.body
            - spacing fields -> spacing.density, spacing.whitespace_ratio
            - personality -> meta.personality, meta.aesthetic_name

        Args:
            dna_path: Path to a Design DNA JSON file.

        Returns:
            Summary string describing how many tokens were loaded and from which aesthetic.
        """
        dna_path = Path(dna_path)
        if not dna_path.exists():
            return f"DNA file not found: {dna_path}"

        data = json.loads(dna_path.read_text())
        count = 0

        aesthetic_name = data.get("synthesis", {}).get("aesthetic_name", dna_path.stem)

        # ── Palette colors: hex -> rgb tokens ────────────────────────────
        palette = data.get("palette", {})
        for color_entry in palette.get("colors", []):
            role = color_entry.get("role", "unknown")
            hex_val = color_entry.get("hex", "")
            if hex_val.startswith("#") and len(hex_val) >= 7:
                r = int(hex_val[1:3], 16)
                g = int(hex_val[3:5], 16)
                b = int(hex_val[5:7], 16)
                note = color_entry.get("note", "")
                self.set(
                    f"color.{role}",
                    {"r": r, "g": g, "b": b, "hex": hex_val},
                    category="color",
                    description=f"{aesthetic_name}: {note}" if note else f"{aesthetic_name} palette",
                )
                count += 1

        # ── Typography: heading + body tokens ────────────────────────────
        typography = data.get("typography", {})
        heading = typography.get("heading", {})
        if heading:
            self.set(
                "type.heading",
                {
                    "style": heading.get("style", "bold-geometric-sans"),
                    "weight": heading.get("weight", "bold"),
                    "scale_ratio": typography.get("scale_ratio", 3.0),
                },
                category="typography",
                description=f"{aesthetic_name}: heading typography",
            )
            count += 1

        body = typography.get("body", {})
        if body:
            self.set(
                "type.body",
                {
                    "style": body.get("style", "geometric-sans"),
                    "weight": body.get("weight", "regular"),
                },
                category="typography",
                description=f"{aesthetic_name}: body typography",
            )
            count += 1

        # ── Spacing: density + whitespace ratio ──────────────────────────
        spacing = data.get("spacing", {})
        density = spacing.get("density", {})
        if density:
            self.set(
                "spacing.density",
                density.get("value", "normal"),
                category="spacing",
                description=f"{aesthetic_name}: element density ({density.get('confidence', 0):.0%} confidence)",
            )
            count += 1

        whitespace = spacing.get("whitespace_ratio", {})
        if whitespace:
            self.set(
                "spacing.whitespace_ratio",
                whitespace.get("value", 0.3),
                category="spacing",
                description=f"{aesthetic_name}: whitespace ratio (range {whitespace.get('range', [])})",
            )
            count += 1

        # ── Composition metadata ─────────────────────────────────────────
        composition = data.get("composition", {})
        if composition:
            self.set(
                "composition.balance",
                composition.get("balance", {}).get("value", "balanced"),
                category="composition",
                description=f"{aesthetic_name}: composition balance",
            )
            self.set(
                "composition.grid",
                composition.get("grid_type", {}).get("value", "standard"),
                category="composition",
                description=f"{aesthetic_name}: grid type",
            )
            count += 2

        # ── Personality / meta ───────────────────────────────────────────
        personality = data.get("personality", {})
        if personality:
            self.set(
                "meta.personality",
                personality.get("value", ""),
                category="meta",
                description=f"{aesthetic_name}: {', '.join(personality.get('descriptors', [])[:3])}",
            )
            self.set(
                "meta.aesthetic_name",
                aesthetic_name,
                category="meta",
                description=f"Design DNA aesthetic: {aesthetic_name}",
            )
            count += 2

        return (
            f"Loaded '{aesthetic_name}' DNA preset: {count} tokens set "
            f"(palette: {len(palette.get('colors', []))}, "
            f"typography: {1 if heading else 0}+{1 if body else 0}, "
            f"spacing: {1 if density else 0}+{1 if whitespace else 0}, "
            f"composition: {2 if composition else 0}, "
            f"meta: {2 if personality else 0})"
        )

    def classify_fonts(self, font_list: list[dict]) -> dict:
        """Classify a list of fonts against DR-style design criteria.

        Scores each font on weight, geometric quality, pixel/modular feel,
        industrial character, and penalizes serif/script families. Groups
        top scorers into heading, display, label, and body roles.

        Args:
            font_list: List of font dicts with 'name', 'family', 'style' keys
                       (as returned by Illustrator's app.textFonts query).

        Returns:
            Dict with 'heading', 'display', 'label', 'body' role lists,
            each containing scored font entries, plus scan/classify counts.
        """
        # ── Known family lists (lowercase for case-insensitive matching) ──
        _geometric_families = [
            "futura", "avenir", "din", "eurostile", "gotham", "proxima",
            "bank gothic", "knockout", "agency", "impact", "bebas", "oswald",
            "barlow", "montserrat", "raleway", "poppins", "exo", "orbitron",
            "rajdhani", "audiowide", "michroma", "quantico", "jura",
            "electrolize", "share tech",
        ]
        _pixel_terms = [
            "pixel", "bitmap", "ocr", "terminal", "fixedsys", "vga", "dos",
            "chicago", "press start", "silkscreen", "munro", "upheaval",
        ]
        _industrial_terms = [
            "stencil", "highway", "industrial", "roboto mono", "sf mono",
            "fira mono", "inconsolata", "source code", "jetbrains mono",
            "menlo", "monaco", "consolas", "andale mono", "courier",
        ]
        _serif_terms = [
            "times", "georgia", "garamond", "palatino", "baskerville",
            "cambria", "caslon", "didot", "bodoni", "book antiqua",
        ]
        _script_terms = [
            "script", "brush", "handwriting", "cursive", "comic", "papyrus",
            "zapfino", "snell", "lucida handwriting",
        ]

        # ── Bold/weight keywords ──────────────────────────────────────────
        _bold_keywords = ["bold", "black", "heavy", "extrabold", "ultra"]
        _medium_keywords = ["medium", "demi", "semi"]
        _light_keywords = ["light", "thin", "ultralight", "hairline"]

        def _substring_match(text: str, terms: list[str]) -> bool:
            text_lower = text.lower()
            return any(t in text_lower for t in terms)

        scored: list[dict] = []

        for font in font_list:
            family = font.get("family", "")
            style = font.get("style", "")
            name = font.get("name", "")
            style_lower = style.lower()

            # Weight score
            weight_score = 0
            if any(kw in style_lower for kw in _bold_keywords):
                weight_score = 3
            elif any(kw in style_lower for kw in _medium_keywords):
                weight_score = 1
            elif any(kw in style_lower for kw in _light_keywords):
                weight_score = -3

            # Geometric sans score
            geometric_score = 3 if _substring_match(family, _geometric_families) else 0

            # Pixel / modular score
            pixel_score = 3 if _substring_match(family, _pixel_terms) else 0

            # Industrial / tech score
            industrial_score = 2 if _substring_match(family, _industrial_terms) else 0

            # Anti-DR penalty (serif or script families)
            anti_dr_penalty = 0
            if _substring_match(family, _serif_terms):
                anti_dr_penalty = -5
            elif _substring_match(family, _script_terms):
                anti_dr_penalty = -5

            scored.append({
                "name": name,
                "family": family,
                "style": style,
                "weight_score": weight_score,
                "geometric_score": geometric_score,
                "pixel_score": pixel_score,
                "industrial_score": industrial_score,
                "anti_dr_penalty": anti_dr_penalty,
            })

        # ── Role assignment ───────────────────────────────────────────────
        def _top(fonts: list[dict], key_fn, n: int = 5, filter_fn=None) -> list[dict]:
            pool = [f for f in fonts if filter_fn(f)] if filter_fn else list(fonts)
            pool.sort(key=key_fn, reverse=True)
            return [
                {"name": f["name"], "family": f["family"], "style": f["style"], "score": key_fn(f)}
                for f in pool[:n]
            ]

        heading = _top(
            scored,
            key_fn=lambda f: f["weight_score"] + f["geometric_score"] + f["anti_dr_penalty"],
        )
        display = _top(
            scored,
            key_fn=lambda f: f["pixel_score"] + f["anti_dr_penalty"],
        )
        label = _top(
            scored,
            key_fn=lambda f: f["industrial_score"] + f["anti_dr_penalty"],
        )
        body = _top(
            scored,
            key_fn=lambda f: f["geometric_score"] + f["anti_dr_penalty"],
            filter_fn=lambda f: f["weight_score"] >= 0,
        )

        # Count fonts that scored positively in at least one category
        classified_count = sum(
            1 for f in scored
            if (f["weight_score"] + f["geometric_score"] + f["pixel_score"]
                + f["industrial_score"] + f["anti_dr_penalty"]) > 0
        )

        return {
            "heading": heading,
            "display": display,
            "label": label,
            "body": body,
            "total_scanned": len(font_list),
            "total_classified": classified_count,
        }

    @property
    def count(self) -> int:
        return len(self._tokens)


# ── Global singleton ──────────────────────────────────────────────────
tokens = TokenRegistry()
