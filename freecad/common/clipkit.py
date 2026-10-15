# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
# SPDX-License-Identifier: MIT
"""Shared FreeCAD code for the pogo-pin button clip (edge_clamp and hole_mount).

Run under FreeCAD 1.1 (GUI or headless freecadcmd). Callers add this directory
to sys.path and ``import clipkit``.

Frame
-----
All head geometry is in the SWITCH FRAME: origin = footprint center on the PCB
top surface, z = 0 is the PCB top, +X along the pad pairs, +Z away from board.

Spreadsheets  (``make_sheets(doc, presets_csv, boards_csv)``)
------------
``Presets``  verbatim copy of presets.csv: row per parameter, column per preset
             (A = param name, B..I = presets 1..8, last column = note).
             Row 1 = preset names, row 2 = ``index``.
``Boards``   copy of boards.csv (row 2 = board 1, ...) plus a numeric
             ``preset_index`` column resolved from the preset name.
``Params``   A = name, B = value (alias = name), C = note.
             Inputs: ``board`` (0 = manual), ``preset_manual``, ``*_manual``
             placement defaults, and the common fit/pin values.
             ``preset`` (B2) = board > 0 ? Boards preset_index : preset_manual.
             Every switch param is a nested ternary on ``preset`` into Presets;
             placement params (edge_dist, edge_angle, hole_dx, hole_dy, hole_d)
             are nested ternaries on ``board`` with the manual value as the
             fallback (also used for boards that have no mount hole).
             Derived rows (pocket_hl, pocket_hw, roof_z0, roof_z1, head_x0/x1,
             head_y0/y1, wnd_r, wnd_z) are formulas the head geometry uses.

Returns the three sheet objects as a tuple (presets, boards, params).

Head  (``make_head(doc, prefix="Head", extra_solids=None)``)
----
Builds, all driven by Params expressions:
  <prefix>_Roof, _RailP, _RailN (Y registration), _EndP, _EndN (X registration)
  <prefix>_Solid       Part::MultiFuse of the above + extra_solids  (uncut)
  <prefix>_Window, _Bore1, _Bore2, _Notch1, _Notch2, _Cup1, _Cup2,
  _Slot1, _Slot2       cutting tools
  <prefix>_Tools       Part::MultiFuse of the tools
  <prefix>             Part::Cut(<prefix>_Solid, <prefix>_Tools)  -> returned
The returned Cut has ``head.Base`` = the uncut fuse and ``head.Tool`` = tools.

``finish(doc, head, extra_solids)`` adds more solids (e.g. arms, already
placed in the switch frame) to ``head.Base`` so they are fused BEFORE the cuts:
bores, notches, slots and the plunger window also clear the arms.

``add_tool(doc, head, tool)`` adds an extra cutting solid (e.g. a screw hole).

Coupon  (``make_coupon(doc)``)
------
Plate with bores 0.95..1.40 step 0.05, driven by a ``CouponParams`` sheet.
Returns the final Part::Cut.

Expression functions min(), max(), abs() and ``?:`` were verified to evaluate
under freecadcmd 1.1.3.
"""

import csv

import FreeCAD as App

SWITCH_PARAMS = [
    "body_l", "body_w", "body_cy", "body_h", "plunger_d", "plunger_h",
    "pad_x", "pad_y", "pad_lx", "pad_ly", "c1_x", "c1_y", "c2_x", "c2_y",
]

