"""AVAR2-01, checked on a compiled avar2 table.

A mapping whose input is the default location is stored as the VarStore base
value, which varLib discards (`storeMasters(...)[1]`); every other mapping's
delta is then taken relative to it. Two axes: Weight 100:400:1000 and a
parametric YTOS 0:11:30. `Weight=400 -> YTOS=10` asks for 10 at the default.

Run with any environment that has fontTools (tested on 4.66.0):
    python avar2-default-input.py

Result:
               intended | without the default mapping | with it
    wght  400:     10   |   11.0                      |   11.0
    wght  700:    ~15   |   15.5                      |  16.36
    wght 1000:     20   |   20.0                      |  21.73

The default-input mapping is ignored where it applies and shifts every other
point. The AmstelvarA2-Roman designspace from fontTools' test data has exactly
this mapping (Weight=400 -> YTOS=10, YTOS default 11).
"""

from collections import OrderedDict

from fontTools.designspaceLib import AxisDescriptor, AxisMappingDescriptor
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.varLib import _add_avar


def build(mappings):
    axes = OrderedDict()
    for name, tag, mn, df, mx in [("Weight", "wght", 100, 400, 1000), ("YTOS", "YTOS", 0, 11, 30)]:
        a = AxisDescriptor()
        a.name, a.tag, a.minimum, a.default, a.maximum = name, tag, mn, df, mx
        axes[name] = a
    ms = []
    for i, o in mappings:
        m = AxisMappingDescriptor()
        m.inputLocation, m.outputLocation = i, o
        ms.append(m)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef"])
    fb.setupCharacterMap({})
    fb.setupGlyf({".notdef": TTGlyphPen(None).glyph()})
    fb.setupHorizontalMetrics({".notdef": (500, 0)})
    fb.setupHorizontalHeader()
    fb.setupNameTable({"familyName": "T", "styleName": "R"})
    fb.setupOS2()
    fb.setupPost()
    fb.setupFvar([("wght", 100, 400, 1000, "Weight"), ("YTOS", 0, 11, 30, "YTOS")], [])
    _add_avar(fb.font, axes, ms, ["wght", "YTOS"])
    return fb.font


def ytos(font, w):
    n = (w - 400) / 300 if w < 400 else (w - 400) / 600
    loc = font["avar"].renormalizeLocation({"wght": n, "YTOS": 0.0}, font, dropZeroes=False)
    y = loc.get("YTOS", 0.0)
    return round(11 + (y * 11 if y < 0 else y * 19), 2)


good = build([({"Weight": 1000}, {"YTOS": 20})])
bad = build([({"Weight": 400}, {"YTOS": 10}), ({"Weight": 1000}, {"YTOS": 20})])
print("           intended | without the default mapping | with it")
for w, want in ((400, 10), (700, "~15"), (1000, 20)):
    print(f"wght {w:4}:  {str(want):>5}   | {ytos(good, w):>6}                      | {ytos(bad, w):>6}")
