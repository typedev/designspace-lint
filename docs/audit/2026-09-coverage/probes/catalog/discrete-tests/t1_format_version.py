import sys
from fontTools.designspaceLib import DesignSpaceDocument

xml = '''<?xml version="1.0" encoding="UTF-8"?>
<designspace format="4.1">
  <axes>
    <axis tag="ital" name="Italic" values="0 1" default="0"/>
  </axes>
  <sources>
  </sources>
</designspace>'''

with open("t1.designspace", "w") as f:
    f.write(xml)

doc = DesignSpaceDocument()
try:
    doc.read("t1.designspace")
    print("OK, no error. axis type:", type(doc.axes[0]))
    print("minimum attr present?", hasattr(doc.axes[0], "minimum"))
except Exception as e:
    print(f"{type(e).__name__}: {e}")
