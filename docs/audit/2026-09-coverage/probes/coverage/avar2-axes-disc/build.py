import os
D = os.path.dirname(os.path.abspath(__file__))

def extra_ufo(name, upm=1000, size=150):
    from fontParts.world import NewFont
    path = os.path.join(D, name)
    if os.path.exists(path):
        return
    f = NewFont(showInterface=False)
    f.info.unitsPerEm = upm
    f.info.familyName = "Probe"
    f.info.styleName = name
    gl = f.newGlyph("A")
    gl.width = 500
    pen = gl.getPen()
    pen.moveTo((0, 0)); pen.lineTo((size, 0)); pen.lineTo((size, size)); pen.closePath()
    f.save(path)
    f.close()

extra_ufo("X.ufo", size=175)  # third distinct UFO for discrete-value tests

def w(name, body):
    open(os.path.join(D, name), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<designspace format="5.0">\n' + body + "\n</designspace>\n"
    )

SRC2 = '''<sources>
  <source filename="L.ufo" name="L"><location><dimension name="Weight" xvalue="100"/></location></source>
  <source filename="R.ufo" name="R"><location><dimension name="Weight" xvalue="400"/></location></source>
</sources>'''

# --- AVAR2-01/02: mapping at default input (all-zero) with non-identity output on hidden axis ---
w("a1_avar2_default_input.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
  <axis tag="XHID" name="XHID" minimum="0" default="0" maximum="100" hidden="1"/>
  <mappings>
    <mapping><input><dimension name="Weight" xvalue="400"/></input><output><dimension name="XHID" xvalue="80"/></output></mapping>
    <mapping><input><dimension name="Weight" xvalue="900"/></input><output><dimension name="XHID" xvalue="80"/></output></mapping>
  </mappings>
</axes>''' + SRC2.replace("</sources>", '  <source filename="B.ufo" name="B"><location><dimension name="Weight" xvalue="900"/></location></source>\n</sources>'))

# --- AVAR2-07: dimension name is a tag, not the axis name ---
w("a2_avar2_tagname.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
  <mappings>
    <mapping><input><dimension name="wght" xvalue="900"/></input><output><dimension name="wght" xvalue="850"/></output></mapping>
  </mappings>
</axes>''' + SRC2)

# --- AVAR2-33: mappings present but format declared as 5.0 (needs 5.1) ---
open(os.path.join(D, "a3_avar2_format50.designspace"), "w").write(
    '<?xml version="1.0" encoding="UTF-8"?>\n<designspace format="5.0">\n<axes>\n'
    '<axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>\n'
    '<mappings><mapping><input><dimension name="Weight" xvalue="900"/></input>'
    '<output><dimension name="Weight" xvalue="850"/></output></mapping></mappings>\n'
    '</axes>' + SRC2 + '\n</designspace>\n'
)

# --- AVAR2-08: uservalue inside a mapping dimension (should KeyError at read time) ---
w("a4_avar2_uservalue.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
  <mappings>
    <mapping><input><dimension name="Weight" uservalue="900"/></input><output><dimension name="Weight" xvalue="850"/></output></mapping>
  </mappings>
</axes>''' + SRC2)

# --- AXIS-01: non-monotonic map outputs (should hit 1.9) ---
w("b1_nonmonotonic.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900">
    <map input="100" output="0"/><map input="400" output="500"/><map input="700" output="300"/><map input="900" output="600"/>
  </axis>
</axes>''' + SRC2.replace('xvalue="100"', 'xvalue="0"').replace('xvalue="400"', 'xvalue="500"'))

# --- AXIS-02: map missing entry at axis minimum (only default+max mapped) ---
w("b2_map_missing_min.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900">
    <map input="400" output="400"/><map input="900" output="900"/>
  </axis>
</axes>''' + SRC2.replace('xvalue="100"', 'xvalue="400"'))

# --- AXIS-03: map missing entry at axis maximum (only min+default mapped) ---
w("b3_map_missing_max.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900">
    <map input="100" output="100"/><map input="400" output="400"/>
  </axis>
</axes>''' + SRC2)

