# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Point correspondence between masters, by fontTools' varLib.interpolatable.

The glyph checks compare structure: how many contours, points, which curve
types. Two masters can agree on all of it and still interpolate badly -- a
contour whose start point sits elsewhere, or that runs the other way, twists
as it moves; contours listed in a different order swap shapes halfway; a
curve whose handles cross collapses or kinks in between. varLib builds all of
these without a word, since it only asks for equal counts and flags.
`varLib.interpolatable` looks at the geometry, and this runs it over the fonts
already open instead of opening every UFO again.

Codes (category 4; ours, after designspaceProblems' 0-10 and our 11-13):
- 4.14: contours in a different order
- 4.15: a contour starts at a different point, or runs the other way
- 4.16: a contour thins out halfway between two masters
- 4.17: a contour kinks halfway between two masters (information)
- 4.18: glyphs left unchecked for want of an assignment solver (information)

The structural findings interpolatable also makes (missing glyph, path and
node counts, segment types) are left out: 4.0-4.9 report those already.

Only on request (`--interpolatable`): on large families it costs about as
much as the rest of the run.
"""

from __future__ import annotations

import logging
from typing import Iterator

from fontTools.pens.filterPen import FilterPen
from fontTools.pens.pointPen import PointToSegmentPen

from ..model import SEVERITY_INFO, CheckResult, GlyphProblemType
from .glyphs import GlyphsChecker

logger = logging.getLogger(__name__)

CONTOUR_ORDER = 14
WRONG_START_POINT = 15
UNDERWEIGHT = 16
KINK = 17
UNCHECKED_NO_SOLVER = 18

# interpolatable's default threshold: a problem is reported below it, and the
# further below, the surer.
TOLERANCE = 0.95


def _has_solver() -> bool:
    """Whether interpolatable can match the contours of glyphs with more than six.

    It picks scipy, then munkres, then a brute force limited to six, once, when
    its helpers are imported; ask it what it picked rather than guessing.
    """
    from fontTools.varLib import interpolatableHelpers as helpers

    return (
        helpers.min_cost_perfect_bipartite_matching
        is not helpers.min_cost_perfect_bipartite_matching_bruteforce
    )


class _SkipMissingComponents(FilterPen):
    """Draw a component whose base this master lacks as nothing.

    That is what the compiled master holds: ufo2ft gives a non-default master
    an empty placeholder for a missing component base, and varLib leaves the
    placeholder out of the variations (`OutlineTTFCompiler.makeMissingRequiredGlyphs`).
    """

    def __init__(self, outPen, glyphset):
        super().__init__(outPen)
        self._glyphset = glyphset

    def addComponent(self, glyphName, transformation, **kwargs):
        if self._glyphset.has(glyphName):
            self._outPen.addComponent(glyphName, transformation, **kwargs)


class _Glyph:
    """A glyph as interpolatable reads it: drawn the way ufoLib's glyphs draw.

    `glifLib.Glyph.draw` goes through `drawPoints` with an implied closing
    line; drawing a fontParts glyph the same way makes the comparison the one
    interpolatable's own command line makes.
    """

    def __init__(self, glyph, glyphset):
        self._glyph = glyph
        self._glyphset = glyphset

    def draw(self, pen, outputImpliedClosingLine=False):
        self._glyph.drawPoints(
            PointToSegmentPen(
                _SkipMissingComponents(pen, self._glyphset),
                outputImpliedClosingLine=outputImpliedClosingLine,
            )
        )


class _GlyphSet:
    """One master's own glyphs; `None` for a glyph it does not have.

    Components are looked up here too, so a master resolves its components
    from its own layer, as the compiled master would.
    """

    def __init__(self, checker: GlyphsChecker, source):
        self._checker = checker
        self._source = source
        self._keys = None

    def keys(self):
        return list(self._own())

    def has(self, name) -> bool:
        return name in self._own()

    def _own(self):
        if self._keys is None:
            self._keys = self._checker._own_keys(self._source)
        return self._keys

    def __getitem__(self, name):
        glyph = self._checker._own_glyph(self._source, name)
        return _Glyph(glyph, self) if glyph is not None else None


class InterpolationChecker(GlyphsChecker):
    """Runs varLib.interpolatable over each interpolable slice."""

    def check(self) -> Iterator[CheckResult]:
        from fontTools.varLib.interpolatable import test_gen

        entry = self.entry
        if entry is None or len(entry.sources) < 2:
            return

        has_solver = _has_solver()
        for _discrete_loc, sub_doc, sources, pairs in self._slices():
            if len(sources) < 2:
                continue
            default_source = self._default_font_source(sub_doc, sources)
            if default_source is None:
                continue

            ordered, locations = self._ordered_masters(sub_doc, pairs, default_source)
            names = [self._label(source) for source in ordered]
            glyphsets = [_GlyphSet(self, source) for source in ordered]
            try:
                upem = default_source.font.info.unitsPerEm or 1000
            except Exception:  # pragma: no cover - defensive
                upem = 1000

            glyph_names = sorted(self._own_keys(default_source))
            unchecked = []
            for i, glyph_name in enumerate(glyph_names):
                # One glyph per call: an error escaping the generator ends it,
                # and without a solver interpolatable raises on any glyph of
                # more than six contours.
                try:
                    problems = list(
                        test_gen(
                            glyphsets,
                            glyphs=[glyph_name],
                            names=names,
                            ignore_missing=True,
                            locations=locations,
                            tolerance=TOLERANCE,
                            upem=upem,
                        )
                    )
                except Exception as exc:
                    if not has_solver and "munkres" in str(exc):
                        unchecked.append(glyph_name)
                    else:
                        logger.warning(f"interpolatable failed on {glyph_name}: {exc}")
                    continue
                results = [self._result(glyph_name, problem) for _name, problem in problems]
                yield from _merge_pairs([r for r in results if r is not None])
                if self._on_glyph_progress:
                    self._on_glyph_progress(i + 1, len(glyph_names))

            if unchecked:
                yield self._make_result(
                    code=UNCHECKED_NO_SOLVER,
                    description=(
                        f"{len(unchecked)} glyph(s) not compared point by point: they need an "
                        f"assignment solver"
                    ),
                    details=(
                        "varLib.interpolatable matches contours with scipy or munkres once a "
                        "glyph has more than six of them. Install "
                        '"designspace-lint[interpolatable]" to check them. First few: '
                        + ", ".join(unchecked[:10])
                    ),
                    severity=SEVERITY_INFO,
                    raw_data={"glyphs": unchecked},
                )

    def _ordered_masters(self, sub_doc, pairs, default_source) -> tuple[list, list | None]:
        """Masters with the default first, then by distance from it.

        Without scipy interpolatable compares each master with the one before
        it, so this order is what makes those comparisons between neighbours.
        With scipy it builds its own tree from the normalized locations.
        """
        located = []
        for descriptor, source in pairs:
            try:
                loc = sub_doc.normalizeLocation(descriptor.getFullDesignLocation(sub_doc))
            except Exception:  # pragma: no cover - defensive
                loc = {}
            located.append((source, loc))
        if not located:
            return [default_source], None

        def distance(item):
            source, loc = item
            if source is default_source:
                return (0, -1.0)
            return (1, sum(v * v for v in loc.values()))

        located.sort(key=distance)
        ordered = [source for source, _loc in located]
        locations = [loc for _source, loc in located]
        return ordered, locations

    def _result(self, glyph_name: str, problem: dict) -> CheckResult | None:
        kind = problem.get("type")
        m1, m2 = problem.get("master_1"), problem.get("master_2")
        between = f"{m1} / {m2}"
        tolerance = problem.get("tolerance")
        raw = {
            "glyphName": glyph_name,
            "type": kind,
            "masters": [m1, m2],
            "tolerance": tolerance,
        }
        contour = problem.get("contour")
        if contour is not None:
            raw["contour"] = contour

        if kind == "contour_order":
            return self._make_result(
                code=CONTOUR_ORDER,
                description=f"contours in a different order between {between}",
                glyph_name=glyph_name,
                location=between,
                details=(
                    f"The contours of {m2} match those of {m1} best in the order "
                    f"{list(problem.get('value_2', []))}; as drawn, each interpolates toward a "
                    f"different shape, and they cross over in between."
                ),
                problem_type=GlyphProblemType.INCOMPATIBLE_GLYPH,
                raw_data=raw,
            )
        if kind == "wrong_start_point":
            reversed_ = bool(problem.get("reversed"))
            return self._make_result(
                code=WRONG_START_POINT,
                description=(
                    f"contour {contour} "
                    + ("runs the other way" if reversed_ else "starts at a different point")
                    + f" between {between}"
                ),
                glyph_name=glyph_name,
                location=between,
                details=(
                    f"Contour {contour} of {m2} matches {m1} best starting at point "
                    f"{problem.get('value_2')}"
                    + (", reversed" if reversed_ else "")
                    + ". Interpolated as drawn, its points travel to the wrong partners and "
                    "the contour twists between the two masters. varLib builds it without "
                    "a warning."
                ),
                problem_type=GlyphProblemType.START_POINT_MISMATCH,
                raw_data={**raw, "reversed": reversed_, "proposedStart": problem.get("value_2")},
            )
        if kind == "underweight":
            return self._make_result(
                code=UNDERWEIGHT,
                description=f"contour {contour} thins out halfway between {between}",
                glyph_name=glyph_name,
                location=between,
                details=(
                    f"At the midpoint between {m1} and {m2}, contour {contour} covers much "
                    f"less area than either master: its points pass close to one another on "
                    f"the way, usually a sign of mismatched points."
                ),
                problem_type=GlyphProblemType.INCOMPATIBLE_GLYPH,
                raw_data=raw,
            )
        if kind == "kink":
            return self._make_result(
                code=KINK,
                description=f"contour {contour} kinks at point {problem.get('value')} "
                f"halfway between {between}",
                glyph_name=glyph_name,
                location=between,
                details=(
                    f"A smooth point of contour {contour} turns into a corner at the midpoint "
                    f"between {m1} and {m2}: its handles are not aligned the same way in both."
                ),
                severity=SEVERITY_INFO,
                problem_type=GlyphProblemType.INCOMPATIBLE_GLYPH,
                raw_data={**raw, "point": problem.get("value")},
            )
        # missing, open_path, path_count, node_count, node_incompatibility:
        # the structural checks 4.0-4.9 report these already.
        return None


def _merge_pairs(results: list[CheckResult]) -> list[CheckResult]:
    """One finding per glyph, code and contour, however many master pairs share it.

    A contour that kinks usually kinks between every pair of masters around a
    corner of the space: on GoogleSansFlex 1376 kinks were 58 glyphs. The
    finding shown is the pair interpolatable is surest about (the lowest
    tolerance); the others are counted and listed in `raw_data["pairs"]`.
    """
    groups: dict[tuple, list[CheckResult]] = {}
    for result in results:
        key = (result.code, result.raw_data.get("contour"))
        groups.setdefault(key, []).append(result)

    merged = []
    for group in groups.values():
        group.sort(key=lambda r: r.raw_data.get("tolerance") or 1.0)
        first = group[0]
        first.raw_data["pairs"] = [r.raw_data.get("masters") for r in group]
        if len(group) > 1:
            first.description += f" (and {len(group) - 1} more master pair(s))"
        merged.append(first)
    return merged
