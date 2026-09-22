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

# Error codes (0-7 match designspaceProblems exactly)
NO_KERNING_IN_SOURCE = 0  # 5,0
NO_KERNING_IN_DEFAULT = 1  # 5,1
KERNING_GROUP_DIFFERS = 2  # 5,2 - members do not match
KERNING_GROUP_MISSING = 3  # 5,3 - group missing from source
# 5,4 - kerning pair missing - NOT IMPLEMENTED in designspaceProblems
NO_KERNING_GROUPS_DEFAULT = 5  # 5,5
NO_KERNING_GROUPS_SOURCE = 6  # 5,6
KERNING_GROUP_SORTED_DIFF = 7  # 5,7 - members sorted differently
GLYPH_IN_TWO_KERN_GROUPS = 8  # 5,8 - ours: a glyph in two groups of one side


class KerningChecker(BaseChecker):
    """
    Validates kerning consistency across sources.

    Groups only; pair sets are deliberately not compared. ufo2ft resolves a
    pair a master does not list through that master's group pair, falling back
    to 0 (`kernFeatureWriter.py`, `ufoLib/kerning.py`), which is exactly what
    "no pair here" means in a UFO. Masters therefore differ in which pairs they
    spell out as a matter of course, and flagging that is noise.

    What is worth reporting is what the build swallows in silence:

    - a full UFO with no kern groups at all, while its siblings have them: its
      class kerning resolves to 0 everywhere, so the master pulls the whole
      designspace's class kerning toward zero. Verified by building: with
      ``kern1.A x kern2.V = -50`` in the default and a group-less master
      carrying only a flat ``A,V = -30``, the built font has ``Agrave,V = 0``
      at that master.
    - a group redefined with different members (ufo2ft keeps the first
      definition it sees and logs a warning nobody reads), and
    - a glyph placed in two groups of the same side, which makes ufo2ft
      discard the second group entirely.

    Layer sources are skipped throughout: ufo2ft ignores their kerning, since
    a layer has none of its own.
    """

    CATEGORY = CATEGORY_KERNING

    def check(self) -> Iterator[CheckResult]:
        """Run all kerning validation checks."""
        entry = self.entry
        if entry is None:
            logger.debug("KerningChecker requires DesignSpaceEntry with loaded fonts")
            return

        # A layer has no kerning of its own; ufo2ft skips layer sources.
        sources = [s for s in entry.sources if not self._is_layer_source(s)]
        if not sources:
            return

        # Check if there is ANY kerning in the designspace
        # If no kerning anywhere, assume intentional and skip
        has_any_kerning = False
        for source in sources:
            if len(source.font.kerning.items()) > 0:
                has_any_kerning = True
                break

        if not has_any_kerning:
            return

        # Find default source
        default_source = self._default_font_source(sources=sources)
        if default_source is None:
            default_source = sources[0]

        default_font = default_source.font
        default_name = self._source_label(default_source)

        yield from self._check_group_overlaps(sources)

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
        for source in sources:
            if source is default_source:
                continue

            source_font = source.font
            source_name = self._source_label(source)

            # 5,0: No kerning in source. Every pair then resolves to 0 at this
            # master, which is a real effect but a legitimate choice, so it is
            # reported for information rather than as a problem.
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
                if default_groups:
                    yield self._make_result(
                        code=NO_KERNING_GROUPS_SOURCE,
                        description="no kerning groups: class kerning becomes 0 here",
                        location=source_name,
                        is_structural=True,
                        details=(
                            f"{source_name} defines no public.kern1/kern2 groups while the "
                            f"default has {len(default_groups)}. ufo2ft looks a class pair up "
                            f"in this master's own kerning, finds nothing and uses 0, so every "
                            f"class pair interpolates toward zero here."
                        ),
                        raw_data={"font": source_name},
                    )
                continue

            # Check each source group against default
            for group_name, source_members in source_groups.items():
                if group_name not in default_groups:
                    # 5,3: a group this source has and the default does not.
                    # Harmless on its own -- ufo2ft unions the groups of every
                    # source -- so this is information, not a problem.
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

    def _check_group_overlaps(self, sources) -> Iterator[CheckResult]:
        """5,8: a glyph in two kerning groups of the same side.

        ufo2ft builds one set of groups out of every source. When a glyph is
        already in a side-1 (or side-2) group and another group of that side
        claims it, the later group is **discarded whole** -- every pair written
        against it stops applying. The UFO looks fine; only a log line marks
        it.
        """
        for source in sources:
            source_name = self._source_label(source)
            for prefix, side in (("public.kern1.", "first"), ("public.kern2.", "second")):
                seen: dict[str, str] = {}
                groups = source.font.groups
                for group_name in sorted(groups.keys()):
                    if not group_name.startswith(prefix):
                        continue
                    for glyph_name in groups[group_name]:
                        if glyph_name in seen:
                            yield self._make_result(
                                code=GLYPH_IN_TWO_KERN_GROUPS,
                                description=(
                                    f"'{glyph_name}' is in two {side}-side groups: "
                                    f"{seen[glyph_name]} and {group_name}"
                                ),
                                location=source_name,
                                glyph_name=glyph_name,
                                group_name=group_name,
                                is_structural=True,
                                details=(
                                    f"ufo2ft keeps '{seen[glyph_name]}' and discards "
                                    f"'{group_name}' entirely, so every kerning pair written "
                                    f"against '{group_name}' stops applying."
                                ),
                                raw_data={
                                    "font": source_name,
                                    "glyphName": glyph_name,
                                    "groupName": group_name,
                                    "otherGroup": seen[glyph_name],
                                    "side": side,
                                },
                            )
                        else:
                            seen[glyph_name] = group_name

    def _find_default_source(self):
        """Find the default source, matched by path and layer."""
        return self._default_font_source()
