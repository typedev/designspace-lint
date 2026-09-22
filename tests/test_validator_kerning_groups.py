# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Kerning checks that follow what ufo2ft does with groups.

Pair sets are not compared: a pair a master does not list resolves to that
master's group value or to 0, which is what its absence means in a UFO. What is
reported is what the build swallows silently -- a master with no groups at all
(its class kerning becomes 0), a group redefined with other members, and a
glyph claimed by two groups of the same side (the second group is discarded).
"""

import pytest

pytest.importorskip("gi")

from designspace_lint.checkers.kerning import (  # noqa: E402
    GLYPH_IN_TWO_KERN_GROUPS,
    KERNING_GROUP_DIFFERS,
    NO_KERNING_GROUPS_SOURCE,
    NO_KERNING_IN_SOURCE,
    KerningChecker,
)
from tests.fakes_designspace import build_entry  # noqa: E402

GROUPS = {"public.kern1.A": ["A", "Agrave"], "public.kern2.V": ["V", "W"]}
KERNING = {("public.kern1.A", "public.kern2.V"): -50}


def _entry(second_source, first_source=None):
    first = first_source or {
        "name": "Light",
        "location": {"Weight": 0},
        "glyphs": ["A", "Agrave", "V", "W"],
        "groups": GROUPS,
        "kerning": KERNING,
    }
    return build_entry(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}],
        sources=[first, second_source],
    )


def _codes(entry):
    return [r.code for r in KerningChecker(entry=entry).check()]


def test_master_with_pairs_but_without_kern_groups_is_reported():
    entry = _entry(
        {
            "name": "Bold",
            "location": {"Weight": 100},
            "glyphs": ["A", "Agrave", "V", "W"],
            "kerning": {("A", "V"): -30},  # flat pairs only, no groups
        }
    )

    assert NO_KERNING_GROUPS_SOURCE in _codes(entry)


def test_master_with_no_kerning_at_all_is_reported_once():
    """One row, not two: no pairs is the cause, no groups only its symptom."""
    entry = _entry(
        {
            "name": "Bold",
            "location": {"Weight": 100},
            "glyphs": ["A", "Agrave", "V", "W"],
        }
    )

    results = [r for r in KerningChecker(entry=entry).check() if r.location.startswith("Bold")]

    assert [r.code for r in results] == [NO_KERNING_IN_SOURCE]
    assert results[0].is_structural is True
    assert "layer" in results[0].details


def test_groups_without_pairs_do_not_excuse_the_master():
    """Verified by building a VF: the value lookup still lands on 0."""
    entry = _entry(
        {
            "name": "Bold",
            "location": {"Weight": 100},
            "glyphs": ["A", "Agrave", "V", "W"],
            "groups": GROUPS,  # groups but no pairs
        }
    )

    codes = _codes(entry)

    assert NO_KERNING_IN_SOURCE in codes
    assert NO_KERNING_GROUPS_SOURCE not in codes


def test_different_pair_sets_are_not_reported():
    entry = _entry(
        {
            "name": "Bold",
            "location": {"Weight": 100},
            "glyphs": ["A", "Agrave", "V", "W"],
            "groups": GROUPS,
            "kerning": {("public.kern1.A", "public.kern2.V"): -40, ("A", "W"): -10},
        }
    )

    assert _codes(entry) == []


def test_group_with_different_members_is_reported():
    entry = _entry(
        {
            "name": "Bold",
            "location": {"Weight": 100},
            "glyphs": ["A", "Agrave", "V", "W"],
            "groups": {"public.kern1.A": ["A"], "public.kern2.V": ["V", "W"]},
            "kerning": KERNING,
        }
    )

    assert KERNING_GROUP_DIFFERS in _codes(entry)


def test_glyph_in_two_groups_of_the_same_side():
    entry = _entry(
        {
            "name": "Bold",
            "location": {"Weight": 100},
            "glyphs": ["A", "Agrave", "V", "W"],
            "groups": {
                "public.kern1.A": ["A", "Agrave"],
                "public.kern1.Alt": ["A"],  # A claimed twice on side 1
                "public.kern2.V": ["V", "W"],
            },
            "kerning": KERNING,
        }
    )

    results = [r for r in KerningChecker(entry=entry).check() if r.code == GLYPH_IN_TWO_KERN_GROUPS]

    assert len(results) == 1
    assert results[0].glyph_name == "A"
    assert results[0].is_structural is True


def test_the_same_glyph_on_both_sides_is_fine():
    entry = _entry(
        {
            "name": "Bold",
            "location": {"Weight": 100},
            "glyphs": ["A", "Agrave", "V", "W"],
            "groups": {"public.kern1.A": ["A", "Agrave"], "public.kern2.A": ["A", "Agrave"]},
            "kerning": KERNING,
        }
    )

    assert GLYPH_IN_TWO_KERN_GROUPS not in _codes(entry)


def test_layer_masters_are_skipped():
    """A layer has no kerning of its own, and ufo2ft ignores it."""
    entry = build_entry(
        axes=[{"name": "Width", "tag": "wdth", "minimum": 0, "default": 0, "maximum": 100}],
        sources=[
            {
                "name": "Narrow",
                "path": "/tmp/fake/shared.ufo",
                "location": {"Width": 0},
                "glyphs": ["A", "V"],
                "groups": GROUPS,
                "kerning": KERNING,
                "layers": {"Wide": ["A", "V"]},
            },
            {
                "name": "Wide",
                "path": "/tmp/fake/shared.ufo",
                "location": {"Width": 100},
                "layer_name": "Wide",
            },
        ],
    )

    assert _codes(entry) == []
