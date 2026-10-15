# Edge clamp button clip

A printed clip that holds
two Adafruit P75-B1 needle pogo pins (product 2430, 1.0 mm barrel) on the pads of one SMD tact switch.
An arm runs from the head (the part over the switch) to the nearest board edge,
drops down a spine and hooks under the board with a lower jaw. The pogo preload
pushes the head up, the jaw pulls it down, so the clip stays put. An optional M2
screw through the jaw can be snugged up against the board bottom.

Rebuild headless from the repo root (also runs all checks and writes the STLs):

    freecadcmd freecad/edge_clamp/build_edge_clamp.py
    freecadcmd freecad/common/export_3mf.py

Files: `freecad/edge_clamp/edge_clamp.FCStd` (saved with board = 1),
`freecad/edge_clamp/stl/edge_clamp_<board>_<button>.stl` for each Boards row and
`edge_clamp_<preset>.stl` for each preset with board = 0. The STLs are build output
(not committed); `export_3mf.py` turns them into `3mf/edge_clamp/*.3mf`.

## Picking a board or preset

Open the `Params` sheet:

- `board` = N uses data row N of the `Boards` sheet (switch preset, edge distance and
  edge angle all come from that row).
- `board` = 0 uses `preset_manual` (1..8, see the note next to it) plus
  `edge_dist_manual` and `edge_angle_manual`.

Recompute after editing. Bottom side switches need nothing special: the clip is
modeled in the switch frame and the boards.csv angles are already mirrored into it.

## Parameters added for the clamp

| alias | default | meaning |
|---|---|---|
| board_t | 1.6 | PCB thickness |
| slot_clear | 0.15 | min gap between clip and PCB top at the edge (checked, not geometry) |
| arm_t | 3.0 | arm thickness |
| arm_z0 | =roof_z0 | arm underside, level with the head roof underside |
| arm_lift | 0 | raise the arm to clear taller parts between switch and edge |
| edge_gap | 0.3 | board edge to spine inner face |
| spine_t | 2.0 | spine thickness |
| jaw_len | 5.0 | how far the lower jaw reaches under the board |
| jaw_t | 2.0 | lower jaw thickness |
| jaw_squeeze | 0.1 | jaw top sits this far above the PCB bottom, so it grips |
| screw_d | 1.8 | M2 tapping hole through the jaw, 0 = none |
| screw_off | =jaw_len - 2 | screw axis distance back from the spine inner face |
| arm_w | =clip_w | arm, spine and jaw width |

Derived rows (edge_in, arm_len, arm_zb, arm_zt, jaw_top, jaw_bot, screw_x, screw_r,
screw_z) are formulas; edit the inputs above instead.

Headers: a Feather with male headers soldered pin-down has header plastic along the
long edges on the bottom side, 0 to about 2.5 mm in from the edge. The lower jaw sits
in that zone. Clamp a short edge, a board without headers, or cut `jaw_len` down to
about 1 and rely on a different hold. With `jaw_len` under about 3.5 there is no room
for the screw under the board, so set `screw_d` to 0 (the build warns about this).

## Printing

Print it on its side (arm width vertical). Each layer then holds the whole C shape of
arm, spine and jaw, so the jaw flexes along the layers instead of peeling them apart at
the spine. The bores then print horizontal; print the bore coupon the same way and
tune `bore_d` from it.

Roof down gives the roundest vertical bores, but the jaw then bends across layer lines
and tends to snap at the spine. Use it only with a short jaw and the screw.

## Pogo pins and wiring

The pins are Adafruit P75-B1 needle pogo pins (product 2430, 1.0 mm barrel).
Print `3mf/bore_coupon.3mf` (model: `freecad/coupon/bore_coupon.FCStd`) first and set
`bore_d` to the hole that holds the barrel snugly. Push each pin in from below (the pocket side) until the solder cup sits in the
wire slot at the top of the roof. Solder a thin wire to each cup and lay it out along
its slot to the head end. The two wires go to the output of the optocoupler or PhotoMOS
relay, which then shorts the switch pads.
