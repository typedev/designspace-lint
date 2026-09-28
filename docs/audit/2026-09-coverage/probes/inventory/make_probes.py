import os, shutil
from fontParts.world import NewFont
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probes")

def ufo(name, upm=1000, glyphs=("A","B"), size=100):
    path = os.path.join(P, name)
    if os.path.exists(path): shutil.rmtree(path)
    f = NewFont(showInterface=False)
    f.info.unitsPerEm = upm; f.info.familyName = "Probe"; f.info.styleName = name
    for g in glyphs:
        gl = f.newGlyph(g); gl.width = 500
        pen = gl.getPen(); pen.moveTo((0,0)); pen.lineTo((size,0)); pen.lineTo((size,size)); pen.closePath()
    f.save(path); f.close()

ufo("L.ufo", size=100); ufo("R.ufo", size=200); ufo("B.ufo", size=300, upm=2048)
ufo("IL.ufo", size=110); ufo("IR.ufo", size=210); ufo("IB.ufo", size=310)
ufo("H.ufo", size=250)

def w(name, body):
    open(os.path.join(P, name), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<designspace format="5.0">\n' + body + "\n</designspace>\n")

AX = '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900">
    <map input="100" output="0"/><map input="400" output="100"/><map input="900" output="200"/>
  </axis>
</axes>'''
SRC = '''<sources>
  <source filename="L.ufo" name="L"><location><dimension name="Weight" xvalue="0"/></location></source>
  <source filename="R.ufo" name="R"><location><dimension name="Weight" xvalue="100"/></location></source>
  <source filename="B.ufo" name="B"><location><dimension name="Weight" xvalue="200"/></location></source>
</sources>'''
# P1 rule with no conditionset, followed by a rule out of bounds (7.3) that should still be seen
w("p1_rule_noconditions.designspace", AX + SRC + '''
<rules>
  <rule name="nocond"><sub name="A" with="B"/></rule>
  <rule name="oob"><conditionset><condition name="Weight" minimum="150" maximum="999"/></conditionset><sub name="A" with="B"/></rule>
</rules>''')
# P2 instance without familyname + duplicate location
w("p2_instance_nofamily_dup.designspace", AX + SRC + '''
<instances>
  <instance stylename="X" filename="i/x.ufo"><location><dimension name="Weight" xvalue="50"/></location></instance>
  <instance stylename="Y" filename="i/y.ufo"><location><dimension name="Weight" xvalue="50"/></location></instance>
</instances>''')
# P3 avar2 + hidden axis: mapping output wildly out of range and to an undefined axis; hidden axis never touched by sources
w("p3_avar2_hidden.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
  <axis tag="XOPQ" name="XOPQ" minimum="0" default="50" maximum="100" hidden="1"/>
  <mappings>
    <mapping><input><dimension name="Weight" xvalue="900"/></input><output><dimension name="XOPQ" xvalue="5000"/></output></mapping>
    <mapping><input><dimension name="Weight" xvalue="900"/></input><output><dimension name="XOPQ" xvalue="10"/></output></mapping>
  </mappings>
</axes>
<sources>
  <source filename="L.ufo" name="L"><location><dimension name="Weight" xvalue="100"/></location></source>
  <source filename="R.ufo" name="R"><location><dimension name="Weight" xvalue="400"/></location></source>
  <source filename="B.ufo" name="B"><location><dimension name="Weight" xvalue="900"/></location></source>
</sources>''')
# P4 discrete: missing UFO in slice 0 hides problems in slice 1 (IB.ufo missing + slice-1 upm)
w("p4_discrete_leak.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
  <axis tag="ital" name="Italic" values="0 1" default="0"/>
</axes>
<sources>
  <source filename="MISSING.ufo" name="U0"><location><dimension name="Weight" xvalue="100"/><dimension name="Italic" xvalue="0"/></location></source>
  <source filename="R.ufo" name="U1"><location><dimension name="Weight" xvalue="400"/><dimension name="Italic" xvalue="0"/></location></source>
  <source filename="IL.ufo" name="I0"><location><dimension name="Weight" xvalue="100"/><dimension name="Italic" xvalue="1"/></location></source>
  <source filename="IR.ufo" name="I1"><location><dimension name="Weight" xvalue="400"/><dimension name="Italic" xvalue="1"/></location></source>
  <source filename="ALSO_MISSING.ufo" name="I2"><location><dimension name="Weight" xvalue="900"/><dimension name="Italic" xvalue="1"/></location></source>
</sources>''')
# P5 DS5 user-location instance out of bounds + variable-fonts element + labels
w("p5_ds5_userloc.designspace", AX.replace("</axis>", '<labels><label uservalue="400" name="Regular" elidable="true"/></labels></axis>') + SRC + '''
<variable-fonts><variable-font name="VF"><axis-subsets><axis-subset name="Weight" userminimum="100" usermaximum="2000"/></axis-subsets></variable-font></variable-fonts>
<instances>
  <instance familyname="P" stylename="Huge" filename="i/h.ufo"><location><dimension name="Weight" uservalue="1200"/></location></instance>
  <instance familyname="P" stylename="NoFile"><location><dimension name="Weight" uservalue="400"/></location></instance>
</instances>''')
# P6 duplicate source location spelled differently (explicit default vs omitted) -- no discrete axes
w("p6_dup_implicit.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
  <axis tag="wdth" name="Width" minimum="50" default="100" maximum="100"/>
</axes>
<sources>
  <source filename="R.ufo" name="R"><location><dimension name="Weight" xvalue="400"/></location></source>
  <source filename="H.ufo" name="H"><location><dimension name="Weight" xvalue="400"/><dimension name="Width" xvalue="100"/></location></source>
  <source filename="B.ufo" name="B"><location><dimension name="Weight" xvalue="900"/></location></source>
</sources>''')
# P9 first source not the default; its UPM differs -> who gets blamed?
w("p9_fontinfo_default.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
</axes>
<sources>
  <source filename="B.ufo" name="B"><location><dimension name="Weight" xvalue="900"/></location></source>
  <source filename="L.ufo" name="L"><location><dimension name="Weight" xvalue="100"/></location></source>
  <source filename="R.ufo" name="R"><location><dimension name="Weight" xvalue="400"/></location></source>
</sources>''')
# P10 no default source at all (avar2-free); mapping with default not an exact map input
w("p10_map_default_between.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900">
    <map input="100" output="0"/><map input="900" output="200"/>
  </axis>
</axes>
<sources>
  <source filename="L.ufo" name="L"><location><dimension name="Weight" xvalue="0"/></location></source>
  <source filename="R.ufo" name="R"><location><dimension name="Weight" xvalue="75"/></location></source>
  <source filename="B.ufo" name="B"><location><dimension name="Weight" xvalue="200"/></location></source>
</sources>''')
# P11 map output not monotonic and 1.5 candidate (output outside anything) ; input beyond axis
w("p11_axis_map.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900">
    <map input="100" output="0"/><map input="400" output="300"/><map input="900" output="200"/><map input="1000" output="250"/>
  </axis>
</axes>''' + SRC.replace('xvalue="100"','xvalue="300"'))
