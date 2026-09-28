import sys
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.varLib import load_designspace, VarLibValidationError

def make_ds(sources):
    ds = DesignSpaceDocument()
    ds.addAxisDescriptor(tag="wght", name="weight", minimum=100, default=400, maximum=900)
    for name, loc in sources:
        ds.addSourceDescriptor(name=name, location=loc)
    return ds

print("=== TEST: no default/base master ===")
ds = make_ds([("A", {"weight": 300}), ("B", {"weight": 700})])
try:
    load_designspace(ds, log_enabled=False)
except VarLibValidationError as e:
    print("OK raised:", e)

print("=== TEST: out-of-range location ===")
ds = make_ds([("A", {"weight": 400}), ("B", {"weight": 1200})])
try:
    load_designspace(ds, log_enabled=False)
except VarLibValidationError as e:
    print("OK raised:", e)

print("=== TEST: duplicate master locations (both at default) ===")
ds = make_ds([("A", {"weight": 400}), ("B", {"weight": 400})])
try:
    r = load_designspace(ds, log_enabled=False)
    print("no error at load_designspace, base_idx=", r.base_idx)
    from fontTools.varLib import models
    m = models.VariationModel(r.normalized_master_locs, axisOrder=list(r.axes.keys()))
except Exception as e:
    print(f"OK raised {type(e).__name__}:", e)
