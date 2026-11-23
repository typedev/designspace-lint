# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Which compatibility findings are errors: the ones a build does not survive.

Each case was built with ufo2ft 3.9 (two masters, one glyph changed, variable
TrueType and CFF2):

- 4.0, 4.3, 4.4, 4.5: the TrueType build stops in cu2qu ("fonts contains
  incompatible glyphs"), or with quadratic outlines varLib skips the glyph's
  variations ("incompatible masters; skipping") and it stays static; CFF2
  stops.
- 4.1, 4.19: TrueType skips the glyph's variations; CFF2 decomposes the
  components and silently morphs one base into another.
- 4.9 is the umbrella for the same differences.
- 4.8: both builds succeed and the glyph varies, through a twisted shape
  halfway. Worth a look, not an error.
"""

from designspace_lint.checkers.glyphs import (
    DIFFERENT_COMPONENTS,
    DIFFERENT_CONTOUR_COUNT,
    DIFFERENT_OFF_CURVES,
    DIFFERENT_ON_CURVES,
    INCOMPATIBLE_GLYPH,
    WRONG_CONTOUR_DIRECTION,
    WRONG_CURVE_TYPE,
    GlyphsChecker,
)
from designspace_lint.model import SEVERITY_DESIGN, SEVERITY_STRUCTURAL, effective_severity
from fakes import FakeGlyph, FakePoint, build_designspace

SQUARE = [(0, 0), (400, 0), (400, 400), (0, 400)]


def _severities(light, bold):
    entry = build_designspace(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}],
        sources=[
            {"name": "Light", "location": {"Weight": 0}, "glyphs": {"a": light}},
            {"name": "Bold", "location": {"Weight": 100}, "glyphs": {"a": bold}},
        ],
    )
    return {r.code: effective_severity(r) for r in GlyphsChecker(entry=entry).check()}


def test_a_different_contour_count_is_an_error():
    found = _severities(
        FakeGlyph("a", contours=[SQUARE]),
        FakeGlyph("a", contours=[SQUARE, [(500, 0), (600, 0), (600, 100)]]),
    )
    assert found[DIFFERENT_CONTOUR_COUNT] == SEVERITY_STRUCTURAL
    assert found[INCOMPATIBLE_GLYPH] == SEVERITY_STRUCTURAL


def test_a_different_on_curve_count_is_an_error():
    found = _severities(
        FakeGlyph("a", contours=[SQUARE]),
        FakeGlyph("a", contours=[[(0, 0), (200, 0), (400, 0), (400, 400), (0, 400)]]),
    )
    assert found[DIFFERENT_ON_CURVES] == SEVERITY_STRUCTURAL


def test_a_line_drawn_as_a_curve_is_an_error():
    line = [(0, 0), (0, 400), (400, 400), (400, 0)]
    curve = [
        FakePoint(0, 0),
        FakePoint(0, 400),
        FakePoint(400, 400),
        FakePoint(400, 200, "offcurve"),
        FakePoint(300, 0, "offcurve"),
        FakePoint(200, 0, "curve"),
    ]
    found = _severities(FakeGlyph("a", contours=[line]), FakeGlyph("a", contours=[curve]))
    assert found[DIFFERENT_OFF_CURVES] == SEVERITY_STRUCTURAL
    assert found[WRONG_CURVE_TYPE] == SEVERITY_STRUCTURAL


def test_a_different_component_is_an_error():
    found = _severities(
        FakeGlyph("a", components=[("b",)]),
        FakeGlyph("a", components=[("c",)]),
    )
    assert found[DIFFERENT_COMPONENTS] == SEVERITY_STRUCTURAL


def test_a_reversed_contour_stays_a_warning():
    found = _severities(
        FakeGlyph("a", contours=[SQUARE]),
        FakeGlyph("a", contours=[[SQUARE[0]] + SQUARE[:0:-1]]),
    )
    assert found == {WRONG_CONTOUR_DIRECTION: SEVERITY_DESIGN}
