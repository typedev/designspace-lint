# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Which way each contour of a glyph should run, and what it costs when it does not.

Every renderer fills a glyph by the nonzero rule: at each point, each contour
around it adds 1 or -1 by its direction, and the point is ink unless the sum
is 0. A counter is a hole because it runs against its outer contour; two
pieces of ink that overlap stay ink only when they run the same way. A piece
drawn the other way cuts a hole wherever it overlaps ink -- a cedilla cuts
into its C, the bar of a drawn Ħ cuts two holes in the stems -- in the
variable font (TrueType and CFF2), in a static font that keeps its overlaps,
and baked into the outline by a CFF build that removes them.

The convention, for a UFO built by ufo2ft: outer contours run
counter-clockwise, counters clockwise, islands inside counters
counter-clockwise again -- PostScript's direction, for both formats. ufo2ft
writes a CFF font as drawn and reverses the contours of a TrueType one
itself (``reverseDirection``, fontmake ``--keep-direction``), so a UFO drawn
in TrueType's direction comes out against each format's own convention
(FontBakery's ``outline_direction`` warns on the TrueType font).

`contour_roles` decides each contour's expected direction from where it lies:
the number of contours it lies entirely inside (crossing none of their
edges) is its depth, even for ink, odd for a hole. A contour that crosses
another is not inside it, so a bar across a stem or a slash through an O is
ink, as it should be. One case is not settled by depth: a contour that
crosses another of the same odd depth, such as a bar that ends inside an
O's ring and crosses its counter. Of two such, one is ink and one a hole, so
they must run opposite ways; when they do not, and one of them belongs to a
component (whose own glyph is judged on its own), the glyph's contour is the
one that is wrong; when both are the glyph's own, the pair is reported.
A contour that crosses itself has no direction and is not judged.

It is public so that a host's fix can call it and never disagree with the
check (as `canonical_component_order` is for 4.20).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence

__all__ = [
    "ContourRole",
    "Hole",
    "Piece",
    "component_pieces",
    "contour_roles",
    "crossing_pairs",
    "expected_directions",
    "flatten",
    "lost_ink",
    "read_outline",
    "signed_area",
]

#: A contour as the UFO draws it: (x, y, segmentType), None for off-curve.
Point = tuple

#: Below this many square units a contour is too small to have a direction.
_MIN_AREA = 1.0
# Longest chord of a flattened curve, roughly, in font units.
_CHORD = 12.0
_MAX_STEPS = 32


def _on(kind) -> bool:
    return kind not in (None, "offcurve")


def _quad(p0, c, p1, steps):
    return [
        (
            (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p1[0],
            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p1[1],
        )
        for t in (i / steps for i in range(1, steps + 1))
    ]


def _cubic(p0, c1, c2, p1, steps):
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        out.append(
            (
                u**3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * p1[0],
                u**3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * p1[1],
            )
        )
    return out


def _steps(points) -> int:
    length = sum(math.dist(a, b) for a, b in zip(points, points[1:], strict=False))
    return max(2, min(_MAX_STEPS, int(length / _CHORD) + 1))


def flatten(contour: Sequence[Point]) -> list[tuple[float, float]]:
    """The contour as a closed polygon, its curves cut into short chords.

    An open contour is closed with a straight line, as every compiler closes
    it. Quadratic curves take their implied on-curve points; a contour of
    off-curve points only is a closed quadratic curve.
    """
    pts = [(float(p[0]), float(p[1]), p[2]) for p in contour]
    n = len(pts)
    if n == 0:
        return []
    on = [i for i, p in enumerate(pts) if _on(p[2])]
    if not on:
        out = []
        for i in range(n):
            a, c, b = pts[i - 1], pts[i], pts[(i + 1) % n]
            p0 = ((a[0] + c[0]) / 2, (a[1] + c[1]) / 2)
            p1 = ((c[0] + b[0]) / 2, (c[1] + b[1]) / 2)
            out.extend(_quad(p0, c[:2], p1, _steps([p0, c[:2], p1])))
        return out
    order = pts[on[0] :] + pts[: on[0]]
    out = [order[0][:2]]
    i = 1
    while i <= len(order):
        offs = []
        while i < len(order) and not _on(order[i][2]):
            offs.append(order[i][:2])
            i += 1
        end = order[i] if i < len(order) else order[0]
        start = out[-1]
        target = end[:2]
        if not offs:
            out.append(target)
        elif end[2] == "qcurve" or len(offs) == 1:
            prev = start
            for j, c in enumerate(offs):
                nxt = (
                    target
                    if j == len(offs) - 1
                    else ((c[0] + offs[j + 1][0]) / 2, (c[1] + offs[j + 1][1]) / 2)
                )
                out.extend(_quad(prev, c, nxt, _steps([prev, c, nxt])))
                prev = nxt
        elif len(offs) == 2:
            out.extend(_cubic(start, offs[0], offs[1], target, _steps([start, *offs, target])))
        else:  # a cubic "super-curve": through its control points (rare)
            out.extend(offs)
            out.append(target)
        i += 1
    if len(out) > 1 and out[-1] == out[0]:
        out.pop()
    return out


def signed_area(polygon: Sequence[tuple[float, float]]) -> float:
    """The shoelace area: positive when the polygon runs counter-clockwise."""
    total = 0.0
    n = len(polygon)
    for i in range(n):
        x0, y0 = polygon[i - 1]
        x1, y1 = polygon[i]
        total += x0 * y1 - x1 * y0
    return total / 2


def _bbox(polygon):
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return (min(xs), min(ys), max(xs), max(ys))


def _overlap(a, b) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def _inside_box(a, b) -> bool:
    return b[0] <= a[0] and b[1] <= a[1] and a[2] <= b[2] and a[3] <= b[3]


def _winding(polygon, x, y) -> int:
    w = 0
    n = len(polygon)
    for i in range(n):
        ax, ay = polygon[i - 1]
        bx, by = polygon[i]
        if ay <= y < by:
            if (bx - ax) * (y - ay) - (x - ax) * (by - ay) > 0:
                w += 1
        elif by <= y < ay:
            if (bx - ax) * (y - ay) - (x - ax) * (by - ay) < 0:
                w -= 1
    return w


def _edges_in(polygon, box):
    """The polygon's edges whose bounding boxes meet ``box``."""
    found = []
    n = len(polygon)
    for i in range(n):
        a, b = polygon[i - 1], polygon[i]
        if (
            min(a[0], b[0]) <= box[2]
            and box[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= box[3]
            and box[1] <= max(a[1], b[1])
        ):
            found.append((a, b))
    return found


def _orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _proper(a, b, c, d) -> bool:
    """Whether segments ab and cd cross (touching or running along does not count)."""
    return (_orient(a, b, c) * _orient(a, b, d) < 0) and (_orient(c, d, a) * _orient(c, d, b) < 0)


def _crosses(pa, box_a, pb, box_b) -> bool:
    if not _overlap(box_a, box_b):
        return False
    common = (
        max(box_a[0], box_b[0]),
        max(box_a[1], box_b[1]),
        min(box_a[2], box_b[2]),
        min(box_a[3], box_b[3]),
    )
    ea = _edges_in(pa, common)
    if not ea:
        return False
    eb = _edges_in(pb, common)
    for a, b in ea:
        lo_x, hi_x = min(a[0], b[0]), max(a[0], b[0])
        lo_y, hi_y = min(a[1], b[1]), max(a[1], b[1])
        for c, d in eb:
            if (
                max(c[0], d[0]) < lo_x
                or min(c[0], d[0]) > hi_x
                or max(c[1], d[1]) < lo_y
                or min(c[1], d[1]) > hi_y
            ):
                continue
            if _proper(a, b, c, d):
                return True
    return False


def _self_intersects(polygon) -> bool:
    n = len(polygon)
    edges = [(polygon[i - 1], polygon[i]) for i in range(n)]
    boxes = [(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])) for a, b in edges]
    order = sorted(range(n), key=lambda i: boxes[i][0])
    active: list[int] = []
    for i in order:
        box = boxes[i]
        active = [j for j in active if boxes[j][2] >= box[0]]
        for j in active:
            if abs(i - j) in (1, n - 1):
                continue  # neighbours share a point
            other = boxes[j]
            if other[1] > box[3] or box[1] > other[3]:
                continue
            if _proper(*edges[i], *edges[j]):
                return True
        active.append(i)
    return False


@dataclass
class ContourRole:
    """What one contour of a glyph is, and which way it should run."""

    #: Index of the contour in the glyph, from 0.
    contour: int
    #: "outer" (depth 0), "counter" (odd depth) or "island" (even depth inside a counter).
    role: str
    #: How many contours it lies entirely inside.
    depth: int
    #: 1 for counter-clockwise, -1 for clockwise: the way it runs as drawn (0: no area).
    actual: int
    #: The way it should run.
    expected: int
    #: Whether it was judged at all; see `reason` when not.
    judged: bool = True
    #: Why not: "no area" or "crosses itself"; for a judged contour that crosses
    #: one of its own depth, "crossing": it must run opposite to that one.
    reason: str = ""
    #: For "crossing": the contours (own indexes) it crosses at its own depth.
    crosses: list[int] = field(default_factory=list)
    #: The contour it lies directly inside: an index into the glyph's own
    #: contours, then into ``context`` (offset by their count); None for an
    #: outer contour.
    container: int | None = None

    @property
    def wrong(self) -> bool:
        """Judged, and running the other way."""
        return self.judged and self.actual != 0 and self.actual != self.expected


def contour_roles(
    contours: Sequence[Sequence[Point]],
    context: Iterable[Sequence[tuple[float, float]]] = (),
    clockwise_outer: bool = False,
    every_crossing: bool = False,
) -> list[ContourRole]:
    """Each contour's role and expected direction (see the module docstring).

    ``contours``: the glyph's own contours, each a list of (x, y, segmentType).
    ``context``: polygons of the glyph's components, decomposed (see
    `flatten`): they count for depth and as crossing partners, and are not
    judged here -- their own glyph is. ``clockwise_outer``: the masters are
    drawn in TrueType's direction, so every expectation turns round.
    ``every_crossing``: test every contour for crossing itself, not only the
    ones that run the wrong way (all a check needs to know).
    """
    own = [flatten(c) for c in contours]
    others = [list(p) for p in context if len(p) >= 3]
    polys = own + others
    boxes = [_bbox(p) if len(p) >= 3 else None for p in polys]
    areas = [signed_area(p) if len(p) >= 3 else 0.0 for p in polys]
    count_own = len(own)
    outer = -1 if clockwise_outer else 1

    crossing: dict[tuple[int, int], bool] = {}

    def crosses(i, j) -> bool:
        key = (min(i, j), max(i, j))
        if key not in crossing:
            crossing[key] = _crosses(polys[i], boxes[i], polys[j], boxes[j])
        return crossing[key]

    depth = [0] * len(polys)
    container: list[int | None] = [None] * len(polys)
    for i, poly in enumerate(polys):
        if boxes[i] is None:
            continue
        for j, other in enumerate(polys):
            if i == j or boxes[j] is None or not _inside_box(boxes[i], boxes[j]):
                continue
            if abs(areas[j]) < abs(areas[i]):
                continue  # a smaller contour cannot hold a larger one
            if crosses(i, j):
                continue
            if _winding(other, *poly[0]) != 0:
                depth[i] += 1
                held = container[i]
                if held is None or abs(areas[j]) < abs(areas[held]):
                    container[i] = j  # the smallest that holds it

    roles = []
    for i in range(count_own):
        d = depth[i]
        actual = 0 if abs(areas[i]) < _MIN_AREA else (1 if areas[i] > 0 else -1)
        role = "outer" if d == 0 else "counter" if d % 2 else "island"
        expected = outer if d % 2 == 0 else -outer
        entry = ContourRole(i, role, d, actual, expected, container=container[i])
        if actual == 0:
            entry.judged, entry.reason = False, "no area"
        elif d % 2:
            peers = [
                j
                for j in range(len(polys))
                if j != i and boxes[j] is not None and depth[j] == d and crosses(i, j)
            ]
            if peers:
                entry.reason = "crossing"
                entry.crosses = [j for j in peers if j < count_own]
                # it must run opposite to what it crosses: a component's
                # contour is judged in its own glyph, so it is the reference
                theirs = [j for j in peers if j >= count_own and areas[j]]
                if theirs:
                    entry.expected = -(1 if areas[theirs[0]] > 0 else -1)
                else:
                    entry.judged = False  # own pairs: see crossing_pairs
        roles.append(entry)
    for entry in roles:
        if (entry.wrong or (every_crossing and entry.judged)) and _self_intersects(
            own[entry.contour]
        ):
            entry.judged, entry.reason = False, "crosses itself"
    return roles


def crossing_pairs(roles: Sequence[ContourRole]) -> list[tuple[int, int]]:
    """Own contours of one odd depth that cross each other and run the same way.

    Of two such, one is ink and one a hole, so they should run opposite ways;
    which one is reversed is the designer's to say (or two counters overlap,
    which no direction fixes).
    """
    by_index = {r.contour: r for r in roles}
    pairs = []
    for r in roles:
        if r.reason != "crossing" or r.judged:
            continue
        for j in r.crosses:
            other = by_index.get(j)
            if other is None or j < r.contour or other.reason == "crosses itself":
                continue
            if r.actual and r.actual == other.actual:
                pairs.append((r.contour, j))
    return sorted(set(pairs))


@dataclass(frozen=True)
class Hole:
    """Ink two parts of a glyph cancel out where they overlap."""

    #: Square font units, measured along horizontal lines.
    area: float
    #: A point inside it, the middle of its widest span.
    point: tuple[float, float]
    #: (xMin, yMin, xMax, yMax) of what was measured.
    bbox: tuple[float, float, float, float]
    #: One part lies entirely inside the other's ink, so what cancels is the
    #: inner part's whole shape: a knockout (a white digit in a black
    #: circle), drawn so on purpose, not a part cutting into another.
    knockout: bool = False


#: Below this many square units, or on fewer than two scan lines, two parts
#: only touch: an edge drawn on another, or the error of flattening curves.
MIN_HOLE = 4.0


def lost_ink(
    part: Sequence[Sequence[tuple[float, float]]],
    rest: Sequence[Sequence[tuple[float, float]]],
) -> Hole | None:
    """Where ``part`` and ``rest`` cancel each other out, or None.

    Lost ink is where one of them alone is ink and the two together are not
    (their windings sum to 0). Scanned along horizontal lines across the
    region where they overlap. A hole where one part lies entirely inside the
    other's ink is a knockout (`Hole.knockout`).
    """
    part = [p for p in part if len(p) >= 3]
    rest = [p for p in rest if len(p) >= 3]
    if not part or not rest:
        return None
    a = _union_box([_bbox(p) for p in part])
    b = _union_box([_bbox(p) for p in rest])
    if not _overlap(a, b):
        return None
    y0, y1 = max(a[1], b[1]), min(a[3], b[3])
    height = y1 - y0
    if height <= 0:
        return None
    step = min(4.0, max(1.0, height / 100))
    edges = []
    for side, polys in ((0, part), (1, rest)):
        for poly in polys:
            n = len(poly)
            for i in range(n):
                (ax, ay), (bx, by) = poly[i - 1], poly[i]
                if ay == by or max(ay, by) < y0 or min(ay, by) > y1:
                    continue
                # (bottom, top, x at the bottom, dx/dy, side, +1 upwards / -1 downwards)
                if ay < by:
                    edges.append((ay, by, ax, (bx - ax) / (by - ay), side, 1))
                else:
                    edges.append((by, ay, bx, (ax - bx) / (ay - by), side, -1))
    # a sweep: each line looks only at the edges that span it
    edges.sort()
    waiting = 0
    active: list[tuple] = []
    area = 0.0
    outside = [0.0, 0.0]  # ink of the part where the rest is empty, and the other way
    best = (0.0, None)
    lines = 0
    box = [math.inf, math.inf, -math.inf, -math.inf]
    y = y0 + step / 2
    while y < y1:
        hit = False
        while waiting < len(edges) and edges[waiting][0] <= y:
            active.append(edges[waiting])
            waiting += 1
        active = [e for e in active if y < e[1]]
        events = sorted(
            (x + (y - bottom) * slope, side, d) for bottom, _top, x, slope, side, d in active
        )
        windings = [0, 0]
        for k in range(len(events) - 1):
            x, side, d = events[k]
            windings[side] += d
            span = events[k + 1][0] - x
            if span > 0 and bool(windings[0]) != bool(windings[1]):
                outside[0 if windings[0] else 1] += span * step
            if span > 0 and windings[0] + windings[1] == 0 and (windings[0] or windings[1]):
                area += span * step
                hit = True
                box = [min(box[0], x), min(box[1], y), max(box[2], x + span), max(box[3], y)]
                if span > best[0]:
                    best = (span, (x + span / 2, y))
        lines += hit
        y += step
    if area < MIN_HOLE or lines < 2:
        return None
    half = step / 2
    knockout = (_inside_box(b, a) and outside[1] < MIN_HOLE) or (
        _inside_box(a, b) and outside[0] < MIN_HOLE
    )
    return Hole(
        round(area, 1),
        (round(best[1][0], 1), round(best[1][1], 1)),
        (round(box[0], 1), round(box[1] - half, 1), round(box[2], 1), round(box[3] + half, 1)),
        knockout,
    )


def _union_box(boxes):
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


# =============================================================================
# Glyphs: reading them, and their components laid out
# =============================================================================


def read_outline(glyph) -> tuple[list[list[Point]], list[tuple[str, tuple]]]:
    """A glyph's contours as (x, y, segmentType) lists, and its components as
    (base glyph, transformation): drawn through defcon when there is one under
    a fontParts glyph, which skips fontParts' wrappers."""
    from fontTools.pens.recordingPen import RecordingPointPen

    pen = RecordingPointPen()
    naked = getattr(glyph, "naked", None)
    source = naked() if callable(naked) else None
    (source if source is not None and hasattr(source, "drawPoints") else glyph).drawPoints(pen)
    contours, components, current = [], [], None
    for method, args, kwargs in pen.value:
        if method == "beginPath":
            current = []
        elif method == "addPoint":
            kind = args[1] if len(args) > 1 else kwargs.get("segmentType")
            current.append((args[0][0], args[0][1], kind))
        elif method == "endPath":
            contours.append(current)
        elif method == "addComponent":
            transformation = args[1] if len(args) > 1 else kwargs.get("transformation")
            components.append((args[0], tuple(transformation)))
    return contours, components


def _compose(outer, inner):
    a, b, c, d, e, f = outer
    a2, b2, c2, d2, e2, f2 = inner
    return (
        a * a2 + c * b2,
        b * a2 + d * b2,
        a * c2 + c * d2,
        b * c2 + d * d2,
        a * e2 + c * f2 + e,
        b * e2 + d * f2 + f,
    )


def _apply(t, polygon):
    a, b, c, d, e, f = t
    return [(a * x + c * y + e, b * x + d * y + f) for x, y in polygon]


@dataclass
class Piece:
    """One contour of a component, laid out in the composite."""

    #: Index of the composite's own component it comes through.
    component: int
    #: The glyphs from that component down to the one that draws the contour.
    path: tuple[str, ...]
    #: Index of the contour in the glyph that draws it (``path[-1]``).
    contour: int
    polygon: list[tuple[float, float]]
    #: Determinant of the whole transformation: below 0 when mirrored.
    determinant: float


def component_pieces(components, outline_of, _depth: int = 0) -> list[Piece]:
    """Every contour the components draw, decomposed and transformed.

    ``components``: (base glyph, transformation) pairs; ``outline_of(name)``
    returns a glyph's (contours, components) as `read_outline` does, or None
    for a glyph that is not there (then it draws nothing). A ring of
    components (4.24) is cut off.
    """
    pieces = []
    if _depth > 16:
        return pieces
    for index, (base, transformation) in enumerate(components):
        outline = outline_of(base)
        if outline is None:
            continue
        contours, nested = outline
        t = tuple(transformation)
        det = t[0] * t[3] - t[1] * t[2]
        for ci, contour in enumerate(contours):
            polygon = flatten(contour)
            if len(polygon) >= 3:
                pieces.append(Piece(index, (base,), ci, _apply(t, polygon), det))
        for inner in component_pieces(nested, outline_of, _depth + 1):
            pieces.append(
                Piece(
                    index,
                    (base, *inner.path),
                    inner.contour,
                    _apply(t, inner.polygon),
                    det * inner.determinant,
                )
            )
    return pieces


def expected_directions(glyph, layer, convention: str = "postscript") -> dict[int, int | None]:
    """Which way each of the glyph's own contours should run.

    ``{contour index: 1 (counter-clockwise) or -1 (clockwise)}``, by the rule
    of `contour_roles`, with the components laid out from ``layer`` (any
    mapping of glyph names to glyphs) for depth; None where the rule cannot
    say -- a contour that crosses itself, has no area, or crosses another of
    its own of the same odd depth while running the same way. Indexes are
    the UFO's. ``convention``: "postscript" (outer contours counter-clockwise,
    what ufo2ft expects) or "truetype" (the masters are drawn the other way).
    """

    def outline_of(name):
        try:
            return read_outline(layer[name])
        except (KeyError, TypeError):
            return None

    contours, components = read_outline(glyph)
    context = [piece.polygon for piece in component_pieces(components, outline_of)]
    roles = contour_roles(
        contours, context, clockwise_outer=convention == "truetype", every_crossing=True
    )
    return {r.contour: (r.expected if r.judged and r.actual else None) for r in roles}
