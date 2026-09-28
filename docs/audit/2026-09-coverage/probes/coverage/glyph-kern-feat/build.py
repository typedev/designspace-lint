#!/usr/bin/env python
"""Build UFO/DS probe fixtures for GLYPH/KERN/FEAT/ORDER/INFO coverage checks."""
import os, shutil
import defcon

ROOT = os.path.dirname(os.path.abspath(__file__))

def fresh(path):
    if os.path.exists(path):
        shutil.rmtree(path)

def base_font(family, style, upm=1000):
    f = defcon.Font()
    f.info.familyName = family
    f.info.styleName = style
    f.info.unitsPerEm = upm
    f.info.ascender = 800
    f.info.descender = -200
    return f

def simple_glyph(f, name, npoints=3, width=500):
    g = f.newGlyph(name)
    g.width = width
    pen = g.getPen()
    pen.moveTo((0, 0))
    if npoints >= 2:
        pen.lineTo((300, 0))
    if npoints >= 3:
        pen.lineTo((300, 300))
    if npoints >= 4:
        pen.lineTo((150, 450))
    pen.closePath()
    return g

def save(f, path):
    fresh(path)
    f.save(path)

def make_ds(path, axis_tag, axis_name, minimum, default, maximum, sources):
    # sources: list of (name, path, location_value, is_default)
    src_xml = []
    for name, ufopath, loc, isdef in sources:
        src_xml.append(f'''
    <source name="{name}" filename="{os.path.relpath(ufopath, os.path.dirname(path))}">
      <location>
        <dimension name="{axis_name}" xvalue="{loc}"/>
      </location>
    </source>''')
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<designspace format="5.0">
  <axes>
    <axis tag="{axis_tag}" name="{axis_name}" minimum="{minimum}" maximum="{maximum}" default="{default}"/>
  </axes>
  <sources>{"".join(src_xml)}
  </sources>
