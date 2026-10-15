# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
# SPDX-License-Identifier: MIT
"""Convert the STLs the build scripts write into 3MFs under the repo's 3mf/ tree.

    freecadcmd common/build_coupon.py
    freecadcmd common/build_head_demo.py
    freecadcmd edge_clamp/build_edge_clamp.py
    freecadcmd hole_mount/build_hole_mount.py
    freecadcmd common/export_3mf.py

freecad/edge_clamp/stl -> 3mf/edge_clamp, freecad/hole_mount/stl -> 3mf/hole_mount,
freecad/common/stl -> 3mf/heads, freecad/coupon/stl/bore_coupon.stl -> 3mf/bore_coupon.3mf.
3mf/fitted/ is not regenerated here (it comes from the board assembly, not part of this repo).
Each 3MF is read back and checked against its STL (facets, solid, volume).
"""
import glob
import os
import sys

import Mesh

HERE = os.path.dirname(os.path.abspath(
    __file__ if "__file__" in globals() else
    # fallback when run via exec() without __file__: the script path on the
    # command line, else the current directory
    next((a for a in sys.argv if a.endswith("export_3mf.py")), "x")))
FC = os.path.dirname(HERE)          # freecad/
REPO = os.path.dirname(FC)          # repo root
OUT = os.path.join(REPO, "3mf")

jobs = []
for src_dir, dst_dir in (("edge_clamp/stl", "edge_clamp"),
                         ("hole_mount/stl", "hole_mount"),
                         ("common/stl", "heads")):
    for f in sorted(glob.glob(os.path.join(FC, src_dir, "*.stl"))):
        jobs.append((f, os.path.join(OUT, dst_dir, os.path.basename(f)[:-4] + ".3mf")))
jobs.append((os.path.join(FC, "coupon", "stl", "bore_coupon.stl"),
             os.path.join(OUT, "bore_coupon.3mf")))
bad = 0
for src, dst in jobs:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    m = Mesh.Mesh(src)
    m.write(dst)
    back = Mesh.Mesh(dst)
    ok = back.CountFacets == m.CountFacets and back.isSolid() and abs(back.Volume - m.Volume) < 0.01
    bad += not ok
    print("3MF", "ok " if ok else "BAD", os.path.relpath(dst, REPO), m.CountFacets, round(back.Volume, 1))
print("3MF total", len(jobs), "bad", bad)
if bad:
    raise SystemExit(1)
