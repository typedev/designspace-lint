# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
4.20/4.21: the house order of a composite's components (opt-in).

Bases first, heaviest first; then the marks from the bottom up. A convention
Font-Rover's users asked for, not something ufo2ft needs -- so these tests
check the rule as stated, and `canonical_component_order` is what Font-Rover's
fix calls, so the fix and the check agree.
"""

import designspace_lint
from designspace_lint import canonical_component_order, component_role
from designspace_lint.checkers.construction import (
    COMPONENT_ORDER_CANONICAL,
    COMPONENT_ROLE_UNKNOWN,
)
from designspace_lint.construction import (
    ACCENT,
    BASE,
    MISSING_BASE,
    NO_OUTLINE,
    NO_UNICODE,
)
from fakes import FakeComponent, FakeGlyph, FakeLayer, build_designspace


def _box(name, bottom, top, unicode=None):
    return FakeGlyph(
        name,
        unicodes=[unicode] if unicode else [],
        contours=[[(0, bottom), (100, bottom), (100, top), (0, top)]],
    )


BASES = {
    "C": _box("C", 0, 700, 0x43),
    "e": _box("e", 0, 500, 0x65),
    "i": _box("i", 0, 500, 0x69),
    "f_f": _box("f_f", 0, 700),
    "f": _box("f", 0, 700, 0x66),
    "period": _box("period", 0, 100, 0x2E),
    "cedilla": _box("cedilla", -200, 0, 0xB8),  # Sk
    "acute": _box("acute", 550, 700, 0xB4),  # Sk
    "acute.uc": _box("acute.uc", 750, 850),  # takes acute's unicode
    "circumflex": _box("circumflex", 550, 700, 0x2C6),  # Lm
    "tilde": _box("tilde", 550, 650, 0x2DC),  # Sk
    "circumflex_tilde.uc": _box("circumflex_tilde.uc", 750, 1000),
    "e_acute": _box("e_acute", 0, 700),
    "hook": _box("hook", 550, 700, 0x2440),  # OCR HOOK, So -- as fonts do encode it
    "hook.uc": _box("hook.uc", 750, 900),
    "commaaccent": _box("commaaccent", -250, -100, 0xF6C3),  # private use, Co
    "uni01A0": _box("uni01A0", 0, 700, 0x1A0),  # O with horn
    "circumflex_hook": _box("circumflex_hook", 550, 900),
    "circumflex_horn": _box("circumflex_horn", 550, 900),  # no "horn" glyph
    "one": _box("one", 0, 700, 0x31),  # Nd
    "j": _box("j", -200, 500, 0x6A),
    "underdot": _box("underdot", -200, -100),  # no unicode
    "hornA": _box("hornA", 0, 700),  # no unicode
    "blank": FakeGlyph("blank", unicodes=[0x2D9]),  # a mark with no outline
}


def _font(extra=()):
    glyphs = dict(BASES)
    for glyph in extra:
        glyphs[glyph.name] = glyph
    return FakeLayer("public.default", glyphs)


def _composite(*components, name="X"):
    return FakeGlyph(
        name,
        components=[
            FakeComponent(c, (1, 0, 0, 1, 0, 0)) if isinstance(c, str) else FakeComponent(*c)
            for c in components
        ],
    )


def _order(*components):
    glyph = _composite(*components)
    order, notes = canonical_component_order(glyph, _font())
    names = [c.baseGlyph for c in glyph.components]
    return [names[i] for i in order], [(names[i], reason) for i, reason in notes]


# --- roles ---


def test_roles_come_from_unicode_categories_suffixes_and_ligature_parts():
    font = _font()
    assert component_role(font, "C") == (BASE, 1, "")
    assert component_role(font, "cedilla") == (ACCENT, 0, "")  # Sk
    assert component_role(font, "circumflex") == (ACCENT, 0, "")  # Lm
    assert component_role(font, "acute.uc") == (ACCENT, 0, "")  # via "acute"
    assert component_role(font, "circumflex_tilde.uc") == (ACCENT, 0, "")
    assert component_role(font, "f_f") == (BASE, 2, "")
    assert component_role(font, "e_acute") == (BASE, 1, "")
    # Anything that is not a letter is a mark, however the font encodes it.
    assert component_role(font, "hook.uc") == (ACCENT, 0, "")  # So, via "hook"
    assert component_role(font, "commaaccent") == (ACCENT, 0, "")  # Co
    assert component_role(font, "one") == (ACCENT, 0, "")  # Nd
    assert component_role(font, "circumflex_hook") == (ACCENT, 0, "")
    # No unicode: a mark too, with the reason kept for the note.
    assert component_role(font, "underdot") == (ACCENT, 0, NO_UNICODE)
    assert component_role(font, "nothere") == (ACCENT, 0, MISSING_BASE)
    kind, weight, reason = component_role(font, "circumflex_horn")
    assert (kind, weight) == (ACCENT, 0) and "horn" in reason


# --- the order ---


def test_the_base_goes_before_its_mark():
    assert _order("cedilla", "C") == (["C", "cedilla"], [])


def test_marks_go_from_the_bottom_up_as_placed():
    # acute is drawn at 550-700; moved down 400 it sits below the circumflex.
    order, _notes = _order("e", "circumflex", ("acute", (1, 0, 0, 1, 0, -400)))
    assert order == ["e", "acute", "circumflex"]


def test_heavier_ligatures_go_first_and_ties_keep_their_order():
    assert _order("i", "acute", "f_f")[0] == ["f_f", "i", "acute"]
    assert _order("C", "e", "acute")[0] == ["C", "e", "acute"]


def test_no_mark_or_no_letter_means_nothing_to_order():
    assert _order("period", "period") == (["period", "period"], [])
    assert _order("f", "i") == (["f", "i"], [])
    assert _order("j", "i") == (["j", "i"], [])  # ij: only letters


def test_a_hook_encoded_as_a_symbol_goes_after_its_letter():
    assert _order("hook.uc", "uni01A0") == (["uni01A0", "hook.uc"], [])


def test_a_digit_goes_after_a_letter():
    assert _order("one", "C")[0] == ["C", "one"]


def test_a_component_with_no_unicode_is_ordered_as_a_mark_and_noted():
    order, notes = _order("e", "circumflex", "underdot")
    assert order == ["e", "underdot", "circumflex"]
    assert notes == [("underdot", NO_UNICODE)]


def test_without_a_letter_nothing_moves_but_the_notes_stay():
    assert _order("underdot", "hornA") == (
        ["underdot", "hornA"],
        [("underdot", NO_UNICODE), ("hornA", NO_UNICODE)],
    )
    order, notes = _order("acute", "underdot")
    assert order == ["acute", "underdot"]
    assert notes == [("underdot", NO_UNICODE)]


def test_a_mark_with_no_outline_leaves_the_order_alone():
    order, notes = _order("blank", "e", "acute")
    assert order == ["blank", "e", "acute"]
    assert notes == [("blank", NO_OUTLINE)]


def test_nested_components_are_measured_drawn():
    # "lowmark" is itself a composite: a cedilla moved further down.
    nested = _composite(("cedilla", (1, 0, 0, 1, 0, -300)), name="lowmark")
    nested.unicodes = [0x2CD]  # Lm
    glyph = _composite("e", "acute", "lowmark")
    order, _notes = canonical_component_order(glyph, _font([nested]))
    assert order == [0, 2, 1]


# --- the phase ---


def _entry(*glyph_sets):
    return build_designspace(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}],
        sources=[
            {"name": f"M{i}", "location": {"Weight": 100 * i}, "glyphs": {**BASES, **glyphs}}
            for i, glyphs in enumerate(glyph_sets)
        ],
    )


def _found(entry, **kwargs):
    return [
        r
        for r in designspace_lint.lint(entry, construction=True, **kwargs)
        if r.code in (COMPONENT_ORDER_CANONICAL, COMPONENT_ROLE_UNKNOWN)
    ]


def test_masters_out_of_order_are_grouped_with_both_orders():
    entry = _entry(
        {"Ccedilla": _composite("cedilla", "C", name="Ccedilla")},
        {"Ccedilla": _composite("cedilla", "C", name="Ccedilla")},
    )
    (finding,) = _found(entry)
    assert finding.code == COMPONENT_ORDER_CANONICAL
    assert finding.raw_data["glyphName"] == "Ccedilla"
    assert finding.raw_data["current"] == {"order1": ["cedilla", "C"]}
    assert finding.raw_data["expected"] == {"order1": ["C", "cedilla"]}
    assert len(finding.raw_data["groups"]["order1"]) == 2
    assert finding.raw_data["expectedDiffers"] is False
    assert finding.location == "all 2 sources"


def test_masters_whose_marks_stack_differently_are_flagged():
    low = ("acute", (1, 0, 0, 1, 0, -400))
    entry = _entry(
        {"X": _composite("e", "circumflex", low)},  # acute below: e, acute, circumflex
        {"X": _composite("e", "circumflex", "acute")},  # level: stays as it is
    )
    (finding,) = _found(entry)
    assert finding.raw_data["expectedDiffers"] is True
    assert list(finding.raw_data["groups"]) == ["order1"]


def test_unknown_components_are_reported_as_information():
    entry = _entry({"X": _composite("e", "underdot")}, {"X": _composite("e", "underdot")})
    (finding,) = _found(entry)
    assert finding.code == COMPONENT_ROLE_UNKNOWN
    (component,) = finding.raw_data["components"]
    assert component["baseGlyph"] == "underdot"
    assert component["index"] == 1
    assert component["reason"] == NO_UNICODE
    assert len(component["sources"]) == 2


def test_the_phase_runs_only_when_asked_for():
    entry = _entry({"X": _composite("cedilla", "C")}, {"X": _composite("cedilla", "C")})
    codes = {r.code for r in designspace_lint.lint(entry)}
    assert COMPONENT_ORDER_CANONICAL not in codes
    assert _found(entry)
    assert _found(entry, glyphs=["C"]) == []


def test_a_layer_master_reads_unicodes_from_the_default_layer_and_outlines_from_its_own():
    # The layer's acute has no unicode and sits lower than its circumflex.
    layer_glyphs = {
        "e": _box("e", 0, 500),
        "circumflex": _box("circumflex", 550, 700),
        "acute": _box("acute", 100, 200),
        "X": _composite("e", "circumflex", "acute"),
    }
    entry = build_designspace(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}],
        sources=[
            {
                "name": "Light",
                "path": "/tmp/fake/Family.ufo",
                "location": {"Weight": 0},
                "glyphs": {**BASES, "X": _composite("e", "circumflex", "acute")},
                "layers": {"bold": layer_glyphs},
            },
            {
                "name": "Bold",
                "path": "/tmp/fake/Family.ufo",
                "location": {"Weight": 100},
                "layer_name": "bold",
            },
        ],
    )
    (finding,) = _found(entry)
    assert finding.raw_data["expected"] == {"order1": ["e", "acute", "circumflex"]}
    (sources,) = finding.raw_data["groups"].values()
    assert len(sources) == 1 and "bold" in sources[0]
    assert finding.raw_data["expectedDiffers"] is True
