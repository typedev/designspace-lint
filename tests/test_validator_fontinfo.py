# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Font info is compared against the designspace default, as the build copies it.

The variable font is a copy of the master `findDefault()` names. This check
used to take whichever source was listed first, so a designspace listing Bold
first reported the Regular as the odd one out.
"""

from designspace_lint.checkers.fontinfo import UNITS_PER_EM_DIFFERS, FontInfoChecker
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
