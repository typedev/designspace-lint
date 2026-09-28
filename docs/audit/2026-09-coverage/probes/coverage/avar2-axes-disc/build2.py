import os
D = os.path.dirname(os.path.abspath(__file__))

def w(name, body):
    open(os.path.join(D, name), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<designspace format="5.0">\n' + body + "\n</designspace>\n"
    )

# --- AXIS-13/DISC-06 retry: discrete default OOB, WITH a continuous axis present too, real UFOs ---
w("c1b_discrete_default_oob_mixed.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
  <axis tag="ital" name="Italic" values="0 1" default="2"/>
</axes>
<sources>
  <source filename="L.ufo" name="U0"><location><dimension name="Weight" xvalue="100"/><dimension name="Italic" xvalue="0"/></location></source>
  <source filename="R.ufo" name="U1"><location><dimension name="Weight" xvalue="400"/><dimension name="Italic" xvalue="0"/></location></source>
  <source filename="B.ufo" name="U2"><location><dimension name="Weight" xvalue="900"/><dimension name="Italic" xvalue="1"/></location></source>
</sources>''')

# --- DISC-10 retry: source at an undeclared discrete value, WITH a continuous axis present ---
w("c2b_discrete_undeclared_value_mixed.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
  <axis tag="ital" name="Italic" values="0 1" default="0"/>
</axes>
<sources>
  <source filename="L.ufo" name="U0"><location><dimension name="Weight" xvalue="100"/><dimension name="Italic" xvalue="0"/></location></source>
  <source filename="R.ufo" name="U1"><location><dimension name="Weight" xvalue="400"/><dimension name="Italic" xvalue="0"/></location></source>
  <source filename="B.ufo" name="U2"><location><dimension name="Weight" xvalue="900"/><dimension name="Italic" xvalue="1"/></location></source>
  <source filename="X.ufo" name="U3"><location><dimension name="Weight" xvalue="400"/><dimension name="Italic" xvalue="2"/></location></source>
</sources>''')

# --- sanity control: confirm the "all-discrete-axes -> spurious 1.0" bug is specific to zero-remaining-continuous-axes ---
w("e1_pure_discrete_control.designspace", '''<axes>
  <axis tag="ital" name="Italic" values="0 1" default="0"/>
</axes>
<sources>
  <source filename="L.ufo" name="U0"><location><dimension name="Italic" xvalue="0"/></location></source>
  <source filename="R.ufo" name="U1"><location><dimension name="Italic" xvalue="1"/></location></source>
</sources>''')

# --- fixed b2 (AXIS-02): map missing entry at minimum, without accidental source-location collision ---
w("b2b_map_missing_min_fixed.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900">
    <map input="400" output="400"/><map input="900" output="900"/>
  </axis>
</axes>
<sources>
  <source filename="L.ufo" name="L"><location><dimension name="Weight" xvalue="400"/></location></source>
  <source filename="R.ufo" name="R"><location><dimension name="Weight" xvalue="900"/></location></source>
</sources>''')

# --- fixed b10 (AXIS-15): variable-fonts range-subset on discrete axis, WITH userdefault so it passes the completeness gate ---
w("b10b_vf_range_on_discrete_fixed.designspace", '''<axes>
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
      <axis-subset name="Italic" userminimum="0" usermaximum="1" userdefault="0"/>
    </axis-subsets>
  </variable-font>
</variable-fonts>''')

print("built:", sorted(f for f in os.listdir(D) if f.startswith(("c1b","c2b","e1","b2b","b10b"))))
