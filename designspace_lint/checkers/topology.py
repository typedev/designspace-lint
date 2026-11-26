# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Outlines between the masters, sampled where the variable font draws them.

Codes (category 4):
- 4.27: an on-curve point the masters hide inside the ink comes out of it
  between them, and the instance there has a notch or a spike
- 4.28: a point some masters hide inside the ink and others leave outside

The rule and its definitions are in `designspace_lint.topology`. The masters,
their normalized locations and the model are varLib's: the designspace's
sources in order, each glyph over the masters that draw it (the sub-model a
sparse master gets), a non-default master whose glyph is empty counted as
leaving it out, as varLib's gvar does.

Only on request (`--topology`), and with NumPy: it evaluates thousands of
locations per glyph.
"""

from __future__ import annotations

import logging
from typing import Iterator

from ..model import SEVERITY_DESIGN, CheckResult
from .glyphs import GlyphsChecker, _Outline
from .interpolation import _GlyphSet, _neighbour_pairs

logger = logging.getLogger(__name__)

BURIED_POINT_SURFACES = 27
BURIED_POINT_WANDERS = 28
SEGMENT_TURNS_OVER = 32
CURVE_LOOPS = 33

# How many points a finding's text lists; raw_data has them all.
_LISTED = 5
# How many sets of masters keep their sampled weights (locations × masters
# each, a few hundred MB on a large family): glyphs that skip the same
# masters come together rarely enough that a few suffice.
_KEPT_WEIGHTS = 4


def _number(value: float) -> str:
    return f"{value:.0f}" if abs(value - round(value)) < 0.05 else f"{value:.1f}"


def _where(location: dict) -> str:
    return ", ".join(f"{name}={_number(value)}" for name, value in location.items())


def _point(contour: int, point: int) -> str:
    return f"point {point} of contour {contour}"


class TopologyChecker(GlyphsChecker):
    """Buried points that come out of the ink between the masters (4.27, 4.28)."""

    #: Units a point may come out and still count as on the edge; set by the engine.
    tolerance: float | None = None
    #: `topology.sample_locations`'s ``axes_between``; set by the engine.
    axes_between: int | str | None = "auto"

    def check(self) -> Iterator[CheckResult]:
        from fontTools.varLib import models

        from .. import topology

        entry = self.entry
        if entry is None or len(entry.sources) < 2:
            return
        tolerance = topology.DEFAULT_TOLERANCE if self.tolerance is None else self.tolerance

        for _discrete_loc, sub_doc, sources, pairs in self._slices():
            if len(sources) < 2 or not pairs:
                continue
            default_source = self._default_font_source(sub_doc, sources)
            if default_source is None:
                continue
            axes = [axis for axis in sub_doc.axes if not hasattr(axis, "values")]
            supports = {
                axis.name: tuple(
                    axis.map_forward(v) for v in (axis.minimum, axis.default, axis.maximum)
                )
                for axis in axes
            }
            # varLib's masters: the document's sources in order, normalized
            # through the axis maps.
            masters = [source for _descriptor, source in pairs]
            try:
                locations = [
                    models.normalizeLocation(descriptor.getFullDesignLocation(sub_doc), supports)
                    for descriptor, _source in pairs
                ]
                model = models.VariationModel(locations, axisOrder=[axis.name for axis in axes])
            except Exception as exc:  # duplicate locations and the like: 2.x reports them
                logger.debug(f"no variation model for this slice: {exc}")
                continue
            if default_source not in masters:
                continue
            default_index = masters.index(default_source)
            names = [self._designspace_name(source) for source in masters]
            labels = {
                name: self._label(source) for name, source in zip(names, masters, strict=True)
            }
            user_of = self._user_converter(axes, supports)

            glyph_names = sorted(self._own_keys(default_source))
            if self.only_glyphs is not None:
                glyph_names = [name for name in glyph_names if name in self.only_glyphs]
            sampled: dict[tuple[bool, ...], tuple] = {}
            correspondence = _Correspondence(self, masters, locations, default_index)
            for i, glyph_name in enumerate(glyph_names):
                if self._cancel_requested():
                    return
                try:
                    yield from self._check_glyph(
                        glyph_name,
                        masters,
                        names,
                        labels,
                        default_index,
                        model,
                        supports,
                        sampled,
                        tolerance,
                        user_of,
                        correspondence,
                    )
                except Exception as exc:  # one glyph must not stop the scan
                    logger.warning(f"topology check of {glyph_name} failed: {exc}")
                if self._on_glyph_progress:
                    self._on_glyph_progress(i + 1, len(glyph_names))

    # --- one glyph -----------------------------------------------------------

    def _check_glyph(
        self,
        glyph_name,
        masters,
        names,
        labels,
        default_index,
        model,
        supports,
        sampled,
        tolerance,
        user_of,
        correspondence,
    ) -> Iterator[CheckResult]:
        import numpy as np

        from .. import topology

        outlines = []
        for source in masters:
            glyph = self._own_glyph(source, glyph_name)
            outlines.append(_Outline(glyph) if glyph is not None else None)
        reference = outlines[default_index]
        if reference is None or not reference.contours:
            return
        ends, count = [], 0
        tags = []
        for contour in reference.contours:
            count += len(contour)
            ends.append(count - 1)
            tags.extend(topology.point_tags(contour))

        items = []
        for m, outline in enumerate(outlines):
            if outline is None or (
                m != default_index and not outline.contours and not outline.components
            ):
                # varLib's gvar: a master without the glyph, or an empty one
                # beside a default that is not, leaves the glyph out
                items.append(None)
                continue
            if [len(c) for c in outline.contours] != [len(c) for c in reference.contours]:
                return  # not interpolable: 4.0/4.3 say so
            if [t for c in outline.contours for t in topology.point_tags(c)] != tags:
                return  # 4.4/4.5 say so
            items.append([(x, y) for c in outline.contours for x, y, _kind in c])
        key = tuple(item is not None for item in items)
        if key not in sampled:
            while len(sampled) >= _KEPT_WEIGHTS:
                sampled.pop(next(iter(sampled)))
            sub_model, _ = model.getSubModel(items)
            masters_of = [m for m, present in enumerate(key) if present]
            glyph_masters = topology.GlyphMasters(
                glyph_name, (), sub_model, np.zeros((len(masters_of), 0, 2)), [], [], supports
            )
            used = topology.resolve_axes_between(glyph_masters, self.axes_between)
            sampled[key] = {
                "model": sub_model,
                "masters": masters_of,
                "used": used,
                "sampling": topology.Sampling(glyph_masters, used),
                "locations": None,  # with their weights, for buried points only
            }
        prepared = sampled[key]
        sub_model, masters_of, used = prepared["model"], prepared["masters"], prepared["used"]
        glyph_masters = topology.GlyphMasters(
            name=glyph_name,
            sources=tuple(names[m] for m in masters_of),
            model=sub_model,
            points=np.array([items[m] for m in masters_of], dtype=np.float64),
            contours=np.array(ends, dtype=np.int64),
            tags=np.array(tags, dtype=np.int8),
            design_axes=supports,
        )
        checker = topology.BuriedPointChecker(glyph_masters, tolerance)
        surfacing, wandering = [], []
        if checker.candidates:
            if prepared["locations"] is None:
                locations = topology.sample_locations(glyph_masters, axes_between=used)
                weights = topology.master_scalars_at(sub_model, locations)
                prepared["locations"] = (locations, weights)
            locations, weights = prepared["locations"]
            surfacing = topology.buried_points_surfacing(
                glyph_masters, locations=locations, weights=weights, checker=checker
            )
            wandering = sorted(
                checker.wandering(), key=lambda p: (-round(p.depth, 6), p.contour, p.point)
            )
        turnovers = topology.segment_turnovers(glyph_masters, prepared["sampling"])
        loops = topology.curve_loops(glyph_masters, prepared["sampling"])
        if not (surfacing or wandering or turnovers or loops):
            return

        found = correspondence.problems(glyph_name)
        if surfacing:
            result = self._surfacing_result(glyph_name, surfacing, tolerance, user_of, found)
            result.raw_data["axesBetween"] = used
            yield result
        if wandering:
            location_of = {
                names[m]: user_of(sub_model.origLocations[k]) for k, m in enumerate(masters_of)
            }
            result = self._wandering_result(
                glyph_name, wandering, tolerance, labels, location_of, found
            )
            result.raw_data["axesBetween"] = used
            yield result
        if turnovers:
            yield self._turnover_result(glyph_name, turnovers, user_of, found)
        if loops:
            result = self._loop_result(glyph_name, loops, user_of, labels, found)
            result.raw_data["axesBetween"] = used
            yield result

    def _turnover_result(self, glyph_name, turnovers, user_of, found) -> CheckResult:
        def what(t):
            pair = f"from point {t.point} to {t.next_point} of contour {t.contour}"
            return {
                "handle": f"the handle {pair}",
                "betweenHandles": f"the span between handles {pair}",
                "line": f"the line {pair}",
            }[t.kind]

        first = turnovers[0]
        if len(turnovers) == 1:
            description = f"{what(first)} turns over between masters"
        else:
            description = f"{len(turnovers)} segments turn over between masters"
        lines = [f"{what(t)}, near {_where(user_of(t.location))}" for t in turnovers[:_LISTED]]
        if len(turnovers) > _LISTED:
            lines.append(f"{len(turnovers) - _LISTED} more")
        raw = {
            "glyphName": glyph_name,
            "segments": [
                {
                    "contour": t.contour,
                    "point": t.point,
                    "nextPoint": t.next_point,
                    "kind": t.kind,
                    "location": user_of(t.location),
                    "normalizedLocation": dict(t.location),
                    "places": t.places,
                }
                for t in turnovers
            ],
        }
        if found:
            raw["correspondence"] = found
        return self._make_result(
            code=SEGMENT_TURNS_OVER,
            description=description,
            glyph_name=glyph_name,
            location=_where(user_of(first.location)),
            details=(
                "Between two masters the vector from one point to the next moves "
                "straight from one to the other, and it is zero only where they point "
                "opposite ways: this one reverses, so somewhere on the way the two points "
                "meet and the outline has a cusp or a loop, which the variable font draws. "
                "Usually a handle turned through its on-curve point, or two handles "
                "swapped, in one master. "
                + "; ".join(lines)
                + "."
                + self._correspondence_note(found)
            ),
            severity=SEVERITY_DESIGN,
            raw_data=raw,
        )

    def _loop_result(self, glyph_name, loops, user_of, labels, found) -> CheckResult:
        first = loops[0]
        if len(loops) == 1:
            description = (
                f"the curve from point {first.point} of contour {first.contour} loops "
                "between masters"
            )
        else:
            description = f"{len(loops)} curves loop between masters"
        lines = []
        for loop in loops[:_LISTED]:
            text = (
                f"the curve from point {loop.point} of contour {loop.contour}, widest at "
                f"{_where(user_of(loop.location))} (at {loop.looping} of {loop.checked} "
                "locations checked)"
            )
            if loop.masters_looping:
                text += ", in " + ", ".join(labels.get(m, m) for m in loop.masters_looping[:3])
                if len(loop.masters_looping) > 3:
                    text += f" and {len(loop.masters_looping) - 3} more masters"
                text += " already"
            lines.append(text)
        if len(loops) > _LISTED:
            lines.append(f"{len(loops) - _LISTED} more")
        raw = {
            "glyphName": glyph_name,
            "curves": [
                {
                    "contour": loop.contour,
                    "point": loop.point,
                    "location": user_of(loop.location),
                    "normalizedLocation": dict(loop.location),
                    "looping": loop.looping,
                    "checked": loop.checked,
                    "mastersLooping": list(loop.masters_looping),
                }
                for loop in loops
            ],
        }
        if found:
            raw["correspondence"] = found
        return self._make_result(
            code=CURVE_LOOPS,
            description=description,
            glyph_name=glyph_name,
            location=_where(user_of(first.location)),
            details=(
                "A cubic curve that crosses itself draws a small loop where it should "
                "only bend, and the variable font draws it: "
                + "; ".join(lines)
                + ". Its handles reach too far, or past each other, where the masters "
                "around meet." + self._correspondence_note(found)
            ),
            severity=SEVERITY_DESIGN,
            raw_data=raw,
        )

    @staticmethod
    def _user_converter(axes, supports):
        """Normalized -> user location, through each axis' map (rounded to 0.01)."""

        def convert(location: dict) -> dict:
            user = {}
            for axis in axes:
                value = float(location.get(axis.name, 0.0))
                lo, default, hi = supports[axis.name]
                design = default + value * ((default - lo) if value < 0 else (hi - default))
                user[axis.name] = round(float(axis.map_backward(design)), 2)
            return user

        return convert

    # --- findings ------------------------------------------------------------

    @staticmethod
    def _correspondence_note(found: list[dict]) -> str:
        if not found:
            return ""
        kinds = sorted({p["type"] for p in found})
        what = " and ".join(
            "contours in another order (4.14)"
            if k == "contour_order"
            else "a contour starting elsewhere or running the other way (4.15)"
            for k in kinds
        )
        return (
            f" The masters' points do not correspond, though: {what}. Point by point, as "
            "varLib pairs them, a point travels to another master's other point, which can "
            "make this notch by itself; make the contours correspond first."
        )

    def _surfacing_result(self, glyph_name, points, tolerance, user_of, found) -> CheckResult:
        worst = points[0]
        where = _where(user_of(worst.location))
        if len(points) == 1:
            description = (
                f"{_point(worst.contour, worst.point)} comes out of the ink by "
                f"{worst.depth:.1f} units between masters"
            )
        else:
            description = (
                f"{len(points)} buried points come out of the ink between masters, "
                f"up to {worst.depth:.1f} units"
            )
        lines = [
            f"{_point(p.contour, p.point)}: {p.depth:.1f} units out at "
            f"{_where(user_of(p.location))} (at {p.surfacing} of {p.checked} locations "
            f"checked; hidden in {len(p.masters_buried)} "
            f"master{'s' if len(p.masters_buried) != 1 else ''})"
            for p in points[:_LISTED]
        ]
        if len(points) > _LISTED:
            lines.append(f"{len(points) - _LISTED} more")
        raw = {
            "glyphName": glyph_name,
            "location": user_of(worst.location),
            "normalizedLocation": dict(worst.location),
            "tolerance": tolerance,
            "points": [
                {
                    "contour": p.contour,
                    "point": p.point,
                    "depth": round(p.depth, 2),
                    "location": user_of(p.location),
                    "normalizedLocation": dict(p.location),
                    "surfacing": p.surfacing,
                    "checked": p.checked,
                    "mastersBuried": list(p.masters_buried),
                }
                for p in points
            ],
        }
        if found:
            raw["correspondence"] = found
        return self._make_result(
            code=BURIED_POINT_SURFACES,
            description=description,
            glyph_name=glyph_name,
            location=where,
            details=(
                "The masters keep these points inside the ink; between them a point comes "
                "out and makes a notch or a spike, and the variable font draws it there. "
                + "; ".join(lines)
                + ". A sparse master at the worst location, or the point moved deeper into "
                "the ink in the masters around it, fixes it." + self._correspondence_note(found)
            ),
            severity=SEVERITY_DESIGN,
            raw_data=raw,
        )

    def _wandering_result(
        self, glyph_name, points, tolerance, labels, location_of, found
    ) -> CheckResult:
        worst = points[0]
        worst_master = worst.masters_outside[0][0]
        if len(points) == 1:
            description = (
                f"{_point(worst.contour, worst.point)} is buried in "
                f"{len(worst.masters_buried)} master(s) and outside in "
                f"{len(worst.masters_outside)}, up to {worst.depth:.1f} units"
            )
        else:
            description = (
                f"{len(points)} buried points are outside in some masters, "
                f"up to {worst.depth:.1f} units"
            )
        lines = [
            f"{_point(p.contour, p.point)}: out in "
            + ", ".join(f"{labels.get(m, m)} ({d:.1f} units)" for m, d in p.masters_outside[:3])
            + (f" and {len(p.masters_outside) - 3} more" if len(p.masters_outside) > 3 else "")
            + f"; buried in {len(p.masters_buried)}"
            for p in points[:_LISTED]
        ]
        if len(points) > _LISTED:
            lines.append(f"{len(points) - _LISTED} more")
        raw = {
            "glyphName": glyph_name,
            "sourceName": worst_master,
            "location": location_of.get(worst_master, {}),
            "tolerance": tolerance,
            "points": [
                {
                    "contour": p.contour,
                    "point": p.point,
                    "depth": round(p.depth, 2),
                    "location": location_of.get(p.masters_outside[0][0], {}),
                    "mastersOutside": [
                        {"sourceName": m, "depth": round(d, 2)} for m, d in p.masters_outside
                    ],
                    "mastersBuried": list(p.masters_buried),
                }
                for p in points
            ],
        }
        if found:
            raw["correspondence"] = found
        return self._make_result(
            code=BURIED_POINT_WANDERS,
            description=description,
            glyph_name=glyph_name,
            location=labels.get(worst_master, worst_master),
            details=(
                "Some masters keep these points inside the ink, others leave them outside. "
                "Between those masters 4.27 does not check the point: the change may be "
                "meant. If it is not, a master is drawn slightly off. "
                + "; ".join(lines)
                + "."
                + self._correspondence_note(found)
            ),
            severity=SEVERITY_DESIGN,
            raw_data=raw,
        )


