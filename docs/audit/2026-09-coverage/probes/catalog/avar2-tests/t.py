import io, traceback, logging
logging.basicConfig(level=logging.WARNING, format="LOG %(levelname)s %(name)s: %(message)s")
from fontTools.fontBuilder import FontBuilder
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.varLib.avar.build import build as avar_build

AXES = '''<axis tag="wght" name="Weight" minimum="100" maximum="900" default="400">%s</axis>
<axis tag="wdth" name="Width" minimum="50" maximum="150" default="100"/>
<axis tag="XHID" name="Hidden" minimum="0" maximum="100" default="50" hidden="1"/>'''
def ds(mappings, wmap=""):
    x = f'<?xml version="1.0"?><designspace format="5.1"><axes>{AXES % wmap}<mappings>{mappings}</mappings></axes></designspace>'
    return DesignSpaceDocument.fromstring(x)
def m(inp, out, attr="xvalue"):
    i = "".join(f'<dimension name="{k}" {attr}="{v}"/>' for k,v in inp.items())
    o = "".join(f'<dimension name="{k}" xvalue="{v}"/>' for k,v in out.items())
    return f"<mapping><input>{i}</input><output>{o}</output></mapping>"
def font():
    fb = FontBuilder(1000, isTTF=True); fb.setupGlyphOrder([".notdef"]); fb.setupCharacterMap({})
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    fb.setupGlyf({".notdef": TTGlyphPen(None).glyph()}); fb.setupHorizontalMetrics({".notdef": (500,0)})
    fb.setupHorizontalHeader(); fb.setupNameTable({"familyName":"T","styleName":"R"}); fb.setupOS2(); fb.setupPost()
    return fb.font
def run(name, d, locs):
    print("=== ", name)
    try:
        f = font(); avar_build(f, d)
        if "avar" not in f: print("no avar"); return f
        for L in locs:
            print("  ", L, "->", {k: round(v,4) for k,v in f["avar"].renormalizeLocation(L, f, dropZeroes=False).items()})
        return f
    except Exception as e:
        print("  EXC", type(e).__name__, e); traceback.print_exc(limit=-2)

def tryread(name, fn):
    print("=== ", name)
    try: fn(); print("  ok")
    except Exception as e: print("  EXC", type(e).__name__, repr(e)); traceback.print_exc(limit=-1)

Z={"wght":0,"wdth":0,"XHID":0}
# T1 input outside range (wght 1200 on 100..900) -> clamps to 900
run("T1 input out of range", ds(m({"Weight":1200},{"Hidden":100})), [Z, {"wght":1.0}])
# T1b out-of-range input colliding with in-range one
run("T1b out-of-range input collides", ds(m({"Weight":1200},{"Hidden":100})+m({"Weight":900},{"Hidden":0})), [{"wght":1.0}])
# T2 tag instead of name
run("T2 tag used as dimension name", ds(m({"wght":900},{"XHID":100})), [Z])
# T3 uservalue in mapping dimension
tryread("T3 uservalue attr in mapping", lambda: ds(m({"Weight":900},{"Hidden":100}, attr="uservalue")))
# T4 mapping at default input with nonzero output -> default shifted
run("T4 default input remapped", ds(m({"Weight":400},{"Hidden":100})), [Z])
# T5 additive corners
run("T5 corner superposition", ds(m({"Weight":900},{"Hidden":80})+m({"Width":150},{"Hidden":80})), [{"wght":1,"wdth":0,"XHID":0},{"wght":0,"wdth":1,"XHID":0},{"wght":1,"wdth":1,"XHID":0}])
# T6 two partial default-inputs
run("T6 two mappings at default via different axes", ds(m({"Weight":400},{"Hidden":60})+m({"Width":100},{"Hidden":70})), [Z])
# T6b exact duplicate input
run("T6b duplicate input, conflicting output", ds(m({"Weight":900},{"Hidden":60})+m({"Weight":900},{"Hidden":70})), [Z])
# T7 output outside axis range -> clamped
run("T7 output out of range", ds(m({"Weight":900},{"Hidden":500})), [{"wght":1.0}])
# T8 avar1 map: input is design space
wmap = '<map input="100" output="20"/><map input="400" output="80"/><map input="900" output="200"/>'
run("T8 input given in USER value 900 while design is 200", ds(m({"Weight":900},{"Hidden":100}), wmap), [{"wght":1.0},{"wght":0.0}])
run("T8b input in design value 200", ds(m({"Weight":200},{"Hidden":100}), wmap), [{"wght":1.0}])
# T9 chained mappings: output of one used as input of another
run("T9 no chaining", ds(m({"Weight":900},{"Hidden":100})+m({"Hidden":100},{"Width":150})), [{"wght":1.0},{"XHID":1.0}])
# T10 user sets hidden axis directly: delta adds on top
run("T10 user-set hidden axis + delta", ds(m({"Weight":900},{"Hidden":75})), [{"wght":1.0,"XHID":0.0},{"wght":1.0,"XHID":0.5},{"wght":1.0,"XHID":-1.0}])
# T11 mid-point not specified: linear between mappings (HOI curvature only piecewise)
run("T11 in-between values", ds(m({"Weight":900},{"Hidden":100})), [{"wght":0.5}])
# T12 mapping input on unknown axis name entirely
run("T12 output axis unknown", ds(m({"Weight":900},{"Nope":1})), [Z])
# T13 empty output
run("T13 empty output", ds(m({"Weight":900},{})), [{"wght":1.0}])
# T14 empty input (explicit default mapping)
run("T14 empty input with output", ds(m({},{"Hidden":100})), [Z])
