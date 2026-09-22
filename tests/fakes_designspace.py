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


class FakePoint:
    def __init__(self, x, y, type="line"):
        self.x = x
        self.y = y
        self.type = type


class FakeContour:
    def __init__(self, points):
        self.points = [p if isinstance(p, FakePoint) else FakePoint(*p) for p in points]


class FakeComponent:
    def __init__(self, base_glyph, transformation=(1, 0, 0, 1, 0, 0)):
        self.baseGlyph = base_glyph
        self.transformation = transformation


class FakeAnchor:
    def __init__(self, name, x, y):
        self.name = name
        self.x = x
        self.y = y


class FakeGlyph:
    def __init__(
        self,
        name,
        layer=None,
        width=500,
        contours=(),
        components=(),
        anchors=(),
        unicodes=(),
    ):
        self.name = name
        self.layer = layer
        self.width = width
        self.unicodes = list(unicodes)
        self.lib = {}
        self.contours = [c if isinstance(c, FakeContour) else FakeContour(c) for c in contours]
        self.components = [
            c if isinstance(c, FakeComponent) else FakeComponent(*c) for c in components
        ]
        self.anchors = [a if isinstance(a, FakeAnchor) else FakeAnchor(*a) for a in anchors]

    def __len__(self):
        return len(self.contours)

    def drawPoints(self, pen):
        """Enough of the point pen protocol for DigestPointStructurePen."""
        for contour in self.contours:
            pen.beginPath()
            for point in contour.points:
                segment_type = point.type if point.type != "offcurve" else None
                pen.addPoint((point.x, point.y), segmentType=segment_type)
            pen.endPath()
        for component in self.components:
            pen.addComponent(component.baseGlyph, component.transformation)


class FakeInfo:
    def __init__(self, upm=1000):
        self.unitsPerEm = upm
        self.ascender = int(upm * 0.8)
        self.descender = -int(upm * 0.2)
        self.xHeight = None
        self.capHeight = None
        self.italicAngle = 0


class FakeFeatures:
    def __init__(self, text=""):
        self.text = text


class FakeLayer:
    def __init__(self, name, glyph_names):
        self.name = name
        self._glyphs = {
            n: (g if isinstance(g, FakeGlyph) else FakeGlyph(n, layer=self))
            for n, g in (
                glyph_names.items()
                if isinstance(glyph_names, dict)
                else ((n, None) for n in glyph_names)
            )
        }
        for glyph in self._glyphs.values():
            glyph.layer = self

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

    def __init__(
        self,
        path,
        default_glyphs,
        layers=None,
        default_layer_name="public.default",
        upm=1000,
        groups=None,
        kerning=None,
        features="",
    ):
        self.path = str(path)
        self._default = FakeLayer(default_layer_name, default_glyphs)
        self._layers = {name: FakeLayer(name, names) for name, names in (layers or {}).items()}
        self.info = FakeInfo(upm)
        self.groups = dict(groups or {})
        self.kerning = dict(kerning or {})
        self.features = FakeFeatures(features)
        self.lib = {}

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


def build_doc(axes, sources, path="/tmp/fake/test.designspace"):
    """A real DesignSpaceDocument over fake sources.

    The checkers call `findDefault()`, `splitInterpolable()` and
    `getFullDesignLocation()`, none of which a stub document can answer, so the
    document itself is the real thing and only the fonts are fakes.

    Args:
        axes: dicts with name/tag plus either minimum/default/maximum, or
            `values` (+ `default`) for a discrete axis.
        sources: dicts with path/name/location and optionally layer_name.
    """
    from fontTools.designspaceLib import (
        AxisDescriptor,
        DesignSpaceDocument,
        DiscreteAxisDescriptor,
        SourceDescriptor,
    )

    doc = DesignSpaceDocument()
    doc.path = str(path)
    for spec in axes:
        if "values" in spec:
            axis = DiscreteAxisDescriptor()
            axis.values = list(spec["values"])
            axis.default = spec.get("default", spec["values"][0])
        else:
            axis = AxisDescriptor()
            axis.minimum = spec["minimum"]
            axis.maximum = spec["maximum"]
            axis.default = spec["default"]
        axis.name = spec["name"]
        axis.tag = spec.get("tag", spec["name"][:4].ljust(4))
        doc.addAxis(axis)

    for spec in sources:
        descriptor = SourceDescriptor()
        descriptor.path = str(spec["path"])
        descriptor.filename = Path(spec["path"]).name
        descriptor.name = spec.get("name")
        descriptor.styleName = spec.get("name")
        descriptor.location = dict(spec.get("location", {}))
        if spec.get("layer_name"):
            descriptor.layerName = spec["layer_name"]
        doc.addSource(descriptor)
    return doc


def build_entry(axes, sources, ds_path="/tmp/fake/test.designspace"):
    """Fake fonts + FontSources + a real document, wired together.

    Each source spec takes `name`, `location`, `glyphs` (names or
    name -> FakeGlyph) and optionally `path`, `layer_name`, `layers`, `upm`,
    `groups`, `kerning`, `features`. Sources sharing a `path` share one
    FakeFont, which is what a layer-based designspace looks like.
    """
    fonts: dict[str, FakeFont] = {}
    font_sources = []
    source_specs = []

    for spec in sources:
        path = Path(spec.get("path", f"/tmp/fake/{spec['name']}.ufo"))
        key = str(path)
        if key not in fonts:
            fonts[key] = FakeFont(
                path,
                spec.get("glyphs", []),
                layers=spec.get("layers"),
                upm=spec.get("upm", 1000),
                groups=spec.get("groups"),
                kerning=spec.get("kerning"),
                features=spec.get("features", ""),
            )
        font_sources.append(
            FontSource(
                font=fonts[key],
                path=path,
                name=spec["name"],
                style_name=spec.get("style_name", spec["name"]),
                location=dict(spec.get("location", {})),
                layer_name=spec.get("layer_name"),
            )
        )
        source_specs.append(
            {
                "path": path,
                "name": spec["name"],
                "location": spec.get("location", {}),
                "layer_name": spec.get("layer_name"),
            }
        )

    doc = build_doc(axes, source_specs, path=ds_path)
    return DesignSpaceEntry(path=Path(ds_path), doc=doc, sources=font_sources)


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
