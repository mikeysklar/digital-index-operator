# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
# SPDX-License-Identifier: MIT
"""Hole mount variant of the pogo-pin button clip.

The shared clipkit head sits on the switch; an arm runs from the head center
to the nearest board mounting hole, where a boss sits flat on the PCB and
takes one screw (Feather M2.5, Metro M3).

    freecadcmd hole_mount/build_hole_mount.py

Writes hole_mount/hole_mount.FCStd and hole_mount/stl/*.stl, prints a
validation table and exits non-zero on any error.
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
    next((a for a in sys.argv if a.endswith("build_hole_mount.py")), "x")))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "common"))
import clipkit  # noqa: E402

SAVE_BOARD = 7  # Feather M4 AirLift rev A, SW1

# name, value or formula, note  (appended to Params after the clipkit rows)
HOLE_PARAMS = [
    ("has_hole", None, "1 if the selected board row has a mount hole (board = 0: 1)"),
    ("screw_clear", "0.2", "screw hole = hole_d + screw_clear"),
    ("boss_wall", "1.6", "boss wall around the PCB drill"),
    ("cbore_d", "=hole_d * 2 + 0.5", "screw head counterbore diameter (M2.5 head 4.5, M3 5.5)"),
    ("cbore_depth", "1.5", "counterbore depth from the boss top"),
    ("cbore_wall", "0.8", "min wall around the counterbore"),
    ("boss_od", "=max(hole_d + 2 * boss_wall; cbore_d + 2 * cbore_wall)",
     "boss diameter (big enough for the counterbore)"),
    ("boss_z0", "0", "boss bottom z (0 = flat on the PCB)"),
    ("foot_od", "=hole_d + 1.8", "boss foot diameter where it touches the PCB (clears parts near the hole)"),
    ("foot_h", "0.6", "height of the foot relief ring (0 = full-width boss on the PCB)"),
    ("arm_t", "3.0", "arm thickness"),
    ("arm_lift", "0", "arm bottom = roof_z0 + arm_lift (head_t - arm_t = flush top)"),
    ("arm_w", "=clip_w", "arm width"),
    ("arm_rib", "0", "1 = stiffening rib on top of the arm, 0 = off"),
    ("rib_h", "3.0", "rib height above the arm top"),
    ("rib_w", "1.2", "rib width"),
    ("hole_dist", "=hypot(hole_dx; hole_dy)", "head center to hole center (arm length)"),
    ("arm_ang", "=atan2(hole_dy; hole_dx)", "arm direction about Z"),
    ("arm_z0", "=roof_z0 + arm_lift", "arm bottom z"),
    ("arm_z1", "=arm_z0 + arm_t", "arm top z = boss top z"),
    ("screw_d", "=hole_d + screw_clear", "screw clearance hole diameter"),
    ("tool_top", "=max(roof_z1; arm_z1 + rib_h) + 5", "cutters run up to here"),
]


def add_params(params, boards_csv):
    used = params.getUsedCells()
    last = max(int(re.sub(r"[A-Z]+", "", c)) for c in used if c.startswith("A"))
    brows = clipkit._read_csv(boards_csv)
    hcol = brows[0].index("hole_dx")
    flags = ["1" if r[hcol].strip() else "0" for r in brows[1:]]
    rows = []
    for name, val, note in HOLE_PARAMS:
        if name == "has_hole":
            val = "=board > 0 ? %s : 1" % clipkit._ternary("board", flags)
        rows.append((name, val, note))
    for i, (name, val, note) in enumerate(rows):
        r = last + 1 + i
        params.set("A%d" % r, "'" + name)
        params.set("C%d" % r, "'" + note)
        params.setAlias("B%d" % r, name)
    for i, (name, val, note) in enumerate(rows):
        params.set("B%d" % (last + 1 + i), val)
    return [r for r in brows[1:]]


def expr(o, m):
    for k, v in m.items():
        o.setExpression(k, v.replace("$", "Params."))


def build(doc):
    head = clipkit.make_head(doc, "Head")
    # arm: box from the head center along +X, rotated to the hole direction.
    # Placement = R * p + Base, so Base = R * (0, -w/2) to center the width.
    arm = doc.addObject("Part::Box", "Arm")
    expr(arm, {"Length": "$hole_dist", "Width": "$arm_w", "Height": "$arm_t",
               ".Placement.Rotation.Axis.z": "1",
               ".Placement.Rotation.Angle": "$arm_ang",
               ".Placement.Base.x": "$arm_w / 2 * sin($arm_ang)",
               ".Placement.Base.y": "-$arm_w / 2 * cos($arm_ang)",
               ".Placement.Base.z": "$arm_z0"})
    # rib starts inside the arm so arm_rib = 0 leaves it fully buried
    rib = doc.addObject("Part::Box", "Rib")
    expr(rib, {"Length": "$hole_dist", "Width": "$rib_w",
               "Height": "$arm_t + $arm_rib * $rib_h",
               ".Placement.Rotation.Axis.z": "1",
               ".Placement.Rotation.Angle": "$arm_ang",
               ".Placement.Base.x": "$rib_w / 2 * sin($arm_ang)",
               ".Placement.Base.y": "-$rib_w / 2 * cos($arm_ang)",
               ".Placement.Base.z": "$arm_z0"})
    boss = doc.addObject("Part::Cylinder", "Boss")
    expr(boss, {"Radius": "$boss_od / 2", "Height": "$arm_z1 - $boss_z0",
                ".Placement.Base.x": "$hole_dx", ".Placement.Base.y": "$hole_dy",
                ".Placement.Base.z": "$boss_z0"})
    clipkit.finish(doc, head, [arm, rib, boss])

    screw = doc.addObject("Part::Cylinder", "ScrewHole")
    expr(screw, {"Radius": "$screw_d / 2", "Height": "$tool_top + 1",
                 ".Placement.Base.x": "$hole_dx", ".Placement.Base.y": "$hole_dy",
                 ".Placement.Base.z": "-1"})
    cbore = doc.addObject("Part::Cylinder", "Cbore")
    expr(cbore, {"Radius": "$cbore_d / 2", "Height": "$tool_top - $arm_z1 + $cbore_depth",
                 ".Placement.Base.x": "$hole_dx", ".Placement.Base.y": "$hole_dy",
                 ".Placement.Base.z": "$arm_z1 - $cbore_depth"})
    # keep the boss/arm out of the switch body (same box as the head pocket,
    # which is already empty, so the head itself is unchanged)
    bclr = doc.addObject("Part::Box", "BodyClear")
    expr(bclr, {"Length": "2 * $pocket_hl", "Width": "2 * $pocket_hw",
                "Height": "$roof_z0 + 1",
                ".Placement.Base.x": "-$pocket_hl",
                ".Placement.Base.y": "$body_cy - $pocket_hw",
                ".Placement.Base.z": "-1"})
    # foot relief: ring from boss_z0 up to foot_h, between foot_od and past boss_od,
    # so only a narrow foot sits on the PCB (status LEDs sit ~2.5 mm from Feather holes)
    ring_o = doc.addObject("Part::Cylinder", "FootRingOuter")
    expr(ring_o, {"Radius": "$boss_od / 2 + 1", "Height": "$foot_h + 1",
                  ".Placement.Base.x": "$hole_dx", ".Placement.Base.y": "$hole_dy",
                  ".Placement.Base.z": "$boss_z0 - 1"})
    ring_i = doc.addObject("Part::Cylinder", "FootRingInner")
    expr(ring_i, {"Radius": "$foot_od / 2", "Height": "$foot_h + 3",
                  ".Placement.Base.x": "$hole_dx", ".Placement.Base.y": "$hole_dy",
                  ".Placement.Base.z": "$boss_z0 - 2"})
    foot = doc.addObject("Part::Cut", "FootRelief")
    foot.Base, foot.Tool = ring_o, ring_i
    for o in (ring_o, ring_i):
        o.Visibility = False
    for t in (screw, cbore, bclr, foot):
        clipkit.add_tool(doc, head, t)
    head.Label = "HoleMount"
    return head


def circle_rect_overlap(cx, cy, r, x0, x1, y0, y1):
    dx = max(x0 - cx, 0, cx - x1)
    dy = max(y0 - cy, 0, cy - y1)
    return math.hypot(dx, dy) < r


def sanitize(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def check(doc, head, label):
    """Return (errors, warnings, info dict) for the current recompute."""
    P = doc.Params
    g = lambda a: float(P.get(a))  # noqa: E731  (quantities -> float)
    errs, warns = [], []
    errs += ["%s: %s" % (label, p) for p in clipkit.check_doc(doc)]
    sh = head.Shape
    ok = (not sh.isNull()) and sh.isValid() and len(sh.Solids) == 1 and sh.Volume > 0
    if not ok:
        errs.append("%s: bad shape valid=%s solids=%d vol=%.3f"
                    % (label, sh.isValid(), len(sh.Solids), sh.Volume))
        return errs, warns, None
    hx, hy = g("hole_dx"), g("hole_dy")
    sr = g("screw_d") / 2
    bb = sh.BoundBox
    # screw axis passes fully through: thin probe on the axis hits nothing
    probe = Part.makeCylinder(0.05, bb.ZLength + 10, App.Vector(hx, hy, bb.ZMin - 5))
    v = sh.common(probe).Volume
    if v > 1e-6:
        errs.append("%s: screw axis blocked (%.4f mm3)" % (label, v))
    # and the boss wall surrounds it from boss_z0 up to the counterbore floor
    d = math.hypot(hx, hy) or 1.0
    px, py = hx + hx / d * (sr + 0.3), hy + hy / d * (sr + 0.3)
    z0, z1 = g("boss_z0"), g("arm_z1") - g("cbore_depth")
    wp = Part.makeCylinder(0.05, z1 - z0 - 0.02, App.Vector(px, py, z0 + 0.01))
    if abs(sh.common(wp).Volume - wp.Volume) > 1e-4:
        errs.append("%s: boss wall missing next to the screw hole" % label)
    # no overlap with the switch body box
    body = Part.makeBox(g("body_l"), g("body_w"), g("body_h"),
                        App.Vector(-g("body_l") / 2, g("body_cy") - g("body_w") / 2, 0))
    bv = sh.common(body).Volume
    if bv > 1e-6:
        errs.append("%s: part overlaps switch body box (%.4f mm3)" % (label, bv))
    # soft checks
    br = g("boss_od") / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            if circle_rect_overlap(hx, hy, br, sx * g("pad_x") - g("pad_lx") / 2,
                                   sx * g("pad_x") + g("pad_lx") / 2,
                                   sy * g("pad_y") - g("pad_ly") / 2,
                                   sy * g("pad_y") + g("pad_ly") / 2):
                warns.append("%s: boss footprint lands on a switch pad (%+.2f, %+.2f)"
                             % (label, sx * g("pad_x"), sy * g("pad_y")))
    if circle_rect_overlap(hx, hy, g("cbore_d") / 2, g("head_x0"), g("head_x1"),
                           g("head_y0"), g("head_y1")):
        warns.append("%s: counterbore notches the head roof" % label)
    for i in (1, 2):
        gap = math.hypot(g("c%d_x" % i) - hx, g("c%d_y" % i) - hy) \
            - g("cbore_d") / 2 - g("bore_d") / 2
        if gap < 0.8:
            warns.append("%s: pogo bore %d only %.2f mm from the counterbore" % (label, i, gap))
    info = dict(vol=sh.Volume, bb=bb, dist=g("hole_dist"), hole_d=g("hole_d"),
                has_hole=int(g("has_hole")), preset=int(g("preset")))
    return errs, warns, info


def main():
    out = os.path.join(HERE, "hole_mount.FCStd")
    stl_dir = os.path.join(HERE, "stl")
    os.makedirs(stl_dir, exist_ok=True)
    for f in os.listdir(stl_dir):
        if f.endswith(".stl"):
            os.remove(os.path.join(stl_dir, f))
    boards_csv = os.path.join(ROOT, "boards.csv")
    doc = App.newDocument("hole_mount")
    presets, boards, params = clipkit.make_sheets(
        doc, os.path.join(ROOT, "presets.csv"), boards_csv)
    brows = add_params(params, boards_csv)
    head = build(doc)
    doc.recompute()

    pnames = {int(presets.get(clipkit._col(c) + "2")): presets.get(clipkit._col(c) + "1")
              for c in range(1, 9)}
    board_cell = params.getCellFromAlias("board")
    pm_cell = params.getCellFromAlias("preset_manual")

    runs = [(n, None) for n in range(1, len(brows) + 1)] + [(0, k) for k in range(1, 9)]
    errors, warnings, table = [], [], []
    for bnum, pk in runs:
        params.set(board_cell, str(bnum))
        if pk is not None:
            params.set(pm_cell, str(pk))
        doc.recompute()
        if bnum:
            bname, ref = brows[bnum - 1][0], brows[bnum - 1][1]
        else:
            bname, ref = "(manual)", "-"
        label = "row %d" % bnum if bnum else "preset %d" % pk
        e, w, info = check(doc, head, label)
        errors += e
        if info is None:
            table.append((bnum, bname, ref, "?", 0, 0, 0, "", "FAILED"))
            continue
        if bnum and not info["has_hole"]:
            status = "no mount hole, use edge_clamp"
        else:
            status = "ok" if bnum else "manual hole (hole_*_manual)"
            warnings += w
            if bnum:
                stl = "hole_mount_%s_%s.stl" % (sanitize(bname), sanitize(ref))
            else:
                stl = "hole_mount_%s.stl" % pnames[pk]
            clipkit.export_stl(head.Shape, os.path.join(stl_dir, stl))
            if w:
                status += " (%d warn)" % len(w)
        bb = info["bb"]
        table.append((bnum, bname, ref, pnames[info["preset"]], info["dist"], info["hole_d"],
                      info["vol"], "%.1fx%.1fx%.1f" % (bb.XLength, bb.YLength, bb.ZLength),
                      status))

    params.set(board_cell, str(SAVE_BOARD))
    params.set(pm_cell, "1")
    doc.recompute()
    errors += ["saved state: %s" % p for p in clipkit.check_doc(doc)]
    if os.path.exists(out):
        os.remove(out)
    doc.saveAs(out)

    print("\n%-3s %-32s %-6s %-13s %6s %6s %8s %-17s %s" % (
        "row", "board", "button", "preset", "dist", "hole_d", "vol mm3", "bbox", "mount"))
    for t in table:
        print("%-3d %-32s %-6s %-13s %6.2f %6.3f %8.1f %-17s %s" % t)
    for w in warnings:
        print("WARNING", w)
    for e in errors:
        print("ERROR", e)
    print("saved", out, "(board %d)" % SAVE_BOARD)
    if errors:
        raise SystemExit(1)


main()
