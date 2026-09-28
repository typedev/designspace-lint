exec(open("probes/catalog/avar2-tests/t.py").read().split("Z={")[0])
Z={"wght":0,"wdth":0,"XHID":0}
run("T4b default-input mapping poisons others", ds(m({"Weight":400},{"Hidden":100})+m({"Weight":900},{"Hidden":100})), [Z,{"wght":1.0},{"wght":-1.0}])
run("T4c control: only wght900 mapping", ds(m({"Weight":900},{"Hidden":100})), [Z,{"wght":1.0},{"wght":-1.0}])
wmap = '<map input="100" output="20"/><map input="400" output="80"/><map input="900" output="200"/>'
run("T8c user value 300 written as input on design-space axis 20..200 (intended user 300=design 60)", ds(m({"Weight":300},{"Hidden":100}), wmap), [{"wght":-0.3333},{"wght":0.8333}])
# partial-coverage: mapping only on one side
run("T15 one-sided mapping, other side", ds(m({"Weight":900},{"Hidden":100})), [{"wght":-1.0}])
# mapping outputs to a user axis (wdth) from wght: user can no longer reach wdth extremes
run("T16 output on user-visible axis", ds(m({"Weight":900},{"Width":150})), [{"wght":1.0,"wdth":-1.0},{"wght":1.0,"wdth":1.0}])
