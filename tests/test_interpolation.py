# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Point correspondence, by fontTools' varLib.interpolatable over open masters.

Every master pair here has the same structure -- equal contour and point
counts, the same segment types -- so the structural checks pass and varLib
builds the glyph. What differs is where the points go: a start point moved
along the contour, a contour drawn the other way, two contours listed in the
other order. Each of those twists or swaps the shape between the masters.
"""

from designspace_lint import lint
from designspace_lint.checkers.interpolation import (
    CONTOUR_ORDER,
    UNCHECKED_NO_SOLVER,
    WRONG_START_POINT,
)
from designspace_lint.model import CATEGORY_GLYPHS, SEVERITY_INFO
from fakes import FakeGlyph, build_designspace

SQUARE = [(0, 0), (100, 0), (100, 100), (0, 100)]


def _shifted(points, dx):
    return [(x + dx, y) for x, y in points]


def _glyph(name, *contours):
    return FakeGlyph(name, contours=[list(c) for c in contours])


def _two_masters(light, bold):
    return build_designspace(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}],
        sources=[
            {"name": "Light", "location": {"Weight": 0}, "glyphs": light},
            {"name": "Bold", "location": {"Weight": 100}, "glyphs": bold},
        ],
    )


def _interpolation(entry, **kwargs):
    return [
        r
        for r in lint(entry, interpolatable=True, **kwargs)
        if r.category == CATEGORY_GLYPHS and r.code >= 14
    ]


def test_matching_masters_have_nothing_to_report():
    entry = _two_masters({"a": _glyph("a", SQUARE)}, {"a": _glyph("a", _shifted(SQUARE, 10))})
    assert _interpolation(entry) == []


def test_a_moved_start_point_is_reported():
    rotated = SQUARE[1:] + SQUARE[:1]
    entry = _two_masters({"a": _glyph("a", SQUARE)}, {"a": _glyph("a", rotated)})
    results = [r for r in _interpolation(entry) if r.code == WRONG_START_POINT]

    assert len(results) == 1
    assert results[0].raw_data["reversed"] is False
    assert "starts at a different point" in results[0].description


def test_a_reversed_contour_is_reported_as_such():
    reversed_square = [SQUARE[0]] + SQUARE[:0:-1]
    entry = _two_masters({"a": _glyph("a", SQUARE)}, {"a": _glyph("a", reversed_square)})
    results = [r for r in _interpolation(entry) if r.code == WRONG_START_POINT]

    assert results and results[0].raw_data["reversed"] is True


def test_contours_in_another_order_are_reported():
    left, right = SQUARE, _shifted(SQUARE, 300)
    small = [(x // 2 + 600, y // 2) for x, y in SQUARE]
    entry = _two_masters(
        {"a": _glyph("a", left, right, small)},
        {"a": _glyph("a", right, left, small)},
    )
    assert CONTOUR_ORDER in [r.code for r in _interpolation(entry)]


def test_the_phase_runs_only_when_asked_for():
    rotated = SQUARE[1:] + SQUARE[:1]
    entry = _two_masters({"a": _glyph("a", SQUARE)}, {"a": _glyph("a", rotated)})
    codes = [(r.category, r.code) for r in lint(entry)]
    assert (CATEGORY_GLYPHS, WRONG_START_POINT) not in codes


def test_glyphs_that_need_a_solver_are_counted_once(monkeypatch):
    """Without scipy or munkres interpolatable cannot match 7+ contours."""
    from fontTools.varLib import interpolatableHelpers as helpers

    monkeypatch.setattr(
        helpers,
        "min_cost_perfect_bipartite_matching",
        helpers.min_cost_perfect_bipartite_matching_bruteforce,
    )

    many = [_shifted(SQUARE, 200 * i) for i in range(7)]
    entry = _two_masters(
        {"a": _glyph("a", *many), "b": _glyph("b", *many)},
        {"a": _glyph("a", *many), "b": _glyph("b", *many)},
    )
    unchecked = [r for r in _interpolation(entry) if r.code == UNCHECKED_NO_SOLVER]

    assert len(unchecked) == 1
    assert unchecked[0].raw_data["glyphs"] == ["a", "b"]
    assert unchecked[0].severity == SEVERITY_INFO


def test_a_component_base_missing_from_a_master_draws_as_nothing():
    """ufo2ft gives the master an empty placeholder for it, which varLib ignores.

    Amstelvar's `Ldot` reaches `periodcentered-loclCATcomb.case` through
    another composite, and four masters do not have it; comparing them used
    to raise inside interpolatable.
    """
    dot = _glyph("dot", [(0, 0), (20, 0), (20, 20), (0, 20)])
    light = {
        "L": _glyph("L", SQUARE),
        "dot": dot,
        "Ldot": FakeGlyph("Ldot", components=[("L",), ("dot", (1, 0, 0, 1, 150, 50))]),
    }
    bold = {
        "L": _glyph("L", _shifted(SQUARE, 5)),
        "Ldot": FakeGlyph("Ldot", components=[("L",), ("dot", (1, 0, 0, 1, 160, 50))]),
    }
    entry = _two_masters(light, bold)

    assert [r for r in _interpolation(entry) if r.glyph_name == "Ldot"] == []


def test_one_problem_across_several_master_pairs_is_one_finding():
    """A contour off in one master is off against both of its neighbours."""
    rotated = SQUARE[1:] + SQUARE[:1]
    entry = build_designspace(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}],
        sources=[
            {"name": "Light", "location": {"Weight": 0}, "glyphs": {"a": _glyph("a", SQUARE)}},
            {"name": "Mid", "location": {"Weight": 50}, "glyphs": {"a": _glyph("a", rotated)}},
            {"name": "Bold", "location": {"Weight": 100}, "glyphs": {"a": _glyph("a", SQUARE)}},
        ],
    )
    results = [r for r in _interpolation(entry) if r.code == WRONG_START_POINT]

    assert len(results) == 1
    assert len(results[0].raw_data["pairs"]) == 2
    assert "1 more master pair" in results[0].description
