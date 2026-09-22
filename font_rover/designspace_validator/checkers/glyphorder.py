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

from ...utils.glyph_order import safe_glyph_order
from ..model import CATEGORY_GLYPHORDER, CheckResult
from .base import BaseChecker

if TYPE_CHECKING:
    from font_rover.designspace import FontSource

logger = logging.getLogger(__name__)

# Error codes
GLYPHORDER_EXTRA_GLYPH = 0
GLYPHORDER_MISSING_GLYPH = 1
GLYPHORDER_NAMING_MISMATCH = 2
GLYPHORDER_POSITION_MISMATCH = 3


def _format_source_name(font_source: "FontSource") -> str:
    """Format source name for display.

    Delegates to the shared labeller so a layer master is named by its layer
    rather than by the UFO it shares with its siblings.
    """
    if font_source is None:
        return "unknown"
    return BaseChecker._source_label(font_source) or "unknown"


class _SourceLookup:
    """Finds the loaded master a designspace source descriptor stands for.

    Keeps the master's index in the entry, which GlyphOrderManager works in
    terms of.
    """

    def __init__(self, sources):
        self._sources = list(sources)
        self._index = {id(source): idx for idx, source in enumerate(self._sources)}

    def for_descriptor(self, descriptor):
        source = BaseChecker._match_source(descriptor, self._sources)
        if source is None:
            return None
        return self._index[id(source)], source


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
            from font_rover.designspace import GlyphOrderManager

            manager = GlyphOrderManager(entry)
        except Exception as e:
            logger.warning(f"Failed to create GlyphOrderManager: {e}")
            return

        # Descriptor -> (index, FontSource). Keying this by path alone made
        # every layer of a shared UFO answer to the same key; a master is a
        # path *and* a layer.
        path_to_source = _SourceLookup(entry.sources)

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

            # 9.1 (missing glyphs) is deliberately not run here any more: which
            # masters a glyph may skip is a property of the axes, and it is
            # decided in the glyphs checker (4.7 / 4.11). Reporting it twice,
            # once per master, buried the cases that actually break a build.

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
                lookup = path_to_source.for_descriptor(source_desc)
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

    def _check_position_consistency(
        self,
        sub_doc,
        path_to_source: dict,
        default_source_desc,
        discrete_loc: dict | None,
        discrete_label: str,
    ) -> Iterator[CheckResult]:
        """Detect glyphOrder position mismatches between default and other sources.

        This is what fontmake trips over. When the sources' ``features.fea``
        files are not all identical, ufo2ft compiles features per master and
        varLib then merges the master GPOS tables; that merge sorts each
        master's coverage by the *default's* glyph ids and raises
        ``InconsistentGlyphOrder`` when a master's glyphs do not come in the
        default's order.

        Both lists are filtered to their common glyph names first, so a master
        that simply has fewer glyphs is fine -- a subset in the right order is
        what a sparse master looks like. Only the first mismatching name is
        reported per source; the rest cascade from it.
        """
        # Find default font
        default_lookup = path_to_source.for_descriptor(default_source_desc)
        if default_lookup is None:
            return

        default_idx, default_font_source = default_lookup
        default_order = safe_glyph_order(default_font_source.font)
        if not default_order:
            return

        mismatch_count = 0

        for source_desc in sub_doc.sources:
            if source_desc == default_source_desc:
                continue
            if source_desc.path is None:
                continue
            # A layer master has no glyph order of its own: it shares the
            # parent UFO's, which is checked once, through that UFO.
            if getattr(source_desc, "layerName", None):
                continue

            lookup = path_to_source.for_descriptor(source_desc)
            if lookup is None:
                continue

            source_idx, font_source = lookup
            source_order = safe_glyph_order(font_source.font)
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
