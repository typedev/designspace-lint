import json, sys, time, subprocess, collections, os
from fontTools.designspaceLib import DesignSpaceDocument
p = sys.argv[1]; out = sys.argv[2]
d = DesignSpaceDocument.fromfile(p)
n_src = len(d.sources); present = sum(1 for s in d.sources if s.path and os.path.exists(s.path))
t = time.time()
r = subprocess.run([sys.executable, "-m", "designspace_lint.cli", "--json", p], capture_output=True, text=True, timeout=3000)
dt = time.time() - t
open(out + ".stderr", "w").write(r.stderr)
open(out + ".json", "w").write(r.stdout)
try:
    probs = json.loads(r.stdout)
except Exception:
    probs = None
c = collections.Counter((x["code"], x["severity"]) for x in probs) if probs is not None else None
print(json.dumps({"ds": p, "axes": len(d.axes), "discrete": sum(1 for a in d.axes if getattr(a,'values',None)),
  "hidden": sum(1 for a in d.axes if getattr(a,'hidden',False)), "axisMappings": len(d.axisMappings),
  "vfs": len(d.variableFonts), "sources": n_src, "ufos_present": present, "instances": len(d.instances), "rules": len(d.rules),
  "exit": r.returncode, "secs": round(dt,1), "n": None if probs is None else len(probs),
  "codes": None if c is None else {f"{k[0]}({k[1]})": v for k, v in sorted(c.items())},
  "stderr_tail": r.stderr.strip().splitlines()[-3:]}))
