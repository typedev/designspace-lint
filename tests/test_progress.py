# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Progress and cancel inside the phases that walk the glyphs.

The engine used to hand its progress callback to the glyphs phase only and
count every other phase as one unit, so on a large designspace the bar stood
still for the whole point-correspondence phase (about a minute) and then
jumped. A cancel waited for the next finding or the end of the phase, and a
phase with nothing to report has no next finding.
"""

import threading

from designspace_lint import Linter
from fakes import FakeGlyph, build_designspace

SQUARE = [(0, 0), (100, 0), (100, 100), (0, 100)]
WEIGHT = {"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}
ITALIC = {"name": "Italic", "tag": "ital", "values": [0, 1], "default": 0}
NAMES = [f"g{i:02d}" for i in range(20)]


def _glyphs(dx=0):
    return {
        name: FakeGlyph(name, contours=[[(x + dx, y) for x, y in SQUARE]], unicodes=[0x100 + i])
        for i, name in enumerate(NAMES)
    }


def _entry(italic=False):
    sources = [
        {"name": "Light", "location": {"Weight": 0}, "glyphs": _glyphs()},
        {"name": "Bold", "location": {"Weight": 100}, "glyphs": _glyphs(10)},
    ]
    axes = [WEIGHT]
    if italic:
        axes.append(ITALIC)
        for source in sources:
            source["location"]["Italic"] = 0
        sources += [
            {"name": "LightItalic", "location": {"Weight": 0, "Italic": 1}, "glyphs": _glyphs()},
            {"name": "BoldItalic", "location": {"Weight": 100, "Italic": 1}, "glyphs": _glyphs(10)},
        ]
    return build_designspace(axes=axes, sources=sources)


def _ticks(entry, **kwargs):
    ticks = []
    linter = Linter(designspace=entry, interpolatable=True, construction=True, **kwargs)
    list(linter.run(on_progress=lambda done, total, message: ticks.append((done, total, message))))
    return ticks


def test_every_glyph_phase_reports_each_glyph():
    ticks = _ticks(_entry())
    for stem in ("Checking glyphs", "Checking point correspondence"):
        per_glyph = [message for _d, _t, message in ticks if message.startswith(f"{stem} (")]
        assert per_glyph[-1] == f"{stem} ({len(NAMES)}/{len(NAMES)})", stem
        assert len(per_glyph) == len(NAMES), stem


def test_the_bar_only_moves_forward_and_ends_full():
    for italic in (False, True):
        ticks = _ticks(_entry(italic=italic))
        done = [d for d, _t, _m in ticks]
        assert done == sorted(done), f"italic={italic}"
        total = ticks[-1][1]
        assert {t for _d, t, _m in ticks} == {total}
        assert done[-1] == total


def test_a_cancel_stops_a_phase_between_glyphs():
    cancel = threading.Event()
    seen = []

    def on_progress(done, total, message):
        if message.startswith("Checking point correspondence ("):
            seen.append(message)
            cancel.set()

    linter = Linter(designspace=_entry(), cancel=cancel, interpolatable=True)
    list(linter.run(on_progress=on_progress))
    # the phase finds nothing, so only the per-glyph poll can stop it
    assert seen == ["Checking point correspondence (1/20)"]
