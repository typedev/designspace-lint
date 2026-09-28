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
    INSTANCE_LOCATION_MISSING,
    INSTANCE_UNDEFINED_AXIS,
    INSTANCE_MULTIPLE_ON_LOCATION,
    INSTANCE_NAME_REUSED,
    INSTANCE_OFF_DISCRETE_VALUES,
    INSTANCE_UNKNOWN_LOCATION_LABEL,
    InstancesChecker,
)
from designspace_lint.checkers.sources import (
    DUPLICATE_SOURCE_LOCATION,
    SOURCE_LAYER_NOT_FOUND,
    SOURCE_LOCATION_MISSING_AXIS,
    SOURCE_NOT_VALID_UFO,
    SOURCE_OFF_DISCRETE_VALUES,
    SourcesChecker,
)
from dsxml import ITALIC, WEIGHT, ds, source, written

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

    unknown = [
        r
        for r in InstancesChecker(doc=doc).check_document(doc)
        if r.code == INSTANCE_UNKNOWN_LOCATION_LABEL
    ]
    assert [r.raw_data["locationLabel"] for r in unknown] == ["Blak"]
    # the per-slice check leaves it to the document-level one: reported once
    codes = [r.code for r in InstancesChecker(doc=doc).check()]
    assert INSTANCE_UNKNOWN_LOCATION_LABEL not in codes


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


# --- 2.3 / 3.2, from the file itself ---------------------------------------


def test_a_dimension_on_an_undeclared_axis_is_read_from_the_file(tmp_path):
    """fontTools drops it while reading, so only the file still shows it.

    Usually an axis that was renamed: the source quietly moves to the default
    of the axis it was meant for.
    """
    doc = written(
        tmp_path,
        WEIGHT,
        source("R.ufo", Weight=400) + source("B.ufo", Wieght=900),
        instances=_instance("F", "Bold", Wieght=700),
        labels='<label name="Heavy"><location><dimension name="Wdth" uservalue="100"/>'
        "</location></label>",
    )
    assert doc.sources[1].location == {}  # the reader has already dropped it

    sources = [r for r in SourcesChecker(doc=doc).check_document(doc)]
    instances = [r for r in InstancesChecker(doc=doc).check_document(doc)]

    assert [(r.code, r.location, r.raw_data["axisName"]) for r in sources] == [
        (SOURCE_LOCATION_MISSING_AXIS, "B.ufo", "Wieght")
    ]
    assert [(r.code, r.location) for r in instances] == [
        (INSTANCE_UNDEFINED_AXIS, "F Bold"),
        (INSTANCE_UNDEFINED_AXIS, "label Heavy"),
    ]


def test_a_clean_file_has_no_stray_dimensions(tmp_path):
    doc = written(tmp_path, WEIGHT, source("R.ufo", Weight=400))
    assert list(SourcesChecker(doc=doc).check_document(doc)) == []


# --- files on disk: 2.2, 2.7 ------------------------------------------------


def _ufo(path, layers=("public.default",)):
    """A UFO directory with just enough on disk for the file checks."""
    import plistlib

    path.mkdir()
    (path / "metainfo.plist").write_bytes(plistlib.dumps({"formatVersion": 3}))
    (path / "glyphs").mkdir()
    contents = [
        [name, "glyphs" if name == "public.default" else f"glyphs.{name}"] for name in layers
    ]
    (path / "layercontents.plist").write_bytes(plistlib.dumps(contents))
    return path


def test_a_source_that_is_not_a_ufo_is_reported(tmp_path):
    (tmp_path / "Regular.ufo").write_text("not a directory")
    doc = written(tmp_path, WEIGHT, source("Regular.ufo", Weight=400))
    results = [r for r in SourcesChecker(doc=doc).check() if r.code == SOURCE_NOT_VALID_UFO]

    assert [r.raw_data["sourceName"] for r in results] == ["Regular.ufo"]
    assert not results[0].is_structural  # reported, but the other masters are still checked


def test_a_source_layer_the_ufo_does_not_have_is_reported(tmp_path):
    _ufo(tmp_path / "Family.ufo", layers=("public.default", "Bold"))
    sources = (
        source("Family.ufo", Weight=400)
        + '<source filename="Family.ufo" name="Black" layer="Black"><location>'
        '<dimension name="Weight" xvalue="900"/></location></source>'
    )
    doc = written(tmp_path, WEIGHT, sources)
    results = [r for r in SourcesChecker(doc=doc).check() if r.code == SOURCE_LAYER_NOT_FOUND]

    assert [r.raw_data["layerName"] for r in results] == ["Black"]


def test_an_existing_layer_is_fine(tmp_path):
    _ufo(tmp_path / "Family.ufo", layers=("public.default", "Bold"))
    sources = (
        source("Family.ufo", Weight=400)
        + '<source filename="Family.ufo" name="Bold" layer="Bold"><location>'
        '<dimension name="Weight" xvalue="900"/></location></source>'
    )
    doc = written(tmp_path, WEIGHT, sources)
    assert SOURCE_LAYER_NOT_FOUND not in [r.code for r in SourcesChecker(doc=doc).check()]


# --- 3.1 -------------------------------------------------------------------


def test_an_instance_whose_location_cannot_be_resolved_is_reported():
    """fontTools always resolves one for a document it read; a host object may not."""
    from fontTools.designspaceLib import InstanceDescriptor

    class Unplaced(InstanceDescriptor):
        location = None

        def getFullDesignLocation(self, doc):
            raise ValueError("no location")

    doc = ds(WEIGHT, source("R.ufo", Weight=400))
    instance = Unplaced()
    instance.designLocation = None
    instance.familyName, instance.styleName, instance.filename = "Fam", "Lost", "Lost.ufo"
    doc.instances.append(instance)

    results = [r for r in InstancesChecker(doc=doc).check() if r.code == INSTANCE_LOCATION_MISSING]
    assert [r.raw_data["instanceIndex"] for r in results] == [0]
