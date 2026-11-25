# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
How a master's contour lines up with the reference master's, point by point.

varLib pairs the points of a contour by index. Two masters can draw the same
contour from another start point, or the other way round; paired by index,
each point then travels to the wrong partner. When the curve types along the
contour differ only because of that, the structural checks see "different
curve types" (4.5, 4.9), and the masters as drawn do not build; read from
another start, they would. A contour that runs the other way keeps the
structure and shows as another direction (4.8) -- unless it overlaps itself
and its parts nearly cancel, when the sign of its area says nothing.

`align_contour` answers both: of the readings of the target contour whose
curve types match the reference's, which one puts its points closest to the
reference's. Both contours are scaled into their own bounding box first, so a
bold or a wide master compares with a light or a narrow one.

It is public so that a host's fix can call it and never disagree with the
check (as `canonical_component_order` is for 4.20).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

#: One point: x, y and the UFO point type ("line", "curve", "qcurve", "move"
#: for an on-curve point, None or "offcurve" for an off-curve one).
Point = tuple[float, float, "str | None"]


@dataclass(frozen=True)
class Alignment:
    """A reading of the target contour, and how far it lands from the reference."""

    #: Index into the target contour's points as drawn (in the UFO, before
    #: any change) where the reading starts.
    start: int
    #: True when the reading goes backwards: points start, start-1, start-2, ...
    reversed: bool
    #: Mean squared distance of the paired points, each contour scaled into
    #: its own bounding box (0..1 both ways); 0 is a perfect match.
    distance: float

    @property
    def is_identity(self) -> bool:
        """Whether the contour reads best as drawn."""
        return self.start == 0 and not self.reversed


def _on_curve(kind) -> bool:
    return kind is not None and kind != "offcurve"


def _reversed_types(types: Sequence) -> list:
    """The point types of the contour drawn the other way, in original order.

    An on-curve point's type names the segment that ends at it. Read
    backwards, that segment ends at the previous on-curve point instead, so
    each on-curve point takes the type of the next on-curve point.
    """
    n = len(types)
    on = [i for i in range(n) if _on_curve(types[i])]
    result = list(types)
    for a, b in zip(on, on[1:] + on[:1], strict=True):
        result[a] = types[b]
    return result


def _normalized(points: Sequence[Point]) -> list[tuple[float, float]]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, y0 = min(xs), min(ys)
    w = (max(xs) - x0) or 1.0
    h = (max(ys) - y0) or 1.0
    return [((x - x0) / w, (y - y0) / h) for x, y in zip(xs, ys, strict=True)]


def readings(reference: Sequence[Point], target: Sequence[Point]) -> list[Alignment]:
    """Every reading of `target` whose point types match `reference`'s, best first.

    Empty when the two have different point counts or no reading matches:
    then the contours really differ, and no start point or direction fixes it.
    """
    n = len(reference)
    if n == 0 or n != len(target):
        return []
    ref_types = [_norm_type(p[2]) for p in reference]
    forward = [_norm_type(p[2]) for p in target]
    backward = _reversed_types(forward)
    ref_xy = _normalized(reference)
    tgt_xy = _normalized(target)

    found = []
    for is_reversed, types in ((False, forward), (True, backward)):
        for start in range(n):
            order = (
                [(start - i) % n for i in range(n)]
                if is_reversed
                else [(start + i) % n for i in range(n)]
            )
            if any(types[j] != ref_types[i] for i, j in enumerate(order)):
                continue
            distance = (
                sum(
                    (ref_xy[i][0] - tgt_xy[j][0]) ** 2 + (ref_xy[i][1] - tgt_xy[j][1]) ** 2
                    for i, j in enumerate(order)
                )
                / n
            )
            found.append(Alignment(start, is_reversed, distance))
    found.sort(key=lambda a: (a.distance, a.reversed, a.start))
    return found


def _norm_type(kind):
    return None if kind == "offcurve" else kind


def align_contour(reference: Sequence[Point], target: Sequence[Point]) -> Alignment | None:
    """The reading of `target` that lines up best with `reference`, or None.

    None when no reading has the reference's point types. An open contour
    (starting with "move") has a fixed start and direction; pass closed ones.
    """
    found = readings(reference, target)
    return found[0] if found else None


__all__ = ["Alignment", "Point", "align_contour", "readings"]
