# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
# SPDX-License-Identifier: MIT
"""Bore test coupon: freecadcmd common/build_coupon.py"""

import os
import sys

import FreeCAD as App

HERE = os.path.dirname(os.path.abspath(
    __file__ if "__file__" in globals() else
    # fallback when run via exec() without __file__: the script path on the
    # command line, else the current directory
    next((a for a in sys.argv if a.endswith("build_coupon.py")), "x")))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import clipkit  # noqa: E402

out_dir = os.path.join(ROOT, "coupon")
os.makedirs(out_dir, exist_ok=True)
doc = App.newDocument("bore_coupon")
c = clipkit.make_coupon(doc)
doc.recompute()
probs = clipkit.check_doc(doc)
sh = c.Shape
print("coupon valid=%s volume=%.2f solids=%d bbox=%s" % (
    sh.isValid(), sh.Volume, len(sh.Solids), sh.BoundBox))
for p in probs:
    print("ERROR", p)
fc = os.path.join(out_dir, "bore_coupon.FCStd")
if os.path.exists(fc):
    os.remove(fc)  # avoid .FCBak backups
doc.saveAs(fc)
os.makedirs(os.path.join(out_dir, "stl"), exist_ok=True)
clipkit.export_stl(sh, os.path.join(out_dir, "stl", "bore_coupon.stl"))
print("saved", out_dir)
if probs or not sh.isValid() or len(sh.Solids) != 1:
    raise SystemExit(1)
