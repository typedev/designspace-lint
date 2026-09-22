"""
Font info checker - validates font info consistency across sources.

Category 6: Font Info validation
Based on designspaceProblems checkFontInfo().

Checks:
- 6.0: unitsPerEm differs between sources
- 6.1: Required font info field missing
- 6.2: Font info field differs (non-interpolatable)
- 6.3: Interpolatable field differs unexpectedly

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
from typing import Iterator

from ..model import CATEGORY_FONTINFO, CheckResult
from .base import BaseChecker

logger = logging.getLogger(__name__)

# Error codes
UNITS_PER_EM_DIFFERS = 0
REQUIRED_FIELD_MISSING = 1
FIELD_DIFFERS = 2

# Fields that must be identical across all sources
# versionMinor can legitimately differ between masters
IDENTICAL_FIELDS = [
    "unitsPerEm",
    "versionMajor",
]


class FontInfoChecker(BaseChecker):
    """
    Validates font info consistency across sources.

    These are design checks - they indicate issues that could cause
    problems during interpolation or output generation.
    """

    CATEGORY = CATEGORY_FONTINFO

    def check(self) -> Iterator[CheckResult]:
        """Run all font info validation checks."""
        entry = self.entry
        if entry is None:
            logger.debug("FontInfoChecker requires DesignSpaceEntry with loaded fonts")
            return

        if not entry.sources:
            return

        # Find default source
        default_source = entry.sources[0]  # TODO: Use doc.findDefault()
        default_info = default_source.font.info

        # Check 6.0: unitsPerEm must be set in default
        default_upm = default_info.unitsPerEm
        if default_upm is None:
            yield self._make_result(
                code=REQUIRED_FIELD_MISSING,
                description="Default source missing unitsPerEm",
                location=default_source.path.name,
                is_structural=True,  # This is actually structural
                raw_data={"field": "unitsPerEm"},
            )
            return

        # Check all sources
        for source in entry.sources:
            source_name = source.path.name
            source_info = source.font.info

            # Check unitsPerEm matches
            source_upm = source_info.unitsPerEm
            if source_upm != default_upm:
                yield self._make_result(
                    code=UNITS_PER_EM_DIFFERS,
                    description=(f"unitsPerEm differs: {source_upm} (default: {default_upm})"),
                    location=source_name,
                    is_structural=True,  # Different UPM is structural
                    raw_data={
                        "field": "unitsPerEm",
                        "sourceValue": source_upm,
                        "defaultValue": default_upm,
                    },
                )

            # Check other identical fields
            for field in IDENTICAL_FIELDS:
                if field == "unitsPerEm":
                    continue  # Already checked

                default_val = getattr(default_info, field, None)
                source_val = getattr(source_info, field, None)

                if default_val is not None and source_val != default_val:
                    yield self._make_result(
                        code=FIELD_DIFFERS,
                        description=(f"{field} differs: {source_val!r} (default: {default_val!r})"),
                        location=source_name,
                        is_structural=False,
                        raw_data={
                            "field": field,
                            "sourceValue": source_val,
                            "defaultValue": default_val,
                        },
                    )
