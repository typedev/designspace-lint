"""
DesignSpace Validator - unified validation for DesignSpace documents.

Combines structural checks, glyph compatibility analysis, and
design quality validation into a single module.

Categories:
    0: File - basic file validation
    1: Geometry - axis definitions, mappings
    2: Sources - source file validation
    3: Instances - instance definitions
    4: Glyphs - glyph compatibility
    5: Kerning - kerning consistency
    6: Font Info - font info consistency
    7: Rules - rule definitions
    8: Features - feature files
    9: GlyphOrder - glyph order consistency

Example:
    from font_rover.designspace_validator import ValidatorRegistry

    # Async (for UI)
    registry = ValidatorRegistry(designspace_entry=entry)
    registry.check_async(
        on_phase=lambda name, cur, total: print(f"{name} ({cur}/{total})"),
        on_complete=lambda items: print(f"Found {len(items)} problems"),
    )

    # Sync (blocking)
    items = registry.check_sync()
    for item in items:
        print(f"{item.category_name}: {item.description}")

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from .filter_config import (
    FILTER_GROUPS,
    FilterState,
    get_category_name,
    get_group_name_for_code,
    get_subcategory_for_item,
    get_visible_count,
    is_problem_visible,
)
from .model import (
    # Category constants
    CATEGORY_FEATURES,
    CATEGORY_FILE,
    CATEGORY_FONTINFO,
    CATEGORY_GEOMETRY,
    CATEGORY_GLYPHORDER,
    CATEGORY_GLYPHS,
    CATEGORY_INSTANCES,
    CATEGORY_KERNING,
    CATEGORY_NAMES,
    CATEGORY_RULES,
    CATEGORY_SOURCES,
    # Severity constants
    SEVERITY_DESIGN,
    SEVERITY_INFO,
    SEVERITY_STRUCTURAL,
    # Data classes
    AnchorDifference,
    CheckResult,
    ContourDifference,
    GlyphProblemType,
    PointDifference,
    # GObject wrapper
    ProblemItem,
    SourceInfo,
    StartPointDifference,
)
from .registry import PHASES, ValidatorRegistry

# Lazy load window to avoid GTK import at module load time
_window_class = None


def __getattr__(name: str):
    """Lazy load ProblemsWindow."""
    global _window_class

    if name == "ProblemsWindow":
        if _window_class is None:
            from .window import ProblemsWindow

            _window_class = ProblemsWindow
        return _window_class

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Category constants
    "CATEGORY_FILE",
    "CATEGORY_GEOMETRY",
    "CATEGORY_SOURCES",
    "CATEGORY_INSTANCES",
    "CATEGORY_GLYPHS",
    "CATEGORY_KERNING",
    "CATEGORY_FONTINFO",
    "CATEGORY_RULES",
    "CATEGORY_FEATURES",
    "CATEGORY_GLYPHORDER",
    "CATEGORY_NAMES",
    # Severity constants
    "SEVERITY_STRUCTURAL",
    "SEVERITY_DESIGN",
    "SEVERITY_INFO",
    # Phase list
    "PHASES",
    # Filter config
    "FILTER_GROUPS",
    "FilterState",
    "is_problem_visible",
    "get_visible_count",
    "get_category_name",
    "get_group_name_for_code",
    "get_subcategory_for_item",
    # Data classes
    "CheckResult",
    "SourceInfo",
    "PointDifference",
    "ContourDifference",
    "StartPointDifference",
    "AnchorDifference",
    "GlyphProblemType",
    # GObject wrapper
    "ProblemItem",
    # Registry
    "ValidatorRegistry",
    # Window (lazy loaded)
    "ProblemsWindow",
]