# --- AXIS-04: map missing entry at axis default (min+max mapped, default in between unmapped) ---
w("b4_map_missing_default.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900">
    <map input="100" output="100"/><map input="900" output="900"/>
  </axis>
</axes>''' + SRC2)

# --- AXIS-05: duplicate map input values, different outputs ---
w("b5_dup_map_input.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900">
    <map input="100" output="100"/><map input="400" output="440"/><map input="400" output="460"/><map input="900" output="900"/>
  </axis>
</axes>''' + SRC2.replace('xvalue="400"', 'xvalue="440"'))

# --- AXIS-10: minimum > maximum (reversed) ---
w("b6_reversed_range.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="900" default="400" maximum="100"/>
</axes>''' + SRC2)

# --- AXIS-11: minimum == maximum on continuous axis ---
w("b7_min_eq_max.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="400" default="400" maximum="400"/>
</axes>''' + SRC2.replace('xvalue="100"', 'xvalue="400"'))

# --- AXIS-09: default outside [min,max] ---
w("b8_default_oob.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="50" maximum="900"/>
</axes>''' + SRC2)

# --- AXIS-16: hidden axis, default out of range -> should still get 1.2 like a normal axis ---
w("b9_hidden_axis_default_oob.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
  <axis tag="XHID" name="XHID" minimum="0" default="500" maximum="100" hidden="1"/>
</axes>''' + SRC2)

# --- AXIS-15: variable-fonts with a range axis-subset on a DISCRETE axis (should require uservalue only) ---
w("b10_vf_range_on_discrete.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
  <axis tag="ital" name="Italic" values="0 1" default="0"/>
</axes>
<sources>
  <source filename="L.ufo" name="L"><location><dimension name="Weight" xvalue="100"/><dimension name="Italic" xvalue="0"/></location></source>
  <source filename="R.ufo" name="R"><location><dimension name="Weight" xvalue="400"/><dimension name="Italic" xvalue="0"/></location></source>
</sources>
<variable-fonts>
  <variable-font name="VF">
    <axis-subsets>
      <axis-subset name="Italic" userminimum="0" usermaximum="1"/>
    </axis-subsets>
  </variable-font>
</variable-fonts>''')

# --- AXIS-13 / DISC-06: discrete axis default not among declared values, real UFOs on both sides ---
w("c1_discrete_default_oob.designspace", '''<axes>
  <axis tag="ital" name="Italic" values="0 1" default="2"/>
</axes>
<sources>
  <source filename="L.ufo" name="U0"><location><dimension name="Italic" xvalue="0"/></location></source>
  <source filename="R.ufo" name="U1"><location><dimension name="Italic" xvalue="1"/></location></source>
</sources>''')

# --- DISC-10: source at an undeclared discrete value (values="0 1" but a source at 2) ---
w("c2_discrete_undeclared_value.designspace", '''<axes>
  <axis tag="ital" name="Italic" values="0 1" default="0"/>
</axes>
<sources>
  <source filename="L.ufo" name="U0"><location><dimension name="Italic" xvalue="0"/></location></source>
  <source filename="R.ufo" name="U1"><location><dimension name="Italic" xvalue="1"/></location></source>
  <source filename="X.ufo" name="U2"><location><dimension name="Italic" xvalue="2"/></location></source>
</sources>''')

# --- LABEL-06: top-level label given a design location (xvalue) instead of user location ---
w("d1_label_design_location.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
</axes>''' + SRC2 + '''
<labels>
  <label name="Foo"><location><dimension name="Weight" xvalue="400"/></location></label>
</labels>''')

# --- LABEL-12: unknown attribute on a <label> element ---
w("d2_label_unknown_attr.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
</axes>''' + SRC2 + '''
<labels>
  <label name="Foo" uservalue="400" oldesibling="true"/>
</labels>''')

# --- LABEL-05: instance references a nonexistent location label ---
w("d3_instance_bad_locationlabel.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900">
    <labels><label uservalue="400" name="Regular"/></labels>
  </axis>
</axes>''' + SRC2 + '''
<instances>
  <instance familyname="P" stylename="Ghost" location="Bogus"/>
</instances>''')

print("built probes in", D)
print(sorted(os.listdir(D)))
