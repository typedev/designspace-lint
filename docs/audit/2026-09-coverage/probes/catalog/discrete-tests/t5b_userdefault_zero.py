import sys
from fontTools.designspaceLib import (DesignSpaceDocument, AxisDescriptor,
    VariableFontDescriptor, RangeAxisSubsetDescriptor)
from fontTools.designspaceLib.types import getVFUserRegion

doc = DesignSpaceDocument()
slnt = AxisDescriptor()
slnt.tag, slnt.name = "slnt", "Slant"
slnt.minimum, slnt.default, slnt.maximum = -10, -10, 0   # axis default is -10, not 0
doc.addAxis(slnt)

vf = VariableFontDescriptor(name="UprightVF", axisSubsets=[
    RangeAxisSubsetDescriptor(name="Slant", userMinimum=-10, userDefault=0, userMaximum=0)
])
doc.addVariableFont(vf)
region = getVFUserRegion(doc, vf)
print("Requested userDefault=0 (falsy!), axis.default=-10")
print("Actual VF default used:", region["Slant"].default, "(expected 0, got axis's -10 due to `or` bug)")
