# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
DesignSpace 5 labels, and the STAT table and instance names built from them.

What fontTools 4.65 does, verified by building STAT and fvar in memory: labels
outside the font are dropped from STAT, nothing else about them is checked,
and splitting the document for the build renames every instance whose style
name is not given with xml:lang="en" to what the labels spell -- the empty
string when they are all elidable and there is no elidedfallbackname.
"""

from designspace_lint.checkers.labels import (
    ALL_ELIDED_NO_FALLBACK,
    INSTANCE_NAME_REPLACED,
    LABEL_OUTSIDE,
    LABEL_REDUNDANT,
    PARTIAL_LOCATION_LABEL,
    RANGE_LABEL_MALFORMED,
    STYLE_LINK,
    VALUE_WITHOUT_LABEL,
    LabelsChecker,
)
from designspace_lint.model import SEVERITY_DESIGN, SEVERITY_STRUCTURAL
from dsxml import ds, source


def _label(name, value, elidable=False, lo=None, hi=None, linked=None):
    attrs = f'name="{name}" uservalue="{value}"'
    if lo is not None:
        attrs += f' userminimum="{lo}" usermaximum="{hi}"'
    if elidable:
        attrs += ' elidable="true"'
    if linked is not None:
        attrs += f' linkeduservalue="{linked}"'
    return f"<label {attrs}/>"


def _weight(*labels):
    return (
        '<axis tag="wght" name="Weight" minimum="100" default="400" maximum="900">'
        f"<labels>{''.join(labels)}</labels></axis>"
    )


def _italic(*labels):
    return (
        '<axis tag="ital" name="Italic" values="0 1" default="0">'
        f"<labels>{''.join(labels)}</labels></axis>"
    )


REGULAR = _label("Regular", 400, elidable=True, linked=700)
BOLD = _label("Bold", 700)


def _instance(style, weight, english=None):
    names = f'<stylename xml:lang="en">{english}</stylename>' if english else ""
    return (
        f'<instance familyname="Fam" stylename="{style}">{names}<location>'
        f'<dimension name="Weight" uservalue="{weight}"/></location></instance>'
    )


def _check(axes, instances="", fallback=True, labels=""):
    doc = ds(axes, source("R.ufo", Weight=400), instances=instances, labels=labels)
    if fallback:
        doc.elidedFallbackName = "Regular"
    return list(LabelsChecker(doc=doc).check())


def _codes(*args, **kwargs):
    return [r.code for r in _check(*args, **kwargs)]


def test_labelled_and_named_consistently_is_fine():
    assert _codes(_weight(REGULAR, BOLD), _instance("Regular", 400) + _instance("Bold", 700)) == []


def test_no_labels_means_nothing_to_check():
    axis = '<axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>'
    assert _codes(axis, _instance("Whatever", 700), fallback=False) == []


# --- 10.0 / 10.2 -----------------------------------------------------------


def test_an_instance_name_the_labels_spell_differently_is_replaced():
    results = [
        r
        for r in _check(_weight(REGULAR, BOLD), _instance("Heavy", 700))
        if r.code == INSTANCE_NAME_REPLACED
    ]
    assert len(results) == 1
    assert results[0].raw_data["statStyleName"] == "Bold"
    assert results[0].severity == SEVERITY_DESIGN


def test_an_english_style_name_is_kept():
    assert INSTANCE_NAME_REPLACED not in _codes(
        _weight(REGULAR, BOLD), _instance("Heavy", 700, english="Heavy")
    )


def test_all_elided_without_a_fallback_leaves_the_regular_nameless():
    results = _check(_weight(REGULAR, BOLD), _instance("Regular", 400), fallback=False)
    replaced = [r for r in results if r.code == INSTANCE_NAME_REPLACED]

    assert replaced and replaced[0].raw_data["statStyleName"] == ""
    assert replaced[0].severity == SEVERITY_STRUCTURAL
    assert ALL_ELIDED_NO_FALLBACK in [r.code for r in results]


# --- 10.1 ------------------------------------------------------------------


def test_a_value_no_label_covers_is_reported():
    results = [
        r
        for r in _check(_weight(REGULAR, BOLD), _instance("Thin", 200))
        if r.code == VALUE_WITHOUT_LABEL
    ]
    assert [r.raw_data["value"] for r in results] == [200]


def test_a_range_label_covers_its_range():
    light = _label("Light", 300, lo=200, hi=350)
    codes = _codes(_weight(REGULAR, BOLD, light), _instance("Light", 250, english="Light"))
    assert VALUE_WITHOUT_LABEL not in codes


# --- 10.3 / 10.4 / 10.5 / 10.7 ----------------------------------------------


def test_a_label_outside_its_axis_is_dropped_from_stat():
    assert LABEL_OUTSIDE in _codes(_weight(REGULAR, BOLD, _label("Hairline", 50)))


def test_a_location_label_that_leaves_an_axis_out_never_names_anything():
    axes = _weight(REGULAR, BOLD) + _italic(_label("Upright", 0, elidable=True, linked=1))
    labels = (
        '<label name="Reading"><location><dimension name="Weight" uservalue="450"/>'
        "</location></label>"
    )
    assert PARTIAL_LOCATION_LABEL in _codes(axes, labels=labels)


def test_malformed_range_labels_are_reported():
    for label in (
        _label("Odd", 500, lo=600, hi=450),  # min above max
        _label("Odd", 500, lo=550, hi=600),  # value outside its range
        _label("Odd", 500, lo=450, hi=550, linked=700),  # range and link
    ):
        assert RANGE_LABEL_MALFORMED in _codes(_weight(REGULAR, BOLD, label)), label


def test_overlapping_range_labels_are_reported():
    a = _label("Medium", 500, lo=450, hi=600)
    b = _label("Semibold", 600, lo=550, hi=650)
    assert RANGE_LABEL_MALFORMED in _codes(_weight(REGULAR, BOLD, a, b))


def test_two_labels_at_one_value_are_noted():
    assert LABEL_REDUNDANT in _codes(_weight(REGULAR, BOLD, _label("Book", 400)))


# --- 10.6 ------------------------------------------------------------------


def test_a_link_to_no_label_is_reported():
    codes = _codes(_weight(_label("Regular", 400, elidable=True, linked=650), BOLD))
    assert STYLE_LINK in codes


def test_no_link_between_regular_and_bold_is_noted_when_instances_rely_on_it():
    unlinked = _weight(_label("Regular", 400, elidable=True), BOLD)
    assert STYLE_LINK in _codes(unlinked, _instance("Bold", 700))
    assert STYLE_LINK not in _codes(_weight(REGULAR, BOLD), _instance("Bold", 700))


def test_any_localised_style_name_keeps_the_name():
    """The split keeps an instance's localised names when it has any at all.

    fvar then adds "en" from the stylename. So a German name alone is enough
    to keep "Heavy" -- reported by the DSSketch agent, confirmed in split.py
    and varLib._add_fvar.
    """
    instance = (
        '<instance familyname="Fam" stylename="Heavy">'
        '<stylename xml:lang="de">Schwer</stylename><location>'
        '<dimension name="Weight" uservalue="700"/></location></instance>'
    )
    assert INSTANCE_NAME_REPLACED not in _codes(_weight(REGULAR, BOLD), instance)
