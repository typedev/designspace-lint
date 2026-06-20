"""
Kerning checker - validates kerning consistency across sources.

Category 5: Kerning validation
Based on designspaceProblems checkKerning().

Checks:
- 5.0: No kerning in source (source has no kerning but default does)
- 5.1: No kerning in default
- 5.2: Kerning group members do not match
- 5.3: Kerning group missing from source
- 5.5: No kerning groups in default
- 5.6: No kerning groups in source
- 5.7: Kerning group members sorted differently

Note: designspaceProblems does NOT check individual kerning pairs (5.4).

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
from typing import Iterator

from ..model import CATEGORY_KERNING, CheckResult
from .base import BaseChecker

logger = logging.getLogger(__name__)

# Error codes (match designspaceProblems exactly)
NO_KERNING_IN_SOURCE = 0  # 5,0
NO_KERNING_IN_DEFAULT = 1  # 5,1
KERNING_GROUP_DIFFERS = 2  # 5,2 - members do not match
KERNING_GROUP_MISSING = 3  # 5,3 - group missing from source
# 5,4 - kerning pair missing - NOT IMPLEMENTED in designspaceProblems
NO_KERNING_GROUPS_DEFAULT = 5  # 5,5
NO_KERNING_GROUPS_SOURCE = 6  # 5,6
KERNING_GROUP_SORTED_DIFF = 7  # 5,7 - members sorted differently


class KerningChecker(BaseChecker):
    """
    Validates kerning consistency across sources.

    Matches designspaceProblems checkKerning() behavior exactly.
    Does NOT check individual kerning pairs - only groups.
    """

    CATEGORY = CATEGORY_KERNING

    def check(self) -> Iterator[CheckResult]:
        """Run all kerning validation checks."""
        entry = self.entry
        if entry is None:
            logger.debug("KerningChecker requires DesignSpaceEntry with loaded fonts")
            return

        if not entry.sources:
            return

        # Check if there is ANY kerning in the designspace
        # If no kerning anywhere, assume intentional and skip
        has_any_kerning = False
        for source in entry.sources:
            if len(source.font.kerning.items()) > 0:
                has_any_kerning = True
                break

        if not has_any_kerning:
            return

        # Find default source
        default_source = self._find_default_source()
        if default_source is None:
            default_source = entry.sources[0]

        default_font = default_source.font
        default_name = default_source.path.name

        # 5,1: No kerning in default
        if len(default_font.kerning.items()) == 0:
            yield self._make_result(
                code=NO_KERNING_IN_DEFAULT,
                description="no kerning in default",
                location=default_name,
                is_structural=False,
                raw_data={"font": default_name},
            )

        # 5,5: No kerning groups in default
        default_groups = {
            name: list(members)
            for name, members in default_font.groups.items()
            if name.startswith("public.kern")
        }
        if len(default_groups) == 0:
            yield self._make_result(
                code=NO_KERNING_GROUPS_DEFAULT,
                description="no kerning groups in default",
                location=default_name,
                is_structural=False,
                raw_data={"font": default_name},
            )

        # Check each source against default
        for source in entry.sources:
            if source is default_source:
                continue

            source_font = source.font
            source_name = source.path.name

            # 5,0: No kerning in source
            if len(source_font.kerning.keys()) == 0:
                yield self._make_result(
                    code=NO_KERNING_IN_SOURCE,
                    description="no kerning in source",
                    location=source_name,
                    is_structural=False,
                    raw_data={"font": source_name},
                )

            # 5,6: No kerning groups in source
            source_groups = {
                name: list(members)
                for name, members in source_font.groups.items()
                if name.startswith("public.kern")
            }
            if len(source_groups) == 0:
                yield self._make_result(
                    code=NO_KERNING_GROUPS_SOURCE,
                    description="no kerning groups in source",
                    location=source_name,
                    is_structural=False,
                    raw_data={"font": source_name},
                )
                continue

            # Check each source group against default
            for group_name, source_members in source_groups.items():
                if group_name not in default_groups:
                    # 5,3: Kerning group missing (extra group in source)
                    yield self._make_result(
                        code=KERNING_GROUP_MISSING,
                        description=f"kerning group missing: {group_name}",
                        location=source_name,
                        group_name=group_name,
                        is_structural=False,
                        raw_data={"font": source_name, "groupName": group_name},
                    )
                else:
                    default_members = default_groups[group_name]
                    if source_members != default_members:
                        # Members differ
                        if sorted(source_members) == sorted(default_members):
                            # 5,7: Same members but sorted differently
                            details = f"{group_name}: {source_members}, {default_members}"
                            yield self._make_result(
                                code=KERNING_GROUP_SORTED_DIFF,
                                description=f"kerning group members sorted differently: {group_name}",
                                location=source_name,
                                group_name=group_name,
                                details=details,
                                is_structural=False,
                                raw_data={
                                    "font": source_name,
                                    "groupName": group_name,
                                    "sourceMembers": source_members,
                                    "defaultMembers": default_members,
                                },
                            )
                        else:
                            # 5,2: Members do not match
                            details = f"{group_name}: {source_members}, {default_members}"
                            yield self._make_result(
                                code=KERNING_GROUP_DIFFERS,
                                description=f"kerning group members do not match: {group_name}",
                                location=source_name,
                                group_name=group_name,
                                details=details,
                                is_structural=False,
                                raw_data={
                                    "font": source_name,
                                    "groupName": group_name,
                                    "sourceMembers": source_members,
                                    "defaultMembers": default_members,
                                },
                            )

    def _find_default_source(self):
        """Find default source using designspace document."""
        entry = self.entry
        if entry is None:
            return None

        try:
            default_desc = self.doc.findDefault()
            if default_desc is not None and default_desc.path:
                from pathlib import Path

                default_path = Path(default_desc.path).resolve()
                for source in entry.sources:
                    if source.path.resolve() == default_path:
                        return source
        except Exception:
            pass

        # Fallback: first source or one with copyInfo
        for source in entry.sources:
            if getattr(source, "copyInfo", False):
                return source
        return entry.sources[0] if entry.sources else None
