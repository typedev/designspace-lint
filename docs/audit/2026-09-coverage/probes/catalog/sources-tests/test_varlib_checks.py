import sys, traceback
from fontTools.designspaceLib import DesignSpaceDocument, AxisDescriptor, SourceDescriptor, InstanceDescriptor
from fontTools.varLib import load_designspace
from fontTools.varLib.errors import VarLibValidationError
from fontTools.varLib.models import VariationModel, VariationModelError

def mk_axis(tag, name, minimum, default, maximum):
    a = AxisDescriptor()
    a.tag = tag; a.name = name
    a.minimum = minimum; a.default = default; a.maximum = maximum
    return a

def run(label, fn):
    print(f"\n=== {label} ===")
    try:
        fn()
        print("NO ERROR RAISED")
    except Exception as e:
        print(f"{type(e).__name__}: {e}")

# (a) no source at default location
def test_a():
    doc = DesignSpaceDocument()
    doc.addAxis(mk_axis("wght", "weight", 100, 400, 900))
    s1 = SourceDescriptor(); s1.name="s1"; s1.location={"weight": 100}
    s2 = SourceDescriptor(); s2.name="s2"; s2.location={"weight": 900}
    doc.addSource(s1); doc.addSource(s2)
    load_designspace(doc)

run("(a) no source at default location", test_a)

# (b) duplicate source locations -> caught by VariationModel, not load_designspace
def test_b():
    doc = DesignSpaceDocument()
    doc.addAxis(mk_axis("wght", "weight", 100, 400, 900))
    s1 = SourceDescriptor(); s1.name="s1"; s1.location={"weight": 400}
    s2 = SourceDescriptor(); s2.name="s2"; s2.location={"weight": 400}
    s3 = SourceDescriptor(); s3.name="s3"; s3.location={"weight": 900}
    doc.addSource(s1); doc.addSource(s2); doc.addSource(s3)
    ds = load_designspace(doc)
    print("load_designspace OK, base_idx=", ds.base_idx)
    # Now try building VariationModel like varLib.build does
    normalized = [{ "wght": v for v in [] }]
    norm_locs = [ {"wght": vv} for vv in [ (0.0), (0.0), (1.0) ] ]
    VariationModel(norm_locs, axisOrder=["wght"])

run("(b) duplicate source locations", test_b)

# (c) missing UFO path
def test_c():
    doc = DesignSpaceDocument()
    doc.addAxis(mk_axis("wght", "weight", 100, 400, 900))
    s1 = SourceDescriptor(); s1.name="s1"; s1.location={"weight": 400}
    # no filename/path set at all
    doc.addSource(s1)
    doc.findDefault()
    fonts = doc.loadSourceFonts(lambda p: None)

run("(c) missing UFO path (no filename/path set)", test_c)

# (c2) path points to nonexistent file, exercised via varLib._open_font
def test_c2():
    from fontTools.varLib import _open_font
    _open_font("/nonexistent/path/Font-Regular.ufo")

run("(c2) nonexistent file path via varLib._open_font", test_c2)

# (d) missing layer name without font object supplied
def test_d():
    from fontTools.varLib import load_masters
    doc = DesignSpaceDocument()
    doc.addAxis(mk_axis("wght", "weight", 100, 400, 900))
    s1 = SourceDescriptor(); s1.name="s1"; s1.location={"weight": 400}
    s1.layerName = "wght500"
    s1.path = "/tmp/doesnotmatter.ufo"
    doc.addSource(s1)
    load_masters(doc)

run("(d) source with layerName but no in-memory font object", test_d)

# (e) instance location outside axis min/max
def test_e():
    doc = DesignSpaceDocument()
    doc.addAxis(mk_axis("wght", "weight", 100, 400, 900))
    s1 = SourceDescriptor(); s1.name="s1"; s1.location={"weight": 400}
    s2 = SourceDescriptor(); s2.name="s2"; s2.location={"weight": 900}
    doc.addSource(s1); doc.addSource(s2)
    i1 = InstanceDescriptor(); i1.name="i1"; i1.styleName="Overshoot"; i1.location={"weight": 1200}
    doc.addInstance(i1)
    load_designspace(doc)

run("(e) instance location outside axis range", test_e)

# (f) two instances identical style/postscript name -- test via _add_fvar directly using a stub
def test_f():
    from fontTools.varLib import _add_fvar
    from fontTools.ttLib import TTFont, newTable
    from collections import OrderedDict
    doc_axes = OrderedDict()
    a = mk_axis("wght","weight",100,400,900)
    doc_axes["weight"] = a
    font = TTFont()
    font.setGlyphOrder([".notdef"])
    name = newTable("name")
    name.names = []
    font["name"] = name
    i1 = InstanceDescriptor(); i1.name="i1"; i1.styleName="Bold"; i1.location={"weight":700}
    i2 = InstanceDescriptor(); i2.name="i2"; i2.styleName="Bold"; i2.location={"weight":720}
    fvar = _add_fvar(font, doc_axes, [i1, i2])
    print("Number of NamedInstances:", len(fvar.instances))
    print("subfamilyNameIDs:", [inst.subfamilyNameID for inst in fvar.instances])
    print("coords:", [inst.coordinates for inst in fvar.instances])

run("(f) two instances with identical style name, different location", test_f)
