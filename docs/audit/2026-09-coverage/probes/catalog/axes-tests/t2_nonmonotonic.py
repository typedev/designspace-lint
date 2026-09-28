import sys
from fontTools.designspaceLib import AxisDescriptor

a = AxisDescriptor(tag="wght", name="weight", minimum=100, default=400, maximum=900)
# Non-monotonic map: input increases but output decreases in the middle
a.map = [(100, 100), (400, 500), (700, 300), (900, 900)]
for v in (100, 250, 400, 550, 700, 800, 900):
    print(v, "->", a.map_forward(v))
