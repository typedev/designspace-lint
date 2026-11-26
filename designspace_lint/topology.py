# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Outlines between the masters: buried points that come out of the ink.

Designers hide on-curve points inside ink: the corner of K's arm inside the
stem, the crotch of k drawn as one contour that overlaps itself, the joints
of Ж. Every master looks right, and between them such a point can come out
of the ink and make a notch or a spike. The variable font draws the instances
exactly as varLib interpolates the masters, so the notch is in the font; the
masters alone never show it. Point positions move linearly between masters,
but where an edge lies at the point's height is a product of two linear
terms, so the distance out of the ink is quadratic and largest in between.

Definitions (all in font units):

- a point is **covered** when there is ink on both sides of it: two probes
  just beside its incoming edge, half a unit before the point (nearer when
  another edge is closer than a unit, so the probes stay on the point's side
  of it), one on each side, both filled (nonzero winding over the whole
  glyph, its own contour included). This holds for convex and concave
  corners, counters, contours that overlap themselves and either contour
  direction. A wedge narrower than about 1° at the point is below that
  resolution.
- **depth**: the distance to the nearest edge other than the point's own two
  segments, positive when covered, negative when not. When only one side is
  empty and the point's own segments close that side, at most the width of
  the empty wedge between them: a spike whose edges fold over each other
  between masters opens a crack that narrow inside the ink, and it is not a
  point coming out of the ink by the distance to the ink's edge.
- a point is *outside* when its depth is below ``-threshold``; the threshold
  is the tolerance (1 unit by default; 0 for zero tolerance), never below the
  measuring precision `PRECISION` (curves are flattened to that error).
- a point is **checked** at a location when it is buried (depth above the
  threshold) in at least one master of the glyph -- the designer's intent --
  and is not outside in any master that contributes there (non-zero weight).
  A point the masters disagree on is a transition the designer accepted.
- a **surfacing** point: a checked point outside at a sampled location.
  Every one counts, however small: one unit out already breaks the outline.
- a **wandering** point: buried in some masters, outside in others. Between
  those masters it is not checked (the change may be meant), but it is
  reported on its own, by master, for the designer to decide -- a master
  drawn slightly off (a skewed crossbar's corner half a unit out of its
  stem) looks exactly like this.

Where to look (`sample_locations`): per axis, the masters' values, the axis
ends and the default (the grid), plus the quarters between consecutive
values; every combination over the axes in which at most two axes sit
between grid values at once. Between two masters on an edge at different
fractions of it a point leaves the edge quadratically, most near the middle,
which is why the in-between values matter more than the masters. The whole
product grows as the quarters' count to the power of the axes: 541 125
locations per glyph on a 6-axis family, against 64 000 with two axes at a
time, which found every point the whole product did, on that family and on
a 4-axis one of 84 masters (the worst depth within 4 units).

The glyph's own contours only: components are not decomposed. Open contours
are measured as closed (that is how a compiler closes them). The outline is
the UFO's: a TrueType build approximates cubic curves with quadratic ones
within a unit, and rounds and optimises the deltas within half a unit, both
inside the default tolerance.

The rule was worked out in Font-Rover on a large multi-axis designspace,
where it found exactly what the designer's hand-made sparse masters had been
added to fix. It is public so that a host can mark the points live, at the
location a view shows, with the same rule the check applies
(`BuriedPointChecker.at`). NumPy does the work for all sampled locations at
once; install ``designspace-lint[topology]``.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

__all__ = [
    "AXES_BETWEEN",
    "DEFAULT_TOLERANCE",
    "PRECISION",
    "TAG_CONIC",
    "TAG_CUBIC",
    "TAG_ON",
    "BuriedPointChecker",
    "GlyphMasters",
    "SurfacingPoint",
    "WanderingPoint",
    "buried_points_surfacing",
    "master_scalars",
    "master_scalars_at",
    "point_at",
    "point_tags",
    "sample_locations",
]

