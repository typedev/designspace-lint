# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
4.19: the same components in a different order.

varLib pairs a composite's components by index. Built with ufo2ft 3 and
fontTools 4: a TrueType build warns "glyph Ccedilla has incompatible masters;
skipping" and the glyph never varies; a CFF2 build decomposes the components
and quietly morphs the C into the cedilla. 4.1 compares which components are
present, so it stays silent; 4.9 fired but did not say why.
"""

from designspace_lint.checkers.glyphs import (
    COMPONENT_ORDER,
    DIFFERENT_COMPONENTS,
    INCOMPATIBLE_GLYPH,
    GlyphsChecker,
)
from designspace_lint.model import SEVERITY_STRUCTURAL
from fakes import FakeGlyph, build_designspace


def _entry(*glyphs):
    """One continuous axis, one master per glyph, plus the bases they use."""
    bases = {
        name: FakeGlyph(name, contours=[[(0, 0), (10, 0), (10, 10)]])
        for name in ("C", "cedilla", "i", "dotaccent")
    }
    return build_designspace(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}],
        sources=[
            {
                "name": f"M{i}",
                "location": {"Weight": 100 * i // (len(glyphs) - 1)},
                "glyphs": {**bases, glyph.name: glyph},
            }
            for i, glyph in enumerate(glyphs)
        ],
    )


def _composite(*bases, name="Ccedilla", contours=()):
    return FakeGlyph(name, components=[(b,) for b in bases], contours=contours)


def _results(entry):
    return list(GlyphsChecker(entry=entry).check())


def test_swapped_components_are_reported_once_with_both_orders():
    entry = _entry(
        _composite("C", "cedilla"),
        _composite("C", "cedilla"),
        _composite("cedilla", "C"),
    )
    results = [r for r in _results(entry) if r.glyph_name == "Ccedilla"]

    assert [r.code for r in results] == [COMPONENT_ORDER]
    finding = results[0]
    assert finding.severity == SEVERITY_STRUCTURAL
    assert finding.raw_data["glyphName"] == "Ccedilla"
    assert finding.raw_data["locationType"] == "groups"
    assert finding.raw_data["orders"] == {"order1": ["C", "cedilla"], "order2": ["cedilla", "C"]}
    groups = finding.raw_data["groups"]
    assert list(groups) == ["order1", "order2"]  # largest group first
    assert len(groups["order1"]) == 2 and len(groups["order2"]) == 1


def test_a_repeated_base_in_another_order_is_reported():
    entry = _entry(
        _composite("i", "dotaccent", "dotaccent", name="idotdot"),
        _composite("dotaccent", "i", "dotaccent", name="idotdot"),
    )
    codes = [r.code for r in _results(entry) if r.glyph_name == "idotdot"]

    assert codes == [COMPONENT_ORDER]


def test_different_components_are_not_an_order_problem():
    entry = _entry(
        _composite("C", "cedilla"),
        _composite("cedilla", "C", "dotaccent"),
    )
    codes = {r.code for r in _results(entry) if r.glyph_name == "Ccedilla"}

    assert DIFFERENT_COMPONENTS in codes
    assert COMPONENT_ORDER not in codes


def test_a_base_used_twice_does_not_hide_a_master_without_it():
    entry = _entry(
        _composite("i", "dotaccent", "dotaccent", name="idotdot"),
        _composite("i", "dotaccent", name="idotdot"),
        _composite("i", name="idotdot"),
    )
    found = [
        r for r in _results(entry) if r.glyph_name == "idotdot" and r.code == DIFFERENT_COMPONENTS
    ]

    assert len(found) == 1
    assert len(found[0].raw_data["presentIn"]) == 2
    assert len(found[0].raw_data["missingIn"]) == 1


def test_order_and_outline_differences_report_both():
    contour = [(0, 0), (10, 0), (10, 10)]
    entry = _entry(
        _composite("C", "cedilla", contours=[contour]),
        _composite("cedilla", "C", contours=[contour, contour]),
    )
    codes = {r.code for r in _results(entry) if r.glyph_name == "Ccedilla"}

    assert COMPONENT_ORDER in codes
    assert INCOMPATIBLE_GLYPH in codes


def test_same_order_everywhere_is_fine():
    entry = _entry(_composite("C", "cedilla"), _composite("C", "cedilla"))
    assert [r for r in _results(entry) if r.glyph_name == "Ccedilla"] == []
