import sys
from fontTools.designspaceLib import (DesignSpaceDocument, AxisDescriptor,
    VariableFontDescriptor, RangeAxisSubsetDescriptor)
from fontTools.designspaceLib.types import getVFUserRegion

doc = DesignSpaceDocument()
wght = AxisDescriptor()
wght.tag, wght.name = "wght", "Weight"
wght.minimum, wght.default, wght.maximum = 100, 400, 900
doc.addAxis(wght)

vf = VariableFontDescriptor(name="Test", axisSubsets=[
    RangeAxisSubsetDescriptor(name="Weight", userMinimum=100, userDefault=100, userMaximum=900)
])
doc.addVariableFont(vf)
region = getVFUserRegion(doc, vf)
print("Requested userDefault=100, axis.default=400")
print("Actual VF default used:", region["Weight"].default)
