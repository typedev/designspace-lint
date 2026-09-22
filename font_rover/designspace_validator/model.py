"""
GTK wrapper around a lint result.

The results themselves, and the category/severity vocabulary they are written
in, live in `designspace_lint.model` -- plain data, no toolkit. This module
adds the one thing a GTK list needs and a library must not have: a
`GObject.Object` with properties, built from a `CheckResult` by
`ProblemItem.from_check_result`.

The names below are re-exported so that everything in font-rover keeps
importing them from here.

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

from gi.repository import GObject

from designspace_lint.model import (
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
    SEVERITY_DESIGN,
    SEVERITY_INFO,
    SEVERITY_STRUCTURAL,
    AnchorDifference,
    CheckResult,
    ContourDifference,
    GlyphProblemType,
    PointDifference,
    SourceInfo,
    StartPointDifference,
)

__all__ = [
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
    "SEVERITY_STRUCTURAL",
    "SEVERITY_DESIGN",
    "SEVERITY_INFO",
    "GlyphProblemType",
    "SourceInfo",
    "PointDifference",
    "ContourDifference",
    "StartPointDifference",
    "AnchorDifference",
    "CheckResult",
    "ProblemItem",
]


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
