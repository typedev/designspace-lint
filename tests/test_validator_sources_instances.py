# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Sources and instances, read the way fontTools and varLib read them.

Duplicate locations are compared as varLib compares them, with omitted axes
filled in. A source or instance at a discrete value the axis does not declare
falls into no slice when the document is split. An instance naming a location
label that does not exist makes the split and the build fail. None of these
say anything when the file is read.
"""

from designspace_lint.checkers.instances import (
    INSTANCE_MULTIPLE_ON_LOCATION,
    INSTANCE_NAME_REUSED,
    INSTANCE_OFF_DISCRETE_VALUES,
    INSTANCE_UNKNOWN_LOCATION_LABEL,
    InstancesChecker,
)
from designspace_lint.checkers.sources import (
    DUPLICATE_SOURCE_LOCATION,
    SOURCE_OFF_DISCRETE_VALUES,
    SourcesChecker,
)
from dsxml import ITALIC, WEIGHT, ds, source

WIDTH = '<axis tag="wdth" name="Width" minimum="50" default="100" maximum="200"/>'


def _instance(family, style, label=None, **location):
    attrs = f'familyname="{family}" stylename="{style}"' if family else f'stylename="{style}"'
    if label:
        return f'<instance {attrs} location="{label}"/>'
    dims = "".join(f'<dimension name="{k}" xvalue="{v}"/>' for k, v in location.items())
    return f"<instance {attrs}><location>{dims}</location></instance>"


# --- 2.6 -------------------------------------------------------------------


def test_duplicates_spelled_differently_are_found():
    """SRC-02/03: one leaves Width out, the other writes its default down.

    varLib fills both in before comparing and refuses: "Locations must be
    unique".
    """
    doc = ds(
        WEIGHT + WIDTH,
        source("Regular.ufo", Weight=400)
        + source("Bold.ufo", Weight=900)
        + source("Bold-copy.ufo", Weight=900, Width=100),
    )
    results = [r for r in SourcesChecker(doc=doc).check() if r.code == DUPLICATE_SOURCE_LOCATION]

    assert [r.location for r in results] == ["Bold-copy.ufo"]
    assert "Bold.ufo" in results[0].description


def test_a_default_source_with_no_location_collides_with_an_explicit_one():
    """ "More than one base master" at the default, written two ways."""
    doc = ds(WEIGHT, source("A.ufo") + source("B.ufo", Weight=400))
    codes = [r.code for r in SourcesChecker(doc=doc).check()]
    assert DUPLICATE_SOURCE_LOCATION in codes


def test_distinct_locations_are_not_duplicates():
    doc = ds(WEIGHT + WIDTH, source("A.ufo", Weight=400) + source("B.ufo", Weight=400, Width=150))
    codes = [r.code for r in SourcesChecker(doc=doc).check()]
    assert DUPLICATE_SOURCE_LOCATION not in codes


# --- 2.10 / 3.11 ------------------------------------------------------------


def test_a_source_off_the_discrete_values_is_reported_on_the_whole_document():
    """DISC-10: the source at Italic=2 belongs to no slice and vanishes silently."""
    doc = ds(
        WEIGHT + ITALIC,
        source("R.ufo", Weight=400, Italic=0)
        + source("I.ufo", Weight=400, Italic=1)
        + source("X.ufo", Weight=400, Italic=2),
    )
    results = list(SourcesChecker(doc=doc).check_document(doc))

    assert [(r.code, r.location) for r in results] == [(SOURCE_OFF_DISCRETE_VALUES, "X.ufo")]
    assert "Italic=2" in results[0].description


def test_an_instance_off_the_discrete_values_is_reported():
    doc = ds(
        WEIGHT + ITALIC,
        source("R.ufo", Weight=400, Italic=0),
        instances=_instance("F", "Oblique", Weight=400, Italic=0.5),
    )
    results = list(InstancesChecker(doc=doc).check_document(doc))
    assert [r.code for r in results] == [INSTANCE_OFF_DISCRETE_VALUES]


# --- 3.4, 3.12, 3.13 --------------------------------------------------------


def test_duplicate_instances_without_a_family_name_are_still_reported():
    """3.4 used to join familyName + styleName and raise on None, losing itself."""
    doc = ds(
        WEIGHT,
        source("R.ufo", Weight=400),
        instances=_instance(None, "Bold", Weight=700) + _instance(None, "Heavy", Weight=700),
    )
    codes = [r.code for r in InstancesChecker(doc=doc).check()]
    assert INSTANCE_MULTIPLE_ON_LOCATION in codes


def test_an_unknown_location_label_is_reported():
    """LABEL-05: read without complaint, then fatal to the split and the build."""
    doc = ds(
        WEIGHT,
        source("R.ufo", Weight=400),
        labels='<label name="Bold"><location><dimension name="Weight" uservalue="700"/>'
        "</location></label>",
        instances=_instance("F", "Bold", label="Bold") + _instance("F", "Black", label="Blak"),
    )

    for results in (
        list(InstancesChecker(doc=doc).check()),
        list(InstancesChecker(doc=doc).check_document(doc)),
    ):
        unknown = [r for r in results if r.code == INSTANCE_UNKNOWN_LOCATION_LABEL]
        assert [r.raw_data["locationLabel"] for r in unknown] == ["Blak"]


def test_one_name_at_two_locations_is_reported():
    """INST-08: a style menu cannot tell them apart."""
    doc = ds(
        WEIGHT,
        source("R.ufo", Weight=400),
        instances=_instance("F", "Bold", Weight=700) + _instance("F", "Bold", Weight=800),
    )
    results = [r for r in InstancesChecker(doc=doc).check() if r.code == INSTANCE_NAME_REUSED]

    assert len(results) == 1
    assert results[0].location == "F Bold"