#: Default tolerance: a point up to this far outside counts as on the edge.
DEFAULT_TOLERANCE = 1.0

#: Measuring precision: curves are flattened to this error, so with zero
#: tolerance a deviation below it cannot be told from the edge.
PRECISION = 0.05

#: Point tags, as FreeType's (FT_CURVE_TAG_*): an on-curve point, an
#: off-curve point of a quadratic curve, an off-curve point of a cubic one.
TAG_ON = 1
TAG_CONIC = 0
TAG_CUBIC = 2

# Locations evaluated together (memory: locations × edges per array).
_CHUNK = 512
# Segments per flattened curve, at most.
_MAX_STEPS = 64
# A master with a smaller |weight| does not take part at a location.
_WEIGHT_EPSILON = 1e-6
# The probes beside a point: this far back along its incoming edge, and this
# fraction of that sideways (about 1°: a thinner wedge is not seen).
_PROBE_BACK = 0.5
_PROBE_SIDE = 0.02
# Nearer than this to another edge the point is on it (below PRECISION anyway)
_PROBE_MIN = 1e-3
# Where the width of an empty wedge at a point is measured, units from it.
_GAP_BACK = (0.5, 1.0, 2.0, 5.0, 10.0)


@dataclass
class GlyphMasters:
    """A glyph's own outline in each master it is interpolated from.

    The value at a normalized location is ``Σ weight × master``, with the
    weights from `master_scalars` (``model.getMasterScalars``), in
    ``sources`` order. Components are not included.
    """

    name: str
    #: The masters that draw it, in the model's order (any labels).
    sources: tuple[str, ...]
    #: A fontTools VariationModel over those masters: the sub-model varLib
    #: builds for a glyph some masters leave out.
    model: Any
    #: (masters, points, 2) float64: every master's points, in UFO order.
    points: np.ndarray
    #: Index of each contour's last point in ``points``.
    contours: np.ndarray
    #: (points,) the tag of each point: `TAG_ON`, `TAG_CONIC` or `TAG_CUBIC`.
    tags: np.ndarray
    #: {axis name: (minimum, default, maximum)} in design space.
    design_axes: dict


@dataclass(frozen=True)
class SurfacingPoint:
    """A buried on-curve point that comes out of the ink between masters."""

    contour: int  # contour index in the glyph
    point: int  # point index in that contour (UFO order)
    depth: float  # how far outside at the worst location, in units (> 0)
    location: dict  # the worst sampled location, normalized
    surfacing: int  # sampled locations where the point is outside
    checked: int  # sampled locations where the point was checked
    masters_buried: tuple[str, ...]  # masters hiding it


@dataclass(frozen=True)
class WanderingPoint:
    """A point some masters keep inside the ink and others leave outside it."""

    contour: int
    point: int
    masters_buried: tuple[str, ...]  # masters hiding it
    masters_outside: tuple[tuple[str, float], ...]  # (master, units out), worst first

    @property
    def depth(self) -> float:
        """Units out in the worst master."""
        return self.masters_outside[0][1]


def point_tags(contour: Sequence) -> list[int]:
    """The tags of one UFO contour's points, from their segment types.

    ``contour`` is a sequence of points whose last item is the UFO segment
    type ("line", "curve", "qcurve", "move"; None or "offcurve" off the
    curve), such as ``(x, y, segmentType)``. An off-curve point belongs to the
    curve of the next on-curve point after it; a contour of off-curve points
    only is a closed quadratic curve.
    """
    kinds = [p[-1] for p in contour]
    on = [k not in (None, "offcurve") for k in kinds]
    if not any(on):
        return [TAG_CONIC] * len(kinds)
    tags = [TAG_ON] * len(kinds)
    n = len(kinds)
    for i in range(n):
        if on[i]:
            continue
        j = (i + 1) % n
        while not on[j]:
            j = (j + 1) % n
        tags[i] = TAG_CONIC if kinds[j] == "qcurve" else TAG_CUBIC
    return tags


