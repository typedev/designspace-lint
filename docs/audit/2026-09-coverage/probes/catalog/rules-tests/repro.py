"""
Standalone repro script for the RULE-* findings in fragment-rules.md.
Run with the DSSketch project's venv: source <venv>/bin/activate

Every block below corresponds to one or more rows in fragment-rules.md and was
run inline during the audit; this file collects them for reproducibility.
"""
from fontTools.varLib.featureVars import (
    addFeatureVariationsRaw, buildGSUB, overlayFeatureVariations,
    _checkSubstitutionGlyphsExist,
)
from fontTools.varLib import models, load_designspace
from fontTools.designspaceLib import (
    DesignSpaceDocument, AxisDescriptor, DiscreteAxisDescriptor, SourceDescriptor,
)


class FakeAxis:
    def __init__(self, tag):
        self.axisTag = tag


class FakeFvar:
    axes = [FakeAxis("wght"), FakeAxis("wdth")]


def fresh_font():
    gsubTable = buildGSUB().table
    font = {}
    font["fvar"] = FakeFvar()
    font["GSUB"] = type("T", (), {"table": gsubTable})()
    return font, gsubTable


def rule_02_min_gt_max():
    font, gsubTable = fresh_font()
    conditionalSubstitutions = [({"wght": (0.8, 0.2)}, [0])]
    try:
        addFeatureVariationsRaw(font, gsubTable, conditionalSubstitutions, ["rvrn"])
    except Exception as e:
        print("RULE-02:", type(e).__name__, ":", e)


def rule_03_min_eq_max():
    font, gsubTable = fresh_font()
    conditionalSubstitutions = [({"wght": (0.5, 0.5)}, [0])]
    addFeatureVariationsRaw(font, gsubTable, conditionalSubstitutions, ["rvrn"])
    ct = gsubTable.FeatureVariations.FeatureVariationRecord[0].ConditionSet.ConditionTable[0]
    print("RULE-03: no exception; degenerate box =", ct.__dict__)


def rule_04_undefined_axis():
    internal_axis_supports = {"weight": [0.0, 400.0, 900.0]}

    def normalize(name, value):
        return models.normalizeLocation({name: value}, internal_axis_supports)[name]

    try:
        normalize("grade", 500)
    except Exception as e:
        print("RULE-04 (normalize path):", type(e).__name__, ":", e)

    axes = {"weight": type("A", (), {"tag": "wght"})()}
    axis_tags = {name: axis.tag for name, axis in axes.items()}
    try:
        axis_tags["grade"]
    except Exception as e:
        print("RULE-04 (axis_tags path):", type(e).__name__, ":", e)


def rule_05_06_overlap_order():
    print("RULE-05/06a: specific-first, broad-second declared order (broad wins for 'a')")
    condSubst = [
        ([{"wght": (0.0, 1.0)}], {"a": "a.rule1"}),
        ([{"wght": (0.5, 1.0)}], {"a": "a.rule2"}),
    ]
    print(overlayFeatureVariations(condSubst))

    print("RULE-05/06b: specific-first declared, broad-second declared (specific still loses)")
    condSubst2 = [
        ([{"wght": (0.5, 1.0)}], {"a": "a.specific"}),
        ([{"wght": (0.0, 1.0)}], {"a": "a.broad"}),
    ]
    print(overlayFeatureVariations(condSubst2))


def rule_08_09_missing_glyphs():
    glyphNames = {"a", "b", "c"}
    try:
        _checkSubstitutionGlyphsExist(
            glyphNames=glyphNames,
            substitutions=[([{"wght": (0.0, 1.0)}], {"a": "a.missing"})],
        )
    except Exception as e:
        print("RULE-08 (missing target):", type(e).__name__, ":", e)
    try:
        _checkSubstitutionGlyphsExist(
            glyphNames=glyphNames,
            substitutions=[([{"wght": (0.0, 1.0)}], {"zzz_missing_source": "a"})],
        )
    except Exception as e:
        print("RULE-09 (missing source):", type(e).__name__, ":", e)


def rule_15_discrete_axis_crash():
    doc = DesignSpaceDocument()
    a1 = AxisDescriptor()
    a1.tag = "wght"
    a1.name = "weight"
    a1.minimum, a1.default, a1.maximum = 100, 400, 900
    doc.addAxis(a1)

    a2 = DiscreteAxisDescriptor()
    a2.tag = "ital"
    a2.name = "italic"
    a2.values = [0, 1]
    a2.default = 0
    doc.addAxis(a2)

    s1 = SourceDescriptor()
    s1.filename = "Regular.ufo"
    s1.location = {"weight": 400, "italic": 0}
    s1.name = "s1"
    doc.addSource(s1)

    try:
        load_designspace(doc)
    except Exception as e:
        print("RULE-15:", type(e).__name__, ":", e)


if __name__ == "__main__":
    rule_02_min_gt_max()
    rule_03_min_eq_max()
    rule_04_undefined_axis()
    rule_05_06_overlap_order()
    rule_08_09_missing_glyphs()
    rule_15_discrete_axis_crash()