class _Correspondence:
    """Whether a glyph's points correspond across the masters, asked only of
    glyphs with a finding: fontTools' interpolatable between neighbouring
    masters, as the --interpolatable phase runs it (4.14, 4.15)."""

    def __init__(self, checker, masters, locations, default_index):
        order = [default_index] + [m for m in range(len(masters)) if m != default_index]
        self._masters = [masters[m] for m in order]
        self._locations = [locations[m] for m in order]
        self._names = [checker._label(source) for source in self._masters]
        self._glyphsets = [_GlyphSet(checker, source) for source in self._masters]
        try:
            self._upem = self._masters[0].font.info.unitsPerEm or 1000
        except Exception:  # pragma: no cover - defensive
            self._upem = 1000

    def problems(self, glyph_name: str) -> list[dict]:
        from fontTools.varLib.interpolatable import test_gen

        from .interpolation import TOLERANCE

        glyphsets = self._glyphsets
        members = tuple(m for m, glyphset in enumerate(glyphsets) if glyphset.has(glyph_name))
        found = []
        try:
            for m1, m2 in _neighbour_pairs(self._locations, members):
                for _name, problem in test_gen(
                    [glyphsets[m1], glyphsets[m2]],
                    glyphs=[glyph_name],
                    names=[self._names[m1], self._names[m2]],
                    ignore_missing=True,
                    tolerance=TOLERANCE,
                    upem=self._upem,
                ):
                    kind = problem.get("type")
                    if kind in ("contour_order", "wrong_start_point"):
                        item = {"type": kind, "masters": [self._names[m1], self._names[m2]]}
                        if problem.get("contour") is not None:
                            item["contour"] = problem.get("contour")
                        found.append(item)
        except Exception as exc:  # no solver for 7+ contours: say nothing
            logger.debug(f"correspondence of {glyph_name} not checked: {exc}")
        finally:
            for glyphset in glyphsets:
                glyphset.release()
        return found
