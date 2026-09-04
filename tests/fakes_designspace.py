# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Minimal stand-ins for fontParts objects, for headless designspace tests.

Real `RFont`/`RGlyph` need a UFO on disk and drag in defcon notifications; these
model just enough of the shape the layer and source code touches — a default
layer plus named extra layers, glyphs that know which layer they belong to.

Kept faithful on purpose: the code under test resolves layers through
`layerOrder` and `defaultLayer` as well as `getLayer`, so a fake missing those
would pass tests that a real font fails.
"""

from pathlib import Path

from font_rover.designspace import DesignSpaceEntry, FontSource


class FakeGlyph:
    def __init__(self, name, layer=None, width=500):
        self.name = name
        self.layer = layer
        self.width = width
        self.unicodes = []
        self.lib = {}


class FakeLayer:
    def __init__(self, name, glyph_names):
        self.name = name
        self._glyphs = {n: FakeGlyph(n, layer=self) for n in glyph_names}

    def __contains__(self, name):
        return name in self._glyphs

    def __getitem__(self, name):
        return self._glyphs[name]

    def __iter__(self):
        return iter(self._glyphs.values())

    def keys(self):
        return list(self._glyphs)

    def newGlyph(self, name):
        glyph = FakeGlyph(name, layer=self, width=0)
        self._glyphs[name] = glyph
        return glyph


class FakeFont:
    """A default layer plus named extra layers."""

    def __init__(self, path, default_glyphs, layers=None, default_layer_name="public.default"):
        self.path = str(path)
        self._default = FakeLayer(default_layer_name, default_glyphs)
        self._layers = {name: FakeLayer(name, names) for name, names in (layers or {}).items()}

    # --- default layer is the font's own mapping, as in fontParts ---

    def __contains__(self, name):
        return name in self._default

    def __getitem__(self, name):
        return self._default[name]

    def keys(self):
        return self._default.keys()

    def newGlyph(self, name):
        return self._default.newGlyph(name)

    # --- layers ---

    @property
    def defaultLayer(self):
        return self._default

    @property
    def layerOrder(self):
        return [self._default.name] + list(self._layers)

    def getLayer(self, name):
        if name == self._default.name:
            return self._default
        return self._layers[name]  # KeyError when absent, as fontParts does


def plain_designspace():
    """Three ordinary masters, one UFO each. 'B' is missing from Bold."""
    sources = []
    for idx, (style, glyphs) in enumerate(
        [("Light", ["A", "B"]), ("Regular", ["A", "B"]), ("Bold", ["A"])]
    ):
        path = Path(f"/tmp/fake/{style}.ufo")
        sources.append(
            FontSource(
                font=FakeFont(path, glyphs),
                path=path,
                name=style,
                style_name=style,
                location={"wght": 100 * (idx + 1)},
            )
        )
    return DesignSpaceEntry(path=Path("/tmp/fake/test.designspace"), doc=None, sources=sources)


def layer_designspace():
    """Two masters that are LAYERS of one UFO — they share a path.

    The 'Wide' layer is sparse: it does not draw 'B'.
    """
    path = Path("/tmp/fake/shared.ufo")
    font = FakeFont(path, ["A", "B"], layers={"Wide": ["A"]})
    sources = [
        FontSource(font=font, path=path, name="Narrow", style_name="Narrow"),
        FontSource(font=font, path=path, name="Wide", style_name="Wide", layer_name="Wide"),
    ]
    return DesignSpaceEntry(path=Path("/tmp/fake/shared.designspace"), doc=None, sources=sources)


def entry_with_plain_layer():
    """One master whose UFO also has an ordinary, non-master layer.

    'sketch' draws only 'A', so it is sparse for 'B' — the case where a layer
    switch must refuse rather than hand back the default layer's outline.
    """
    path = Path("/tmp/fake/one.ufo")
    font = FakeFont(path, ["A", "B"], layers={"sketch": ["A"]})
    source = FontSource(font=font, path=path, name="Regular", style_name="Regular")
    return DesignSpaceEntry(path=Path("/tmp/fake/one.designspace"), doc=None, sources=[source])
