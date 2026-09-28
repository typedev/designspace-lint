#!/usr/bin/env python
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

def simple_glyph(f, name, width=500):
    g = f.newGlyph(name)
    g.width = width
    pen = g.getPen()
    pen.moveTo((0, 0)); pen.lineTo((300, 0)); pen.lineTo((300, 300)); pen.lineTo((0,300))
    pen.closePath()
    return g

def save(f, path):
    fresh(path)
    f.save(path)

def make_ds(path, axis_tag, axis_name, minimum, default, maximum, sources):
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

# ---------- KERN-01: master has zero kerning pairs while default has some ----------
d = os.path.join(ROOT, "k01")
os.makedirs(d, exist_ok=True)
f1 = base_font("K01", "Regular")
for n in ("A", "V", "T", "o"):
    simple_glyph(f1, n)
f1.kerning[("A", "V")] = -50
f2 = base_font("K01", "Bold")
for n in ("A", "V", "T", "o"):
    simple_glyph(f2, n)
# no kerning at all in f2
save(f1, os.path.join(d, "default.ufo"))
save(f2, os.path.join(d, "other.ufo"))
make_ds(os.path.join(d, "k01.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("other", os.path.join(d, "other.ufo"), 900, False)])

# ---------- KERN-03: normal sparse kerning, both have SOME kerning but different specific pairs (positive control, no error expected) ----------
d = os.path.join(ROOT, "k03")
os.makedirs(d, exist_ok=True)
f1 = base_font("K03", "Regular")
for n in ("A", "V", "T", "o"):
    simple_glyph(f1, n)
f1.groups["public.kern1.A"] = ["A"]
f1.groups["public.kern2.V"] = ["V"]
f1.kerning[("public.kern1.A", "public.kern2.V")] = -40
f1.kerning[("A", "T")] = -20  # extra pair only in default
f2 = base_font("K03", "Bold")
for n in ("A", "V", "T", "o"):
    simple_glyph(f2, n)
f2.groups["public.kern1.A"] = ["A"]
f2.groups["public.kern2.V"] = ["V"]
f2.kerning[("public.kern1.A", "public.kern2.V")] = -60
# f2 lacks the (A, T) pair -- expected/normal (resolves to group/0), not a bug
save(f1, os.path.join(d, "default.ufo"))
save(f2, os.path.join(d, "other.ufo"))
make_ds(os.path.join(d, "k03.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("other", os.path.join(d, "other.ufo"), 900, False)])

# ---------- KERN-04: group membership differs between masters ----------
d = os.path.join(ROOT, "k04")
os.makedirs(d, exist_ok=True)
f1 = base_font("K04", "Regular")
for n in ("A", "Aacute", "V", "o"):
    simple_glyph(f1, n)
f1.groups["public.kern1.A"] = ["A", "Aacute"]
f1.groups["public.kern2.V"] = ["V"]
f1.kerning[("public.kern1.A", "public.kern2.V")] = -40
f2 = base_font("K04", "Bold")
for n in ("A", "Aacute", "V", "o"):
    simple_glyph(f2, n)
f2.groups["public.kern1.A"] = ["A"]  # Aacute missing from this master's group -- different membership
f2.groups["public.kern2.V"] = ["V"]
f2.kerning[("public.kern1.A", "public.kern2.V")] = -60
save(f1, os.path.join(d, "default.ufo"))
save(f2, os.path.join(d, "other.ufo"))
make_ds(os.path.join(d, "k04.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("other", os.path.join(d, "other.ufo"), 900, False)])

# ---------- FEAT-01: top-level feature block present in default's features.fea only (8.1) ----------
d = os.path.join(ROOT, "f01")
os.makedirs(d, exist_ok=True)
f1 = base_font("F01", "Regular")
for n in ("A", "V"):
    simple_glyph(f1, n)
f1.features.text = "feature kern {\n    pos A V -50;\n} kern;\n"
f2 = base_font("F01", "Bold")
for n in ("A", "V"):
    simple_glyph(f2, n)
f2.features.text = ""  # no top-level kern block
save(f1, os.path.join(d, "default.ufo"))
save(f2, os.path.join(d, "other.ufo"))
make_ds(os.path.join(d, "f01.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("other", os.path.join(d, "other.ufo"), 900, False)])

# ---------- FEAT-02 / 8.3: genuinely different non-empty features.fea content ----------
d = os.path.join(ROOT, "f02")
os.makedirs(d, exist_ok=True)
f1 = base_font("F02", "Regular")
for n in ("A", "V", "dollar", "dollar.alt"):
    simple_glyph(f1, n)
f1.features.text = "feature calt {\n    sub dollar by dollar.alt;\n} calt;\n"
f2 = base_font("F02", "Bold")
for n in ("A", "V", "dollar", "dollar.alt"):
    simple_glyph(f2, n)
f2.features.text = "feature calt {\n    sub A by V;\n} calt;\n"  # different, non-empty content
save(f1, os.path.join(d, "default.ufo"))
save(f2, os.path.join(d, "other.ufo"))
make_ds(os.path.join(d, "f02.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("other", os.path.join(d, "other.ufo"), 900, False)])

# ---------- ORDER-02: differing public.glyphOrder across masters ----------
d = os.path.join(ROOT, "o02")
os.makedirs(d, exist_ok=True)
f1 = base_font("O02", "Regular")
for n in ("A", "B", "C"):
    simple_glyph(f1, n)
f1.lib["public.glyphOrder"] = ["A", "B", "C"]
f2 = base_font("O02", "Bold")
for n in ("A", "B", "C"):
    simple_glyph(f2, n)
f2.lib["public.glyphOrder"] = ["B", "A", "C"]  # different order, same names
save(f1, os.path.join(d, "default.ufo"))
save(f2, os.path.join(d, "other.ufo"))
make_ds(os.path.join(d, "o02.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("other", os.path.join(d, "other.ufo"), 900, False)])

# ---------- ORDER-03: glyph renamed between masters ----------
d = os.path.join(ROOT, "o03")
os.makedirs(d, exist_ok=True)
f1 = base_font("O03", "Regular")
simple_glyph(f1, "d")
f1.lib["public.glyphOrder"] = ["d"]
f2 = base_font("O03", "Bold")
simple_glyph(f2, "d.alt")  # renamed; "d" absent, "d.alt" is new
f2.lib["public.glyphOrder"] = ["d.alt"]
save(f1, os.path.join(d, "default.ufo"))
save(f2, os.path.join(d, "other.ufo"))
make_ds(os.path.join(d, "o03.designspace"), "wght", "weight", 100, 100, 900,
        [("default", os.path.join(d, "default.ufo"), 100, True),
         ("other", os.path.join(d, "other.ufo"), 900, False)])

print("KERN/FEAT/ORDER fixtures built OK")
