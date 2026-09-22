"""
Glyphs checker - validates glyph compatibility across sources.

Category 4: Glyph validation
Based on designspaceProblems checkGlyphs().

Checks (codes match designspaceProblems):
- 4.0: Different number of contours in glyph
- 4.1: Different components in glyph
- 4.2: Different number of anchors in glyph
- 4.3: Different number of on-curve points on contour
- 4.4: Different number of off-curve points on contour
- 4.5: Curve has wrong type
- 4.7: Default glyph is empty (glyph exists in other sources but not default)
- 4.8: Contour has wrong direction
- 4.9: Incompatible constructions for glyph
- 4.10: Different unicodes in glyph

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from fontParts.world import RFont

from fontPens.digestPointPen import DigestPointStructurePen

from ..model import (
    CATEGORY_GLYPHS,
    AnchorDifference,
    CheckResult,
    GlyphProblemType,
)
from .base import BaseChecker

logger = logging.getLogger(__name__)

# Error codes (match designspaceProblems)
DIFFERENT_CONTOUR_COUNT = 0  # different number of contours in glyph
DIFFERENT_COMPONENTS = 1  # different components in glyph
DIFFERENT_ANCHORS = 2  # different number of anchors in glyph
DIFFERENT_ON_CURVES = 3  # different number of on-curve points on contour
DIFFERENT_OFF_CURVES = 4  # different number of off-curve points on contour
WRONG_CURVE_TYPE = 5  # curve has wrong type
DEFAULT_GLYPH_EMPTY = 7  # glyph missing from the default master
WRONG_CONTOUR_DIRECTION = 8  # contour has wrong direction
INCOMPATIBLE_GLYPH = 9  # incompatible constructions for glyph
DIFFERENT_UNICODES = 10  # different unicodes in glyph
# Codes past 10 are ours; designspaceProblems stops at 10. They are a public
# contract now (font-rover and other consumers key on them), so numbers are
# only ever added, never reused.
GLYPH_AXIS_SPAN_GAP = 11  # glyph does not reach one end of an axis
GLYPH_EMPTY_IN_SOURCE = 12  # glyph empty in one master, drawn in others

# Minimum area threshold to consider direction meaningful
MIN_AREA_THRESHOLD = 1000


def format_groups_location(groups: dict[str, list[str]]) -> str:
    """
    Format location string for grouped problems.

    Shows outliers (smaller groups) with their values.
    Example: "Light (2) ≠ 3 others (3)" or "2 variants"
    """
    if len(groups) < 2:
        return ""

    # Sort groups by size (smallest first = likely outliers)
    sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]))
    total_sources = sum(len(v) for v in groups.values())

    # If smallest group is ≤25% of total, show it as outlier
    smallest_value, smallest_sources = sorted_groups[0]
    if len(smallest_sources) <= total_sources * 0.25:
        if len(smallest_sources) == 1:
            src_display = smallest_sources[0].replace(".ufo", "")
        else:
            src_display = f"{len(smallest_sources)} sources"
        others_count = total_sources - len(smallest_sources)
        return f"{src_display} ({smallest_value}) ≠ {others_count} others"

    # Otherwise just show variant count
    return f"{len(groups)} variants"


def format_binary_location(present_in: list[str], missing_in: list[str]) -> str:
    """
    Format location string for binary (present/missing) problems.

    Example: "missing in Bold, Black" or "missing in 5 sources"
    """
    if not missing_in:
        return ""

    if len(missing_in) <= 2:
        names = [s.replace(".ufo", "") for s in missing_in]
        return f"missing in {', '.join(names)}"
    return f"missing in {len(missing_in)} sources"


def parse_digest_contours(digest: tuple) -> list[dict]:
    """
    Parse a DigestPointStructurePen digest into per-contour statistics.

    Returns a list of dicts, one per contour:
        {'on_curves': int, 'off_curves': int, 'types': tuple}
    """
    contours = []
    current = None
    for item in digest:
        if isinstance(item, tuple) and item[0] == "beginPath":
            current = {"on_curves": 0, "off_curves": 0, "types": []}
        elif item == "endPath":
            if current is not None:
                current["types"] = tuple(current["types"])
                contours.append(current)
            current = None
        elif current is not None:
            if item is None:
                current["off_curves"] += 1
            else:
                current["on_curves"] += 1
                current["types"].append(item)
    return contours


class GlyphsChecker(BaseChecker):
    """
    Validates glyph compatibility across sources.

    Performs detailed analysis of glyph structure differences:
    - Contour and point counts
    - Curve types
    - Contour directions
    - Anchors
    - Components
    - Unicodes

    Uses parallel processing for large glyph sets.
    """

    CATEGORY = CATEGORY_GLYPHS

    def __init__(self, *args, on_glyph_progress=None, **kwargs):
        """
        Initialize GlyphsChecker.

        Args:
            on_glyph_progress: Optional callback (checked: int, total: int) for progress reporting
        """
        super().__init__(*args, **kwargs)
        self._font_cache: dict[str, "RFont"] = {}
        self._on_glyph_progress = on_glyph_progress

    def check(self) -> Iterator[CheckResult]:
        """Run all glyph compatibility checks."""
        yield from self._check_slices(glyph_names=None)

    def check_glyphs(self, glyph_names: set[str]) -> Iterator[CheckResult]:
        """
        Check only specified glyphs.

        This is used for partial recheck after fixing specific glyphs.

        Args:
            glyph_names: Set of glyph names to check

        Yields:
            CheckResult for each problem found
        """
        yield from self._check_slices(glyph_names=set(glyph_names))

    def _slices(self) -> list[tuple[dict, object, list, list]]:
        """The designspace split into interpolable parts, with their sources.

        A discrete axis does not interpolate: each of its values is a separate
        space with its own default and its own extremes, so every rule here is
        a rule about one slice. When the registry has already split the
        document this yields that one slice back unchanged.
        """
        from fontTools.designspaceLib.split import splitInterpolable

        entry = self.entry
        try:
            splits = list(splitInterpolable(self.doc))
        except Exception as exc:  # pragma: no cover - malformed document
            logger.debug(f"splitInterpolable failed: {exc}")
            return [({}, self.doc, list(entry.sources), [])]

        slices = []
        for discrete_loc, sub_doc in splits:
            # Descriptor <-> master is matched once per slice, not once per
            # glyph: the match resolves paths, and doing it inside the glyph
            # loop cost a filesystem call per glyph per master per master.
            pairs = []
            sources = []
            for descriptor in sub_doc.sources:
                matched = self._match_source(descriptor, entry.sources)
                if matched is None or matched in sources:
                    continue
                sources.append(matched)
                pairs.append((descriptor, matched))
            if sources:
                slices.append((discrete_loc, sub_doc, sources, pairs))
        return slices or [({}, self.doc, list(entry.sources), [])]

    def _check_slices(self, glyph_names: set[str] | None) -> Iterator[CheckResult]:
        """Run the per-glyph rules over every interpolable slice."""
        entry = self.entry
        if entry is None:
            logger.debug("GlyphsChecker requires DesignSpaceEntry with loaded fonts")
            return

        if len(entry.sources) < 2:
            return  # Nothing to compare

        for _discrete_loc, sub_doc, sources, pairs in self._slices():
            if len(sources) < 2:
                continue

            default_source = self._default_font_source(sub_doc, sources)
            if default_source is None:
                logger.warning("Could not find default font")
                continue

            present_by_glyph: dict[str, list] = {}
            for source in sources:
                for name in self._own_keys(source):
                    present_by_glyph.setdefault(name, []).append(source)

            if glyph_names is not None:
                present_by_glyph = {
                    name: srcs for name, srcs in present_by_glyph.items() if name in glyph_names
                }

            glyphs_to_check = []
            for glyph_name, present_in in sorted(present_by_glyph.items()):
                if default_source not in present_in:
                    yield self._missing_in_default_result(glyph_name, present_in, default_source)
                    continue
                yield from self._check_axis_coverage(glyph_name, sub_doc, pairs, present_in)
                glyphs_to_check.append(glyph_name)

            # Check glyphs sequentially (ThreadPoolExecutor doesn't help due to GIL)
            total_glyphs = len(glyphs_to_check)
            report_interval = max(1, total_glyphs // 100)  # Report every 1%

            for i, glyph_name in enumerate(glyphs_to_check):
                try:
                    yield from self._check_glyph(glyph_name, present_by_glyph[glyph_name])
                except Exception as e:
                    logger.warning(f"Error checking glyph {glyph_name}: {e}")

                # Report progress
                if self._on_glyph_progress and (i % report_interval == 0 or i == total_glyphs - 1):
                    self._on_glyph_progress(i + 1, total_glyphs)

    def _missing_in_default_result(self, glyph_name, present_in, default_source) -> CheckResult:
        """4.7: the glyph exists somewhere but not in the default master.

        varLib copies the default master and builds variations on top of it, so
        a glyph the default does not have is simply absent from the compiled
        font -- silently, however many other masters draw it.
        """
        present_names = [self._label(s) for s in present_in]
        missing_name = self._label(default_source)

        if len(present_names) <= 2:
            location = f"exists in {', '.join(n.replace('.ufo', '') for n in present_names)}"
        else:
            location = f"exists in {len(present_names)} sources"

        return self._make_result(
            code=DEFAULT_GLYPH_EMPTY,
            description=f"missing in default, exists in {len(present_names)} sources",
            glyph_name=glyph_name,
            location=location,
            is_structural=True,
            details=(
                f"Glyph '{glyph_name}' exists in {', '.join(present_names[:3])} but not in the "
                f"default source ({missing_name}); it will be dropped from the variable font"
            ),
            problem_type=GlyphProblemType.MISSING_GLYPH,
            raw_data={
                "glyphName": glyph_name,
                "locationType": "binary",
                "presentIn": present_names,
                "missingIn": [missing_name],
            },
        )

    def _check_axis_coverage(self, glyph_name, sub_doc, pairs, present_in) -> Iterator[CheckResult]:
        """4.11: the glyph does not reach as far along an axis as the space does.

        Missing from a master in the middle is fine -- varLib interpolates the
        glyph from the masters that have it. Missing from a master at the end
        of an axis is not: past the glyph's last master the variation dies away
        and the glyph falls back to the default master's shape, while its
        neighbours keep changing. Nothing in the build warns about it.
        """
        from ..axis_span import axis_span_gaps

        present_ids = {id(source) for source in present_in}
        all_descs = [descriptor for descriptor, _source in pairs]
        covering_descs = [d for d, source in pairs if id(source) in present_ids]
        if len(covering_descs) == len(all_descs):
            return  # every master draws it; nothing to span-check

        for gap in axis_span_gaps(sub_doc, all_descs, covering_descs):
            end = "maximum" if gap.side == "maximum" else "minimum"
            missing_in = [
                self._label(source) for _d, source in pairs if id(source) not in present_ids
            ]
            yield self._make_result(
                code=GLYPH_AXIS_SPAN_GAP,
                description=(
                    f"missing at {gap.axis} {end} ({gap.required:g}); "
                    f"reverts to the default shape past {gap.covered:g}"
                ),
                glyph_name=glyph_name,
                location=f"{gap.axis} {gap.covered:g} of {gap.required:g}",
                is_structural=True,
                details=(
                    f"Glyph '{glyph_name}' is drawn only up to {gap.axis}={gap.covered:g}, while "
                    f"the masters reach {gap.required:g}. Beyond its last master the glyph goes "
                    f"back to the default master's shape."
                ),
                problem_type=GlyphProblemType.MISSING_GLYPH,
                raw_data={
                    "glyphName": glyph_name,
                    "locationType": "binary",
                    "axis": gap.axis,
                    "side": gap.side,
                    "required": gap.required,
                    "covered": gap.covered,
                    "missingIn": missing_in,
                },
            )

    def _empty_glyph_results(self, glyph_name, drawn, empty) -> Iterator[CheckResult]:
        """4.12: the glyph is drawn in some masters and left empty in others.

        A glyph empty everywhere is an ordinary spacing glyph. One that is
        empty next to masters that draw it cannot interpolate with them: it has
        no points to match, so the shape collapses.

        Takes the two lists from the caller's own pass over the sources --
        fetching every glyph a second time just to look at it is the kind of
        thing that makes an 84-master designspace crawl.
        """
        if not empty or not drawn:
            return

        empty_names = [self._label(s) for s in empty]
        for source in empty:
            yield self._make_result(
                code=GLYPH_EMPTY_IN_SOURCE,
                description=f"empty here, drawn in {len(drawn)} sources",
                glyph_name=glyph_name,
                location=self._label(source).replace(".ufo", ""),
                is_structural=False,
                details=(
                    f"Glyph '{glyph_name}' has no contours and no components in "
                    f"{self._label(source)}, but is drawn in "
                    f"{', '.join(self._label(s) for s in drawn[:3])}"
                ),
                problem_type=GlyphProblemType.EMPTY_GLYPH,
                raw_data={
                    "glyphName": glyph_name,
                    "locationType": "binary",
                    "presentIn": [self._label(s) for s in drawn],
                    "missingIn": empty_names,
                },
            )

    def _check_glyph(self, glyph_name: str, sources=None) -> list[CheckResult]:
        """
        Check a single glyph across the sources that draw it.

        Uses DigestPointStructurePen for precise structure comparison,
        matching designspaceProblems logic.

        Args:
            glyph_name: Glyph to compare.
            sources: The masters to compare, defaulting to every loaded one.
                Callers pass one interpolable slice at a time.
        """
        entry = self.entry
        if entry is None:
            return []
        if sources is None:
            sources = entry.sources

        results = []

        # Collect digest patterns, contour counts, components, anchors, unicodes
        # Store source names for each value to enable location display
        patterns: dict[tuple, list[str]] = defaultdict(list)  # digest -> [source_names]
        contour_count_sources: dict[int, list[str]] = defaultdict(list)  # count -> [sources]
        component_sources: dict[str, list[str]] = defaultdict(list)  # base_glyph -> [sources]
        anchor_sources: dict[str, list[str]] = defaultdict(list)  # anchor_name -> [sources]
        unicode_sources: dict[tuple, list[str]] = defaultdict(list)  # unicodes -> [sources]
        contour_stats: dict[tuple, list[dict]] = {}
        contour_directions: list[tuple[str, tuple]] = []  # (source_name, directions)
        all_source_names: list[str] = []  # Track all sources that have this glyph
        drawn_sources: list = []  # 4.12: sources with an outline ...
        empty_sources: list = []  # ... and sources that leave the glyph empty

        num_sources = 0

        for source in sources:
            # A layer master draws from its own layer; reading the UFO's
            # default layer would compare one master with another's outline.
            glyph = self._own_glyph(source, glyph_name)
            if glyph is None:
                continue

            num_sources += 1
            source_name = self._label(source)
            all_source_names.append(source_name)

            if len(glyph) == 0 and not glyph.components:
                empty_sources.append(source)
            else:
                drawn_sources.append(source)

            # Get digest using DigestPointStructurePen
            pen = DigestPointStructurePen()
            glyph.drawPoints(pen)
            digest = pen.getDigest()

            # Collect pattern with source names
            patterns[digest].append(source_name)

            # Count contours from digest and track sources
            contour_count = 0
            for item in digest:
                if isinstance(item, tuple) and item[0] == "beginPath":
                    contour_count += 1
            contour_count_sources[contour_count].append(source_name)

            # Collect components with sources
            for comp in glyph.components:
                component_sources[comp.baseGlyph].append(source_name)

            # Collect anchors with sources
            for anchor in glyph.anchors:
                if hasattr(anchor, "name") and anchor.name:
                    anchor_sources[anchor.name].append(source_name)

            # Collect unicodes with sources
            unis = tuple(sorted(glyph.unicodes)) if glyph.unicodes else ()
            unicode_sources[unis].append(source_name)

            # Parse contour stats for detailed checks (only if needed)
            if digest not in contour_stats:
                contour_stats[digest] = parse_digest_contours(digest)

            # Collect contour directions
            directions = tuple(self._get_contour_direction(c) for c in glyph.contours)
            contour_directions.append((source_name, directions))

        if num_sources == 0:
            return results

        # 4.0: Different number of contours
        if len(contour_count_sources) > 1:
            # Build groups dict with string keys for display
            groups = {f"{cnt}": sources for cnt, sources in contour_count_sources.items()}
            location = format_groups_location(groups)

            # Build details
            counts_detail = ", ".join(
                f"{cnt} contours ({len(sources)}x)"
                for cnt, sources in sorted(contour_count_sources.items())
            )
            results.append(
                self._make_result(
                    code=DIFFERENT_CONTOUR_COUNT,
                    description=f"different contour count: {counts_detail}",
                    glyph_name=glyph_name,
                    location=location,
                    is_structural=False,
                    details=f"Glyph '{glyph_name}' has different contour counts across sources: {counts_detail}",
                    problem_type=GlyphProblemType.INCOMPATIBLE_GLYPH,
                    raw_data={
                        "glyphName": glyph_name,
                        "locationType": "groups",
                        "groups": {str(k): v for k, v in contour_count_sources.items()},
                    },
                )
            )

        # 4.1: Different components
        for base_glyph, present_in in component_sources.items():
            if len(present_in) < num_sources:
                # Find sources missing this component
                missing_in = [s for s in all_source_names if s not in present_in]
                location = format_binary_location(present_in, missing_in)

                results.append(
                    self._make_result(
                        code=DIFFERENT_COMPONENTS,
                        description=f"component '{base_glyph}' missing in some sources",
                        glyph_name=glyph_name,
                        location=location,
                        is_structural=False,
                        details=f"Glyph '{glyph_name}' uses component '{base_glyph}' in {len(present_in)} sources, but expected in all {num_sources}",
                        problem_type=GlyphProblemType.COMPONENT_MISMATCH,
                        raw_data={
                            "glyphName": glyph_name,
                            "baseGlyph": base_glyph,
                            "locationType": "binary",
                            "presentIn": present_in,
                            "missingIn": missing_in,
                        },
                    )
                )

        # 4.2: Different anchors
        for anchor_name, present_in in anchor_sources.items():
            if len(present_in) < num_sources:
                # Find sources missing this anchor
                missing_in = [s for s in all_source_names if s not in present_in]
                location = format_binary_location(present_in, missing_in)

                results.append(
                    self._make_result(
                        code=DIFFERENT_ANCHORS,
                        description=f"anchor '{anchor_name}' missing in {len(missing_in)} sources",
                        glyph_name=glyph_name,
                        location=location,
                        is_structural=False,
                        details=f"Glyph '{glyph_name}' has anchor '{anchor_name}' in {len(present_in)}/{num_sources} sources",
                        problem_type=GlyphProblemType.DIFFERENT_ANCHORS,
                        anchor_differences=[
                            AnchorDifference(
                                anchor_name=anchor_name,
                                present_in=present_in,
                                missing_in=missing_in,
                            )
                        ],
                        raw_data={
                            "glyphName": glyph_name,
                            "anchorName": anchor_name,
                            "locationType": "binary",
                            "presentIn": present_in,
                            "missingIn": missing_in,
                        },
                    )
                )

        # 4.9: Incompatible glyph + detailed checks (4.3, 4.4, 4.5)
        if len(patterns) > 1:
            # Build groups with pattern labels (pattern1, pattern2, etc.)
            pattern_groups = {
                f"pattern{i + 1}": sources
                for i, (_, sources) in enumerate(sorted(patterns.items(), key=lambda x: -len(x[1])))
            }
            location = format_groups_location(pattern_groups)

            # Build details about which sources have which pattern
            pattern_info = []
            for pat, sources in patterns.items():
                if len(sources) <= 3:
                    pattern_info.append(f"{len(sources)} sources: {', '.join(sources)}")
                else:
                    pattern_info.append(
                        f"{len(sources)} sources: {sources[0]}, ... +{len(sources) - 1} more"
                    )
            details = (
                f"Glyph '{glyph_name}' has {len(patterns)} different structures: "
                + "; ".join(pattern_info)
            )

            results.append(
                self._make_result(
                    code=INCOMPATIBLE_GLYPH,
                    description=f"incompatible: {len(patterns)} different structures",
                    glyph_name=glyph_name,
                    location=location,
                    is_structural=False,
                    details=details,
                    problem_type=GlyphProblemType.INCOMPATIBLE_GLYPH,
                    raw_data={
                        "glyphName": glyph_name,
                        "locationType": "groups",
                        "groups": pattern_groups,
                    },
                )
            )

            # Detailed checks: collect groups per contour for on-curves, off-curves, types
            # Collect per-contour stats with sources
            on_curves_by_contour: dict[int, dict[int, list[str]]] = defaultdict(
                lambda: defaultdict(list)
            )
            off_curves_by_contour: dict[int, dict[int, list[str]]] = defaultdict(
                lambda: defaultdict(list)
            )
            types_by_contour: dict[int, dict[tuple, list[str]]] = defaultdict(
                lambda: defaultdict(list)
            )

            for pat, sources in patterns.items():
                stats = contour_stats.get(pat, [])
                for ci, cs in enumerate(stats):
                    on_curves_by_contour[ci][cs["on_curves"]].extend(sources)
                    off_curves_by_contour[ci][cs["off_curves"]].extend(sources)
                    types_by_contour[ci][cs["types"]].extend(sources)

            # 4.3: Different on-curves per contour
            for ci, groups in on_curves_by_contour.items():
                if len(groups) > 1:
                    str_groups = {str(k): v for k, v in groups.items()}
                    loc = format_groups_location(str_groups)
                    counts_str = " vs ".join(f"{k}" for k in sorted(groups.keys()))
                    results.append(
                        self._make_result(
                            code=DIFFERENT_ON_CURVES,
                            description=f"contour {ci}: {counts_str} on-curves",
                            glyph_name=glyph_name,
                            location=loc,
                            is_structural=False,
                            details=f"Glyph '{glyph_name}' contour {ci} has different on-curve point counts",
                            problem_type=GlyphProblemType.INCOMPATIBLE_GLYPH,
                            raw_data={
                                "glyphName": glyph_name,
                                "contourIndex": ci,
                                "locationType": "groups",
                                "groups": str_groups,
                            },
                        )
                    )

            # 4.4: Different off-curves per contour
            for ci, groups in off_curves_by_contour.items():
                if len(groups) > 1:
                    str_groups = {str(k): v for k, v in groups.items()}
                    loc = format_groups_location(str_groups)
                    counts_str = " vs ".join(f"{k}" for k in sorted(groups.keys()))
                    results.append(
                        self._make_result(
                            code=DIFFERENT_OFF_CURVES,
                            description=f"contour {ci}: {counts_str} off-curves",
                            glyph_name=glyph_name,
                            location=loc,
                            is_structural=False,
                            details=f"Glyph '{glyph_name}' contour {ci} has different off-curve point counts",
                            problem_type=GlyphProblemType.INCOMPATIBLE_GLYPH,
                            raw_data={
                                "glyphName": glyph_name,
                                "contourIndex": ci,
                                "locationType": "groups",
                                "groups": str_groups,
                            },
                        )
                    )

            # 4.5: Wrong curve type per contour
            for ci, groups in types_by_contour.items():
                if len(groups) > 1:
                    # Use simple labels for type groups
                    str_groups = {f"type{i + 1}": v for i, (_, v) in enumerate(groups.items())}
                    loc = format_groups_location(str_groups)
                    results.append(
                        self._make_result(
                            code=WRONG_CURVE_TYPE,
                            description=f"contour {ci}: curve type mismatch",
                            glyph_name=glyph_name,
                            location=loc,
                            is_structural=False,
                            details=f"Glyph '{glyph_name}' contour {ci} has different curve types",
                            problem_type=GlyphProblemType.CURVE_TYPE_MISMATCH,
                            raw_data={
                                "glyphName": glyph_name,
                                "contourIndex": ci,
                                "locationType": "groups",
                                "groups": str_groups,
                            },
                        )
                    )

        # 4.8: Wrong contour direction - group by direction per contour
        if len(contour_directions) > 1:
            dir_names = {1: "CCW", -1: "CW", 0: "flat"}

            # Collect direction groups per contour
            direction_by_contour: dict[int, dict[int, list[str]]] = defaultdict(
                lambda: defaultdict(list)
            )
            for source_name, dirs in contour_directions:
                for ci, d in enumerate(dirs):
                    if d != 0:  # Skip flat contours
                        direction_by_contour[ci][d].append(source_name)

            for ci, groups in direction_by_contour.items():
                if len(groups) > 1:
                    str_groups = {dir_names.get(k, "?"): v for k, v in groups.items()}
                    loc = format_groups_location(str_groups)
                    dir_strs = " vs ".join(dir_names.get(k, "?") for k in sorted(groups.keys()))

                    results.append(
                        self._make_result(
                            code=WRONG_CONTOUR_DIRECTION,
                            description=f"contour {ci}: {dir_strs}",
                            glyph_name=glyph_name,
                            location=loc,
                            is_structural=False,
                            details=f"Glyph '{glyph_name}' contour {ci} has different directions across sources",
                            problem_type=GlyphProblemType.CONTOUR_DIRECTION,
                            raw_data={
                                "glyphName": glyph_name,
                                "contourIndex": ci,
                                "locationType": "groups",
                                "groups": str_groups,
                            },
                        )
                    )

        # 4.10: Different unicodes
        if len(unicode_sources) > 1:
            # Build groups with unicode labels
            groups = {}
            for unis, sources in unicode_sources.items():
                if unis:
                    label = ", ".join(f"U+{u:04X}" for u in unis)
                else:
                    label = "(none)"
                groups[label] = sources

            location = format_groups_location(groups)

            # Format details
            uni_strs = list(groups.keys())
            details = f"Glyph '{glyph_name}' has different unicode values: {' vs '.join(uni_strs)}"

            results.append(
                self._make_result(
                    code=DIFFERENT_UNICODES,
                    description=f"unicode mismatch: {len(unicode_sources)} different values",
                    glyph_name=glyph_name,
                    location=location,
                    is_structural=False,
                    details=details,
                    problem_type=GlyphProblemType.DIFFERENT_UNICODES,
                    raw_data={
                        "glyphName": glyph_name,
                        "locationType": "groups",
                        "groups": groups,
                    },
                )
            )

        results.extend(self._empty_glyph_results(glyph_name, drawn_sources, empty_sources))

        return results

    def _find_default_font(self):
        """The default master's font, matched by path *and* layer.

        Kept as a thin wrapper over the shared source lookup: a font alone
        cannot say which layer of a shared UFO it came from, so callers that
        need the master itself use ``_default_font_source``.
        """
        source = self._default_font_source()
        return source.font if source is not None else None

    @staticmethod
    def _get_contour_direction(contour) -> int:
        """
        Calculate contour direction using signed area (shoelace formula).

        Returns 1 for counter-clockwise, -1 for clockwise, 0 for degenerate.
        """
        points = [(p.x, p.y) for p in contour.points if p.type is not None]
        n = len(points)
        if n < 3:
            return 0

        area = 0
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]

        if area > 0:
            return 1
        elif area < 0:
            return -1
        return 0
