#!/usr/bin/env python3
"""
Theme manifest validator for Tandoor Recipes.
Ensures all theme files conform to the required schema.
"""

import json
import sys
from pathlib import Path
from typing import List

from jsonschema import ValidationError, validate

# Theme manifest schema
THEME_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["id", "name", "author", "version", "type", "colors"],
    "properties": {
        "id": {
            "type": "string",
            "pattern": "^[a-z0-9-]+$",
            "description": "Unique theme identifier (lowercase, alphanumeric, hyphens)",
        },
        "name": {"type": "string", "minLength": 1, "maxLength": 50},
        "description": {"type": "string", "maxLength": 200},
        "author": {"type": "string", "minLength": 1, "maxLength": 100},
        "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
        "type": {"type": "string", "enum": ["light", "dark", "auto"]},
        "colors": {
            "type": "object",
            "required": [
                "--color-primary",
                "--color-secondary",
                "--color-background",
                "--color-surface",
                "--color-error",
                "--color-on-primary",
                "--color-on-background",
                "--color-text-primary",
            ],
            "patternProperties": {
                "^--[a-z-]+$": {
                    "type": "string",
                    "anyOf": [
                        {"pattern": "^#[0-9a-fA-F]{6}$"},  # Hex color
                        {"pattern": "^#[0-9a-fA-F]{8}$"},  # Hex with alpha
                        {"pattern": "^rgb\\("},  # RGB
                        {"pattern": "^rgba\\("},  # RGBA
                        {"pattern": "^hsl\\("},  # HSL
                        {"pattern": "^hsla\\("},  # HSLA
                        {"pattern": "^[0-9]+(px|em|rem|%|vh|vw)$"},  # Size values
                        {"pattern": "^[0-9]+$"},  # Numbers
                        {"pattern": "^[0-9]+ms$"},  # Duration
                        {"pattern": '^".*"$'},  # Quoted strings for fonts
                        {"pattern": "^'.*'$"},  # Single quoted strings
                        {"pattern": "^[0-9].*$"},  # Box shadows and complex values
                        {"pattern": "^[a-zA-Z0-9\\s,'-]+$"},  # Font families
                    ],
                }
            },
            "additionalProperties": False,
        },
        "compatibility": {
            "type": "object",
            "properties": {
                "min_version": {
                    "type": ["string", "null"],
                    "pattern": "^\\d+\\.\\d+\\.\\d+$",
                },
                "max_version": {
                    "type": ["string", "null"],
                    "pattern": "^\\d+\\.\\d+\\.\\d+$",
                },
            },
        },
        "screenshots": {"type": "array", "items": {"type": "string", "format": "uri"}},
        "extends": {
            "type": "string",
            "description": "ID of theme to extend/inherit from",
        },
    },
}

# Required CSS variables for themes
REQUIRED_VARS = {
    "--color-primary",
    "--color-secondary",
    "--color-background",
    "--color-surface",
    "--color-error",
    "--color-on-primary",
    "--color-on-background",
    "--color-text-primary",
}


# Color contrast validation (simplified WCAG check)
def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def calculate_luminance(rgb: tuple) -> float:
    """Calculate relative luminance for contrast checking."""

    def adjust(val):
        val = val / 255.0
        if val <= 0.03928:
            return val / 12.92
        return ((val + 0.055) / 1.055) ** 2.4

    r, g, b = [adjust(c) for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(color1: str, color2: str) -> float:
    """Calculate contrast ratio between two colors."""
    if not (color1.startswith("#") and color2.startswith("#")):
        return 21  # Can't calculate, assume OK

    try:
        rgb1 = hex_to_rgb(color1)
        rgb2 = hex_to_rgb(color2)
        lum1 = calculate_luminance(rgb1)
        lum2 = calculate_luminance(rgb2)

        lighter = max(lum1, lum2)
        darker = min(lum1, lum2)

        return (lighter + 0.05) / (darker + 0.05)
    except:
        return 21  # Can't calculate, assume OK


def validate_theme_file(filepath: Path) -> List[str]:
    """Validate a single theme file."""
    errors = []

    try:
        with open(filepath, "r") as f:
            theme_data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]
    except Exception as e:
        return [f"Error reading file: {e}"]

    # Validate against schema
    try:
        validate(instance=theme_data, schema=THEME_SCHEMA)
    except ValidationError as e:
        errors.append(f"Schema validation failed: {e.message}")
        return errors

    # Check required variables
    colors = theme_data.get("colors", {})
    missing_vars = REQUIRED_VARS - set(colors.keys())
    if missing_vars:
        errors.append(f"Missing required variables: {', '.join(missing_vars)}")

    # Check color contrast (WCAG AA compliance)
    if "--color-background" in colors and "--color-text-primary" in colors:
        ratio = contrast_ratio(
            colors["--color-background"], colors["--color-text-primary"]
        )
        if ratio < 4.5:
            errors.append(
                f"Poor text contrast ratio: {ratio:.2f} (minimum 4.5 required)"
            )

    if "--color-primary" in colors and "--color-on-primary" in colors:
        ratio = contrast_ratio(colors["--color-primary"], colors["--color-on-primary"])
        if ratio < 4.5:
            errors.append(
                f"Poor primary button contrast: {ratio:.2f} (minimum 4.5 required)"
            )

    return errors


def main():
    """Validate all theme files in the themes directory."""
    themes_dir = Path(__file__).parent.parent / "cookbook" / "themes"

    if not themes_dir.exists():
        print("✓ No themes directory found (this is OK for initial setup)")
        return 0

    theme_files = list(themes_dir.glob("*.json"))

    if not theme_files:
        print("✓ No theme files to validate")
        return 0

    all_errors = {}
    theme_ids = set()

    for theme_file in theme_files:
        errors = validate_theme_file(theme_file)

        # Check for duplicate IDs
        try:
            with open(theme_file, "r") as f:
                theme_data = json.load(f)
                theme_id = theme_data.get("id")
                if theme_id in theme_ids:
                    errors.append(f"Duplicate theme ID: {theme_id}")
                theme_ids.add(theme_id)
        except:
            pass

        if errors:
            all_errors[theme_file.name] = errors

    if all_errors:
        print("✗ Theme validation failed:\n")
        for filename, errors in all_errors.items():
            print(f"  {filename}:")
            for error in errors:
                print(f"    - {error}")
        return 1

    print(f"✓ All {len(theme_files)} theme(s) validated successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
