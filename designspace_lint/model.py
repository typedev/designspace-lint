# Copyright 2024-2026 TypeDev
# Licensed under the Apache License, Version 2.0

"""
The result of a check, and the vocabulary a result is written in.

Everything here is plain data: a consumer reads a `CheckResult` without
importing a UI toolkit, and font-rover wraps it in a GObject of its own for
display. The category and code numbers are a **public contract** -- other
projects key on them -- so a retired check keeps its number and new checks
only ever get new ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


# =============================================================================
# Category constants
# =============================================================================

CATEGORY_FILE = 0
CATEGORY_GEOMETRY = 1
CATEGORY_SOURCES = 2
CATEGORY_INSTANCES = 3
CATEGORY_GLYPHS = 4
CATEGORY_KERNING = 5
CATEGORY_FONTINFO = 6
CATEGORY_RULES = 7
CATEGORY_FEATURES = 8
CATEGORY_GLYPHORDER = 9  # Our custom checks

CATEGORY_NAMES = {
    CATEGORY_FILE: "File",
    CATEGORY_GEOMETRY: "Geometry",
    CATEGORY_SOURCES: "Sources",
    CATEGORY_INSTANCES: "Instances",
    CATEGORY_GLYPHS: "Glyphs",
    CATEGORY_KERNING: "Kerning",
    CATEGORY_FONTINFO: "Font Info",
    CATEGORY_RULES: "Rules",
    CATEGORY_FEATURES: "Features",
    CATEGORY_GLYPHORDER: "GlyphOrder",
}

# Severity levels
SEVERITY_STRUCTURAL = 0  # Blocks designspace usage
SEVERITY_DESIGN = 1  # Design issues (glyphs, kerning, fontinfo)
SEVERITY_INFO = 2  # Informational (rules, features)


# =============================================================================
# Glyph compatibility problem types (for detailed diagnostics)
# =============================================================================


class GlyphProblemType(Enum):
    """Types of glyph compatibility problems."""

    INCOMPATIBLE_GLYPH = auto()  # Different contour/point count
    CURVE_TYPE_MISMATCH = auto()  # curve vs line vs qcurve
    CONTOUR_DIRECTION = auto()  # CW vs CCW
    DIFFERENT_ANCHORS = auto()  # Missing/extra anchors
    START_POINT_MISMATCH = auto()  # Same contour, different start point
    COMPONENT_MISMATCH = auto()  # Different components
    DIFFERENT_UNICODES = auto()  # Different unicode values
    EMPTY_GLYPH = auto()  # Glyph empty in some sources
    MISSING_GLYPH = auto()  # Glyph missing in some sources


# =============================================================================
# CheckResult - internal dataclass for checker output
# =============================================================================


@dataclass
class SourceInfo:
    """Information about a specific source."""

    filename: str
    location: dict = field(default_factory=dict)


@dataclass
class PointDifference:
    """Details about a point-level difference."""

    contour_index: int
    point_index: int
    expected_type: str
    actual_type: str
    coordinates: tuple[float, float] = (0.0, 0.0)


@dataclass
class ContourDifference:
    """Details about a contour-level difference."""

    contour_index: int
    expected_points: int
    actual_points: int
    expected_direction: str | None = None
    actual_direction: str | None = None


@dataclass
class StartPointDifference:
    """Details about start point mismatch."""

    contour_index: int
    majority_start: tuple[float, float] | None
    outlier_start: tuple[float, float] | None
    rotation_offset: int  # How many positions the start is shifted


@dataclass
class AnchorDifference:
    """Details about anchor differences."""

    anchor_name: str
    present_in: list[str] = field(default_factory=list)
    missing_in: list[str] = field(default_factory=list)


@dataclass
class CheckResult:
    """
    Internal result from a checker.

    This is the output format from individual checkers before
    conversion to ProblemItem for display.
    """

    category: int
    code: int
    description: str
    location: str = ""
    glyph_name: str | None = None
    group_name: str | None = None
    details: str = ""
    is_structural: bool = False
    raw_data: dict = field(default_factory=dict)

    # Glyph diagnostics (optional, for detailed reports)
    problem_type: GlyphProblemType | None = None
    majority_sources: list[SourceInfo] = field(default_factory=list)
    outlier_sources: list[SourceInfo] = field(default_factory=list)
    point_differences: list[PointDifference] = field(default_factory=list)
    contour_differences: list[ContourDifference] = field(default_factory=list)
    start_point_differences: list[StartPointDifference] = field(default_factory=list)
    anchor_differences: list[AnchorDifference] = field(default_factory=list)
    suggested_fix: str = ""
