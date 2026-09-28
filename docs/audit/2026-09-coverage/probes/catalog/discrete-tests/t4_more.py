import sys
from fontTools.designspaceLib import (DesignSpaceDocument, DiscreteAxisDescriptor,
    AxisDescriptor, VariableFontDescriptor, RangeAxisSubsetDescriptor, ValueAxisSubsetDescriptor,
    SourceDescriptor)
from fontTools.designspaceLib.split import splitVariableFonts

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

# Case D: ValueAxisSubsetDescriptor picks a discrete value not in axis.values (typo: 2 instead of 0/1)
doc = make_doc()
vf = VariableFontDescriptor(name="Typo", axisSubsets=[
    RangeAxisSubsetDescriptor(name="Weight"),
    ValueAxisSubsetDescriptor(name="Italic", userValue=2),
])
doc.addVariableFont(vf)
try:
    for name, subdoc in splitVariableFonts(doc):
        print(f"D: VF '{name}' -> sources kept: {len(subdoc.sources)}")
except Exception as e:
    print(f"D: {type(e).__name__}: {e}")

# Case E: duplicate values in discrete axis values list
doc2 = make_doc()
doc2.axes[0].values = [0, 0, 1]  # duplicate 0
vfs = doc2.getVariableFonts()
names = [vf.name for vf in vfs]
print("E: implicit VF names from duplicated values list:", names)
print("E: duplicate name collision?", len(names) != len(set(names)))
