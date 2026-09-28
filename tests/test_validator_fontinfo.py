# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Font info is compared against the designspace default, as the build copies it.

The variable font is a copy of the master `findDefault()` names. This check
used to take whichever source was listed first, so a designspace listing Bold
first reported the Regular as the odd one out.
"""

from designspace_lint.checkers.fontinfo import (
    FIELD_DIFFERS,
    REQUIRED_FIELD_MISSING,
    UNITS_PER_EM_DIFFERS,
    FontInfoChecker,
)
from fakes import build_designspace


def test_the_default_is_the_reference_whatever_the_source_order():
    entry = build_designspace(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 400, "default": 400, "maximum": 900}],
        sources=[
            {"name": "Bold", "location": {"Weight": 900}, "glyphs": ["A"], "upm": 2048},
            {"name": "Regular", "location": {"Weight": 400}, "glyphs": ["A"]},
        ],
    )
    results = [r for r in FontInfoChecker(entry=entry).check() if r.code == UNITS_PER_EM_DIFFERS]

    assert [r.location for r in results] == ["Bold.ufo"]


def _two(default_info=None, other_info=None):
    entry = build_designspace(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 400, "default": 400, "maximum": 900}],
        sources=[
            {"name": "Regular", "location": {"Weight": 400}, "glyphs": ["A"]},
            {"name": "Bold", "location": {"Weight": 900}, "glyphs": ["A"]},
        ],
    )
    for source, values in zip(entry.sources, (default_info, other_info), strict=True):
        for field, value in (values or {}).items():
            setattr(source.font.info, field, value)
    return [r.code for r in FontInfoChecker(entry=entry).check()]


def test_a_default_without_units_per_em_is_reported():
    assert REQUIRED_FIELD_MISSING in _two(default_info={"unitsPerEm": None})


def test_a_version_that_differs_from_the_default_is_reported():
    codes = _two(default_info={"versionMajor": 2}, other_info={"versionMajor": 1})
    assert FIELD_DIFFERS in codes