# name, value, note
COMMON_PARAMS = [
    ("fit_clear", 0.15, "pocket clearance per side around body"),
    ("wall_t", 1.2, "pocket wall thickness (rails and end walls)"),
    ("window_clear", 0.4, "extra radius of the plunger window over plunger_d/2"),
    ("pin_barrel_d", 1.0, "P75 pogo barrel diameter (Adafruit 2429/2430)"),
    ("bore_d", 1.10, "printed bore for the barrel, tune with coupon"),
    ("bore_len", 6.0, "min bore length for alignment"),
    ("pin_len", 16.5, "uncompressed pin length (P75-H2 16.5, P75-B1 16.0)"),
    ("pin_preload", 1.0, "how far below the pad surface the free tip would reach"),
    ("clip_w", 8.0, "head/arm width"),
    ("head_t", 6.0, "roof thickness (bore length region)"),
    ("roof_gap", 0.2, "roof underside sits body_h + roof_gap above PCB"),
    ("rail_z0", 1.15, "side rails stop this far above PCB (clears 0805/SOT-23 parts ~1 mm from the switch; Feather RP2040 fit check)"),
    ("end_z0", 1.05, "end walls stop this far above PCB (clears terminals, solder and 1.0 mm tall 0805 parts)"),
    ("notch_clear", 0.25, "wall notch radius over bore_d/2 at each pogo axis"),
    ("wire_slot_w", 1.6, "slot width for solder cup + wire at top of bore"),
    ("wire_slot_d", 2.0, "slot depth from the roof top"),
]

# placement params: name, Boards column header, manual default, note
PLACE_PARAMS = [
    ("edge_dist", "edge_dist", 6.0, "switch center to PCB edge"),
    ("edge_angle", "edge_angle", 90.0, "edge direction in switch frame, deg"),
    ("hole_dx", "hole_dx", 8.0, "mount hole X from switch center"),
    ("hole_dy", "hole_dy", 4.0, "mount hole Y from switch center"),
    ("hole_d", "hole_d", 2.5, "mount hole diameter"),
]

# derived rows used by the head geometry
DERIVED_PARAMS = [
    ("pocket_hl", "=body_l / 2 + fit_clear", "pocket half length (X)"),
    ("pocket_hw", "=body_w / 2 + fit_clear", "pocket half width (Y)"),
    ("roof_z0", "=body_h + roof_gap", "roof underside z"),
    ("roof_z1", "=roof_z0 + head_t", "roof top z"),
    ("head_x0", "=min(-pocket_hl - wall_t; min(c1_x; c2_x) - bore_d / 2 - wall_t)",
     "head min X"),
    ("head_x1", "=max(pocket_hl + wall_t; max(c1_x; c2_x) + bore_d / 2 + wall_t)",
     "head max X"),
    ("head_y0",
     "=min(body_cy - pocket_hw - wall_t; min(c1_y; c2_y) - bore_d / 2 - wall_t)",
     "head min Y"),
    ("head_y1",
     "=max(body_cy + pocket_hw + wall_t; max(c1_y; c2_y) + bore_d / 2 + wall_t)",
     "head max Y"),
    ("wnd_r", "=plunger_d / 2 + window_clear", "plunger window radius"),
    ("wnd_z", "=plunger_d > 0 ? roof_z0 - 1 : roof_z1 + 10",
     "window start z (parked above the head when plunger_d = 0)"),
]


