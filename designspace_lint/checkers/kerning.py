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

from ..kerning_data import safe_kerning
from ..model import CATEGORY_KERNING, SEVERITY_INFO, CheckResult
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
KERNING_KEY_MALFORMED = 9  # 5,9 - ours: a key a UFO reader refuses


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

        # Read every master's kerning once, going around fontParts when it
        # refuses a file outright -- a malformed key is a finding, not a
        # reason to lose the whole category.
        pairs_by_source = {}
        for source in sources:
            pairs, malformed = safe_kerning(source.font)
            pairs_by_source[id(source)] = pairs
            if malformed:
                yield self._malformed_key_result(source, malformed)

        if not any(pairs_by_source.values()):
            return  # no kerning anywhere: assume that is intentional

        # Find default source
        default_source = self._default_font_source(sources=sources)
        if default_source is None:
            default_source = sources[0]

        default_font = default_source.font
        default_name = self._label(default_source)
        default_pairs = pairs_by_source.get(id(default_source), {})

        yield from self._check_group_overlaps(sources)

        # 5,1: No kerning in default
        if not default_pairs:
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
            source_name = self._label(source)

            source_groups = {
                name: list(members)
                for name, members in source_font.groups.items()
                if name.startswith("public.kern")
            }
            source_pairs = pairs_by_source.get(id(source), {})

            # 5,0: no kerning at all in a full UFO master, while the default
            # has some. ufo2ft asks THIS master for every pair the designspace
            # kerns, finds nothing and uses 0, so the kerning of the whole
            # family sags toward zero around this master's location -- in the
            # built font, silently. Measured on a two-master test: with -50 in
            # the default and nothing here, the midpoint gets -25 and this
            # master 0. Carrying the groups without the pairs does not help;
            # the value lookup goes to this master's own kerning either way.
            # A master meant to correct outlines only belongs in a layer of a
            # full UFO, which ufo2ft skips for kerning.
            if not source_pairs and default_pairs:
                yield self._make_result(
                    code=NO_KERNING_IN_SOURCE,
                    description="no kerning: the family's kerning sags to 0 here",
                    location=source_name,
                    is_structural=True,
                    details=(
                        f"{source_name} has no kerning pairs"
                        + ("" if source_groups else " and no kerning groups")
                        + f", while the default has {len(default_pairs)} pairs. "
                        f"Every pair resolves to 0 at this master and interpolates toward zero "
                        f"around it. Give it the kerning, or make it a layer of a full UFO -- "
                        f"ufo2ft skips layer sources for kerning."
                    ),
                    raw_data={"font": source_name, "hasGroups": bool(source_groups)},
                )
                continue

            # 5,6: groups missing but pairs present -- the class pairs among
            # them cannot resolve, so those specific pairs go to 0.
            if len(source_groups) == 0:
                if default_groups:
                    yield self._make_result(
                        code=NO_KERNING_GROUPS_SOURCE,
                        description="no kerning groups: class kerning becomes 0 here",
                        location=source_name,
                        is_structural=True,
                        details=(
                            f"{source_name} defines no public.kern1/kern2 groups while the "
                            f"default has {len(default_groups)}. Its flat pairs still apply, "
                            f"but every class pair resolves to 0 at this master."
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
                            # ufo2ft sorts a group's members before using them
                            # (`tuple(sorted(members))`), so the order never
                            # reaches the build. Worth knowing when reading a
                            # diff of groups.plist; not worth an alarm.
                            yield self._make_result(
                                code=KERNING_GROUP_SORTED_DIFF,
                                severity=SEVERITY_INFO,
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

    def _malformed_key_result(self, source, malformed) -> CheckResult:
        """5,9: a kerning key no UFO reader will accept.

        An empty glyph or group name on either side of a pair. fontParts
        refuses the whole kerning object rather than the one pair, so until
        this is repaired the master's kerning does not reach the compiler at
        all -- and nothing says so.
        """
        shown = ", ".join(repr(k) for k in malformed[:3])
        more = len(malformed) - min(3, len(malformed))
        return self._make_result(
            code=KERNING_KEY_MALFORMED,
            description=f"{len(malformed)} malformed kerning key(s): the file will not load",
            location=self._label(source),
            is_structural=True,
            details=(
                f"{shown}" + (f" (+{more} more)" if more else "") + ". A kerning key with an "
                "empty side makes fontParts refuse the whole kerning object, so this master's "
                "kerning is lost on the way to the compiler. The pairs that can be read were "
                "still checked."
            ),
            raw_data={"font": self._label(source), "keys": [list(k) for k in malformed[:20]]},
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
            source_name = self._label(source)
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