def master_scalars(model, location: dict) -> list[float]:
    """Each master's weight at a normalized location, in the model's master order.

    ``model.getMasterScalars`` where fontTools has it; the same sum otherwise.
    """
    method = getattr(model, "getMasterScalars", None)
    if method is not None:
        return list(method(location))
    out = list(model.getScalars(location))  # pragma: no cover - older fontTools
    for i, weights in reversed(list(enumerate(model.deltaWeights))):  # pragma: no cover
        for j, weight in weights.items():
            out[j] -= out[i] * weight
    return [out[model.mapping[i]] for i in range(len(out))]  # pragma: no cover


def master_scalars_at(model, locations: Sequence[dict]) -> np.ndarray:
    """`master_scalars` at many locations at once: (locations, masters).

    The same products as fontTools' ``supportScalar`` (OpenType rules, no
    extrapolation) and the same sums as ``getMasterScalars``, over arrays.
    """
    if getattr(model, "extrapolate", False):  # pragma: no cover - not what a build does
        return np.array([master_scalars(model, loc) for loc in locations], dtype=float)
    axes = list(model.axisOrder or [])
    for support in model.supports:
        axes.extend(axis for axis in support if axis not in axes)
    column = {axis: i for i, axis in enumerate(axes)}
    values = np.zeros((len(locations), len(axes)))
    for row, location in enumerate(locations):
        for axis, value in location.items():
            if axis in column:
                values[row, column[axis]] = value
    scalars = np.ones((len(locations), len(model.supports)))
    with np.errstate(divide="ignore", invalid="ignore"):
        for r, support in enumerate(model.supports):
            for axis, (lower, peak, upper) in support.items():
                if peak == 0.0 or lower > peak or peak > upper or (lower < 0.0 and upper > 0.0):
                    continue
                v = values[:, column[axis]]
                ratio = np.where(
                    v < peak, (v - lower) / (peak - lower), (v - upper) / (peak - upper)
                )
                factor = np.where(v == peak, 1.0, np.where((v <= lower) | (upper <= v), 0.0, ratio))
                scalars[:, r] *= factor
    for i, weights in reversed(list(enumerate(model.deltaWeights))):
        for j, weight in weights.items():
            scalars[:, j] -= scalars[:, i] * weight
    return scalars[:, [model.mapping[i] for i in range(len(model.mapping))]]


# =============================================================================
# Outline structure: flattening as a linear map of the control points
# =============================================================================


@dataclass
class _Outline:
    """The flattened outline as a linear map of the glyph's points.

    Bezier points at fixed parameters are linear in the control points, so
    ``vertices = F @ points`` for any location: build once per glyph.
    """

    F: np.ndarray  # (vertices, points)
    edge_a: np.ndarray  # (edges,) vertex index of each edge's start
    edge_b: np.ndarray  # (edges,) vertex index of each edge's end
    edge_contour: np.ndarray  # (edges,) contour of each edge
    edge_segment: np.ndarray  # (edges,) segment id of each edge
    # [(point index, contour, index in contour, seg_in, seg_out,
    #   prev_v, v, next_v, prev_on_v, next_on_v)]
    on_points: list


def _bezier(controls: list[np.ndarray], t: float) -> np.ndarray:
    """The Bezier point at ``t``, as weights over the glyph's points (de Casteljau)."""
    n = len(controls) - 1
    work = [c.copy() for c in controls]
    for r in range(1, n + 1):
        for i in range(n - r + 1):
            work[i] = (1 - t) * work[i] + t * work[i + 1]
    return work[0]


