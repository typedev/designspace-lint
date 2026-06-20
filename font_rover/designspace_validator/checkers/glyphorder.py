"""
GlyphOrder checker - validates glyph order consistency across sources.

Category 9: GlyphOrder validation
This is our custom check (not from designspaceProblems library).

Checks:
- 9.0: Extra glyph (in source but not in default glyphOrder)
- 9.1: Missing glyph (in default glyphOrder but not in source)
- 9.2: Naming mismatch (different name for same Unicode)  -- not yet implemented
- 9.3: Position mismatch (same glyph at different index in default vs source)

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from fontTools.designspaceLib.split import splitInterpolable

from ..model import CATEGORY_GLYPHORDER, CheckResult
from .base import BaseChecker

if TYPE_CHECKING:
    from ufo_widgets_gtk4.designspace import FontSource

logger = logging.getLogger(__name__)

# Error codes
GLYPHORDER_EXTRA_GLYPH = 0
GLYPHORDER_MISSING_GLYPH = 1
GLYPHORDER_NAMING_MISMATCH = 2
GLYPHORDER_POSITION_MISMATCH = 3


def _format_source_name(font_source: "FontSource") -> str:
    """Format source name for display."""
    if font_source is None:
        return "unknown"

    name = font_source.path.name if font_source.path else "unknown"

    style = getattr(font_source, "style_name", None)
    if style:
        name = f"{name} ({style})"
    elif hasattr(font_source, "get_location_label"):
        location = font_source.get_location_label()
        if location and location != getattr(font_source, "name", ""):
            name = f"{name} ({location})"

    return name


class GlyphOrderChecker(BaseChecker):
    """
    Validates glyph order consistency across sources.

    Uses splitInterpolable to properly handle discrete axes,
    checking only within each interpolable sub-space.
    """

    CATEGORY = CATEGORY_GLYPHORDER

    def check(self) -> Iterator[CheckResult]:
        """Run all glyph order checks."""
        entry = self.entry
        if entry is None:
            logger.debug("GlyphOrderChecker requires DesignSpaceEntry with loaded fonts")
            return

        try:
            from ufo_widgets_gtk4.designspace import GlyphOrderManager

            manager = GlyphOrderManager(entry)
        except Exception as e:
            logger.warning(f"Failed to create GlyphOrderManager: {e}")
            return

        # Build path -> FontSource lookup
        path_to_source: dict[str, tuple[int, "FontSource"]] = {}
        for idx, source in enumerate(entry.sources):
            path_to_source[str(source.path)] = (idx, source)
            path_to_source[source.path.name] = (idx, source)

        # Use splitInterpolable to get proper sub-documents per discrete location
        for discrete_loc, sub_doc in splitInterpolable(entry.doc):
            discrete_label = self._format_discrete_location(discrete_loc) if discrete_loc else ""

            # Get default source for this sub-doc
            default_source_desc = sub_doc.findDefault()
            if default_source_desc is None:
                continue

            # --- Check 9.0: Extra glyphs ---
            yield from self._check_extra_glyphs(
                manager, sub_doc, path_to_source, discrete_loc, discrete_label
            )

            # --- Check 9.1: Missing glyphs ---
            yield from self._check_missing_glyphs(
                manager,
                sub_doc,
                path_to_source,
                default_source_desc,
                discrete_loc,
                discrete_label,
            )

            # --- Check 9.3: Position mismatch ---
            yield from self._check_position_consistency(
                sub_doc,
                path_to_source,
                default_source_desc,
                discrete_loc,
                discrete_label,
            )

    def _check_extra_glyphs(
        self,
        manager,
        sub_doc,
        path_to_source: dict,
        discrete_loc: dict | None,
        discrete_label: str,
    ) -> Iterator[CheckResult]:
        """Check for glyphs in sources but not in default glyphOrder."""
        extras = manager.get_extras(discrete_loc)

        for glyph_name in extras:
            # Find which sources contain this extra glyph
            sources_with_glyph = []
            for source_desc in sub_doc.sources:
                if source_desc.path is None:
                    continue
                lookup = path_to_source.get(source_desc.path) or path_to_source.get(
                    Path(source_desc.path).name
                )
                if lookup is None:
                    continue
                idx, font_source = lookup
                if manager.exists_in_source(glyph_name, idx):
                    source_name = _format_source_name(font_source)
                    sources_with_glyph.append(source_name)

            location = ", ".join(sources_with_glyph[:3])
            if len(sources_with_glyph) > 3:
                location += f" (+{len(sources_with_glyph) - 3} more)"
            if discrete_label:
                location = f"{location} [{discrete_label}]"

            yield self._make_result(
                code=GLYPHORDER_EXTRA_GLYPH,
                description=f"Extra glyph '{glyph_name}' not in default glyphOrder",
                location=location,
                glyph_name=glyph_name,
                details=f"Found in {len(sources_with_glyph)} source(s)",
                is_structural=False,
                raw_data={
                    "glyphName": glyph_name,
                    "sources": sources_with_glyph,
                    "discreteLocation": discrete_loc,
                },
            )

        logger.info(
            f"GlyphOrder check: found {len(extras)} extra glyphs"
            + (f" [{discrete_label}]" if discrete_label else "")
        )

    def _check_missing_glyphs(
        self,
        manager,
        sub_doc,
        path_to_source: dict,
        default_source_desc,
        discrete_loc: dict | None,
        discrete_label: str,
    ) -> Iterator[CheckResult]:
        """Check for glyphs in default glyphOrder but missing from sources."""
        default_order_set = set(manager.get_default_order(discrete_loc))
        missing_count = 0

        for source_desc in sub_doc.sources:
            # Skip the default source
            if source_desc == default_source_desc:
                continue

            if source_desc.path is None:
                continue

            # Sparse masters carry only a small set of correction glyphs and
            # are expected to be incomplete; missing-glyph reports for them
            # are pure noise.
            if self._is_sparse_source(source_desc):
                continue

            # Find matching FontSource
            lookup = path_to_source.get(source_desc.path) or path_to_source.get(
                Path(source_desc.path).name
            )
            if lookup is None:
                continue

            idx, font_source = lookup
            source_name = _format_source_name(font_source)
            source_glyphs = set(font_source.font.keys())

            # Find glyphs in default order that are missing from this source
            missing_glyphs = default_order_set - source_glyphs

            for glyph_name in missing_glyphs:
                location = source_name
                if discrete_label:
                    location = f"{location} [{discrete_label}]"

                yield self._make_result(
                    code=GLYPHORDER_MISSING_GLYPH,
                    description=f"Glyph '{glyph_name}' missing from source",
                    location=location,
                    glyph_name=glyph_name,
                    details=f"In default glyphOrder but not in {source_name}",
                    is_structural=False,
                    raw_data={
                        "glyphName": glyph_name,
                        "sourceIndex": idx,
                        "sourceName": source_name,
                        "discreteLocation": discrete_loc,
                    },
                )
                missing_count += 1

        logger.info(
            f"GlyphOrder check: found {missing_count} missing glyphs"
            + (f" [{discrete_label}]" if discrete_label else "")
        )

    def _check_position_consistency(
        self,
        sub_doc,
        path_to_source: dict,
        default_source_desc,
        discrete_loc: dict | None,
        discrete_label: str,
    ) -> Iterator[CheckResult]:
        """Detect glyphOrder position mismatches between default and other sources.

        Compares each non-default source's glyphOrder against the default's.
        Both lists are filtered to their common glyph names (intersection of
        the two glyphOrders, including template entries on both sides) and
        compared positionally. The first mismatching name is reported per
        source — subsequent mismatches typically cascade from the first one
        and would just spam the list.
        """
        # Find default font
        default_lookup = path_to_source.get(default_source_desc.path) or path_to_source.get(
            Path(default_source_desc.path).name
        )
        if default_lookup is None:
            return

        default_idx, default_font_source = default_lookup
        default_order = list(default_font_source.font.glyphOrder or [])
        if not default_order:
            return

        mismatch_count = 0

        for source_desc in sub_doc.sources:
            if source_desc == default_source_desc:
                continue
            if source_desc.path is None:
                continue
            # Sparse masters are not expected to share full structure with
            # the default; their glyphOrder differing is normal.
            if self._is_sparse_source(source_desc):
                continue

            lookup = path_to_source.get(source_desc.path) or path_to_source.get(
                Path(source_desc.path).name
            )
            if lookup is None:
                continue

            source_idx, font_source = lookup
            source_order = list(font_source.font.glyphOrder or [])
            if not source_order:
                continue

            # Intersection — names that exist in both glyphOrders. Position
            # comparison is only meaningful between names both sides know.
            common = set(default_order) & set(source_order)
            if not common:
                continue

            expected = [n for n in default_order if n in common]
            actual = [n for n in source_order if n in common]
            if expected == actual:
                continue

            # Find first mismatch — most informative, single per source.
            first_mismatch_index = None
            for i in range(min(len(expected), len(actual))):
                if expected[i] != actual[i]:
                    first_mismatch_index = i
                    break
            if first_mismatch_index is None:
                # Shouldn't happen — lists are non-equal but every leading
                # element matches. Be defensive and skip.
                continue

            first_glyph = expected[first_mismatch_index]
            default_pos = default_order.index(first_glyph)
            source_pos = source_order.index(first_glyph)

            source_name = _format_source_name(font_source)
            location = source_name
            if discrete_label:
                location = f"{location} [{discrete_label}]"

            default_filename = Path(default_source_desc.path).name
            source_filename = Path(source_desc.path).name

            yield self._make_result(
                code=GLYPHORDER_POSITION_MISMATCH,
                description=f"glyphOrder differs from default: '{first_glyph}'",
                location=location,
                glyph_name=first_glyph,
                details=(
                    f"In {default_filename}: position {default_pos}; "
                    f"in {source_filename}: position {source_pos}"
                ),
                is_structural=False,
                raw_data={
                    "glyphName": first_glyph,
                    "defaultPosition": default_pos,
                    "sourcePosition": source_pos,
                    "sourceIndex": source_idx,
                    "sourceName": source_name,
                    "sourcePath": str(source_desc.path),
                    "defaultSourceIndex": default_idx,
                    "defaultSourcePath": str(default_source_desc.path),
                    "discreteLocation": discrete_loc,
                },
            )
            mismatch_count += 1

        logger.info(
            f"GlyphOrder check: found {mismatch_count} position mismatches"
            + (f" [{discrete_label}]" if discrete_label else "")
        )
