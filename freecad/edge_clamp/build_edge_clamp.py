# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
# SPDX-License-Identifier: MIT
"""Edge clamp variant of the pogo-pin button clip.

    freecadcmd edge_clamp/build_edge_clamp.py

Builds edge_clamp.FCStd (board = 1 selected) and one STL per Boards row and
per preset (board = 0), after checking every case.

Arm frame: the switch frame rotated by Params.edge_angle about Z, so +X points
from the switch center to the nearest board edge. Every arm solid is placed
with placement(vector(R * corner); rotation(Z; edge_angle)).
"""

import math
import os
import re
import sys

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.abspath(
    __file__ if "__file__" in globals() else
    # fallback when run via exec() without __file__: the script path on the
    # command line, else the current directory
    next((a for a in sys.argv if a.endswith("build_edge_clamp.py")), "x")))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "common"))
import clipkit  # noqa: E402

# name, value or formula, note
EDGE_PARAMS = [
    ("board_t", "1.6", "PCB thickness"),
    ("slot_clear", "0.15", "min clearance of clip material above the PCB top (checked)"),
    ("arm_t", "3.0", "arm thickness"),
    ("arm_z0", "=roof_z0", "arm base z, level with the head roof underside"),
    ("arm_lift", "0.0", "raise the arm above arm_z0 to clear taller parts"),
    ("edge_gap", "0.3", "clearance from board edge to spine inner face"),
    ("spine_t", "2.0", "spine thickness (along the edge direction)"),
    ("jaw_len", "5.0", "how far the lower jaw reaches back under the board"),
    ("jaw_t", "2.0", "lower jaw thickness"),
    ("jaw_squeeze", "0.1", "jaw top sits this far above the PCB bottom (grip)"),
    ("screw_d", "1.8", "M2 tapping hole through the lower jaw, 0 = none"),
    ("screw_off", "=jaw_len - 2", "screw axis distance back from the spine inner face"),
    ("arm_w", "=clip_w", "arm, spine and jaw width"),
    # derived
    ("edge_in", "=edge_dist + edge_gap", "spine inner face distance from switch center"),
    ("arm_len", "=edge_in + spine_t", "arm length from switch center"),
    ("arm_zb", "=arm_z0 + arm_lift", "arm underside z"),
    ("arm_zt", "=arm_zb + arm_t", "arm top z"),
    ("jaw_top", "=-(board_t - jaw_squeeze)", "lower jaw top z"),
    ("jaw_bot", "=jaw_top - jaw_t", "lower jaw bottom z"),
    ("screw_x", "=edge_in - screw_off", "screw axis along the edge direction"),
    ("screw_r", "=max(screw_d / 2; 0.01)", "screw hole radius"),
    ("screw_z", "=screw_d > 0 ? jaw_bot - 1 : jaw_bot - 100",
     "screw hole start z (parked far below when screw_d = 0)"),
]

A = "Params.edge_angle"


def add_params(params):
    last = max(int(re.sub(r"[A-Z]+", "", c)) for c in params.getUsedCells())
    rows = list(enumerate(EDGE_PARAMS, start=last + 1))
    for r, (name, val, note) in rows:
        params.set("A%d" % r, "'" + name)
        params.set("C%d" % r, "'" + note)
    for r, (name, val, note) in rows:
        params.setAlias("B%d" % r, name)
    for r, (name, val, note) in rows:
        params.set("B%d" % r, val)


def p(s):
    return s.replace("$", "Params.")


def arm_placement(x, y, z):
    """Placement expression for a local arm-frame corner (x, y, z)."""
    return ("placement(vector((%s) * cos(%s) - (%s) * sin(%s); "
            "(%s) * sin(%s) + (%s) * cos(%s); %s); rotation(vector(0; 0; 1); %s))"
            % (x, A, y, A, x, A, y, A, z, A))


def arm_box(doc, name, L, W, H, x, y, z):
    o = doc.addObject("Part::Box", name)
    for prop, e in (("Length", L), ("Width", W), ("Height", H),
                    (".Placement", arm_placement(x, y, z))):
        o.setExpression(prop, p(e))
    return o


