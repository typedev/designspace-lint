import sys
from fontTools.designspaceLib import (DesignSpaceDocument, DiscreteAxisDescriptor,
    AxisDescriptor, VariableFontDescriptor, RangeAxisSubsetDescriptor, ValueAxisSubsetDescriptor,
    SourceDescriptor)
from fontTools.designspaceLib.split import splitVariableFonts, splitInterpolable

def make_doc():
    doc = DesignSpaceDocument()
    doc.formatVersion = "5.0"
    ital = DiscreteAxisDescriptor()
    ital.tag, ital.name, ital.values, ital.default = "ital", "Italic", [0, 1], 0
    doc.addAxis(ital)
    wght = AxisDescriptor()
    wght.tag, wght.name = "wght", "Weight"
    wght.minimum, wght.default, wght.maximum = 400, 400, 700
    doc.addAxis(wght)
    for ital_v in (0, 1):
        for wght_v, fname in ((400, "Regular"), (700, "Bold")):
            s = SourceDescriptor()
            s.filename = f"{fname}{'-Italic' if ital_v else ''}.ufo"
            s.name = s.filename
            s.location = {"Italic": ital_v, "Weight": wght_v}
            doc.addSource(s)
    return doc

# Case A: axis-subset names a nonexistent axis
doc = make_doc()
vf = VariableFontDescriptor(name="Bogus", axisSubsets=[RangeAxisSubsetDescriptor(name="Wdth")])
doc.addVariableFont(vf)
try:
    list(splitVariableFonts(doc))
    print("A: OK, no error")
except Exception as e:
    print(f"A: {type(e).__name__}: {e}")

# Case B: RangeAxisSubsetDescriptor used on a discrete axis
doc2 = make_doc()
vf2 = VariableFontDescriptor(name="BadRange", axisSubsets=[RangeAxisSubsetDescriptor(name="Italic")])
doc2.addVariableFont(vf2)
try:
    list(splitVariableFonts(doc2))
    print("B: OK, no error")
except Exception as e:
    print(f"B: {type(e).__name__}: {e}")

# Case C: discrete axis default value not among declared values -> findDefault() silently None
doc3 = make_doc()
doc3.axes[0].default = 2  # not in [0, 1]
d = doc3.findDefault()
print("C: findDefault() with default not in values ->", d)
