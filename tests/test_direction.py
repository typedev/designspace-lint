# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Contour direction judged in each glyph, and the holes a wrong one cuts (4.29-4.31).

All of it was built with ufo2ft 3.9 first (a C and a cedilla drawn the other
way, overlapping): the overlap has winding 0 in variable TrueType and CFF2
fonts and in static ones that keep their overlaps, and a CFF build that
removes overlaps bakes the hole into the outline. ufo2ft writes CFF as drawn
and reverses TrueType itself, so in the UFO outer contours run
counter-clockwise for both.
"""

from designspace_lint import lint
from designspace_lint.checkers.direction import (
    CONTOUR_DIRECTION,
    PARTS_CANCEL,
    TRUETYPE_DIRECTION,
)
from designspace_lint.direction import expected_directions
from designspace_lint.model import CATEGORY_GLYPHS, SEVERITY_DESIGN, effective_severity
from fakes import FakeGlyph, FakeLayer, build_designspace

AXES = [{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}]
CODES = (PARTS_CANCEL, CONTOUR_DIRECTION, TRUETYPE_DIRECTION)


def rect(x0, y0, x1, y1, clockwise=False):
    points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return [points[0]] + points[:0:-1] if clockwise else points


def _glyphs(stem, **extra):
    glyphs = {
        "C": FakeGlyph("C", contours=[rect(50, 0, 550, stem), rect(50, 0, 50 + stem, 700)]),
        "cedilla": FakeGlyph("cedilla", contours=[rect(0, -150, 80, 60)]),
        "o": FakeGlyph("o", contours=[rect(0, 0, 500, 500), rect(100, 100, 400, 400, True)]),
        "Ccedilla": FakeGlyph("Ccedilla", components=[("C",), ("cedilla", (1, 0, 0, 1, 260, 0))]),
    }
    glyphs.update(extra)
    return glyphs


def _entry(light, bold):
    return build_designspace(
        axes=AXES,
        sources=[
            {"name": "Light", "location": {"Weight": 0}, "glyphs": light},
            {"name": "Bold", "location": {"Weight": 100}, "glyphs": bold},
        ],
    )


def _found(entry, **kwargs):
    return [
        r
        for r in lint(entry, phases=["glyphs"], **kwargs)
        if r.category == CATEGORY_GLYPHS and r.code in CODES
    ]


def test_a_clean_font_has_nothing_to_say():
    assert _found(_entry(_glyphs(100), _glyphs(160))) == []


def test_a_reversed_accent_cuts_into_every_letter_it_overlaps():
    reversed_cedilla = FakeGlyph("cedilla", contours=[rect(0, -150, 80, 60, True)])
    extra = {
        "cedilla": reversed_cedilla,
        # far below the C: the same reversed cedilla, touching nothing
        "Cdotbelow": FakeGlyph(
            "Cdotbelow", components=[("C",), ("cedilla", (1, 0, 0, 1, 260, -400))]
        ),
        # mirrored, so it runs the right way here: reversing the cedilla would cut a hole
        "Cmirrored": FakeGlyph(
            "Cmirrored", components=[("C",), ("cedilla", (-1, 0, 0, 1, 340, 0))]
        ),
    }
    light, bold = dict(_glyphs(100), **extra), dict(_glyphs(160), **extra)
    light["cedilla"] = bold["cedilla"] = reversed_cedilla
    found = _found(_entry(light, bold))

    (base,) = [r for r in found if r.code == CONTOUR_DIRECTION]
    assert base.glyph_name == "cedilla"
    (contour,) = base.raw_data["contours"]
    assert (contour["expected"], contour["actual"]) == ("ccw", "cw")
    assert contour["consequence"] == "againstConvention"  # on its own it looks the same

    (cut,) = [r for r in found if r.code == PARTS_CANCEL]
    assert effective_severity(cut) == SEVERITY_DESIGN
    assert cut.glyph_name == "Ccedilla"
    raw = cut.raw_data
    assert (raw["componentIndex"], raw["baseGlyph"], raw["cause"]) == (1, "cedilla", "baseReversed")
    assert raw["componentPath"] == ["Ccedilla", "cedilla"]
    assert raw["reverse"] == [0]
    assert sorted(raw["holes"]) == ["Bold", "Light"]
    light_hole = raw["holes"]["Light"]
    assert abs(light_hole["area"] - 60 * 80) < 200  # the cedilla's top 60 units inside the bar
    assert 260 <= light_hole["point"][0] <= 340 and 0 <= light_hole["point"][1] <= 60
    used = raw["usedBy"]
    assert [e["glyphName"] for e in used["fixes"]] == ["Ccedilla"]
    assert [e["glyphName"] for e in used["unaffected"]] == ["Cdotbelow"]
    assert [(e["glyphName"], e["reason"]) for e in used["breaks"]] == [("Cmirrored", "mirrored")]


def test_a_mirrored_component_is_the_composite_s_own_fault():
    extra = {
        "Cmirrored": FakeGlyph("Cmirrored", components=[("C",), ("cedilla", (-1, 0, 0, 1, 340, 0))])
    }
    (cut,) = _found(_entry(_glyphs(100, **extra), _glyphs(160, **extra)))

    assert cut.code == PARTS_CANCEL
    assert cut.raw_data["cause"] == "mirrored"
    assert cut.raw_data["determinant"] == {"Light": -1.0, "Bold": -1.0}
    assert "usedBy" not in cut.raw_data


def test_a_drawn_bar_running_the_other_way_cuts_two_holes():
    hbar = FakeGlyph(
        "Hbar",
        contours=[rect(0, 0, 100, 700), rect(400, 0, 500, 700), rect(-20, 300, 520, 380, True)],
    )
    (finding,) = _found(_entry(_glyphs(100, Hbar=hbar), _glyphs(160, Hbar=hbar)))

    assert finding.code == CONTOUR_DIRECTION
    (contour,) = finding.raw_data["contours"]
    assert contour["contourIndex"] == 2
    assert contour["role"] == "outer" and contour["container"] is None
    assert contour["consequence"] == "cutsInk"
    assert abs(contour["holes"]["Light"]["area"] - 2 * 100 * 80) < 400


def test_a_bar_running_the_other_way_over_a_component_cuts_it_too():
    extra = {
        "H": FakeGlyph("H", contours=[rect(0, 0, 100, 700), rect(400, 0, 500, 700)]),
        "Hbar": FakeGlyph("Hbar", contours=[rect(-20, 300, 520, 380, True)], components=[("H",)]),
    }
    (finding,) = _found(_entry(_glyphs(100, **extra), _glyphs(160, **extra)))
    (contour,) = finding.raw_data["contours"]
    assert finding.glyph_name == "Hbar" and contour["consequence"] == "cutsInk"


def test_a_counter_running_like_its_outer_contour_is_filled():
    filled = FakeGlyph("o", contours=[rect(0, 0, 500, 500), rect(100, 100, 400, 400)])
    (finding,) = _found(_entry(_glyphs(100, o=filled), _glyphs(160, o=filled)))
    (contour,) = finding.raw_data["contours"]
    assert (contour["role"], contour["depth"]) == ("counter", 1)
    assert contour["container"] == {"contourIndex": 0}
    assert contour["consequence"] == "filledCounter"


def test_a_bar_inside_a_ring_running_like_the_counter_it_crosses_is_reported_as_a_pair():
    theta = FakeGlyph(
        "Obar",
        contours=[
            rect(0, 0, 500, 700),
            rect(100, 100, 400, 600, True),
            rect(50, 320, 450, 380, True),
        ],
    )
    right = FakeGlyph(
        "Obar",
        contours=[rect(0, 0, 500, 700), rect(100, 100, 400, 600, True), rect(50, 320, 450, 380)],
    )
    assert _found(_entry(_glyphs(100, Obar=right), _glyphs(160, Obar=right))) == []

    (finding,) = _found(_entry(_glyphs(100, Obar=theta), _glyphs(160, Obar=theta)))
    entries = finding.raw_data["contours"]
    assert [(e["contourIndex"], e["ambiguous"], e["crosses"]) for e in entries] == [
        (1, True, [2]),
        (2, True, [1]),
    ]
    assert all("expected" not in e for e in entries)


def test_a_contour_that_crosses_itself_is_not_judged():
    bow_tie = FakeGlyph("x", contours=[[(0, 0), (300, 100), (300, 0), (0, 120)]])
    assert _found(_entry(_glyphs(100, x=bow_tie), _glyphs(160, x=bow_tie))) == []


def test_parts_that_touch_only_in_the_bold_master_cut_only_there():
    reversed_cedilla = FakeGlyph("cedilla", contours=[rect(0, -150, 80, 60, True)])
    light, bold = _glyphs(100), _glyphs(160)
    light["cedilla"] = bold["cedilla"] = reversed_cedilla
    light["Ccedilla"] = FakeGlyph(
        "Ccedilla", components=[("C",), ("cedilla", (1, 0, 0, 1, 260, -100))]
    )  # the cedilla's top at -40: below the C
    (cut,) = [r for r in _found(_entry(light, bold)) if r.code == PARTS_CANCEL]
    assert sorted(cut.raw_data["holes"]) == ["Bold"]


def test_masters_drawn_the_truetype_way_are_said_once_and_then_followed():
    def turned(glyphs):
        out = {}
        for name, glyph in glyphs.items():
            contours = [
                [c[0]] + c[:0:-1] for c in ([(p.x, p.y) for p in k.points] for k in glyph.contours)
            ]
            out[name] = FakeGlyph(
                name,
                contours=contours,
                components=[(c.baseGlyph, c.transformation) for c in glyph.components],
            )
        return out

    light, bold = turned(_glyphs(100)), turned(_glyphs(160))
    # one glyph the PostScript way: in these masters it is the odd one out
    light["l"] = bold["l"] = FakeGlyph("l", contours=[rect(0, 0, 100, 700)])
    found = _found(_entry(light, bold))

    (master,) = [r for r in found if r.code == TRUETYPE_DIRECTION]
    assert master.raw_data["sourceName"] == "Light"
    assert master.raw_data["convention"] == "truetype"
    assert master.raw_data["clockwiseGlyphs"] == 3 and master.raw_data["votedGlyphs"] == 4
    (odd,) = [r for r in found if r.code == CONTOUR_DIRECTION]
    assert odd.glyph_name == "l" and odd.raw_data["convention"] == "truetype"
    assert not [r for r in found if r.code == PARTS_CANCEL]
    # a run scoped to some glyphs leaves the master-wide finding out
    scoped = _found(_entry(light, bold), glyphs=["l"])
    assert [r.code for r in scoped] == [CONTOUR_DIRECTION]


def test_a_host_s_fix_asks_the_same_rule():
    layer = FakeLayer(
        "public.default",
        {
            "H": FakeGlyph("H", contours=[rect(0, 0, 100, 700), rect(400, 0, 500, 700)]),
            "Obar": FakeGlyph(
                "Obar",
                contours=[
                    rect(0, 0, 500, 700),
                    rect(100, 100, 400, 600, True),
                    rect(50, 320, 450, 380, True),
                ],
            ),
            "x": FakeGlyph("x", contours=[[(0, 0), (300, 100), (300, 0), (0, 120)]]),
        },
    )
    hbar = FakeGlyph("Hbar", contours=[rect(-20, 300, 520, 380, True)], components=[("H",)])
    assert expected_directions(hbar, layer) == {0: 1}
    assert expected_directions(hbar, layer, convention="truetype") == {0: -1}
    assert expected_directions(layer["Obar"], layer) == {0: 1, 1: None, 2: None}
    assert expected_directions(layer["x"], layer) == {0: None}


def test_a_knockout_is_drawn_so_on_purpose_and_reversing_it_would_fill_it():
    black_circle = FakeGlyph("circle", contours=[rect(0, 0, 800, 800, True)])
    digit = FakeGlyph("one", contours=[rect(350, 150, 450, 650)])
    extra = {
        "circle": black_circle,
        "one": digit,
        "one.circled": FakeGlyph("one.circled", components=[("circle",), ("one",)]),
    }
    found = _found(_entry(_glyphs(100, **extra), _glyphs(160, **extra)))

    assert not [r for r in found if r.code == PARTS_CANCEL]
    (base,) = [r for r in found if r.code == CONTOUR_DIRECTION]
    assert base.glyph_name == "circle"
    assert base.raw_data["contours"][0]["consequence"] == "againstConvention"
    (broken,) = base.raw_data["usedBy"]["breaks"]
    assert (broken["glyphName"], broken["reason"]) == ("one.circled", "knockout")
    assert "knock their inner part out" in base.details


def test_a_knockout_drawn_in_one_glyph_is_only_against_the_convention():
    drawn = FakeGlyph(
        "one.circled", contours=[rect(0, 0, 800, 800, True), rect(350, 150, 450, 650)]
    )
    (finding,) = _found(
        _entry(_glyphs(100, **{"one.circled": drawn}), _glyphs(160, **{"one.circled": drawn}))
    )
    assert [e["consequence"] for e in finding.raw_data["contours"]] == [
        "againstConvention",
        "againstConvention",
    ]
