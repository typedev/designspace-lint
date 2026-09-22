# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Glyph order: a subset is fine, a different order is not.

varLib sorts every master's coverage by the default master's glyph ids when it
merges per-master GPOS tables, and raises InconsistentGlyphOrder when a
master's glyphs do not come in the default's order. A master with fewer glyphs
is fine -- that is what a sparse master is -- so the comparison runs on the
names the two masters share.
"""

from designspace_lint.checkers.glyphorder import (
    GLYPHORDER_MISSING_GLYPH,
    GLYPHORDER_POSITION_MISMATCH,
    GlyphOrderChecker,
)
from fakes import build_designspace


def _entry(source_specs):
    return build_designspace(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}],
        sources=source_specs,
    )


def _results(entry):
    return list(GlyphOrderChecker(entry=entry).check())


def test_a_master_with_fewer_glyphs_in_the_same_order_is_fine():
    entry = _entry(
        [
            {"name": "Light", "location": {"Weight": 0}, "glyphs": ["A", "B", "C"]},
            {"name": "Bold", "location": {"Weight": 100}, "glyphs": ["A", "C"]},
        ]
    )

    assert [r.code for r in _results(entry)] == []


def test_a_master_that_reorders_its_glyphs_is_reported():
    entry = _entry(
        [
            {"name": "Light", "location": {"Weight": 0}, "glyphs": ["A", "B", "C"]},
            {"name": "Bold", "location": {"Weight": 100}, "glyphs": ["A", "C", "B"]},
        ]
    )

    assert GLYPHORDER_POSITION_MISMATCH in [r.code for r in _results(entry)]


def test_missing_glyphs_are_no_longer_reported_here():
    """Which masters a glyph may skip is decided by the axes, in category 4."""
    entry = _entry(
        [
            {"name": "Light", "location": {"Weight": 0}, "glyphs": ["A", "B", "C"]},
            {"name": "Bold", "location": {"Weight": 100}, "glyphs": ["A"]},
        ]
    )

    assert GLYPHORDER_MISSING_GLYPH not in [r.code for r in _results(entry)]


def test_sparse_in_the_name_no_longer_silences_a_reordered_master():
    entry = _entry(
        [
            {"name": "Light", "location": {"Weight": 0}, "glyphs": ["A", "B", "C"]},
            {
                "name": "Bold-sparse",
                "path": "/tmp/fake/Bold-sparse.ufo",
                "location": {"Weight": 100},
                "glyphs": ["A", "C", "B"],
            },
        ]
    )

    assert GLYPHORDER_POSITION_MISMATCH in [r.code for r in _results(entry)]


def test_layer_masters_have_no_glyph_order_of_their_own():
    entry = build_designspace(
        axes=[{"name": "Width", "tag": "wdth", "minimum": 0, "default": 0, "maximum": 100}],
        sources=[
            {
                "name": "Narrow",
                "path": "/tmp/fake/shared.ufo",
                "location": {"Width": 0},
                "glyphs": ["A", "B"],
                "layers": {"Wide": ["B", "A"]},  # a layer's order is not a master's
            },
            {
                "name": "Wide",
                "path": "/tmp/fake/shared.ufo",
                "location": {"Width": 100},
                "layer_name": "Wide",
            },
        ],
    )

    assert [r.code for r in _results(entry)] == []
