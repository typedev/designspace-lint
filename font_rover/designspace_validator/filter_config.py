"""
Filter configuration for DesignSpace validator.

Defines filter groups (subcategories) for each problem category,
and FilterState class for tracking enabled/disabled filters.

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .model import (
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
)

if TYPE_CHECKING:
    from .model import ProblemItem


# =============================================================================
# Filter Groups Definition
# =============================================================================
# Each category has a list of (group_id, display_name, error_codes, tooltip)
# error_codes=None means all codes in that category

FILTER_GROUPS: dict[int, list[tuple[str, str, list[int] | None, str]]] = {
    # Category 0: File
    CATEGORY_FILE: [
        ("file_validity", "File Validity", [0], "Check if designspace file is readable"),
    ],
    # Category 1: Geometry
    CATEGORY_GEOMETRY: [
        (
            "axes",
            "Axis Definitions",
            [0, 1, 2, 13, 14],
            "No axes, min=max, default out of range, duplicate names/tags",
        ),
        (
            "mapping",
            "Axis Mapping",
            [3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
            "Axis mapping validation (input/output ranges, ordering)",
        ),
    ],
    # Category 2: Sources
    CATEGORY_SOURCES: [
        (
            "files",
            "Source Files",
            [0, 1, 2],
            "No sources, file not found, invalid UFO",
        ),
        (
            "locations",
            "Source Locations",
            [3, 4, 6],
            "Missing axis value, out of range, duplicates",
        ),
        ("layers", "Layers", [7], "Layer not found in source"),
        (
            "default",
            "Default Source",
            [5, 8, 9],
            "No default source, no font attribute, location mismatch",
        ),
    ],
    # Category 3: Instances
    CATEGORY_INSTANCES: [
        (
            "locations",
            "Instance Locations",
            [1, 2, 3, 4, 5],
            "Missing location, undefined axis, out of bounds, extrapolation, duplicates",
        ),
        (
            "naming",
            "Instance Naming",
            [6, 7, 8, 10],
            "Missing family/style name, filename, no instances defined",
        ),
    ],
    # Category 4: Glyphs - Most granular control
    CATEGORY_GLYPHS: [
        (
            "contours",
            "Contours",
            [0, 3, 4, 5, 9],
            "Different contour count, on/off-curve points, curve types, incompatible",
        ),
        ("direction", "Direction", [8], "Wrong contour direction (CW vs CCW)"),
        ("components", "Components", [1], "Different components in glyph"),
        ("anchors", "Anchors", [2], "Different anchors across sources"),
        ("unicodes", "Unicodes", [10], "Different unicode values"),
        ("empty", "Empty/Missing", [7, 12], "Glyph missing in default, or empty in one source"),
        ("coverage", "Axis Coverage", [11], "Glyph does not reach one end of an axis"),
    ],
    # Category 5: Kerning
    CATEGORY_KERNING: [
        ("data", "Kerning Data", [0, 1], "No kerning in source/default"),
        (
            "groups",
            "Kerning Groups",
            [2, 3, 5, 6, 7, 8],
            "Group differences, missing groups, sort order, a glyph in two groups",
        ),
    ],
    # Category 6: Font Info
    CATEGORY_FONTINFO: [
        ("all", "Font Info", None, "All font info consistency checks"),
    ],
    # Category 7: Rules
    CATEGORY_RULES: [
        ("all", "Rules", None, "All designspace rules validation"),
    ],
    # Category 8: Features
    CATEGORY_FEATURES: [
        ("all", "Features", None, "Feature file parsing and consistency"),
    ],
    # Category 9: GlyphOrder
    CATEGORY_GLYPHORDER: [
        ("extra", "Extra Glyphs", [0], "Glyphs in source but not in default glyphOrder"),
        ("naming", "Naming Mismatch", [2], "Different name for same Unicode"),
        ("position", "Glyph Order", [3], "Glyphs not in the default's order (breaks the merge)"),
    ],
}


def get_category_groups(category: int) -> list[tuple[str, str, list[int] | None, str]]:
    """Get filter groups for a category."""
    return FILTER_GROUPS.get(category, [])


def get_all_categories() -> list[int]:
    """Get all category IDs in display order."""
    return [
        CATEGORY_FILE,
        CATEGORY_GEOMETRY,
        CATEGORY_SOURCES,
        CATEGORY_INSTANCES,
        CATEGORY_GLYPHS,
        CATEGORY_KERNING,
        CATEGORY_FONTINFO,
        CATEGORY_RULES,
        CATEGORY_FEATURES,
        CATEGORY_GLYPHORDER,
    ]


# =============================================================================
# FilterState - tracks enabled/disabled filters
# =============================================================================


@dataclass
class FilterState:
    """
    Tracks which filters are enabled/disabled.

    Structure: {category: {group_id: enabled}}
    By default, all filters are enabled.
    """

    # {category_id: {group_id: bool}}
    _state: dict[int, dict[str, bool]] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize with all filters enabled."""
        if not self._state:
            self._state = self._get_default_state()

    @staticmethod
    def _get_default_state() -> dict[int, dict[str, bool]]:
        """Create default state with all filters enabled."""
        state = {}
        for category, groups in FILTER_GROUPS.items():
            state[category] = {}
            for group_id, _, _, _ in groups:
                state[category][group_id] = True
        return state

    def is_enabled(self, category: int, group_id: str) -> bool:
        """Check if a specific filter group is enabled."""
        if category not in self._state:
            return True
        return self._state[category].get(group_id, True)

    def set_enabled(self, category: int, group_id: str, enabled: bool) -> None:
        """Set enabled state for a specific filter group."""
        if category not in self._state:
            self._state[category] = {}
        self._state[category][group_id] = enabled

    def is_category_enabled(self, category: int) -> bool:
        """Check if entire category is enabled (all groups enabled)."""
        if category not in self._state:
            return True
        return all(self._state[category].values())

    def is_category_partially_enabled(self, category: int) -> bool:
        """Check if category is partially enabled (some but not all groups)."""
        if category not in self._state:
            return False
        values = list(self._state[category].values())
        return any(values) and not all(values)

    def set_category_enabled(self, category: int, enabled: bool) -> None:
        """Enable or disable all groups in a category."""
        if category not in self._state:
            self._state[category] = {}
        for group_id, _, _, _ in FILTER_GROUPS.get(category, []):
            self._state[category][group_id] = enabled

    def get_disabled_count(self) -> int:
        """Count total number of disabled filter groups."""
        count = 0
        for category_state in self._state.values():
            for enabled in category_state.values():
                if not enabled:
                    count += 1
        return count

    def has_any_disabled(self) -> bool:
        """Check if any filters are disabled."""
        return self.get_disabled_count() > 0

    def reset_to_defaults(self) -> None:
        """Reset all filters to enabled."""
        self._state = self._get_default_state()

    # --- Serialization for Settings ---

    def to_dict(self) -> dict:
        """Convert to dict for settings storage."""
        return {str(cat): groups for cat, groups in self._state.items()}

    @classmethod
    def from_dict(cls, data: dict) -> "FilterState":
        """Create from dict loaded from settings."""
        state = cls()
        for cat_str, groups in data.items():
            try:
                category = int(cat_str)
                if category in FILTER_GROUPS:
                    for group_id, enabled in groups.items():
                        if isinstance(enabled, bool):
                            state.set_enabled(category, group_id, enabled)
            except (ValueError, TypeError):
                continue
        return state


