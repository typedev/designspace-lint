# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
4.22 and 4.23: codepoints within one master.

Built with ufo2ft 3.9 / fontTools 4.65, a codepoint on two glyphs of any master
(default or not, whole UFO or layer) stops `compileVariableTTF` with
"cannot map 'A.alt' to U+0041; already mapped to 'A'", unless the designspace's
`public.skipExportGlyphs` drops one of them; the UFO's own key does not.
Ported from Font-Rover's local 4.104/4.105 tests.
"""

import pytest

from designspace_lint import lint, lint_path, unicode_findings
from designspace_lint.checkers.unicodes import DUPLICATE_UNICODE, MULTIPLE_UNICODES
from designspace_lint.model import SEVERITY_INFO, SEVERITY_STRUCTURAL, effective_severity
from fakes import FakeFont, FakeGlyph, build_designspace

AXIS = [{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}]


def _glyphs():
    # Bdup is created first: the claimant order must come from the glyph
    # order, not from creation order.
    return {
        "Bdup": FakeGlyph("Bdup", unicodes=[0x42]),
        "A": FakeGlyph("A", unicodes=[0x41]),
        "A.alt": FakeGlyph("A.alt", unicodes=[0x41, 0xC0]),
        "B": FakeGlyph("B", unicodes=[0x42]),
        "C": FakeGlyph("C", unicodes=[0x43, 0x2102]),
    }


def _one_master(**extra):
    entry = build_designspace(
        axes=AXIS,
        sources=[{"name": "Regular", "location": {"Weight": 0}, "glyphs": _glyphs(), **extra}],
    )
    entry.sources[0].font.glyphOrder = ["A", "A.alt", "B", "Bdup", "C"]
    return entry


def _by_code(results, code):
    return [r for r in results if (r.category, r.code) == (4, code)]


def _dupes(results):
    return {r.raw_data["codepoint"]: r.raw_data["glyphNames"] for r in _by_code(results, 22)}


def test_duplicates_are_reported_per_codepoint_in_glyph_order():
    results = lint(_one_master(), phases=["glyphs"])

    assert _dupes(results) == {0x41: ["A", "A.alt"], 0x42: ["B", "Bdup"]}
    row = _by_code(results, DUPLICATE_UNICODE)[0]
    assert effective_severity(row) == SEVERITY_STRUCTURAL
    assert row.glyph_name == row.raw_data["glyphName"] == "A"
    assert row.raw_data["sourceName"] == "Regular"
    assert row.raw_data["layerName"] is None
    assert row.description == "U+0041 is given to 2 glyphs: 'A', 'A.alt'"
    assert "cannot map 'A.alt' to U+0041; already mapped to 'A'" in row.details


def test_several_codepoints_on_one_glyph_are_noted_in_the_glyphs_own_order():
    entry = _one_master()
    entry.sources[0].font["C"].unicodes = [0x2102, 0x43]
    results = _by_code(lint(entry, phases=["glyphs"]), MULTIPLE_UNICODES)

    assert [r.glyph_name for r in results] == ["A.alt", "C"]
    c = results[1]
    assert c.raw_data["codepoints"] == [0x2102, 0x43]
    assert effective_severity(c) == SEVERITY_INFO
    assert c.description == "'C' has 2 unicodes: U+2102, U+0043"


def test_notdef_and_unlisted_names_are_placed_as_ufo2ft_places_them():
    entry = build_designspace(
        axes=AXIS,
        sources=[
            {
                "name": "Regular",
                "location": {"Weight": 0},
                "glyphs": {
                    "z": FakeGlyph("z", unicodes=[0x41]),
                    "y": FakeGlyph("y", unicodes=[0x41]),
                    "A": FakeGlyph("A", unicodes=[0x41]),
                    ".notdef": FakeGlyph(".notdef", unicodes=[0x41]),
                },
            }
        ],
    )
    entry.sources[0].font.glyphOrder = ["A", ".notdef"]

    assert _dupes(lint(entry, phases=["glyphs"])) == {0x41: [".notdef", "A", "y", "z"]}


def test_a_background_layer_is_not_checked():
    layers = {"public.background": {"A": None, "A.alt": None}}
    entry = _one_master(layers=layers)
    background = entry.sources[0].font.getLayer("public.background")
    background["A"].unicodes = [0x45]
    background["A.alt"].unicodes = [0x45]

    assert 0x45 not in _dupes(lint(entry, phases=["glyphs"]))


def test_partial_recheck_reports_a_codepoint_any_claimant_asked_for():
    results = lint(_one_master(), phases=["glyphs"], glyphs=["Bdup"])

    assert _dupes(results) == {0x42: ["B", "Bdup"]}
    assert _by_code(results, MULTIPLE_UNICODES) == []


def test_a_duplicate_in_one_master_names_that_master():
    def master(name, weight, alt_unicodes):
        return {
            "name": name,
            "location": {"Weight": weight},
            "glyphs": {
                "A": FakeGlyph("A", unicodes=[0x41]),
                "A.alt": FakeGlyph("A.alt", unicodes=alt_unicodes),
            },
        }

    entry = build_designspace(
        axes=AXIS, sources=[master("Light", 0, []), master("Bold", 100, [0x41])]
    )
    results = lint(entry, phases=["glyphs"])
    rows = _by_code(results, DUPLICATE_UNICODE)

    assert [r.raw_data["sourceName"] for r in rows] == ["Bold"]
    # The masters also disagree about A.alt: 4.10 says so, independently.
    assert [r.glyph_name for r in _by_code(results, 10)] == ["A.alt"]


def test_layer_masters_are_each_checked_and_a_shared_layer_once():
    path = "/tmp/fake/Family.ufo"
    bold = {
        "A": FakeGlyph("A", unicodes=[0x41]),
        "A.alt": FakeGlyph("A.alt", unicodes=[0x41]),
    }
    regular = {"A": FakeGlyph("A", unicodes=[0x41]), "A.alt": FakeGlyph("A.alt")}
    entry = build_designspace(
        axes=AXIS,
        sources=[
            {"name": "Regular", "path": path, "location": {"Weight": 0}, "glyphs": regular,
             "layers": {"bold": bold}},
            {"name": "Bold", "path": path, "location": {"Weight": 100}, "layer_name": "bold"},
            {"name": "Bold again", "path": path, "location": {"Weight": 50},
             "layer_name": "bold"},
        ],
    )  # fmt: skip
    rows = _by_code(lint(entry, phases=["glyphs"]), DUPLICATE_UNICODE)

    assert [(r.raw_data["sourceName"], r.raw_data["layerName"]) for r in rows] == [("Bold", "bold")]


def test_designspace_skip_export_glyphs_claim_nothing():
    entry = _one_master()
    entry.doc.lib["public.skipExportGlyphs"] = ["A.alt"]
    results = lint(entry, phases=["glyphs"])

    assert _dupes(results) == {0x42: ["B", "Bdup"]}
    assert [r.glyph_name for r in _by_code(results, MULTIPLE_UNICODES)] == ["C"]


def test_the_ufos_own_skip_export_glyphs_do_not_count_in_a_designspace():
    entry = _one_master()
    entry.sources[0].font.lib["public.skipExportGlyphs"] = ["A.alt"]

    assert 0x41 in _dupes(lint(entry, phases=["glyphs"]))


def test_unicode_findings_on_a_standalone_layer():
    font = FakeFont("/tmp/fake/Single.ufo", _glyphs())
    font.glyphOrder = ["A", "A.alt", "B", "Bdup", "C"]
    results = list(
        unicode_findings(
            font.defaultLayer,
            source_name="Single.ufo",
            location="Single.ufo",
            glyph_order=font.glyphOrder,
            skip_export=["Bdup"],
        )
    )

    assert _dupes(results) == {0x41: ["A", "A.alt"]}
    assert [r.raw_data["layerName"] for r in results] == [None, None, None]


@pytest.fixture
def real_designspace(tmp_path):
    defcon = pytest.importorskip("defcon")
    from fontTools.designspaceLib import AxisDescriptor, DesignSpaceDocument, SourceDescriptor

    doc = DesignSpaceDocument()
    axis = AxisDescriptor()
    axis.name, axis.tag, axis.minimum, axis.default, axis.maximum = "wght", "wght", 400, 400, 700
    doc.addAxis(axis)
    for name, weight, glyphs in [
        ("Regular", 400, [("Bdup", [0x42]), ("A", [0x41]), ("B", [0x42]), ("C", [0x43, 0x2102])]),
        ("Bold", 700, [("Bdup", []), ("A", [0x41]), ("B", [0x42]), ("C", [0x43, 0x2102])]),
    ]:
        font = defcon.Font()
        for glyph_name, unicodes in glyphs:
            font.newGlyph(glyph_name).unicodes = unicodes
        font.glyphOrder = ["A", "B", "Bdup", "C"]
        font.save(str(tmp_path / f"{name}.ufo"))
        source = SourceDescriptor()
        source.path, source.name = str(tmp_path / f"{name}.ufo"), name
        source.location = {"wght": weight}
        doc.addSource(source)
    path = tmp_path / "Family.designspace"
    doc.write(str(path))
    return path


def test_real_ufos_read_through_defcon_unicode_data(real_designspace):
    results = lint_path(real_designspace, phases=["glyphs"])
    rows = _by_code(results, DUPLICATE_UNICODE)

    assert [(r.raw_data["sourceName"], r.raw_data["glyphNames"]) for r in rows] == [
        ("Regular", ["B", "Bdup"])
    ]
    multiple = _by_code(results, MULTIPLE_UNICODES)
    assert [(r.raw_data["sourceName"], r.raw_data["codepoints"]) for r in multiple] == [
        ("Regular", [0x43, 0x2102]),
        ("Bold", [0x43, 0x2102]),
    ]