def build(doc):
    clipkit.make_sheets(doc, os.path.join(ROOT, "presets.csv"),
                        os.path.join(ROOT, "boards.csv"))
    add_params(doc.Params)
    head = clipkit.make_head(doc, "EdgeClamp")
    arm = arm_box(doc, "Arm", "$arm_len", "$arm_w", "$arm_t",
                  "0", "-$arm_w / 2", "$arm_zb")
    spine = arm_box(doc, "Spine", "$spine_t", "$arm_w", "$arm_zt - $jaw_bot",
                    "$edge_in", "-$arm_w / 2", "$jaw_bot")
    jaw = arm_box(doc, "Jaw", "$arm_len - $edge_dist + $jaw_len", "$arm_w", "$jaw_t",
                  "$edge_dist - $jaw_len", "-$arm_w / 2", "$jaw_bot")
    clipkit.finish(doc, head, [arm, spine, jaw])
    screw = doc.addObject("Part::Cylinder", "Screw")
    for prop, e in (("Radius", "$screw_r"), ("Height", "$jaw_t + 2"),
                    (".Placement.Base.x", "$screw_x * cos(%s)" % A),
                    (".Placement.Base.y", "$screw_x * sin(%s)" % A),
                    (".Placement.Base.z", "$screw_z")):
        screw.setExpression(prop, p(e))
    clipkit.add_tool(doc, head, screw)
    return head


# ---------------------------------------------------------------- checks

def hits(shape, p0, p1):
    """Sorted (t0, t1) spans of segment p0->p1 inside shape, t in mm from p0."""
    seg = Part.Edge(Part.LineSegment(p0, p1))
    d = (p1 - p0)
    d.normalize()
    spans = []
    for e in shape.common(seg).Edges:
        a, b = [(v.Point - p0).dot(d) for v in e.Vertexes]
        spans.append((min(a, b), max(a, b)))
    return sorted(spans)


def check_case(head, g):
    """Return (measurements dict, warnings, errors) for the current recompute."""
    sh = head.Shape
    errs, warns = [], []
    ang = math.radians(g("edge_angle"))
    d = App.Vector(math.cos(ang), math.sin(ang), 0)
    tol = 1e-4

    # spine inner face: probe along the edge direction at mid board thickness
    zm = -g("board_t") / 2
    sp = hits(sh, App.Vector(0, 0, zm), d * (g("arm_len") + 5) + App.Vector(0, 0, zm))
    spine_in = sp[0][0] if sp else float("nan")
    if not sp or abs(spine_in - g("edge_in")) > tol:
        errs.append("spine inner face %.4f, expected %.4f" % (spine_in, g("edge_in")))

    # slot at the edge: vertical probe just inside the board edge
    xp = g("edge_dist") - 0.2
    base = d * xp
    vz = hits(sh, base + App.Vector(0, 0, -20), base + App.Vector(0, 0, 40))
    vz = [(a - 20, b - 20) for a, b in vz]
    below = [s for s in vz if s[1] <= 0 + tol]
    above = [s for s in vz if s[0] > 0 + tol]
    jaw_top = below[-1][1] if below else float("nan")
    clear_above = above[0][0] if above else float("inf")
    slot = 0 - jaw_top
    if abs(slot - (g("board_t") - g("jaw_squeeze"))) > tol:
        errs.append("slot %.4f, expected board_t - jaw_squeeze = %.4f"
                    % (slot, g("board_t") - g("jaw_squeeze")))
    if len(below) + len(above) != len(vz):
        errs.append("material inside the PCB thickness at the edge probe")
    if clear_above < g("slot_clear"):
        warns.append("clip material only %.3f above PCB top at the edge" % clear_above)

    # screw must land in the jaw, under the board
    if g("screw_d") > 0 and not (g("edge_dist") - g("jaw_len") < g("screw_x") - g("screw_r")
                                 and g("screw_x") + g("screw_r") < g("edge_dist")):
        warns.append("screw hole at %.2f is not under the board within the jaw "
                     "(lower screw_off or set screw_d = 0)" % g("screw_x"))

    # switch body interference (arm parts landing on the switch)
    bl, bw, bh, cy = g("body_l"), g("body_w"), g("body_h"), g("body_cy")
    body = Part.makeBox(bl, bw, bh, App.Vector(-bl / 2, cy - bw / 2, 0))
    bv = sh.common(body).Volume
    if bv > 1e-6:
        warns.append("clip overlaps switch body box by %.2f mm3 (edge %.2f mm from center "
                     "is inside the body/head)" % (bv, g("edge_dist")))
    return {"spine_in": spine_in, "slot": slot, "clear_above": clear_above}, warns, errs


