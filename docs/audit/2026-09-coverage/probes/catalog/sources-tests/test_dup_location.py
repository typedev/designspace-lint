from fontTools.designspaceLib import DesignSpaceDocument, AxisDescriptor, SourceDescriptor
from fontTools.varLib import load_designspace
from fontTools.varLib.models import VariationModel

def mk_axis(tag, name, minimum, default, maximum):
    a = AxisDescriptor()
    a.tag = tag; a.name = name
    a.minimum = minimum; a.default = default; a.maximum = maximum
    return a

doc = DesignSpaceDocument()
doc.addAxis(mk_axis("wght", "weight", 100, 400, 900))
s1 = SourceDescriptor(); s1.name="base"; s1.location={"weight": 400}
s2 = SourceDescriptor(); s2.name="bold_a"; s2.location={"weight": 700}
s3 = SourceDescriptor(); s3.name="bold_b"; s3.location={"weight": 700}  # duplicate, non-default
doc.addSource(s1); doc.addSource(s2); doc.addSource(s3)

ds = load_designspace(doc)
print("load_designspace succeeded (no dedup check here). base_idx =", ds.base_idx)
print("normalized_master_locs:", ds.normalized_master_locs)

try:
    normalized = [{ax: v[ax_i] for ax_i, ax in enumerate(["wght"])} for v in [(0.0,), (0.5,), (0.5,)]]
    VariationModel(normalized, axisOrder=["wght"])
    print("VariationModel: NO ERROR")
except Exception as e:
    print(f"VariationModel raised: {type(e).__name__}: {e}")
