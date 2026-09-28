import sys
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.varLib import load_designspace
from fontTools.varLib import models

ds = DesignSpaceDocument()
ds.addAxisDescriptor(tag="wght", name="weight", minimum=100, default=400, maximum=900)
ds.addSourceDescriptor(name="Reg", location={"weight": 400})
ds.addSourceDescriptor(name="Bold1", location={"weight": 700})
ds.addSourceDescriptor(name="Bold2", location={"weight": 700})  # duplicate non-default location

r = load_designspace(ds, log_enabled=False)
print("load_designspace passed silently, base_idx=", r.base_idx)
print("normalized locs:", r.normalized_master_locs)
try:
    m = models.VariationModel(r.normalized_master_locs, axisOrder=["weight"])
except Exception as e:
    print(f"VariationModel raised {type(e).__name__}: {e}")