def safe(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def main():
    out = os.path.join(HERE, "edge_clamp.FCStd")
    stl_dir = os.path.join(HERE, "stl")
    os.makedirs(stl_dir, exist_ok=True)
    doc = App.newDocument("edge_clamp")
    head = build(doc)
    params, boards, presets = doc.Params, doc.Boards, doc.Presets
    doc.recompute()
    board_cell = params.getCellFromAlias("board")
    pm_cell = params.getCellFromAlias("preset_manual")
    pnames = {int(presets.get(clipkit._col(c) + "2")): presets.get(clipkit._col(c) + "1")
              for c in range(1, 9)}
    nboards = max(int(re.sub(r"[A-Z]+", "", c)) for c in boards.getUsedCells()) - 1

    cases = [(b, 1) for b in range(1, nboards + 1)] + [(0, k) for k in range(1, 9)]
    table, allw, alle = [], [], []
    for b, k in cases:
        params.set(board_cell, str(b))
        params.set(pm_cell, str(k))
        doc.recompute()
        g = lambda a: float(params.get(a))  # noqa: E731
        pre = int(g("preset"))
        if b > 0:
            bname, ref = boards.get("A%d" % (b + 1)), boards.get("B%d" % (b + 1))
            tag = "%s_%s" % (bname, ref)
        else:
            bname, ref = "(manual)", "-"
            tag = pnames[pre]
        label = "board %d" % b if b else "preset %d" % k
        errs = ["check_doc " + s for s in clipkit.check_doc(doc)]
        sh = head.Shape
        if sh.isNull() or not sh.isValid() or len(sh.Solids) != 1 or sh.Volume <= 0:
            errs.append("bad shape valid=%s solids=%d vol=%.3f"
                        % (sh.isValid(), len(sh.Solids), sh.Volume))
            m, w = {"spine_in": float("nan"), "slot": float("nan"),
                    "clear_above": float("nan")}, []
        else:
            m, w, e2 = check_case(head, g)
            errs += e2
        allw += ["%s: %s" % (label, s) for s in w]
        alle += ["%s: %s" % (label, s) for s in errs]
        bb = sh.BoundBox
        table.append((b, k if b == 0 else "", bname[:30], ref, pnames[pre], g("edge_dist"),
                      g("edge_angle"), sh.Volume,
                      "%.1fx%.1fx%.1f" % (bb.XLength, bb.YLength, bb.ZLength),
                      m["spine_in"], m["slot"], m["clear_above"], "W" if w else ""))
        if not errs:
            clipkit.export_stl(sh, os.path.join(stl_dir, "edge_clamp_%s.stl" % safe(tag)))

    params.set(board_cell, "1")
    params.set(pm_cell, "1")
    doc.recompute()
    if os.path.exists(out):
        os.remove(out)
    doc.saveAs(out)

    hdr = ("brd", "pre", "board", "button", "preset", "edge", "angle", "vol mm3",
           "bbox mm", "spine_in", "slot", "clr_up", "")
    fmt = "%-3s %-3s %-30s %-6s %-13s %5s %6s %8s %-16s %8s %6s %6s %s"
    print("\n" + fmt % hdr)
    for t in table:
        print(fmt % (t[0], t[1], t[2], t[3], t[4], "%.2f" % t[5], "%.0f" % t[6],
                     "%.1f" % t[7], t[8], "%.3f" % t[9], "%.3f" % t[10],
                     "%.3f" % t[11], t[12]))
    for s in allw:
        print("WARNING", s)
    for s in alle:
        print("ERROR", s)
    print("saved", out)
    if alle:
        raise SystemExit(1)


main()
