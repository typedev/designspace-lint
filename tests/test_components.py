# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
The component graph of each master (4.24, 4.25) and its open contours (4.26).

Each rule was built with ufo2ft 3.9 first: a ring stops every build with
RecursionError; a base the build cannot find stops CFF and CFF2 and silently
drops the component from TrueType; a base the default master has is only
sparse in another master; an open contour ships closed with a straight line.
"""

from designspace_lint import lint
from designspace_lint.checkers.components import (
    COMPONENT_RING,
    MISSING_COMPONENT_BASE,
    OPEN_CONTOUR,
    component_findings,
    component_rings,
)
from designspace_lint.checkers.construction import COMPONENT_ORDER_CANONICAL
from designspace_lint.model import (
    CATEGORY_GLYPHS,
    SEVERITY_DESIGN,
    SEVERITY_STRUCTURAL,
    effective_severity,
)
from fakes import FakeGlyph, FakeLayer, FakePoint, build_designspace

SQUARE = [(0, 0), (100, 0), (100, 100), (0, 100)]
OPEN_SQUARE = [FakePoint(0, 0, "move"), (100, 0), (100, 100), (0, 100)]
AXES = [{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}]


def _glyphs(**extra):
    glyphs = {
        "A": FakeGlyph("A", contours=[SQUARE], unicodes=[0x41]),
        "acute": FakeGlyph("acute", contours=[SQUARE], unicodes=[0xB4]),
        "Aacute": FakeGlyph("Aacute", components=[("A",), ("acute", (1, 0, 0, 1, 0, 600))]),
    }
    glyphs.update(extra)
    return glyphs


def _entry(light, bold, mid=None):
    sources = [
        {"name": "Light", "location": {"Weight": 0}, "glyphs": light},
        {"name": "Bold", "location": {"Weight": 100}, "glyphs": bold},
    ]
    if mid is not None:
        sources[0]["layers"] = {"mid": mid}
        sources.append(
            {
                "name": "Mid",
                "path": "/tmp/fake/Light.ufo",
                "layer_name": "mid",
                "location": {"Weight": 50},
            }
        )
    return build_designspace(axes=AXES, sources=sources)


def _found(entry, code, **kwargs):
    return [r for r in lint(entry, **kwargs) if r.category == CATEGORY_GLYPHS and r.code == code]


def test_two_glyphs_that_use_each_other_are_a_ring():
    ring = {"acute": FakeGlyph("acute", contours=[SQUARE], components=[("Aacute",)])}
    rings = _found(_entry(_glyphs(**ring), _glyphs()), COMPONENT_RING)

    assert len(rings) == 1  # only the master that has it
    ring = rings[0]
    assert ring.raw_data["glyphNames"] == ["Aacute", "acute"]
    assert ring.raw_data["links"] == {"Aacute": ["acute"], "acute": ["Aacute"]}
    assert ring.raw_data["sourceName"] == "Light"
    assert effective_severity(ring) == SEVERITY_STRUCTURAL
    assert "RecursionError" in ring.details


def test_a_glyph_that_uses_itself_is_a_ring():
    selfish = {"A": FakeGlyph("A", contours=[SQUARE], components=[("A",)])}
    rings = _found(_entry(_glyphs(**selfish), _glyphs(**selfish)), COMPONENT_RING)

    assert [r.raw_data["glyphNames"] for r in rings] == [["A"], ["A"]]
    assert "uses itself" in rings[0].description


def test_a_component_of_a_glyph_nowhere_in_the_build_is_an_error():
    extra = {"Abar": FakeGlyph("Abar", components=[("A",), ("barcomb",)])}
    missing = _found(_entry(_glyphs(**extra), _glyphs(**extra)), MISSING_COMPONENT_BASE)

    assert [r.raw_data["missingBases"] for r in missing] == [["barcomb"], ["barcomb"]]
    assert {r.raw_data["sourceName"] for r in missing} == {"Light", "Bold"}
    assert all(effective_severity(r) == SEVERITY_STRUCTURAL for r in missing)


def test_a_base_the_default_master_has_is_only_sparse_elsewhere():
    """Built: the base interpolates from the masters that have it."""
    bold = _glyphs()
    del bold["acute"]
    mid = {"Aacute": FakeGlyph("Aacute", components=[("A",), ("acute", (1, 0, 0, 1, 0, 620))])}

    assert _found(_entry(_glyphs(), bold, mid=mid), MISSING_COMPONENT_BASE) == []


def test_a_base_missing_from_the_default_master_is_reported_there():
    light = _glyphs()
    del light["acute"]
    missing = _found(_entry(light, _glyphs()), MISSING_COMPONENT_BASE)

    assert [r.raw_data["sourceName"] for r in missing] == ["Light"]


def test_an_open_contour_is_a_warning():
    extra = {"O": FakeGlyph("O", contours=[SQUARE, OPEN_SQUARE])}
    found = _found(_entry(_glyphs(**extra), _glyphs()), OPEN_CONTOUR)

    assert len(found) == 1
    assert found[0].glyph_name == "O"
    assert found[0].raw_data["contours"] == [1]
    assert effective_severity(found[0]) == SEVERITY_DESIGN


def test_a_partial_recheck_reports_the_rings_its_glyphs_reach():
    ring = {
        "acute": FakeGlyph("acute", contours=[SQUARE], components=[("Aacute",)]),
        "Aacute": FakeGlyph("Aacute", components=[("A",), ("acute",)]),
        "Aacute.sc": FakeGlyph("Aacute.sc", components=[("Aacute",)]),
        "B": FakeGlyph("B", components=[("B",)]),
    }
    entry = _entry(_glyphs(**ring), _glyphs())

    reached = _found(entry, COMPONENT_RING, glyphs=["Aacute.sc"])
    assert [r.raw_data["glyphNames"] for r in reached] == [["Aacute", "acute"]]
    assert _found(entry, COMPONENT_RING, glyphs=["A"]) == []


def test_a_layer_no_build_reads_gets_warnings_and_no_open_contours():
    layer = FakeLayer(
        "background",
        {
            "A": FakeGlyph("A", contours=[OPEN_SQUARE], components=[("A",)]),
            "B": FakeGlyph("B", components=[("missing",)]),
        },
    )
    found = list(
        component_findings(layer, source_name="Font", layer_name="background", build_layer=False)
    )

    assert sorted(r.code for r in found) == [COMPONENT_RING, MISSING_COMPONENT_BASE]
    assert all(effective_severity(r) == SEVERITY_DESIGN for r in found)
    assert all(r.raw_data["layerName"] == "background" for r in found)


def test_rings_are_found_without_recursion_however_deep_the_nesting():
    chain = {f"g{i}": [f"g{i + 1}"] for i in range(5000)}
    chain["g5000"] = ["g0"]  # closes it
    chain.update({"x": ["y"], "y": ["z"]})  # not a ring

    rings = component_rings(chain)
    assert len(rings) == 1 and len(rings[0]) == 5001


def test_a_ring_costs_the_construction_phase_only_its_own_glyphs():
    """Font-Rover's reproduction: the ring used to stop the phase with RecursionError."""
    dieresis = FakeGlyph("dieresis", contours=[[(x, y + 600) for x, y in SQUARE]])

    def glyphs(ring):
        extra = {
            "dieresis": dieresis,
            "Adieresis": FakeGlyph("Adieresis", components=[("dieresis",), ("A",)]),
        }
        if ring:
            extra["acute"] = FakeGlyph("acute", contours=[SQUARE], components=[("Aacute",)])
        return _glyphs(**extra)

    results = lint(_entry(glyphs(ring=True), glyphs(ring=False)), construction=True)
    order = [r for r in results if r.code == COMPONENT_ORDER_CANONICAL]

    assert [r.glyph_name for r in order] == ["Adieresis"]
    assert not [r for r in results if (r.category, r.code) == (0, 1)]
    assert [r.code for r in results if r.code == COMPONENT_RING] == [COMPONENT_RING]
