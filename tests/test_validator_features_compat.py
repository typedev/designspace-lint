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

pytest.importorskip("ufo2ft")

from designspace_lint.checkers.features import (
    FEATURES_DIFFER_FROM_DEFAULT,
    FeaturesChecker,
)
from fakes import build_designspace

KERN_FEA = "feature kern {\n    pos A V -40;\n} kern;\n"
OTHER_FEA = "feature kern {\n    pos A V -90;\n} kern;\n"


def _entry(*feature_texts):
    return build_designspace(
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


def test_one_result_for_the_designspace_naming_the_offenders():
    """Not one row per master: the combination is what decides the build."""
    results = [
        r
        for r in FeaturesChecker(entry=_entry(KERN_FEA, KERN_FEA, OTHER_FEA)).check()
        if r.code == FEATURES_DIFFER_FROM_DEFAULT
    ]

    assert len(results) == 1
    assert results[0].is_structural is True
    assert results[0].location == "designspace"
    assert "M2" in results[0].details
    assert results[0].raw_data["differing"] == ["M2.ufo (M2)"]


def test_a_large_mix_still_produces_a_single_row():
    entry = _entry(KERN_FEA, *([KERN_FEA] * 40), *([""] * 40))

    results = [
        r for r in FeaturesChecker(entry=entry).check() if r.code == FEATURES_DIFFER_FROM_DEFAULT
    ]

    assert len(results) == 1
    assert "40 match the default" in results[0].description
    assert "40 are empty" in results[0].description