def _col(i):
    """0-based column index -> spreadsheet column letters."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _is_num(v):
    try:
        float(v)
        return True
    except ValueError:
        return False


def _set_cell(sheet, addr, v):
    v = v.strip()
    if v == "":
        return
    if _is_num(v):
        sheet.set(addr, v)
    else:
        sheet.set(addr, "'" + v)


def _read_csv(path):
    with open(path, newline="") as f:
        return [row for row in csv.reader(f)]


def _ternary(sel, refs):
    """sel == 1 ? refs[0] : (sel == 2 ? refs[1] : ... refs[-1]).

    Out-of-range selectors fall through to the last entry."""
    expr = refs[-1]
    for i in range(len(refs) - 1, 0, -1):
        expr = "(%s == %d ? %s : %s)" % (sel, i, refs[i - 1], expr)
    return expr


def make_sheets(doc, presets_csv, boards_csv):
    # ---- Presets: verbatim copy (already row per param, column per preset)
    prows = _read_csv(presets_csv)
    presets = doc.addObject("Spreadsheet::Sheet", "Presets")
    for r, row in enumerate(prows):
        for c, v in enumerate(row):
            _set_cell(presets, "%s%d" % (_col(c), r + 1), v)
    header = prows[0]
    names = [n for n in header[1:] if n and n != "note"]
    prow = {row[0]: r + 1 for r, row in enumerate(prows)}  # param -> sheet row
    idx_row = prows[prow["index"] - 1]
    name_to_idx = {header[c]: int(idx_row[c]) for c in range(1, len(names) + 1)}
    # column letter for preset index k (1-based)
    idx_to_col = {name_to_idx[header[c]]: _col(c) for c in range(1, len(names) + 1)}
    npre = len(names)
    for p in SWITCH_PARAMS:
        if p not in prow:
            raise ValueError("presets.csv missing row %s" % p)

    # ---- Boards: copy + preset_index column
    brows = _read_csv(boards_csv)
    boards = doc.addObject("Spreadsheet::Sheet", "Boards")
    bhdr = brows[0]
    pi_col = _col(len(bhdr))
    for r, row in enumerate(brows):
        for c, v in enumerate(row):
            _set_cell(boards, "%s%d" % (_col(c), r + 1), v)
        if r == 0:
            boards.set("%s1" % pi_col, "'preset_index")
        else:
            pname = row[bhdr.index("preset")].strip()
            if pname not in name_to_idx:
                raise ValueError("boards.csv row %d: unknown preset %r" % (r + 1, pname))
            boards.set("%s%d" % (pi_col, r + 1), str(name_to_idx[pname]))
    nboards = len(brows) - 1
    bcol = {h: _col(c) for c, h in enumerate(bhdr)}

    # ---- Params
    params = doc.addObject("Spreadsheet::Sheet", "Params")
    rows = [("name", None, "note")]

    def add(name, val, note):
        rows.append((name, val, note))

    pref = ["Boards.%s%d" % (pi_col, r + 2) for r in range(nboards)]
    add("preset", "=board > 0 ? %s : preset_manual" % _ternary("board", pref),
        "active preset index (from board, else preset_manual)")
    add("board", "0", "0 = manual; N = data row N of Boards (sheet row N+1)")
    add("preset_manual", "1",
        "preset used when board = 0: " +
        ", ".join("%d %s" % (name_to_idx[n], n) for n in names))
    for p in SWITCH_PARAMS:
        refs = ["Presets.%s%d" % (idx_to_col[k], prow[p]) for k in range(1, npre + 1)]
        note = prows[prow[p] - 1][-1] if len(prows[prow[p] - 1]) > npre + 1 else ""
        add(p, "=" + _ternary("preset", refs), note)
    for name, hcol, default, note in PLACE_PARAMS:
        add(name + "_manual", repr(float(default)), "manual " + name + " (board = 0)")
    for name, hcol, default, note in PLACE_PARAMS:
        refs = []
        for r in range(nboards):
            v = brows[r + 1][bhdr.index(hcol)].strip()
            refs.append("Boards.%s%d" % (bcol[hcol], r + 2) if v else name + "_manual")
        add(name, "=board > 0 ? %s : %s_manual" % (_ternary("board", refs), name),
            note + " (falls back to %s_manual)" % name)
    for name, val, note in COMMON_PARAMS:
        add(name, repr(float(val)), note)
    for name, expr, note in DERIVED_PARAMS:
        add(name, expr, note)

    # write values first, aliases next, formulas last
    for r, (name, val, note) in enumerate(rows):
        params.set("A%d" % (r + 1), "'" + name)
        params.set("C%d" % (r + 1), "'" + note if note else "")
        if r == 0:
            params.set("B1", "'value")
    for r, (name, val, note) in enumerate(rows[1:], start=2):
        params.setAlias("B%d" % r, name)
    for r, (name, val, note) in enumerate(rows[1:], start=2):
        params.set("B%d" % r, val)
    return presets, boards, params


# ----------------------------------------------------------------- geometry

def _expr(obj, mapping):
    for prop, e in mapping.items():
        obj.setExpression(prop, e)


def _box(doc, name, L, W, H, x, y, z):
    o = doc.addObject("Part::Box", name)
    _expr(o, {"Length": L, "Width": W, "Height": H,
              ".Placement.Base.x": x, ".Placement.Base.y": y, ".Placement.Base.z": z})
    return o


def _cyl(doc, name, r, h, x, y, z):
    o = doc.addObject("Part::Cylinder", name)
    _expr(o, {"Radius": r, "Height": h,
              ".Placement.Base.x": x, ".Placement.Base.y": y, ".Placement.Base.z": z})
    return o


def _hide(objs):
    for o in objs:
        o.Visibility = False  # App-side flag, survives headless save
        if getattr(o, "ViewObject", None) is not None:
            o.ViewObject.Visibility = False


def make_head(doc, prefix="Head", extra_solids=None):
    P = "Params."
    p = lambda s: s.replace("$", P)  # noqa: E731  "$body_l" -> "Params.body_l"

    roof = _box(doc, prefix + "_Roof",
                p("$head_x1 - $head_x0"), p("$head_y1 - $head_y0"), p("$head_t"),
                p("$head_x0"), p("$head_y0"), p("$roof_z0"))
    rail_len = p("2 * ($pocket_hl + $wall_t)")
    rail_h = p("$roof_z1 - $rail_z0")
    rail_p = _box(doc, prefix + "_RailP", rail_len, p("$wall_t"), rail_h,
                  p("-$pocket_hl - $wall_t"), p("$body_cy + $pocket_hw"), p("$rail_z0"))
    rail_n = _box(doc, prefix + "_RailN", rail_len, p("$wall_t"), rail_h,
                  p("-$pocket_hl - $wall_t"), p("$body_cy - $pocket_hw - $wall_t"),
                  p("$rail_z0"))
    end_w = p("2 * ($pocket_hw + $wall_t)")
    end_h = p("$roof_z1 - $end_z0")
    end_p = _box(doc, prefix + "_EndP", p("$wall_t"), end_w, end_h,
                 p("$pocket_hl"), p("$body_cy - $pocket_hw - $wall_t"), p("$end_z0"))
    end_n = _box(doc, prefix + "_EndN", p("$wall_t"), end_w, end_h,
                 p("-$pocket_hl - $wall_t"), p("$body_cy - $pocket_hw - $wall_t"),
                 p("$end_z0"))
    solids = [roof, rail_p, rail_n, end_p, end_n] + list(extra_solids or [])
    fuse = doc.addObject("Part::MultiFuse", prefix + "_Solid")
    fuse.Shapes = solids

    tools = [_cyl(doc, prefix + "_Window", p("$wnd_r"), p("$head_t + 2"),
                  "0", "0", p("$wnd_z"))]
    for i in (1, 2):
        cx, cy = p("$c%d_x" % i), p("$c%d_y" % i)
        tools.append(_cyl(doc, "%s_Bore%d" % (prefix, i), p("$bore_d / 2"),
                          p("$roof_z1 + 2"), cx, cy, "-1"))
        tools.append(_cyl(doc, "%s_Notch%d" % (prefix, i),
                          p("$bore_d / 2 + $notch_clear"), p("$roof_z0 + 1"),
                          cx, cy, "-1"))
        tools.append(_cyl(doc, "%s_Cup%d" % (prefix, i), p("$wire_slot_w / 2"),
                          p("$wire_slot_d + 1"), cx, cy,
                          p("$roof_z1 - $wire_slot_d")))
        # slot from the bore axis outward along X to past the head end
        c = "Params.c%d_x" % i
        tools.append(_box(
            doc, "%s_Slot%d" % (prefix, i),
            "%s >= 0 ? Params.head_x1 - %s + 1 : %s - Params.head_x0 + 1" % (c, c, c),
            p("$wire_slot_w"), p("$wire_slot_d + 1"),
            "%s >= 0 ? %s : Params.head_x0 - 1" % (c, c),
            p("$c%d_y - $wire_slot_w / 2" % i), p("$roof_z1 - $wire_slot_d")))
    tfuse = doc.addObject("Part::MultiFuse", prefix + "_Tools")
    tfuse.Shapes = tools

    head = doc.addObject("Part::Cut", prefix)
    head.Base = fuse
    head.Tool = tfuse
    _hide(solids + tools + [fuse, tfuse])
    return head


def finish(doc, head, extra_solids):
    """Fuse extra solids into head.Base so the head cuts also apply to them."""
    head.Base.Shapes = list(head.Base.Shapes) + list(extra_solids)
    _hide(extra_solids)
    return head


def add_tool(doc, head, tool):
    """Add one more cutting solid to the head's tool fuse."""
    head.Tool.Shapes = list(head.Tool.Shapes) + [tool]
    _hide([tool])
    return head