# =============================================================================
# Filter matching functions
# =============================================================================


def get_group_for_code(category: int, code: int) -> str | None:
    """
    Find which group a specific error code belongs to.

    Returns group_id or None if not found.
    """
    groups = FILTER_GROUPS.get(category, [])
    for group_id, _, codes, _ in groups:
        if codes is None:
            # None means all codes in category
            return group_id
        if code in codes:
            return group_id
    return None


def get_group_name_for_code(category: int, code: int) -> str:
    """
    Get display name of the group a specific error code belongs to.

    Returns group display name or empty string if not found.
    """
    groups = FILTER_GROUPS.get(category, [])
    for group_id, group_name, codes, _ in groups:
        if codes is None:
            # None means all codes in category
            return group_name
        if code in codes:
            return group_name
    return ""


def get_subcategory_for_item(item: "ProblemItem") -> str:
    """
    Get subcategory display name for a ProblemItem.

    Args:
        item: ProblemItem to check

    Returns:
        Subcategory display name or empty string
    """
    return get_group_name_for_code(item.category, item.error_code)


def is_problem_visible(item: "ProblemItem", state: FilterState) -> bool:
    """
    Check if a problem item should be visible given filter state.

    Args:
        item: ProblemItem to check
        state: Current FilterState

    Returns:
        True if item should be shown, False if filtered out
    """
    category = item.category
    code = item.error_code

    group_id = get_group_for_code(category, code)
    if group_id is None:
        # Unknown code - show by default
        return True

    return state.is_enabled(category, group_id)


def get_visible_count(items: list["ProblemItem"], state: FilterState) -> int:
    """Count how many items are visible with given filter state."""
    return sum(1 for item in items if is_problem_visible(item, state))


def get_category_name(category: int) -> str:
    """Get display name for category."""
    return CATEGORY_NAMES.get(category, f"Category {category}")
