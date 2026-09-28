# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Rules, as fontTools evaluates them and varLib compiles them.

A rule with no conditionset never applies; an empty conditionset is the spec's
always-on rule. Rule glyphs must exist in the default master, which is what
varLib checks them against. And two rules that substitute one glyph over a
shared region are ordered by varLib by their substitutions, not by the order
they are written in -- verified by compiling both orders with fontTools 4.65.
"""

from fontTools.designspaceLib import RuleDescriptor

from designspace_lint.checkers.rules import (
    RULE_NO_CONDITIONS,
    RULE_OVERLAP,
    RULE_RANGE_OUT_OF_BOUNDS,
    RULE_UNDEFINED_GLYPH,
    RulesChecker,
)
from designspace_lint.model import SEVERITY_STRUCTURAL
from dsxml import WEIGHT, ds, source
from fakes import build_designspace


def _rule(name, subs, *boxes):
    """`boxes` are conditionsets, each {axis: (min, max)}; None leaves a side open."""
    conditions = ""
    for box in boxes:
        conditions += "<conditionset>"
        for axis, (lo, hi) in box.items():
            attrs = (f' minimum="{lo}"' if lo is not None else "") + (
                f' maximum="{hi}"' if hi is not None else ""
            )
            conditions += f'<condition name="{axis}"{attrs}/>'
        conditions += "</conditionset>"
    subs_xml = "".join(f'<sub name="{a}" with="{b}"/>' for a, b in subs.items())
    return f'<rule name="{name}">{conditions}{subs_xml}</rule>'


def _check(*rules):
    doc = ds(WEIGHT, source("R.ufo", Weight=400), rules="".join(rules))
    return list(RulesChecker(doc=doc).check())


# --- 7.0 -------------------------------------------------------------------


def test_a_rule_without_a_conditionset_is_dead_and_the_rest_still_checked():
    """RULE-13: this rule used to crash the phase and take every later rule with it."""
    results = _check(
        '<rule name="dead"><sub name="a" with="a.alt"/></rule>',
        _rule("wide", {"b": "b.alt"}, {"Weight": (50, 900)}),
    )

    assert [(r.code, r.location) for r in results] == [
        (RULE_NO_CONDITIONS, "dead"),
        (RULE_RANGE_OUT_OF_BOUNDS, "wide"),
    ]
    assert "never applies" in results[0].description


def test_an_empty_conditionset_is_always_on_and_fine():
    results = _check(_rule("always", {"a": "a.alt"}, {}))
    assert results == []


# --- 7.5 -------------------------------------------------------------------


def _entry_with_rule(default_glyphs, bold_glyphs, subs, skip_export=()):
    entry = build_designspace(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 400, "default": 400, "maximum": 900}],
        sources=[
            {"name": "Regular", "location": {"Weight": 400}, "glyphs": default_glyphs},
            {"name": "Bold", "location": {"Weight": 900}, "glyphs": bold_glyphs},
        ],
    )
    entry.sources[0].font.lib["public.skipExportGlyphs"] = list(skip_export)
    rule = RuleDescriptor()
    rule.name = "heavy"
    rule.conditionSets = [[{"name": "Weight", "minimum": 700, "maximum": 900}]]
    rule.subs = list(subs.items())
    entry.doc.addRule(rule)
    return entry


def _undefined(entry):
    return [r for r in RulesChecker(entry=entry).check() if r.code == RULE_UNDEFINED_GLYPH]


def test_a_rule_glyph_drawn_only_outside_the_default_master_is_reported():
    """RULE-17: varLib checks the default master's glyphs, not all masters'."""
    entry = _entry_with_rule(["a"], ["a", "a.heavy"], {"a": "a.heavy"})
    results = _undefined(entry)

    assert [r.glyph_name for r in results] == ["a.heavy"]
    assert results[0].severity == SEVERITY_STRUCTURAL


def test_a_rule_glyph_in_the_default_master_is_fine():
    entry = _entry_with_rule(["a", "a.heavy"], ["a"], {"a": "a.heavy"})
    assert _undefined(entry) == []


def test_a_rule_glyph_that_is_not_exported_is_reported():
    entry = _entry_with_rule(["a", "a.heavy"], ["a"], {"a": "a.heavy"}, skip_export=["a.heavy"])
    assert [r.glyph_name for r in _undefined(entry)] == ["a.heavy"]


# --- 7.7 -------------------------------------------------------------------


def test_overlapping_rules_name_the_rule_the_variable_font_uses():
    """RULE-05/06: declared first is not what wins.

    The lookups are numbered in sorted order of their substitutions, so
    `a -> a.aaa` runs before `a -> a.zzz` and wins in the overlap, although
    it is declared second. Static instances apply rules in declaration order
    and get `a.zzz`.
    """
    results = _check(
        _rule("first", {"a": "a.zzz"}, {"Weight": (400, 900)}),
        _rule("second", {"a": "a.aaa"}, {"Weight": (600, 900)}),
    )

    assert [r.code for r in results] == [RULE_OVERLAP]
    assert results[0].raw_data["variableFontRule"] == "second"
    assert "static instances" in results[0].details


def test_rules_with_the_same_region_are_merged_and_the_earlier_wins():
    results = _check(
        _rule("first", {"a": "a.zzz"}, {"Weight": (600, 900)}),
        _rule("second", {"a": "a.aaa"}, {"Weight": (600, 900)}),
    )
    assert results[0].raw_data["variableFontRule"] == "first"


def test_rules_that_only_touch_at_a_boundary_do_not_overlap():
    results = _check(
        _rule("light", {"a": "a.light"}, {"Weight": (100, 400)}),
        _rule("heavy", {"a": "a.heavy"}, {"Weight": (400, 900)}),
    )
    assert results == []


def test_overlapping_rules_on_different_glyphs_are_fine():
    results = _check(
        _rule("one", {"a": "a.alt"}, {"Weight": (400, 900)}),
        _rule("two", {"b": "b.alt"}, {"Weight": (600, 900)}),
    )
    assert results == []