# ------------------------------------------------------------------- coupon

COUPON_PARAMS = [
    ("bore_start", 0.95, "first bore diameter"),
    ("bore_step", 0.05, "diameter step"),
    ("n_bores", 10, "number of bores (geometry is built for 10)"),
    ("pitch", 4.0, "bore spacing"),
    ("plate_t", 6.0, "plate thickness = bore depth (through)"),
    ("plate_w", 8.0, "plate width (Y)"),
    ("margin", 3.0, "plate margin past first/last bore"),
    ("notch_w", 0.8, "index notch width"),
    ("notch_short", 0.6, "notch depth for x.x5 bores"),
    ("notch_long", 1.5, "notch depth for x.x0 bores"),
    ("mark_w", 2.0, "corner cut marking the 0.95 end"),
]


def make_coupon(doc, n=10):
    sh = doc.addObject("Spreadsheet::Sheet", "CouponParams")
    sh.set("A1", "'name"); sh.set("B1", "'value"); sh.set("C1", "'note")
    for r, (name, v, note) in enumerate(COUPON_PARAMS, start=2):
        sh.set("A%d" % r, "'" + name)
        sh.set("B%d" % r, repr(v))
        sh.setAlias("B%d" % r, name)
        sh.set("C%d" % r, "'" + note)
    C = lambda s: s.replace("$", "CouponParams.")  # noqa: E731
    plate = _box(doc, "Coupon_Plate", C("2 * $margin + ($n_bores - 1) * $pitch"),
                 C("$plate_w"), C("$plate_t"), C("-$margin"), "0", "0")
    tools = []
    for i in range(n):
        x = C("%d * $pitch" % i)
        tools.append(_cyl(doc, "Coupon_Bore%02d" % i,
                          C("($bore_start + %d * $bore_step) / 2" % i),
                          C("$plate_t + 2"), x, C("$plate_w / 2"), "-1"))
        d = round(0.95 + 0.05 * i, 2)
        depth = "$notch_long" if abs(round(d * 100) % 10) < 1e-6 else "$notch_short"
        tools.append(_box(doc, "Coupon_Notch%02d" % i, C("$notch_w"), C(depth),
                          C("$plate_t + 2"), C("%s - $notch_w / 2" % x),
                          "-1", "-1"))
        tools[-1].setExpression("Width", C(depth + " + 1"))
    tools.append(_box(doc, "Coupon_Mark", C("$mark_w + 1"), C("$mark_w + 1"),
                      C("$plate_t + 2"), C("-$margin - 1"),
                      C("$plate_w - $mark_w"), "-1"))
    tf = doc.addObject("Part::MultiFuse", "Coupon_Tools")
    tf.Shapes = tools
    cut = doc.addObject("Part::Cut", "Coupon")
    cut.Base = plate
    cut.Tool = tf
    _hide(tools + [plate, tf])
    return cut


# ------------------------------------------------------------------ helpers

def check_doc(doc):
    """Return a list of problem strings (invalid objects, sheet cell errors)."""
    probs = []
    for o in doc.Objects:
        st = list(o.State)
        if "Invalid" in st or "Error" in st or not o.isValid():
            probs.append("%s: state %s" % (o.Name, st))
        if o.TypeId == "Spreadsheet::Sheet":
            for c in o.getUsedCells():
                v = o.get(c)
                if isinstance(v, str) and v.startswith("ERR"):
                    probs.append("%s.%s: %s" % (o.Name, c, v))
    return probs


def export_stl(shape, path, lin=0.01, ang=0.1):
    import Mesh
    import MeshPart
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=lin,
                               AngularDeflection=ang, Relative=False)
    Mesh.Mesh(m).write(path)
