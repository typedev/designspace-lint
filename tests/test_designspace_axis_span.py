# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Which end of which axis a glyph fails to reach.

The rule this encodes: varLib builds a per-glyph model from the masters that
have the glyph, so skipping a master in the middle of an axis is free, while
skipping the master at the end of an axis makes the glyph fall back to the
default master's shape past its own last master.
"""

from designspace_lint.axis_span import axis_span_gaps, continuous_axes
from fakes import build_doc


def _doc(locations, axes=None):
    axes = axes or [{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}]
    sources = [
        {"path": f"/tmp/fake/M{i}.ufo", "name": f"M{i}", "location": loc}
        for i, loc in enumerate(locations)
    ]
    return build_doc(axes, sources)


def test_no_gap_when_the_glyph_is_in_every_master():
    doc = _doc([{"Weight": 0}, {"Weight": 50}, {"Weight": 100}])

    assert axis_span_gaps(doc, doc.sources, doc.sources) == []


def test_no_gap_when_only_an_intermediate_master_lacks_the_glyph():
    doc = _doc([{"Weight": 0}, {"Weight": 50}, {"Weight": 100}])
    covering = [doc.sources[0], doc.sources[2]]

    assert axis_span_gaps(doc, doc.sources, covering) == []


def test_gap_at_the_maximum_end():
    doc = _doc([{"Weight": 0}, {"Weight": 50}, {"Weight": 100}])
    covering = doc.sources[:2]

    gaps = axis_span_gaps(doc, doc.sources, covering)

    assert len(gaps) == 1
    assert (gaps[0].axis, gaps[0].side) == ("Weight", "maximum")
    assert (gaps[0].required, gaps[0].covered) == (100, 50)


def test_gap_at_the_minimum_end():
    doc = _doc([{"Weight": 0}, {"Weight": 50}, {"Weight": 100}])
    covering = doc.sources[1:]

    gaps = axis_span_gaps(doc, doc.sources, covering)

    assert [(g.axis, g.side) for g in gaps] == [("Weight", "minimum")]


def test_axes_are_judged_independently_so_a_corner_master_is_not_required():
    doc = _doc(
        [
            {"Weight": 0, "Width": 0},
            {"Weight": 100, "Width": 0},
            {"Weight": 0, "Width": 100},
            {"Weight": 100, "Width": 100},
        ],
        axes=[
            {"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100},
            {"name": "Width", "tag": "wdth", "minimum": 0, "default": 0, "maximum": 100},
        ],
    )
    # Everything except the far corner: both axis ends are still reached.
    covering = doc.sources[:3]

    assert axis_span_gaps(doc, doc.sources, covering) == []


def test_a_source_that_omits_an_axis_sits_at_its_default():
    doc = _doc(
        [{"Weight": 0}, {"Weight": 100}, {}],  # the third names no axis at all
    )
    covering = [doc.sources[2]]  # only the implicit-default master has the glyph

    gaps = axis_span_gaps(doc, doc.sources, covering)

    assert {g.side for g in gaps} == {"maximum"}
    assert gaps[0].covered == 0


def test_a_single_covering_master_in_a_one_master_space_has_no_gap():
    doc = _doc([{"Weight": 0}])

    assert axis_span_gaps(doc, doc.sources, doc.sources) == []


def test_no_covering_masters_yields_nothing():
    doc = _doc([{"Weight": 0}, {"Weight": 100}])

    assert axis_span_gaps(doc, doc.sources, []) == []


def test_discrete_axes_are_not_span_checked():
    doc = _doc(
        [{"Weight": 0, "Italic": 0}, {"Weight": 100, "Italic": 1}],
        axes=[
            {"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100},
            {"name": "Italic", "tag": "ital", "values": [0, 1], "default": 0},
        ],
    )

    assert [a.name for a in continuous_axes(doc)] == ["Weight"]


def test_near_identical_design_coordinates_count_as_the_same_end():
    doc = _doc([{"Weight": 0}, {"Weight": 100}, {"Weight": 100.0000001}])
    covering = [doc.sources[0], doc.sources[1]]

    assert axis_span_gaps(doc, doc.sources, covering) == []
