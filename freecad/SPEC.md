# Button clip: shared spec for both designs

Two FreeCAD designs that hold two pogo pins onto the pads of one SMD tact switch,
so a HIL controller can short the switch through an optocoupler or PhotoMOS relay.

- `freecad/edge_clamp/`  arm clamps onto the PCB edge (works on every board, incl. QT Py and ItsyBitsy)
- `freecad/hole_mount/`  arm bolts through a board mounting hole (Feather M2.5 x 10, Metro M3 x 10, nut underneath)

Both share the same **head** (the part that sits on the switch) and the same
spreadsheet layout, so a preset tuned on one works on the other.

## Coordinates

Switch-local frame, origin at the footprint center on the PCB top surface (z = 0).
+X along the switch long axis (the axis the two pad pairs sit on), +Z up away from the board.
This matches the Eagle package frame before element rotation.

## Spreadsheet layout (every .FCStd)

Sheet `Presets` : one column per switch preset, one row per parameter (row 1 = preset name,
row 2 = example boards). Values in mm.

Sheet `Params` : column A = name, column B = active value (alias = name), column C = note.
- `preset` (integer, B2) picks the preset column. Every switch parameter in `Params`
  is a ternary `=preset == 1 ? Presets.B5 : (preset == 2 ? Presets.C5 : ...)`.
- Fit, pin and clamp parameters are plain values in `Params`, not per preset.
- All geometry is Part workbench primitives (Box, Cylinder) + Cut/Fusion whose dimensions and
  placements are expressions on `Params` aliases. Editing a cell and recomputing must regenerate
  the part. No hard-coded numbers in geometry.

### Switch preset rows (Presets sheet)

| alias | meaning |
|---|---|
| body_l | switch body length along X (housing, excl. terminals) |
| body_w | switch body width along Y |
| body_h | housing height above PCB (top of body, excl. plunger) |
| plunger_d | plunger diameter (or the side of a square plunger) |
| plunger_h | top of plunger above PCB (free, unpressed) |
| pad_x | pad center X (abs) from footprint |
| pad_y | pad center Y (abs) |
| pad_lx | pad size along X |
| pad_ly | pad size along Y |
| c1_x, c1_y | contact target 1 (where pogo tip lands), switch frame |
| c2_x, c2_y | contact target 2 |
| side_actuated | 0 top plunger, 1 right-angle (plunger points -Y) |

### Common Params rows

| alias | default | meaning |
|---|---|---|
| fit_clear | 0.15 | pocket clearance per side around body |
| wall_t | 1.2 | pocket wall thickness |
| roof_t | 2.0 | head roof thickness above body top |
| window_clear | 0.6 | extra radius of the plunger window over plunger_d/2 |
| pin_barrel_d | 1.0 | pogo barrel diameter (Adafruit P75-B1 needle pin, product 2430) |
| bore_d | 1.10 | printed bore for the barrel, tune with coupon |
| bore_len | 6.0 | min bore length for alignment |
| pin_len | 16.5 | uncompressed pin length (P75-H2 16.5, P75-B1 16.0) |
| pin_preload | 1.0 | how far below the pad surface the free tip would reach |
| wire_slot_w | 1.6 | slot for solder cup + wire at top of bore |
| clip_w | 8.0 | head/arm width |

As built (clipkit.py), these differ from the table above: `window_clear` 0.4, roof thickness is
`head_t` 6.0 (it is also the bore length), `side_actuated` is not a row (plunger_d = 0 means side
actuated, no window). Extra rows: `roof_gap` 0.2, `rail_z0` 1.15, `end_z0` 1.05 (from the Feather RP2040 fit check), `notch_clear` 0.25,
`wire_slot_d` 2.0, and derived `pocket_hl`, `pocket_hw`, `roof_z0`, `roof_z1`, `head_x0..y1`.

Pocket rule: side rails register the body in Y (down to `rail_z0`). End walls register it in X
but stop at `end_z0` so they clear the gull-wing terminals and solder. Every wall is notched
around both pogo axes so the tips reach the pad ends beyond the body.
The plunger window is a through hole so the clip never presses the switch.

Contact rule: the two pads that share a Y row are tied inside the switch (KMR2 and EVQ-Q2
datasheets), so the pogo pins land diagonally: (+X, +Y pad) and (-X, -Y pad).

## Presets (from Adafruit Eagle libraries in adafruit/MBAdafruitBoards + datasheets)

Filled in by `freecad/presets.csv`; see that file for sources.

## Deliverables per design

- `freecad/<design>/<design>.FCStd`      parametric model, opens in FreeCAD 1.1
- `freecad/<design>/build_<design>.py`   headless generator (freecadcmd), regenerates the FCStd
- `freecad/<design>/stl/<design>_<preset>.stl`   one STL per preset and board row (build output, not committed)
- `3mf/<design>/<design>_<preset>.3mf`   printable 3MF, written by `freecad/common/export_3mf.py`
- `freecad/coupon/bore_coupon.FCStd` + `3mf/bore_coupon.3mf`: bore sizes 0.95 to 1.40 step 0.05
