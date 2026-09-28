import os
D = os.path.dirname(os.path.abspath(__file__))

def w(name, body):
    open(os.path.join(D, name), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<designspace format="5.0">\n' + body + "\n</designspace>\n"
    )

# c1c: discrete default OOB (2, not in [0,1]), mixed axes, BOTH slices have a proper Weight-default (400) source
w("c1c_discrete_default_oob_clean.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
  <axis tag="ital" name="Italic" values="0 1" default="2"/>
</axes>
<sources>
  <source filename="L.ufo" name="U0"><location><dimension name="Weight" xvalue="100"/><dimension name="Italic" xvalue="0"/></location></source>
  <source filename="R.ufo" name="U1"><location><dimension name="Weight" xvalue="400"/><dimension name="Italic" xvalue="0"/></location></source>
  <source filename="B.ufo" name="U2"><location><dimension name="Weight" xvalue="900"/><dimension name="Italic" xvalue="1"/></location></source>
  <source filename="H.ufo" name="U3"><location><dimension name="Weight" xvalue="400"/><dimension name="Italic" xvalue="1"/></location></source>
</sources>''')

# c2c: source at undeclared discrete value=2, BOTH real slices (0,1) have proper Weight-default coverage
w("c2c_discrete_undeclared_value_clean.designspace", '''<axes>
  <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
  <axis tag="ital" name="Italic" values="0 1" default="0"/>
</axes>
<sources>
  <source filename="L.ufo" name="U0"><location><dimension name="Weight" xvalue="100"/><dimension name="Italic" xvalue="0"/></location></source>
  <source filename="R.ufo" name="U1"><location><dimension name="Weight" xvalue="400"/><dimension name="Italic" xvalue="0"/></location></source>
  <source filename="B.ufo" name="U2"><location><dimension name="Weight" xvalue="900"/><dimension name="Italic" xvalue="1"/></location></source>
  <source filename="H.ufo" name="U3"><location><dimension name="Weight" xvalue="400"/><dimension name="Italic" xvalue="1"/></location></source>
  <source filename="X.ufo" name="U4"><location><dimension name="Weight" xvalue="400"/><dimension name="Italic" xvalue="2"/></location></source>
</sources>''')

print("built c1c/c2c")
