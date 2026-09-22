# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
When features.fea keeps ufo2ft on the variable-feature path.

ufo2ft compiles one variable GPOS from the default master's features only when
every other master's features.fea tokenizes the same as the default's, or all
of them are empty. Anything else -- including a mix of the two -- silently
switches the build to per-master feature compilation, where varLib's merge is
what finally fails, pointing at something else.
"""

import pytest

pytest.importorskip("gi")
pytest.importorskip("ufo2ft")

from font_rover.designspace_validator.checkers.features import (  # noqa: E402
    FEATURES_DIFFER_FROM_DEFAULT,
    FeaturesChecker,
)
from tests.fakes_designspace import build_entry  # noqa: E402

KERN_FEA = "feature kern {\n    pos A V -40;\n} kern;\n"
OTHER_FEA = "feature kern {\n    pos A V -90;\n} kern;\n"


def _entry(*feature_texts):
    return build_entry(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}],
        sources=[
            {
                "name": f"M{i}",
                "location": {"Weight": i * 50},
                "glyphs": ["A", "V"],
                "features": text,
            }
            for i, text in enumerate(feature_texts)
        ],
    )


def _codes(entry):
    return [r.code for r in FeaturesChecker(entry=entry).check()]


def test_identical_features_are_fine():
    assert FEATURES_DIFFER_FROM_DEFAULT not in _codes(_entry(KERN_FEA, KERN_FEA, KERN_FEA))


def test_features_only_in_the_default_are_fine():
    assert FEATURES_DIFFER_FROM_DEFAULT not in _codes(_entry(KERN_FEA, "", ""))


def test_no_features_anywhere_is_fine():
    assert FEATURES_DIFFER_FROM_DEFAULT not in _codes(_entry("", "", ""))


def test_differing_features_are_reported():
    assert FEATURES_DIFFER_FROM_DEFAULT in _codes(_entry(KERN_FEA, KERN_FEA, OTHER_FEA))


def test_a_mix_of_identical_and_empty_is_reported():
    """ufo2ft accepts 'all equal' or 'all empty', not a mix of the two."""
    assert FEATURES_DIFFER_FROM_DEFAULT in _codes(_entry(KERN_FEA, KERN_FEA, ""))


def test_comments_and_whitespace_do_not_count_as_a_difference():
    spaced = "feature kern {\n\n    # a note\n    pos A V -40;\n} kern;\n"

    assert FEATURES_DIFFER_FROM_DEFAULT not in _codes(_entry(KERN_FEA, spaced, spaced))


def test_the_report_names_the_offending_master():
    results = [
        r
        for r in FeaturesChecker(entry=_entry(KERN_FEA, KERN_FEA, OTHER_FEA)).check()
        if r.code == FEATURES_DIFFER_FROM_DEFAULT
    ]

    assert results
    assert all(r.is_structural for r in results)
    assert any("M2" in r.location for r in results)