def _steps(controls: list[np.ndarray], masters: np.ndarray) -> int:
    """Segments enough for `PRECISION`, from the second differences in every master."""
    degree = len(controls) - 1
    if degree < 2:
        return 1
    worst = 0.0
    for i in range(degree - 1):
        # second difference of the control polygon, in every master
        second = controls[i] - 2 * controls[i + 1] + controls[i + 2]  # weights over points
        diff = np.einsum("p,mpk->mk", second, masters)
        worst = max(worst, float(np.max(np.hypot(diff[:, 0], diff[:, 1]))))
    # |B''| <= degree (degree - 1) max|second difference|; chord error <= |B''| / (8 n^2)
    bound = degree * (degree - 1) * worst
    steps = math.ceil(math.sqrt(bound / (8 * PRECISION))) if bound > 0 else 1
    return max(1, min(_MAX_STEPS, steps))


def _build_outline(contours: np.ndarray, tags: np.ndarray, masters: np.ndarray) -> _Outline:
    count = len(tags)
    unit = np.eye(count)
    rows: list[np.ndarray] = []
    edge_a: list[int] = []
    edge_b: list[int] = []
    edge_contour: list[int] = []
    edge_segment: list[int] = []
    on_points = []
    segment_id = 0

    start = 0
    for contour_index, end in enumerate(contours):
        indices = list(range(start, int(end) + 1))
        start = int(end) + 1
        if len(indices) < 2:
            continue
        on = [i for i in indices if tags[i] == TAG_ON]
        first_vertex = len(rows)

        if not on:
            # All off-curve (TrueType): quadratics between implied midpoints
            n = len(indices)
            mids = [(unit[indices[k]] + unit[indices[(k + 1) % n]]) / 2 for k in range(n)]
            pieces = [[(mids[k - 1], unit[indices[k]], mids[k])] for k in range(n)]
            segment_starts = [None] * n
        else:
            r = indices.index(on[0])
            order = indices[r:] + indices[:r]
            pieces = []
            segment_starts = []
            k = 0
            while k < len(order):
                s = order[k]
                offs = []
                k += 1
                while k < len(order) and tags[order[k]] != TAG_ON:
                    offs.append(order[k])
                    k += 1
                e = order[k] if k < len(order) else order[0]
                S, E = unit[s], unit[e]
                if not offs:
                    curves = [(S, E)]
                elif tags[offs[0]] == TAG_CONIC or len(offs) == 1:
                    # Quadratic chain with implied on-curve points
                    curves = []
                    prev = S
                    for j, o in enumerate(offs):
                        nxt = E if j == len(offs) - 1 else (unit[o] + unit[offs[j + 1]]) / 2
                        curves.append((prev, unit[o], nxt))
                        prev = nxt
                elif len(offs) == 2:
                    curves = [(S, unit[offs[0]], unit[offs[1]], E)]
                else:
                    # A cubic "super-curve": through its control points (rare)
                    chain = [S] + [unit[o] for o in offs] + [E]
                    curves = [(chain[j], chain[j + 1]) for j in range(len(chain) - 1)]
                pieces.append(curves)
                segment_starts.append(s)

        # Vertices: each segment emits its points after its start; the start
        # of the next segment is the end of this one.
        segment_ids = []
        for curves, _s in zip(pieces, segment_starts, strict=True):
            seg_vertices_start = len(rows)
            rows.append(curves[0][0])  # the segment's start
            for controls in curves:
                n = _steps(list(controls), masters)
                for j in range(1, n + 1):
                    if j == n:
                        rows.append(controls[-1])
                    else:
                        rows.append(_bezier(list(controls), j / n))
            rows.pop()  # the end is the next segment's start
            segment_ids.append((segment_id, seg_vertices_start, len(rows)))
            segment_id += 1

        last_vertex = len(rows)
        vertex_count = last_vertex - first_vertex
        if vertex_count < 2:
            continue
        for sid, v0, v1 in segment_ids:
            for v in range(v0, v1):
                a = v
                b = v + 1 if v + 1 < last_vertex else first_vertex
                edge_a.append(a)
                edge_b.append(b)
                edge_contour.append(contour_index)
                edge_segment.append(sid)

        # On-curve points: their vertex, neighbours and own two segments
        n_seg = len(segment_ids)
        contour_start = indices[0]
        for k, s in enumerate(segment_starts):
            if s is None:
                continue
            if n_seg < 2:
                continue  # a contour of one segment: nothing to bury a point in
            sid_out, v0, v1 = segment_ids[k]
            sid_in, w0, _w1 = segment_ids[k - 1]
            prev_v = v0 - 1 if v0 > first_vertex else last_vertex - 1
            next_v = v0 + 1 if v0 + 1 < last_vertex else first_vertex
            next_on_v = v1 if v1 < last_vertex else first_vertex
            on_points.append(
                (
                    s,
                    contour_index,
                    s - contour_start,
                    sid_in,
                    sid_out,
                    prev_v,
                    v0,
                    next_v,
                    w0,
                    next_on_v,
                )
            )

    return _Outline(
        F=np.array(rows, dtype=np.float64) if rows else np.zeros((0, count)),
        edge_a=np.array(edge_a, dtype=np.int64),
        edge_b=np.array(edge_b, dtype=np.int64),
        edge_contour=np.array(edge_contour, dtype=np.int64),
        edge_segment=np.array(edge_segment, dtype=np.int64),
        on_points=on_points,
    )


