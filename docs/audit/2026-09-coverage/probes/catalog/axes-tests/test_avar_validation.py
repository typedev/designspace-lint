from collections import OrderedDict
from fontTools.varLib import _add_avar
from fontTools.designspaceLib import AxisDescriptor
from fontTools.ttLib import TTFont

def make_axis(tag, name, minimum, default, maximum, map=None):
    a = AxisDescriptor()
    a.tag = tag
    a.name = name
    a.minimum = minimum
    a.default = default
    a.maximum = maximum
    a.map = map or []
    return a

def try_it(label, axis):
    axes = OrderedDict()
    axes[axis.tag] = axis
    font = TTFont()
    try:
        _add_avar(font, axes, [], [axis.tag])
        print(label, "-> OK, no error. avar segments:", font["avar"].segments if "avar" in font else None)
    except Exception as e:
        print(label, "-> RAISED:", type(e).__name__, str(e))

# 1. map missing default value
axis1 = make_axis("wght", "Weight", 100, 400, 900, map=[(100,100),(900,900)])
try_it("missing-default-in-map", axis1)

# 2. map missing minimum value as lowest input
axis2 = make_axis("wght", "Weight", 100, 400, 900, map=[(200,150),(400,400),(900,900)])
try_it("missing-minimum-in-map", axis2)

# 3. non-ascending output values (non-monotonic)
axis3 = make_axis("wght", "Weight", 100, 400, 900, map=[(100,100),(400,900),(900,400)])
try_it("non-ascending-output", axis3)

# 4. duplicate input keys
axis4 = make_axis("wght", "Weight", 100, 400, 900, map=[(100,100),(400,400),(400,500),(900,900)])
try_it("duplicate-input-keys", axis4)

# 5. valid map
axis5 = make_axis("wght", "Weight", 100, 400, 900, map=[(100,50),(400,400),(900,950)])
try_it("valid-map", axis5)
