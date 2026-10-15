# Hole mount button clip

A printed clip that holds
two Adafruit P75-B1 needle pogo pins (product 2430, 1.0 mm barrel) on the pads of one SMD tact switch.
The head sits over the switch, and an arm runs to the nearest board mounting hole,
where one screw holds it down. Use `freecad/edge_clamp/` for boards without a mount hole.

Regenerate from the repo root:

    freecadcmd freecad/hole_mount/build_hole_mount.py
    freecadcmd freecad/common/export_3mf.py

The first writes `freecad/hole_mount/hole_mount.FCStd` and `freecad/hole_mount/stl/`
(build output, not committed) and prints a validation table. The second writes
`3mf/hole_mount/*.3mf`.

## Picking a board or preset

Open `hole_mount.FCStd`, sheet `Params`:

- `board` = data row of the `Boards` sheet (1 = first board). The preset, hole position
  and hole size come from that row. Saved with board 7 (Feather M4 AirLift SW1).
- `board` = 0 uses `preset_manual` and `hole_dx_manual`, `hole_dy_manual`, `hole_d_manual`.
- `has_hole` shows 0 for QT Py and ItsyBitsy rows. Those still build (with the manual hole
  values) but have no mount hole: use edge_clamp. No STL is exported for them.

Recompute after editing a cell.

## Added params

| alias | default | meaning |
|---|---|---|
| screw_clear | 0.2 | screw hole = hole_d + screw_clear |
| boss_wall | 1.6 | wall around the drill |
| cbore_d | hole_d * 2 + 0.5 | screw head counterbore |
| cbore_depth | 1.5 | counterbore depth from the boss top |
| cbore_wall | 0.8 | wall around the counterbore |
| boss_od | max(hole_d + 2 boss_wall, cbore_d + 2 cbore_wall) | boss diameter |
| boss_z0 | 0 | boss bottom (flat on the PCB) |
| arm_t | 3.0 | arm thickness |
| arm_lift | 0 | arm bottom = roof_z0 + arm_lift |
| arm_w | clip_w | arm width |
| arm_rib | 0 | 1 adds a rib (rib_h 3.0, rib_w 1.2) on top of the arm |

Derived: `hole_dist`, `arm_ang`, `arm_z0`, `arm_z1`, `screw_d`, `tool_top`.

The boss rests on the PCB around the hole. Adafruit mount holes have a copper-free
ring of about hole_d + 1.5. The boss is wider than that, which is fine since PLA is not
conductive, but check it does not sit on a part or a solder joint next to the hole.

Turn on `arm_rib` for long arms (nRF52840 SW1 37 mm, Metro ESP32-S3 SW1 26 mm).

## Screws

- Feather: M2.5 x 10 screw. Metro: M3 x 10 screw.
- The screw goes down through the boss and the board, with a nut underneath.
- One screw is enough: the head pocket registers on the switch body, so the clip
  cannot rotate.

## Bottom-side switches

No special case. The `Boards` vectors are already in the switch frame (mirrored for
bottom switches), so the same part works on the bottom side.

## Printing

Print upside down with the head roof on the bed so the pogo bores and the screw hole
print vertical. With the defaults the arm and boss top is 3 mm below the roof top
(head_t - arm_t), so they need support. Setting `arm_lift` to `head_t - arm_t` makes the
roof, arm and boss tops flush for a support-free print, at the cost of a taller boss and
longer screw (and do not combine that with `arm_rib`, which then sticks above the roof).

## Pogo pins and wiring

- Pins are Adafruit P75-B1 needle pogo pins (product 2430, 1.0 mm barrel). Push them in from below, tip toward the board.
- Size `bore_d` with `3mf/bore_coupon.3mf` (model: `freecad/coupon/bore_coupon.FCStd`) first: pick the bore that holds the barrel snug.
- Solder a wire to each pin's cup. The wire leaves through the slot on the roof top.
- The two pins go to the switch output of an optocoupler or PhotoMOS relay driven by the
  HIL controller.

## Known tight fits

- Feather RP2040 SW3 (RA_MINI, row 2): the hole is 5.1 mm from the switch. The boss lands
  on the switch pads and the counterbore leaves only 0.05 mm next to pogo bore 1.
  Use edge_clamp or a smaller `cbore_d` there.
- Metro Amethyst SW3 (row 20): boss lands on a pad, counterbore 0.65 mm from bore 1.
- Metro Express RESET (row 18) and rows 2, 20: the counterbore notches the head roof.
  That only clears room for the screw head.
