import logging
logging.basicConfig(level=logging.WARNING, format="LOG %(levelname)s %(name)s: %(message)s")
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.designspaceLib.split import splitVariableFonts
x = '''<?xml version="1.0"?><designspace format="5.1"><axes>
<axis tag="wght" name="Weight" minimum="100" maximum="900" default="400"/>
<axis tag="XHID" name="Hidden" minimum="0" maximum="100" default="50" hidden="1"/>
<axis tag="ital" name="Italic" values="0 1" default="0"/>
<mappings>
<mapping><input><dimension name="Weight" xvalue="900"/></input><output><dimension name="Hidden" xvalue="100"/></output></mapping>
<mapping><input><dimension name="Italic" xvalue="0"/><dimension name="Weight" xvalue="100"/></input><output><dimension name="Hidden" xvalue="0"/></output></mapping>
</mappings></axes>
<sources><source filename="a.ufo" name="a"><location><dimension name="Weight" xvalue="400"/><dimension name="Hidden" xvalue="50"/><dimension name="Italic" xvalue="0"/></location></source>
<source filename="b.ufo" name="b"><location><dimension name="Weight" xvalue="400"/><dimension name="Hidden" xvalue="50"/><dimension name="Italic" xvalue="1"/></location></source></sources>
<variable-fonts>
<variable-font name="Sub"><axis-subsets><axis-subset name="Weight" /><axis-subset name="Hidden"/><axis-subset name="Italic" uservalue="0"/></axis-subsets></variable-font>
</variable-fonts></designspace>'''
doc = DesignSpaceDocument.fromstring(x)
for name, sub in splitVariableFonts(doc):
    print(name, [ (a.name, a.minimum, a.maximum) for a in sub.axes])
    print(" mappings kept:", [(mm.inputLocation, mm.outputLocation) for mm in sub.axisMappings])
