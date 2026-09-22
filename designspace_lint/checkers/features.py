"""
Features checker - validates OpenType feature definitions.

Category 8: Features validation
Based on designspaceProblems checkFeatures().

Checks:
- 8.0: Source features file corrupt (parse error)
- 8.1: Source is missing feature (kern/mark/mkmk inconsistency)

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import io
import logging
import os
from typing import Iterator

from ..model import CATEGORY_FEATURES, CheckResult
from .base import BaseChecker

logger = logging.getLogger(__name__)

# Error codes (0-1 match designspaceProblems exactly)
FEATURE_FILE_CORRUPT = 0  # 8,0 - parse error
FEATURE_MISSING = 1  # 8,1 - feature in some sources but not all
# 8,2 was FEATURE_IN_SPARSE, a check that rested on "sparse" appearing in a
# master's name. Retired, not renumbered: the codes are a public contract.
FEATURES_DIFFER_FROM_DEFAULT = 3  # 8,3 - ufo2ft drops to per-master compilation

# Features to check for consistency
COUNTED_FEATURES = ["kern", "mark", "mkmk"]


class FeaturesChecker(BaseChecker):
    """
    Validates OpenType feature definitions.

    Matches designspaceProblems checkFeatures() behavior:
    - Parses each source's features
    - Reports parse errors as 8,0 (one per source)
    - Counts kern/mark/mkmk features and reports if inconsistent (8,1)
    """

    CATEGORY = CATEGORY_FEATURES

    def check(self) -> Iterator[CheckResult]:
        """Run all features validation checks."""
        entry = self.entry
        if entry is None:
            logger.debug("FeaturesChecker requires DesignSpaceEntry with loaded fonts")
            return

        if not entry.sources:
            return

        # Try to import feaLib
        try:
            from fontTools.feaLib.parser import Parser
            from fontTools.feaLib import ast as featureElements
        except ImportError:
            logger.debug("fontTools.feaLib not available, skipping features check")
            return

        yield from self._check_variable_feature_compat()

        # Count features across sources
        feature_counts = {tag: 0 for tag in COUNTED_FEATURES}
        source_count = 0

        for source in self._ufo_sources():
            font = source.font
            source_name = self._label(source)

            # Get features text
            features = getattr(font, "features", None)
            if features is None:
                continue

            fea_text = getattr(features, "text", None)
            if not fea_text:
                continue

            source_count += 1

            # Parse features
            try:
                fea_data = io.StringIO(fea_text)
                glyph_names = set(font.keys())
                include_dir = os.path.dirname(str(source.path))

                parser = Parser(
                    fea_data,
                    glyphNames=glyph_names,
                    followIncludes=True,
                    includeDir=include_dir,
                )
                fea_file = parser.parse()

                # Count features
                for element in fea_file.statements:
                    if isinstance(element, featureElements.FeatureBlock):
                        if element.name in feature_counts:
                            feature_counts[element.name] += 1

            except Exception as e:
                # 8,0: Parse error (one per source, not per error)
                yield self._make_result(
                    code=FEATURE_FILE_CORRUPT,
                    description="source features file corrupt",
                    location=source_name,
                    details=str(e),
                    is_structural=False,
                    raw_data={"error": str(e)},
                )

        # 8,1: Check feature consistency
        if source_count > 0:
            for tag, count in feature_counts.items():
                if count == 0:
                    # None of the sources have this feature - OK
                    continue
                elif count == source_count:
                    # All sources have this feature - OK
                    continue
                else:
                    # Feature in some sources but not all
                    yield self._make_result(
                        code=FEATURE_MISSING,
                        description=f"source is missing feature: {tag}",
                        location="designspace",
                        is_structural=False,
                        raw_data={"feature": tag, "count": count, "total": source_count},
                    )

    def _ufo_sources(self) -> list:
        """One source per UFO: layers share their parent's features.fea."""
        seen: set = set()
        sources = []
        for source in self.entry.sources:
            if self._is_layer_source(source):
                continue
            key = self._resolve_path(source.path)
            if key in seen:
                continue
            seen.add(key)
            sources.append(source)
        return sources

    def _check_variable_feature_compat(self) -> Iterator[CheckResult]:
        """8,3: features that force ufo2ft off the variable-feature path.

        ufo2ft compiles one variable GPOS from the default master's
        ``features.fea`` -- but only when every other master's file tokenizes
        the same as the default's, **or** every other master's file is empty
        (`featureCompiler._featuresCompatible`). A mix of the two is not
        compatible either.

        Falling off that path is silent: ufo2ft then compiles features in each
        master and varLib merges the results, where a master whose glyphs are
        not in the default's order raises ``InconsistentGlyphOrder`` and a
        master with a different set of lookups raises ``ShouldBeConstant``.
        The report has to name that, because by the time fontmake fails the
        error points somewhere else entirely.
        """
        try:
            from ufo2ft.featureCompiler import tokenizeLayoutFeatures
        except Exception:
            logger.debug("ufo2ft not available, skipping variable-feature compatibility check")
            return

        sources = self._ufo_sources()
        if len(sources) < 2:
            return

        default_source = self._default_font_source(sources=sources)
        others = [s for s in sources if s is not default_source]
        if default_source is None or not others:
            return

        def tokens(source):
            try:
                return tokenizeLayoutFeatures(source.font, os.path.dirname(str(source.path)))
            except Exception as exc:  # a parse error is reported as 8,0
                logger.debug(f"tokenizing features failed for {source.path}: {exc}")
                return None

        default_tokens = tokens(default_source)
        if default_tokens is None:
            return

        other_tokens = {id(s): tokens(s) for s in others}
        if any(t is None for t in other_tokens.values()):
            return

        all_same = all(other_tokens[id(s)] == default_tokens for s in others)
        all_empty = all(not other_tokens[id(s)] for s in others)
        if all_same or all_empty:
            return

        # One result for the designspace, not one per master: the masters are
        # not individually wrong, their *combination* is what decides how the
        # build compiles features. Eighty-three rows saying the same sentence
        # would bury every other problem in the list.
        default_name = self._label(default_source)
        matching = [s for s in others if other_tokens[id(s)] == default_tokens]
        empty = [s for s in others if not other_tokens[id(s)]]
        differing = [s for s in others if s not in matching and s not in empty]

        parts = []
        if matching:
            parts.append(f"{len(matching)} match the default")
        if empty:
            parts.append(f"{len(empty)} are empty")
        if differing:
            parts.append(f"{len(differing)} differ")

        def names(sources):
            labels = [self._label(s) for s in sources[:3]]
            more = len(sources) - len(labels)
            return ", ".join(labels) + (f" (+{more} more)" if more > 0 else "")

        detail_lines = [
            f"ufo2ft builds one variable feature file from {default_name} only when every "
            f"other master's features.fea matches it or all of them are empty. Here "
            f"{' and '.join(parts)}, so features are compiled per master instead and varLib "
            f"must merge them -- which fails on a differing glyph order "
            f"(InconsistentGlyphOrder) or a differing set of lookups (ShouldBeConstant)."
        ]
        if empty:
            detail_lines.append(f"Empty: {names(empty)}")
        if differing:
            detail_lines.append(f"Different: {names(differing)}")

        yield self._make_result(
            code=FEATURES_DIFFER_FROM_DEFAULT,
            description=f"features.fea is mixed across masters: {', '.join(parts)}",
            location="designspace",
            is_structural=True,
            details="\n".join(detail_lines),
            raw_data={
                "default": default_name,
                "matching": [self._label(s) for s in matching],
                "empty": [self._label(s) for s in empty],
                "differing": [self._label(s) for s in differing],
            },
        )
