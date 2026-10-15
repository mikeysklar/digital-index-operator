# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
# SPDX-License-Identifier: MIT
"""Head-only demo + per-preset checks.

    freecadcmd common/build_head_demo.py
"""

import math
import os
import sys

import FreeCAD as App

HERE = os.path.dirname(os.path.abspath(
    __file__ if "__file__" in globals() else
    # fallback when run via exec() without __file__: the script path on the
    # command line, else the current directory
    next((a for a in sys.argv if a.endswith("build_head_demo.py")), "x")))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import clipkit  # noqa: E402

TIP_R = 0.35  # pogo tip radius


def rect_dist(px, py, x0, x1, y0, y1):
    """Distance from a point to an axis-aligned rectangle (negative inside)."""
    dx = max(x0 - px, 0, px - x1)
    dy = max(y0 - py, 0, py - y1)
    if dx == 0 and dy == 0:
        return -min(px - x0, x1 - px, py - y0, y1 - py)
    return math.hypot(dx, dy)


def main():
    out = os.path.join(HERE, "head_demo.FCStd")
    stl_dir = os.path.join(HERE, "stl")
    os.makedirs(stl_dir, exist_ok=True)
    doc = App.newDocument("head_demo")
    clipkit.make_sheets(doc, os.path.join(ROOT, "presets.csv"),
                        os.path.join(ROOT, "boards.csv"))
    head = clipkit.make_head(doc)
    params = doc.Params
    presets = doc.Presets
    doc.recompute()
    pm_cell = params.getCellFromAlias("preset_manual")
    names = {int(presets.get(clipkit._col(c) + "2")): presets.get(clipkit._col(c) + "1")
             for c in range(1, 9)}
    doc.recompute()

    errors, warnings, table = [], [], []
    for k in range(1, 9):
        params.set(pm_cell, str(k))
        doc.recompute()
        g = lambda a: float(params.get(a))  # noqa: E731
        probs = clipkit.check_doc(doc)
        if probs:
            errors += ["preset %d: %s" % (k, p) for p in probs]
        if int(g("preset")) != k:
            errors.append("preset %d: Params.preset = %s" % (k, g("preset")))
        sh = head.Shape
        if sh.isNull() or not sh.isValid() or sh.Volume <= 0 or len(sh.Solids) != 1:
            errors.append("preset %d: bad shape (valid=%s vol=%.3f solids=%d)"
                          % (k, sh.isValid(), sh.Volume, len(sh.Solids)))
        bb = sh.BoundBox
        # body footprint box
        bx0, bx1 = -g("body_l") / 2, g("body_l") / 2
        by0 = g("body_cy") - g("body_w") / 2
        by1 = g("body_cy") + g("body_w") / 2
        tipc, barc = [], []
        for i in (1, 2):
            cx, cy = g("c%d_x" % i), g("c%d_y" % i)
            dist = rect_dist(cx, cy, bx0, bx1, by0, by1)
            tipc.append(dist - TIP_R)
            barc.append(dist - g("pin_barrel_d") / 2)
            # contact point on its pad?
            onpad = False
            for sx in (-1, 1):
                for sy in (-1, 1):
                    px, py = sx * g("pad_x"), sy * g("pad_y")
                    m = min(g("pad_lx") / 2 - abs(cx - px), g("pad_ly") / 2 - abs(cy - py))
                    onpad = onpad or m >= 0
                    if m >= 0 and m < TIP_R:
                        warnings.append("preset %d c%d: tip center only %.3f mm inside pad "
                                        "edge (tip r %.2f)" % (k, i, m, TIP_R))
            if not onpad:
                warnings.append("preset %d c%d (%.3f, %.3f) is not on any pad"
                                % (k, i, cx, cy))
            if dist - TIP_R < -1e-9:
                warnings.append("preset %d c%d: pogo tip circle overlaps body box by %.3f"
                                % (k, i, TIP_R - dist))
            # plunger window vs bore
            if g("plunger_d") > 0:
                gap = math.hypot(cx, cy) - g("wnd_r") - g("bore_d") / 2
                if gap <= 0:
                    warnings.append("preset %d c%d: plunger window intersects bore (%.3f)"
                                    % (k, i, gap))
        if g("plunger_d") > 0:
            wgap = min(math.hypot(g("c%d_x" % i), g("c%d_y" % i)) - g("wnd_r")
                       - g("bore_d") / 2 for i in (1, 2))
        else:
            wgap = float("nan")
        if g("plunger_d") > 0 and g("plunger_h") <= g("roof_z0"):
            warnings.append("preset %d: plunger top %.2f below roof %.2f (window unused)"
                            % (k, g("plunger_h"), g("roof_z0")))
        table.append((k, names[k], sh.Volume, bb.XLength, bb.YLength, bb.ZLength,
                      bb.XMin, bb.XMax, bb.YMin, bb.YMax, min(tipc), min(barc), wgap))
        clipkit.export_stl(sh, os.path.join(stl_dir, "head_%s.stl" % names[k]))

    params.set(pm_cell, "1")
    doc.recompute()
    if os.path.exists(out):
        os.remove(out)  # avoid .FCBak backups
    doc.saveAs(out)

    print("\n%-2s %-14s %8s %6s %6s %6s %13s %13s %7s %7s %7s" % (
        "#", "preset", "vol mm3", "dx", "dy", "dz", "x range", "y range",
        "tip_clr", "bar_clr", "wnd_gap"))
    for t in table:
        print("%-2d %-14s %8.2f %6.2f %6.2f %6.2f %6.2f..%-5.2f %6.2f..%-5.2f %7.3f %7.3f %7.3f"
              % t)
    print("tip_clr = min clearance of pogo tip circle (r %.2f) to body box; "
          "bar_clr = same for barrel; wnd_gap = window edge to bore edge" % TIP_R)
    for w in warnings:
        print("WARNING", w)
    for e in errors:
        print("ERROR", e)
    print("saved", out)
    if errors:
        raise SystemExit(1)


main()
