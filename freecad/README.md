# FreeCAD sources

Parametric models for the pogo pin button clip. Two designs share one head:

- `edge_clamp/edge_clamp.FCStd` clamps onto the board edge (any board)
- `hole_mount/hole_mount.FCStd` bolts through a board mounting hole
- `coupon/bore_coupon.FCStd` test coupon for sizing the pogo pin bore

Design notes are in `SPEC.md` and each design's `README.md`.

## Opening a model

Open the `.FCStd` in FreeCAD 1.1. The part is built from Part workbench
primitives driven by expressions, so all edits go through the `Params` sheet.
Change a cell, then Recompute (Ctrl+R).

## Params sheet

- `board`: N picks data row N of the `Boards` sheet (switch preset, edge or hole
  position all come from that row). 0 means manual.
- `preset_manual`: switch preset 1..8 used when `board` = 0 (see the note column).
- `edge_dist_manual`, `edge_angle_manual` (edge clamp) and `hole_dx_manual`,
  `hole_dy_manual`, `hole_d_manual` (hole mount): manual values used when `board` = 0.

Fit parameters you are most likely to tune:

| alias | default | meaning |
|---|---|---|
| bore_d | 1.10 | printed bore for the pogo barrel, size it with the coupon |
| fit_clear | 0.15 | pocket clearance per side around the switch body |
| rail_z0 | 1.15 | side rails stop this far above the PCB |
| end_z0 | 1.05 | end walls stop this far above the PCB |
| arm_lift | 0 | raise the arm to clear taller parts |

## Data files

`presets.csv` (one column per switch preset) and `boards.csv` (one row per board
button) fill the `Presets` and `Boards` sheets when a build script runs. Edit the
CSVs, not the sheets, then rebuild.

## Rebuilding headless

From any directory (paths below are from the repo root):

    freecadcmd freecad/common/build_coupon.py
    freecadcmd freecad/common/build_head_demo.py
    freecadcmd freecad/edge_clamp/build_edge_clamp.py
    freecadcmd freecad/hole_mount/build_hole_mount.py
    freecadcmd freecad/common/export_3mf.py

On macOS `freecadcmd` is in `FreeCAD.app/Contents/Resources/bin/`.

Each build script rewrites its `.FCStd`, runs its checks (exits non-zero on an
error, prints warnings for tight fits) and writes STLs to an `stl/` folder next to
itself. `build_head_demo.py` only exists to make the head STLs (its
`head_demo.FCStd` is not kept). `export_3mf.py` converts all of those STLs into
the `3mf/` tree at the repo root. `3mf/fitted/` comes from a separate board
assembly and is not regenerated here.
