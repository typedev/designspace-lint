# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
The run as a whole: what stops it, what does not, and what it never swallows.

Each case here is one the September 2026 audit found silently losing checks:
a structural problem in one discrete slice left every later slice unchecked, a
designspace with only discrete axes reported "no axes" once per slice and then
nothing, a check that raised vanished into a log line, and one missing UFO
stopped the run before any of the masters that did open were looked at.

The fake sources point at UFOs that do not exist on disk, so every run here
also reports 2.1 for each of them -- which is itself the point of the last case.
"""

from fontTools.designspaceLib import InstanceDescriptor

from designspace_lint import Linter, lint
from designspace_lint.checkers.axes import NO_AXES, NO_CONTINUOUS_AXIS
from designspace_lint.checkers.instances import (
    INSTANCE_NONE_DEFINED,
    INSTANCE_UNKNOWN_LOCATION_LABEL,
)
from designspace_lint.checkers.sources import SOURCE_FILE_NOT_FOUND
from designspace_lint.engine import PHASE_FAILED
from designspace_lint.model import (
    CATEGORY_FILE,
    CATEGORY_GEOMETRY,
    CATEGORY_INSTANCES,
    CATEGORY_SOURCES,
    SEVERITY_STRUCTURAL,
)
from fakes import build_designspace

WEIGHT = {"name": "Weight", "tag": "wght", "minimum": 400, "default": 400, "maximum": 900}
ITALIC = {"name": "Italic", "tag": "ital", "values": [0, 1], "default": 0}


def _pairs(results):
    return [(r.category, r.code) for r in results]


def test_a_check_that_raises_becomes_a_finding():
    entry = build_designspace(
        axes=[WEIGHT],
        sources=[{"name": "Regular", "location": {"Weight": 400}, "glyphs": ["A"]}],
    )

    class Exploding:
        def __init__(self, **kwargs):
            pass

        def check(self):
            raise RuntimeError("boom")
            yield  # pragma: no cover

    linter = Linter(designspace=entry)
    linter._checkers["rules"] = Exploding
    results = list(linter.run())

    failed = [r for r in results if (r.category, r.code) == (CATEGORY_FILE, PHASE_FAILED)]
    assert len(failed) == 1
    assert failed[0].raw_data["phase"] == "rules"
    assert failed[0].severity == SEVERITY_STRUCTURAL
    assert not failed[0].is_structural  # reported, but the run goes on
    # ...and the phases after it still ran
    assert any(r.raw_data.get("phase") != "rules" for r in results)


def test_a_structural_problem_in_one_slice_leaves_the_next_slice_checked():
    """The stop flag used to be reset once per run, not once per slice."""
    entry = build_designspace(
        axes=[WEIGHT, ITALIC],
        sources=[
            # out of range: structural, stops the upright slice after sources
            {"name": "Regular", "location": {"Weight": 400, "Italic": 0}, "glyphs": ["A"]},
            {"name": "Heavy", "location": {"Weight": 2000, "Italic": 0}, "glyphs": ["A"]},
            {"name": "Italic", "location": {"Weight": 400, "Italic": 1}, "glyphs": ["A"]},
        ],
    )
    results = lint(entry)

    italic = [r for r in results if "Italic:1" in r.location]
    assert (CATEGORY_SOURCES, SOURCE_FILE_NOT_FOUND) in _pairs(italic)
    assert (CATEGORY_INSTANCES, INSTANCE_NONE_DEFINED) in _pairs(italic)


def test_only_discrete_axes_is_one_finding_not_a_blackout():
    """Each slice has no axes by construction; that is not "no axes defined"."""
    entry = build_designspace(
        axes=[ITALIC],
        sources=[
            {"name": "Roman", "location": {"Italic": 0}, "glyphs": ["A"]},
            {"name": "Italic", "location": {"Italic": 1}, "glyphs": ["A"]},
        ],
    )
    pairs = _pairs(lint(entry))

    assert (CATEGORY_GEOMETRY, NO_AXES) not in pairs
    assert pairs.count((CATEGORY_GEOMETRY, NO_CONTINUOUS_AXIS)) == 1
    # both slices went on to their sources
    assert pairs.count((CATEGORY_SOURCES, SOURCE_FILE_NOT_FOUND)) == 2


def test_an_unknown_location_label_does_not_take_the_run_down():
    """With discrete axes the split itself raises on it; report both, raise neither."""
    entry = build_designspace(
        axes=[WEIGHT, ITALIC],
        sources=[{"name": "Regular", "location": {"Weight": 400, "Italic": 0}, "glyphs": ["A"]}],
    )
    instance = InstanceDescriptor()
    instance.familyName, instance.styleName = "F", "Bold"
    instance.locationLabel = "Bold"
    entry.doc.addInstance(instance)

    pairs = _pairs(lint(entry))

    assert (CATEGORY_INSTANCES, INSTANCE_UNKNOWN_LOCATION_LABEL) in pairs
    assert (CATEGORY_FILE, PHASE_FAILED) in pairs


def test_a_missing_ufo_does_not_stop_the_run():
    """Amstelvar A2 v2: 13 of 150 UFOs missing, and the other 137 went unchecked."""
    entry = build_designspace(
        axes=[WEIGHT],
        sources=[
            {"name": "Regular", "location": {"Weight": 400}, "glyphs": ["A"]},
            {"name": "Bold", "location": {"Weight": 900}, "glyphs": ["A"]},
        ],
    )
    results = lint(entry)
    missing = [r for r in results if (r.category, r.code) == (CATEGORY_SOURCES, 1)]

    assert len(missing) == 2
    assert all(r.severity == SEVERITY_STRUCTURAL for r in missing)
    # a later phase ran
    assert (CATEGORY_INSTANCES, INSTANCE_NONE_DEFINED) in _pairs(results)