# =============================================================================
# Depth of points, for many locations at once
# =============================================================================


def _winding(q: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Nonzero winding of points ``q`` (L, 2) against edges ``a→b`` (L, E, 2)."""
    qx, qy = q[:, None, 0], q[:, None, 1]
    ax, ay, bx, by = a[..., 0], a[..., 1], b[..., 0], b[..., 1]
    cross = (bx - ax) * (qy - ay) - (qx - ax) * (by - ay)
    up = (ay <= qy) & (by > qy) & (cross > 0)
    down = (ay > qy) & (by <= qy) & (cross < 0)
    return up.sum(axis=1) - down.sum(axis=1)


def _nearest(q: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Distance from ``q`` (L, 2) to the nearest of the edges ``a→b`` (L, E, 2): (L,).

    Squared distances, and one square root per location: the root of the
    smallest square is the smallest distance.
    """
    ax, ay = a[..., 0], a[..., 1]
    dx, dy = b[..., 0] - ax, b[..., 1] - ay
    wx, wy = q[:, None, 0] - ax, q[:, None, 1] - ay
    length2 = dx * dx + dy * dy
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(length2 > 0, (wx * dx + wy * dy) / length2, 0.0)
    np.clip(t, 0.0, 1.0, out=t)
    ex = wx - t * dx
    ey = wy - t * dy
    return np.sqrt((ex * ex + ey * ey).min(axis=1))


def _depths(vertices: np.ndarray, outline: _Outline, entry, bounds=None) -> np.ndarray:
    """Depth of one on-curve point at each location (see the module docstring).

    ``vertices``: (L, V, 2). NaN where the point coincides with the vertex
    before it, or has no edge but its own to measure to. ``bounds``: each
    vertex's (min, max) over the locations, when the caller has them.
    """
    (_point, _contour, _index, sid_in, sid_out, prev_v, v, _next_v, _prev_on, _next_on) = entry
    p = vertices[:, v]
    d1 = p - vertices[:, prev_v]
    length = np.hypot(d1[:, 0], d1[:, 1])
    valid = length > 0
    u = d1 / np.where(valid, length, 1)[:, None]

    # Only edges that can matter: those crossing the ray to the right of the
    # probes (winding), and those within reach of the nearest one (distance).
    # Bounding boxes over all the locations at once; the answer is unchanged.
    vmin, vmax = bounds if bounds is not None else (vertices.min(axis=0), vertices.max(axis=0))
    emin = np.minimum(vmin[outline.edge_a], vmin[outline.edge_b])
    emax = np.maximum(vmax[outline.edge_a], vmax[outline.edge_b])
    pmin = p.min(axis=0) - _PROBE_BACK
    pmax = p.max(axis=0) + _PROBE_BACK
    ray = (emax[:, 1] >= pmin[1]) & (emin[:, 1] <= pmax[1]) & (emax[:, 0] >= pmin[0])

    own = (outline.edge_segment == sid_in) | (outline.edge_segment == sid_out)
    others = ray & ~own
    if others.any():
        nearest = _nearest(
            p, vertices[:, outline.edge_a[others]], vertices[:, outline.edge_b[others]]
        )
        reach = float(np.nanmax(nearest))
        near = ~own & np.all(emin - reach <= pmax, axis=1) & np.all(emax + reach >= pmin, axis=1)
    else:
        near = ~own  # nothing on the ray: every other edge
    if not near.any():
        return np.full(len(p), np.nan)
    distance = _nearest(p, vertices[:, outline.edge_a[near]], vertices[:, outline.edge_b[near]])

    # The probes stay closer to the point than half its distance to any other
    # edge, so they lie on the point's side of every one of them: a corner
    # 0.4 u inside a slanted stem must not have a probe half a unit back,
    # already outside the stem.
    back = np.minimum(np.minimum(_PROBE_BACK, length / 2), np.fmax(distance / 2, _PROBE_MIN))
    base = p - back[:, None] * u
    side = np.stack([u[:, 1], -u[:, 0]], axis=1) * (back * _PROBE_SIDE)[:, None]
    a = vertices[:, outline.edge_a[ray]]
    b = vertices[:, outline.edge_b[ray]]
    empty_right = _winding(base + side, a, b) == 0
    empty_left = _winding(base - side, a, b) == 0
    covered = ~empty_right & ~empty_left

    # One side empty: how wide is that wedge between the point's own segments
    normal = np.stack([u[:, 1], -u[:, 0]], axis=1)
    normal = np.where(empty_right[:, None], normal, -normal)
    own_a = vertices[:, outline.edge_a[own]]
    own_b = vertices[:, outline.edge_b[own]]
    widths = np.stack(
        [
            _ray_hit(p - np.minimum(back_at, length)[:, None] * u, normal, own_a, own_b)
            for back_at in _GAP_BACK
        ],
        axis=1,
    )
    finite = np.isfinite(widths)
    gap = np.where(finite.any(axis=1), np.where(finite, widths, 0.0).max(axis=1), np.inf)
    one_side = empty_right ^ empty_left
    out = np.where(one_side, np.minimum(distance, gap), distance)
    depth = np.where(covered, distance, -out)
    return np.where(valid, depth, np.nan)


def _ray_hit(start: np.ndarray, direction: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Distance along unit rays ``start + t·direction`` (L, 2) to the first of
    the edges ``a→b`` (L, E, 2) they cross; inf when none."""
    d = b - a
    rel = a - start[:, None, :]
    denom = direction[:, None, 0] * d[..., 1] - direction[:, None, 1] * d[..., 0]
    safe = np.where(np.abs(denom) > 1e-12, denom, 1.0)
    t = (rel[..., 0] * d[..., 1] - rel[..., 1] * d[..., 0]) / safe
    s = (rel[..., 0] * direction[:, None, 1] - rel[..., 1] * direction[:, None, 0]) / safe
    hit = (np.abs(denom) > 1e-12) & (t > 1e-6) & (s >= 0) & (s <= 1)
    return np.where(hit, t, np.inf).min(axis=1, initial=np.inf)


# =============================================================================
# Locations
# =============================================================================


#: How many axes `sample_locations` puts between grid values at once.
AXES_BETWEEN = 2


def sample_locations(
    masters: GlyphMasters, quarters: bool = True, axes_between: int | None = AXES_BETWEEN
) -> list[dict[str, float]]:
    """Normalized locations to check a glyph at (see the module docstring).

    ``quarters``: the quarters between grid values, or only the midpoints.
    ``axes_between``: at most this many axes between grid values at once;
    None for the whole product.
    """
    axis_names = list(masters.model.axisOrder or [])
    locations = [dict(loc) for loc in masters.model.origLocations]
    for loc in locations:
        for name in loc:
            if name not in axis_names:
                axis_names.append(name)
    steps = (0.25, 0.5, 0.75) if quarters else (0.5,)
    grid, between = [], []
    for name in axis_names:
        values = {0.0}
        values.update(round(float(loc.get(name, 0.0)), 9) for loc in locations)
        lo, default, hi = masters.design_axes.get(name, (0.0, 0.0, 0.0))
        if lo < default:
            values.add(-1.0)
        if hi > default:
            values.add(1.0)
        values = sorted(values)
        grid.append(values)
        between.append(
            [a + f * (b - a) for a, b in zip(values, values[1:], strict=False) for f in steps]
        )
    count = len(axis_names)
    limit = count if axes_between is None else min(axes_between, count)
    found = []
    for k in range(limit + 1):
        for off in itertools.combinations(range(count), k):
            per_axis = [between[i] if i in off else grid[i] for i in range(count)]
            found.extend(
                dict(zip(axis_names, combo, strict=True)) for combo in itertools.product(*per_axis)
            )
    return found


# =============================================================================
# The check
# =============================================================================


class BuriedPointChecker:
    """One glyph's buried points, prepared once, checked at any location.

    The outline structure and every point's state in the masters are worked
    out on construction; `at` then checks one normalized location cheaply --
    what a view does on every slider move. `buried_points_surfacing` scans
    many locations with the same preparation.
    """

    def __init__(self, masters: GlyphMasters, tolerance: float = DEFAULT_TOLERANCE):
        self.masters = masters
        self.threshold = max(float(tolerance), PRECISION)
        self.outline = _build_outline(masters.contours, masters.tags, masters.points)
        self.master_vertices = np.einsum("vp,mpk->mvk", self.outline.F, masters.points)
        # (entry, not outside per master, buried per master), for the points
        # buried in at least one master
        self.candidates: list[tuple] = []
        self.master_depths: list[np.ndarray] = []  # per candidate, per master
        if not self.outline.on_points or len(self.outline.edge_a) == 0:
            return
        for entry in self.outline.on_points:
            depth = _depths(self.master_vertices, self.outline, entry)
            buried = depth > self.threshold
            if buried.any():
                not_outside = ~(depth < -self.threshold)  # NaN: not outside
                self.candidates.append((entry, not_outside, buried))
                self.master_depths.append(depth)

    def wandering(self) -> list[WanderingPoint]:
        """Points buried in some masters and outside in others."""
        sources = self.masters.sources
        found = []
        for (entry, not_outside, buried), depth in zip(
            self.candidates, self.master_depths, strict=True
        ):
            if not_outside.all():
                continue
            outside = sorted(
                ((sources[i], float(-depth[i])) for i in np.nonzero(~not_outside)[0]),
                key=lambda item: -item[1],
            )
            hiding = tuple(s for s, b in zip(sources, buried, strict=True) if b)
            found.append(WanderingPoint(entry[1], entry[2], hiding, tuple(outside)))
        return found

    def at(self, normalized_location: dict[str, float]) -> list[tuple[int, int, float, tuple]]:
        """The points that come out at one location: ``[(contour, point,
        how far out, (x, y))]``, worst first."""
        if not self.candidates:
            return []
        weights = np.asarray(master_scalars(self.masters.model, normalized_location), dtype=float)
        contributing = np.abs(weights) > _WEIGHT_EPSILON
        vertices = np.einsum("m,mvk->vk", weights, self.master_vertices)[None]
        found = []
        for entry, not_outside, _buried in self.candidates:
            if (contributing & ~not_outside).any():
                continue  # a master there keeps the point outside: accepted
            depth = float(_depths(vertices, self.outline, entry)[0])
            if depth < -self.threshold:
                x, y = vertices[0, entry[6]]
                found.append((entry[1], entry[2], -depth, (float(x), float(y))))
        found.sort(key=lambda item: -item[2])
        return found


def buried_points_surfacing(
    masters: GlyphMasters,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    quarters: bool = True,
    locations: list[dict[str, float]] | None = None,
    weights: np.ndarray | None = None,
    checker: BuriedPointChecker | None = None,
) -> list[SurfacingPoint]:
    """Buried points of one glyph that come out at a sampled location, worst first.

    ``weights`` (locations × masters) may be passed when several glyphs share
    the masters and the locations; ``checker`` when the glyph's is prepared
    already (built with ``tolerance``).
    """
    if checker is None:
        checker = BuriedPointChecker(masters, tolerance)
    candidates = checker.candidates
    if not candidates:
        return []
    threshold = checker.threshold
    outline = checker.outline
    master_vertices = checker.master_vertices

    if locations is None:
        locations = sample_locations(masters, quarters)
    if weights is None:
        weights = master_scalars_at(masters.model, locations)

    count = len(candidates)
    worst = np.zeros(count)
    worst_index = np.full(count, -1)
    surfacing = np.zeros(count, dtype=np.int64)
    checked = np.zeros(count, dtype=np.int64)
    flat_vertices = master_vertices.reshape(len(master_vertices), -1)

    for begin in range(0, len(locations), _CHUNK):
        w = weights[begin : begin + _CHUNK]
        contributing = np.abs(w) > _WEIGHT_EPSILON
        checks = [
            ~(contributing & ~not_outside[None, :]).any(axis=1)
            for _entry, not_outside, _buried in candidates
        ]
        wanted = np.logical_or.reduce(checks)
        if not wanted.any():
            continue
        rows = np.nonzero(wanted)[0]
        # One matrix product per chunk, shared by every candidate
        vertices = (w[rows] @ flat_vertices).reshape(len(rows), *master_vertices.shape[1:])
        bounds = None
        for k, (entry, _not_outside, _buried) in enumerate(candidates):
            mine = checks[k][rows]
            if not mine.any():
                continue
            if mine.all():  # usually: no copy of the vertices, and shared bounds
                if bounds is None:
                    bounds = (vertices.min(axis=0), vertices.max(axis=0))
                depth = _depths(vertices, outline, entry, bounds)
            else:
                depth = _depths(vertices[mine], outline, entry)
            outside = depth < -threshold
            checked[k] += int(mine.sum())
            surfacing[k] += int(outside.sum())
            if outside.any():
                i = int(np.nanargmin(np.where(outside, depth, np.inf)))
                if -depth[i] > worst[k]:
                    worst[k] = float(-depth[i])
                    worst_index[k] = begin + int(rows[np.nonzero(mine)[0][i]])

    results = []
    for k, (entry, _not_outside, buried) in enumerate(candidates):
        if surfacing[k]:
            hiding = tuple(s for s, b in zip(masters.sources, buried, strict=True) if b)
            results.append(
                SurfacingPoint(
                    contour=entry[1],
                    point=entry[2],
                    depth=float(worst[k]),
                    location=dict(locations[int(worst_index[k])]),
                    surfacing=int(surfacing[k]),
                    checked=int(checked[k]),
                    masters_buried=hiding,
                )
            )
    # worst first; ties (to a millionth of a unit) by contour and point
    results.sort(key=lambda p: (-round(p.depth, 6), p.contour, p.point))
    return results


def point_at(
    masters: GlyphMasters, normalized_location: dict[str, float], contour: int, point: int
) -> tuple[float, float]:
    """Where point ``point`` of contour ``contour`` lies at a normalized location."""
    start = 0 if contour == 0 else int(masters.contours[contour - 1]) + 1
    weights = np.asarray(master_scalars(masters.model, normalized_location), dtype=float)
    x, y = weights @ masters.points[:, start + point]
    return float(x), float(y)
