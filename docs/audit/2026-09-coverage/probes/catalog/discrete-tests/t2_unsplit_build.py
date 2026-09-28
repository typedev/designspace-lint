import sys
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools import varLib

xml = '''<?xml version="1.0" encoding="UTF-8"?>
<designspace format="5.0">
  <axes>
    <axis tag="ital" name="Italic" values="0 1" default="0"/>
    <axis tag="wght" name="Weight" minimum="400" maximum="700" default="400"/>
  </axes>
  <sources>
    <source filename="Regular.ufo" name="Regular">
      <location>
        <dimension name="Italic" xvalue="0"/>
        <dimension name="Weight" xvalue="400"/>
      </location>
    </source>
    <source filename="Bold.ufo" name="Bold">
      <location>
        <dimension name="Italic" xvalue="0"/>
        <dimension name="Weight" xvalue="700"/>
      </location>
    </source>
  </sources>
</designspace>'''
with open("t2.designspace", "w") as f:
    f.write(xml)

doc = DesignSpaceDocument()
doc.read("t2.designspace")
try:
    varLib.build(doc)
    print("OK, no error")
except Exception as e:
    print(f"{type(e).__name__}: {e}")
