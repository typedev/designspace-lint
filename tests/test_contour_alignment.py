# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
A contour's start point and direction, read against the default master.

4.8 used to decide direction by the sign of the contour's area alone. A
contour that overlaps itself has no single direction, and when its parts
nearly cancel the sign is noise: one real project's contour read +52 in one
master and -11 in its siblings, while every part of it ran the same way. Now
a sign that differs from the default master's is checked by lining the
points up: the contour is reversed only when it reads best backwards.

The same lining up tells 4.5/4.9 when a contour is the reference's points
drawn from another start: still an error (the masters as drawn do not
build), but the finding says where the start should be.
"""

from designspace_lint import lint
from designspace_lint.checkers.glyphs import (
    INCOMPATIBLE_GLYPH,
    WRONG_CONTOUR_DIRECTION,
    WRONG_CURVE_TYPE,
)
from designspace_lint.contours import align_contour, readings
from designspace_lint.model import CATEGORY_GLYPHS, SEVERITY_STRUCTURAL, effective_severity
from fakes import FakeContour, FakeGlyph, FakePoint, build_designspace

AXES = [{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}]
SQUARE = [(0, 0), (100, 0), (100, 100), (0, 100)]


def _entry(light, bold):
    return build_designspace(
        axes=AXES,
        sources=[
            {"name": "Light", "location": {"Weight": 0}, "glyphs": {"a": light}},
            {"name": "Bold", "location": {"Weight": 100}, "glyphs": {"a": bold}},
        ],
    )


def _codes(entry):
    return [r for r in lint(entry) if r.category == CATEGORY_GLYPHS]


def _bow_tie(h):
    """Two lobes running opposite ways; the area's sign follows `h` past 100."""
    return FakeGlyph("a", contours=[[(0, 0), (300, 100), (300, 0), (0, h)]])


def test_a_self_overlapping_contour_whose_area_flips_sign_is_not_reversed():
    results = _codes(_entry(_bow_tie(120), _bow_tie(80)))
    assert WRONG_CONTOUR_DIRECTION not in [r.code for r in results]


def test_a_contour_drawn_the_other_way_is_still_reported_and_says_how_to_read_it():
    reversed_square = [SQUARE[0]] + SQUARE[:0:-1]
    results = _codes(
        _entry(FakeGlyph("a", contours=[SQUARE]), FakeGlyph("a", contours=[reversed_square]))
    )
    (direction,) = [r for r in results if r.code == WRONG_CONTOUR_DIRECTION]

    assert direction.raw_data["reference"] == "Light.ufo (Light)"
    assert direction.raw_data["realign"] == {
        "Bold.ufo (Bold)": {"proposedStart": 0, "reversed": True}
    }


def _d_shape(start=0):
    """A D: a stem drawn as a line, the bowl as a curve back to the start."""
    points = [
        FakePoint(0, 0, "curve"),
        FakePoint(0, 700, "line"),
        FakePoint(400, 700, "offcurve"),
        FakePoint(400, 0, "offcurve"),
    ]
    points = points[start:] + points[:start]
    return FakeGlyph("a", contours=[FakeContour(points)])


def test_a_contour_drawn_from_another_start_is_an_error_that_says_where_to_start():
    results = _codes(_entry(_d_shape(), _d_shape(start=1)))
    by_code = {r.code: r for r in results}

    assert {WRONG_CURVE_TYPE, INCOMPATIBLE_GLYPH} <= set(by_code)
    types = by_code[WRONG_CURVE_TYPE]
    assert effective_severity(types) == SEVERITY_STRUCTURAL
    # the reference's point 0 is the shifted contour's point 3, as drawn
    assert types.raw_data["realign"] == {"Bold.ufo (Bold)": {"proposedStart": 3, "reversed": False}}
    assert "starting at its point 3" in types.details
    assert by_code[INCOMPATIBLE_GLYPH].raw_data["realign"] == {
        "Bold.ufo (Bold)": [{"contour": 0, "proposedStart": 3, "reversed": False}]
    }


def test_a_contour_no_reading_matches_carries_no_hint():
    other = FakeGlyph(
        "a",
        contours=[
            FakeContour(
                [
                    FakePoint(0, 0, "line"),
                    FakePoint(0, 700, "curve"),
                    FakePoint(400, 700, "offcurve"),
                    FakePoint(400, 0, "offcurve"),
                ]
            )
        ],
    )
    # line+curve against curve+line with the handles before the curve: the
    # on/off pattern is the same, but no start or direction gives these types
    results = _codes(_entry(_d_shape(), other))
    types = [r for r in results if r.code == WRONG_CURVE_TYPE]

    assert types and "realign" not in types[0].raw_data


def test_readings_index_the_target_as_drawn():
    ref = [(x, y, "line") for x, y in SQUARE]
    rotated = ref[1:] + ref[:1]
    assert align_contour(ref, rotated).start == 3  # ref point 0 is rotated[3]
    backwards = [ref[0]] + ref[:0:-1]
    best = align_contour(ref, backwards)
    assert (best.start, best.reversed) == (0, True)
    assert best.distance == 0.0
    assert readings(ref, ref[:3]) == []  # different point counts
