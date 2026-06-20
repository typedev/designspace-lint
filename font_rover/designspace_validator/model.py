"""
Data models for DesignSpace validation.

CheckResult is the internal result format used by checkers.
ProblemItem is the GObject wrapper for display in GTK4 UI.

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from gi.repository import GObject

if TYPE_CHECKING:
    pass


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


# =============================================================================
# ProblemItem - GObject wrapper for GTK4 UI
# =============================================================================


class ProblemItem(GObject.Object):
    """
    GObject wrapper for validation problems.

    Designed for use with Gtk.ColumnView and Gio.ListStore.

    Attributes:
        category: Problem category (0-9)
        error_code: Error code within category
        description: Human-readable problem description
        location: Master name, path, or discrete location
        glyph_name: Affected glyph name (if applicable)
        details: Additional details from problem
        is_structural: True if problem prevents designspace usage
        raw_data: Original problem.data dict for actions
        severity: 0=structural, 1=design, 2=info
    """

    __gtype_name__ = "ProblemItem"

    def __init__(
        self,
        category: int = 0,
        error_code: int = 0,
        description: str = "",
        location: str = "",
        glyph_name: str | None = None,
        group_name: str | None = None,
        details: str = "",
        is_structural: bool = False,
        raw_data: dict | None = None,
    ):
        super().__init__()
        self._category = category
        self._error_code = error_code
        self._description = description
        self._location = location
        self._glyph_name = glyph_name or ""
        self._group_name = group_name or ""
        self._details = details
        self._is_structural = is_structural
        self._raw_data = raw_data or {}

    # --- GObject Properties ---

    @GObject.Property(type=int)
    def category(self) -> int:
        """Problem category (0-9)."""
        return self._category

    @GObject.Property(type=int)
    def error_code(self) -> int:
        """Error code within category."""
        return self._error_code

    @GObject.Property(type=str)
    def description(self) -> str:
        """Human-readable problem description."""
        return self._description

    @GObject.Property(type=str)
    def location(self) -> str:
        """Master name, path, or discrete location."""
        return self._location

    @GObject.Property(type=str)
    def glyph_name(self) -> str:
        """Affected glyph name (empty if not applicable)."""
        return self._glyph_name

    @GObject.Property(type=str)
    def group_name(self) -> str:
        """Affected kerning group name (empty if not applicable)."""
        return self._group_name

    @GObject.Property(type=str)
    def details(self) -> str:
        """Additional details."""
        return self._details

    @GObject.Property(type=bool, default=False)
    def is_structural(self) -> bool:
        """True if problem prevents designspace usage."""
        return self._is_structural

    # --- Computed Properties ---

    @property
    def raw_data(self) -> dict:
        """Original problem.data dict for actions."""
        return self._raw_data

    @property
    def category_name(self) -> str:
        """Human-readable category name."""
        return CATEGORY_NAMES.get(self._category, "Unknown")

    @property
    def severity(self) -> int:
        """Severity level: 0=structural, 1=design, 2=info."""
        if self._is_structural:
            return SEVERITY_STRUCTURAL
        elif self._category in (
            CATEGORY_GLYPHS,
            CATEGORY_KERNING,
            CATEGORY_FONTINFO,
            CATEGORY_GLYPHORDER,
        ):
            return SEVERITY_DESIGN
        else:
            return SEVERITY_INFO

    @property
    def severity_icon(self) -> str:
        """Icon name for severity level."""
        if self.severity == SEVERITY_STRUCTURAL:
            return "dialog-error-symbolic"
        elif self.severity == SEVERITY_DESIGN:
            return "dialog-warning-symbolic"
        else:
            return "dialog-information-symbolic"

    @property
    def has_glyph(self) -> bool:
        """True if problem has associated glyph."""
        return bool(self._glyph_name)

    @property
    def has_group(self) -> bool:
        """True if problem has associated kerning group."""
        return bool(self._group_name)

    @property
    def has_location(self) -> bool:
        """True if problem has location info."""
        return bool(self._location)

    # --- Factory Methods ---

    @classmethod
    def from_check_result(cls, result: CheckResult) -> "ProblemItem":
        """
        Create ProblemItem from CheckResult.

        Args:
            result: CheckResult from a checker

        Returns:
            ProblemItem instance
        """
        return cls(
            category=result.category,
            error_code=result.code,
            description=result.description,
            location=result.location,
            glyph_name=result.glyph_name,
            group_name=result.group_name,
            details=result.details,
            is_structural=result.is_structural,
            raw_data=result.raw_data,
        )

    def __repr__(self) -> str:
        return (
            f"ProblemItem({self.category_name}: {self._description}"
            f"{f', glyph={self._glyph_name}' if self._glyph_name else ''}"
            f"{f', location={self._location}' if self._location else ''})"
        )