</designspace>
'''
    with open(path, "w") as fh:
        fh.write(xml)

# ---------- GLYPH-01/03: point-count and flag-pattern mismatch (same contour count) ----------
d = os.path.join(ROOT, "g0103")
os.makedirs(d, exist_ok=True)
f_default = base_font("G0103", "Regular")
f_other = base_font("G0103", "Bold")
# default: 4-point contour, other: same 4 points but different on/off-curve flags (quad curve corner)
for name, f in [("default", f_default), ("other", f_other)]:
    g = f.newGlyph("a")
    g.width = 500
    pen = g.getPen()
    pen.moveTo((0, 0))
    pen.lineTo((400, 0))
    pen.lineTo((400, 400))
    pen.lineTo((0, 400))
    pen.closePath()
save(f_default, os.path.join(d, "default.ufo"))
save(f_other, os.path.join(d, "other.ufo"))
# now variant with a genuine POINT COUNT mismatch (5 vs 4 points, same 1 contour) -> reuse "other" ufo but add point
f_ptmismatch = base_font("G0103", "PointMismatch")
g = f_ptmismatch.newGlyph("a")
g.width = 500
pen = g.getPen()
pen.moveTo((0, 0))
pen.lineTo((200, 0))
pen.lineTo((400, 0))
pen.lineTo((400, 400))
pen.lineTo((0, 400))
pen.closePath()
save(f_ptmismatch, os.path.join(d, "ptmismatch.ufo"))
make_ds(os.path.join(d, "g01_pointcount.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("ptmismatch", os.path.join(d, "ptmismatch.ufo"), 900, False)])

# GLYPH-03: same point count (4 pts) but different flag pattern (curve vs line for one segment)
f_curve = base_font("G03", "Curve")
g = f_curve.newGlyph("a")
g.width = 500
pen = g.getPen()
pen.moveTo((0, 0))
pen.lineTo((400, 0))
pen.curveTo((450, 150), (450, 250), (400, 400))  # adds off-curve points -> different point count actually
pen.lineTo((0, 400))
pen.closePath()
save(f_curve, os.path.join(d, "curve.ufo"))
make_ds(os.path.join(d, "g03_flagmismatch.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("curve", os.path.join(d, "curve.ufo"), 900, False)])

# ---------- GLYPH-02: contour-count mismatch ----------
d = os.path.join(ROOT, "g02")
os.makedirs(d, exist_ok=True)
f1 = base_font("G02", "Regular")
simple_glyph(f1, "b", npoints=4)
f2 = base_font("G02", "Bold")
g = f2.newGlyph("b")
g.width = 500
pen = g.getPen()
pen.moveTo((0, 0)); pen.lineTo((400, 0)); pen.lineTo((400, 400)); pen.lineTo((0, 400)); pen.closePath()
pen.moveTo((100, 100)); pen.lineTo((300, 100)); pen.lineTo((300, 300)); pen.closePath()  # extra counter contour
save(f1, os.path.join(d, "default.ufo"))
save(f2, os.path.join(d, "other.ufo"))
make_ds(os.path.join(d, "g02.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("other", os.path.join(d, "other.ufo"), 900, False)])

# ---------- GLYPH-04: composite vs simple outline mix ----------
d = os.path.join(ROOT, "g04")
os.makedirs(d, exist_ok=True)
f1 = base_font("G04", "Regular")
simple_glyph(f1, "base", npoints=4, width=400)
g = f1.newGlyph("c")
g.width = 400
comp = g.instantiateComponent()
comp.baseGlyph = "base"
comp.transformation = (1, 0, 0, 1, 0, 0)
g.appendComponent(comp)
f2 = base_font("G04", "Bold")
simple_glyph(f2, "base", npoints=4, width=400)
g2 = f2.newGlyph("c")
g2.width = 400
pen = g2.getPen()
pen.moveTo((0, 0)); pen.lineTo((300, 0)); pen.lineTo((300, 300)); pen.lineTo((0, 300)); pen.closePath()
save(f1, os.path.join(d, "default.ufo"))
save(f2, os.path.join(d, "other.ufo"))
make_ds(os.path.join(d, "g04.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("other", os.path.join(d, "other.ufo"), 900, False)])

# ---------- GLYPH-08 / GLYPH-13: empty glyph in non-default master, plus wrong width ----------
d = os.path.join(ROOT, "g0813")
os.makedirs(d, exist_ok=True)
f1 = base_font("G0813", "Regular")
simple_glyph(f1, "x", npoints=4, width=500)
f2 = base_font("G0813", "Bold")
gx = f2.newGlyph("x")
gx.width = 12345  # deliberately bogus/arbitrary width, NOT the HVAR 0xFFFF=65535 sentinel, NOT a sane interpolated value
# no pen operations -> 0 contours, 0 components (empty)
save(f1, os.path.join(d, "default.ufo"))
save(f2, os.path.join(d, "other.ufo"))
make_ds(os.path.join(d, "g0813.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("other", os.path.join(d, "other.ufo"), 900, False)])

# ---------- GLYPH-10: glyph missing entirely from one non-default master (2-master, then 3-master) ----------
d = os.path.join(ROOT, "g10_2m")
os.makedirs(d, exist_ok=True)
f1 = base_font("G10", "Regular")
simple_glyph(f1, "c", npoints=4)
f2 = base_font("G10", "Bold")
# "c" NOT created at all in f2
save(f1, os.path.join(d, "default.ufo"))
save(f2, os.path.join(d, "other.ufo"))
make_ds(os.path.join(d, "g10_2m.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("other", os.path.join(d, "other.ufo"), 900, False)])

d = os.path.join(ROOT, "g10_3m")
os.makedirs(d, exist_ok=True)
f1 = base_font("G10", "Regular")
simple_glyph(f1, "c", npoints=4)
f2 = base_font("G10", "Medium")
simple_glyph(f2, "c", npoints=4)  # HAS it
f3 = base_font("G10", "Bold")
# "c" missing in f3 only
save(f1, os.path.join(d, "default.ufo"))
save(f2, os.path.join(d, "medium.ufo"))
save(f3, os.path.join(d, "bold.ufo"))
make_ds(os.path.join(d, "g10_3m.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("medium", os.path.join(d, "medium.ufo"), 500, False),
         ("bold", os.path.join(d, "bold.ufo"), 900, False)])

# ---------- GLYPH-11: anchor set differs ----------
d = os.path.join(ROOT, "g11")
os.makedirs(d, exist_ok=True)
f1 = base_font("G11", "Regular")
g = simple_glyph(f1, "e", npoints=4)
g.appendAnchor(dict(name="top", x=200, y=400))
f2 = base_font("G11", "Bold")
g2 = simple_glyph(f2, "e", npoints=4)
# no anchor on bold master
save(f1, os.path.join(d, "default.ufo"))
save(f2, os.path.join(d, "other.ufo"))
make_ds(os.path.join(d, "g11.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("other", os.path.join(d, "other.ufo"), 900, False)])

print("GLYPH fixtures built OK")
