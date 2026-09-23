# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Which masters a glyph may skip, and when an empty glyph is a problem.

These rules used to hinge on the substring "sparse" in a master's name. They
now follow varLib: a glyph absent from a master in the middle of an axis
interpolates from its neighbours, a glyph absent from a master at the end of an
axis silently reverts to the default master's shape, and a glyph absent from
the default master is dropped from the compiled font altogether.
"""

from designspace_lint.checkers.glyphs import (
    DEFAULT_GLYPH_EMPTY,
    GLYPH_AXIS_SPAN_GAP,
    GLYPH_EMPTY_IN_SOURCE,
    GLYPH_STATIC,
    GlyphsChecker,
)
from fakes import FakeGlyph, build_designspace


def _drawn(name="A", size=100, width=500):
    return FakeGlyph(name, width=width, contours=[[(0, 0), (size, 0), (size, size), (0, size)]])


def _weight_entry(glyph_sets, locations=(0, 50, 100)):
    """One continuous axis, one master per glyph set."""
    return build_designspace(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}],
        sources=[
            {"name": f"M{i}", "location": {"Weight": loc}, "glyphs": glyphs}
            for i, (loc, glyphs) in enumerate(zip(locations, glyph_sets, strict=False))
        ],
    )


def _codes(entry, **kwargs):
    checker = GlyphsChecker(entry=entry, **kwargs)
    return [(r.code, r.glyph_name) for r in checker.check()]


def test_glyph_missing_from_an_intermediate_master_is_not_a_problem():
    entry = _weight_entry(
        [
            {"A": _drawn(), "B": _drawn("B")},
            {"A": _drawn(size=150)},  # middle master lacks B
            {"A": _drawn(size=200), "B": _drawn("B", size=150)},
        ]
    )

    assert _codes(entry) == []


def test_glyph_missing_from_the_extreme_master_is_reported():
    entry = _weight_entry(
        [
            {"A": _drawn(), "B": _drawn("B")},
            {"A": _drawn(size=150), "B": _drawn("B", size=120)},
            {"A": _drawn(size=200)},  # last master on the axis lacks B
        ]
    )

    assert (GLYPH_AXIS_SPAN_GAP, "B") in _codes(entry)


def test_the_gap_names_the_axis_and_how_far_the_glyph_reaches():
    entry = _weight_entry(
        [
            {"A": _drawn(), "B": _drawn("B")},
            {"A": _drawn(size=150), "B": _drawn("B", size=120)},
            {"A": _drawn(size=200)},
        ]
    )

    gap = next(r for r in GlyphsChecker(entry=entry).check() if r.code == GLYPH_AXIS_SPAN_GAP)

    assert gap.raw_data["axis"] == "Weight"
    assert gap.raw_data["side"] == "maximum"
    assert gap.raw_data["required"] == 100
    assert gap.raw_data["covered"] == 50
    assert gap.is_structural is True


def test_glyph_absent_from_the_default_master_is_reported_once():
    entry = _weight_entry(
        [
            {"A": _drawn()},  # default is at Weight=0
            {"A": _drawn(size=150), "B": _drawn("B")},
            {"A": _drawn(size=200), "B": _drawn("B", size=150)},
        ]
    )

    codes = _codes(entry)

    assert codes.count((DEFAULT_GLYPH_EMPTY, "B")) == 1
    # No span gap on top of it: the glyph is gone from the font either way.
    assert (GLYPH_AXIS_SPAN_GAP, "B") not in codes


def test_glyph_empty_in_one_master_but_drawn_in_others():
    entry = _weight_entry(
        [
            {"A": _drawn()},
            {"A": FakeGlyph("A", width=500)},  # present, no contours
            {"A": _drawn(size=200)},
        ]
    )

    codes = _codes(entry)

    assert (GLYPH_EMPTY_IN_SOURCE, "A") in codes


def test_glyph_empty_in_every_master_is_fine():
    entry = _weight_entry(
        [
            {"space": FakeGlyph("space", width=200)},
            {"space": FakeGlyph("space", width=300)},
            {"space": FakeGlyph("space", width=400)},
        ]
    )

    assert _codes(entry) == []


def test_a_glyph_only_the_default_draws_is_static_not_a_gap():
    """25 such glyphs in Amstelvar produced 150 axis-end errors meaning
    "this glyph is static". They are one finding each now."""
    entry = _weight_entry(
        [
            {"A": _drawn(), "B": _drawn("B")},  # default
            {"A": _drawn(size=150)},
            {"A": _drawn(size=200)},
        ]
    )

    codes = _codes(entry)

    assert (GLYPH_STATIC, "B") in codes
    assert (GLYPH_AXIS_SPAN_GAP, "B") not in codes


def test_sparse_in_the_name_no_longer_changes_anything():
    """The old heuristic would have silenced these two masters."""
    plain = _weight_entry(
        [{"A": _drawn(), "B": _drawn("B")}, {"A": _drawn(size=150)}, {"A": _drawn(size=200)}]
    )
    named = build_designspace(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}],
        sources=[
            {
                "name": "M0",
                "location": {"Weight": 0},
                "glyphs": {"A": _drawn(), "B": _drawn("B")},
            },
            {
                "name": "M1-sparse",
                "path": "/tmp/fake/M1-sparse.ufo",
                "location": {"Weight": 50},
                "glyphs": {"A": _drawn(size=150)},
            },
            {
                "name": "M2-sparse",
                "path": "/tmp/fake/M2-sparse.ufo",
                "location": {"Weight": 100},
                "glyphs": {"A": _drawn(size=200)},
            },
        ],
    )

    assert _codes(plain) == _codes(named)
    assert (GLYPH_STATIC, "B") in _codes(named)


def test_each_discrete_slice_is_judged_on_its_own():
    """An upright master cannot cover the italic slice's axis end."""
    entry = build_designspace(
        axes=[
            {"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100},
            {"name": "Italic", "tag": "ital", "values": [0, 1], "default": 0},
        ],
        sources=[
            {
                "name": "Upright Light",
                "location": {"Weight": 0, "Italic": 0},
                "glyphs": {"A": _drawn(), "B": _drawn("B")},
            },
            {
                "name": "Upright Bold",
                "location": {"Weight": 100, "Italic": 0},
                "glyphs": {"A": _drawn(size=200), "B": _drawn("B", size=200)},
            },
            {
                "name": "Italic Light",
                "location": {"Weight": 0, "Italic": 1},
                "glyphs": {"A": _drawn(), "B": _drawn("B")},
            },
            {
                "name": "Italic Medium",
                "location": {"Weight": 50, "Italic": 1},
                "glyphs": {"A": _drawn(size=150), "B": _drawn("B", size=150)},
            },
            {
                "name": "Italic Bold",
                "location": {"Weight": 100, "Italic": 1},
                "glyphs": {"A": _drawn(size=200)},  # italic slice loses B at the end
            },
        ],
    )

    results = [r for r in GlyphsChecker(entry=entry).check() if r.code == GLYPH_AXIS_SPAN_GAP]

    assert len(results) == 1
    assert results[0].glyph_name == "B"


def test_layer_masters_are_compared_on_their_own_layers():
    """Two masters in one UFO: the outline must come from each one's layer."""
    entry = build_designspace(
        axes=[{"name": "Width", "tag": "wdth", "minimum": 0, "default": 0, "maximum": 100}],
        sources=[
            {
                "name": "Narrow",
                "path": "/tmp/fake/shared.ufo",
                "location": {"Width": 0},
                "glyphs": {"A": _drawn(), "B": _drawn("B")},
                # The Wide layer draws A with an extra contour: incompatible.
                "layers": {
                    "Wide": {
                        "A": FakeGlyph(
                            "A",
                            contours=[
                                [(0, 0), (100, 0), (100, 100), (0, 100)],
                                [(10, 10), (20, 10), (20, 20)],
                            ],
                        )
                    }
                },
            },
            {
                "name": "Wide",
                "path": "/tmp/fake/shared.ufo",
                "location": {"Width": 100},
                "layer_name": "Wide",
            },
        ],
    )

    codes = _codes(entry)

    # A differs in contour count between the two layers ...
    assert any(glyph == "A" for _code, glyph in codes)
    # ... and B, drawn only by the default layer, never varies.
    assert (GLYPH_STATIC, "B") in codes
