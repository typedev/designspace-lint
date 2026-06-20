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

# Error codes (match designspaceProblems exactly)
FEATURE_FILE_CORRUPT = 0  # 8,0 - parse error
FEATURE_MISSING = 1  # 8,1 - feature in some sources but not all
FEATURE_IN_SPARSE = 2  # 8,2 - sparse master has non-empty features.fea (compile blocker)

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

        # Count features across sources
        feature_counts = {tag: 0 for tag in COUNTED_FEATURES}
        source_count = 0

        for source in entry.sources:
            font = source.font
            source_name = source.path.name

            # Get features text
            features = getattr(font, "features", None)
            if features is None:
                continue

            fea_text = getattr(features, "text", None)
            if not fea_text:
                continue

            # Sparse masters must not carry features — fontmake compiles all
            # features from the default master, and any feature content here
            # will either be silently dropped or cause a compile error.
            if self._is_sparse_source(source) and fea_text.strip():
                yield self._make_result(
                    code=FEATURE_IN_SPARSE,
                    description="sparse master contains features.fea",
                    location=source_name,
                    details=(
                        f"{len(fea_text)} chars of feature code in a sparse "
                        "master — features must live only in full masters"
                    ),
                    is_structural=True,
                    raw_data={"chars": len(fea_text)},
                )
                # Don't count sparse toward feature consistency — they skew
                # the kern/mark/mkmk tallies and trigger false FEATURE_MISSING.
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
