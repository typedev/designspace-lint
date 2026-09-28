import logging
logging.basicConfig(level=logging.WARNING)
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.designspaceLib import DesignSpaceDocument, AxisDescriptor, SourceDescriptor
from fontTools import varLib
import os

def make_font(path, square_points):
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef", "A"])
    fb.setupCharacterMap({65: "A"})
    pen = TTGlyphPen(None)
    pen.moveTo((0,0))
    for pt in square_points:
        pen.lineTo(pt)
    pen.closePath()
    glyph = pen.glyph()
    pen2 = TTGlyphPen(None)
    pen2.moveTo((0,0)); pen2.lineTo((0,500)); pen2.lineTo((500,500)); pen2.lineTo((500,0)); pen2.closePath()
    notdef = pen2.glyph()
    fb.setupGlyf({".notdef": notdef, "A": glyph})
    metrics = {gn: (600, fb.font["glyf"][gn].xMin if fb.font["glyf"][gn].numberOfContours else 0) for gn in fb.font.getGlyphOrder()}
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "IncompatTest", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    fb.font.save(path)

# Master A: A = simple square, 4 points
make_font("master-A.ttf", [(0,500),(500,500),(500,0)])
# Master B ("incompatible"): A = square with an EXTRA point inserted mid-edge -> 5 points, same contour count
make_font("master-B.ttf", [(0,500),(250,500),(500,500),(500,0)])

ds = DesignSpaceDocument()
axis = AxisDescriptor()
axis.tag = "wght"; axis.name = "Weight"; axis.minimum=100; axis.default=100; axis.maximum=900
ds.addAxis(axis)

s1 = SourceDescriptor(); s1.path = os.path.abspath("master-A.ttf"); s1.location={"Weight":100}; s1.styleName="Regular"
s2 = SourceDescriptor(); s2.path = os.path.abspath("master-B.ttf"); s2.location={"Weight":900}; s2.styleName="Bold"
ds.addSource(s1); ds.addSource(s2)

vf, model, master_ttfs = varLib.build(ds)
vf.save("VF-incompat.ttf")
print("gvar has A:", "A" in vf["gvar"].variations, "-> variations:", vf["gvar"].variations.get("A"))
print("Build succeeded despite incompatible masters (point count 4 vs 5, same contour count).")
