import sys
from fontTools.designspaceLib import DesignSpaceDocument, AxisDescriptor

doc = DesignSpaceDocument()
a1 = AxisDescriptor(tag="wght", name="weight", minimum=100, default=400, maximum=900)
a2 = AxisDescriptor(tag="wght", name="grade", minimum=0, default=0, maximum=100)
doc.addAxis(a1)
doc.addAxis(a2)
print("getAxisByTag wght ->", doc.getAxisByTag("wght").name)
print("no exception raised on addAxis with duplicate tag")

out = "probes/catalog/axes-tests/dup_tag.designspace"
doc.write(out)
print(open(out).read()[:600])

doc2 = DesignSpaceDocument.fromfile(out)
print("re-read OK, axes:", [(a.name, a.tag) for a in doc2.axes])
