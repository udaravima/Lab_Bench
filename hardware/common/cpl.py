#!/usr/bin/env python3
"""JLCPCB pick-and-place (CPL) file from a routed board.

    python3 common/cpl.py phase1-module/phase1-module.kicad_pcb   # from hardware/

Writes <board>/bom/<board>-cpl.csv next to bom.py's <board>-jlcpcb.csv,
in JLCPCB's CPL columns: Designator, Mid X, Mid Y, Layer, Rotation.

- Coordinates are the same frame as the gerbers: page mm, Y negated
  (Gerber Y points up), which is what finish_board.py --fab plots with
  the board's aux origin at 0,0. If the aux origin is ever moved, the
  gerbers move with it and this file must too; it refuses to guess.
- Mid X/Y is the body centre: the centre of the F.Fab (or B.Fab) outline
  when the footprint has one, else the pad bounding-box centre, else the
  anchor. KiCad's own position file uses the anchor, which is pin 1 for
  headers and terminal blocks and off-body for some power packages.
- Rotation is KiCad's footprint rotation, unmodified. JLCPCB's library
  parts do not all share KiCad's zero orientation (per part, not per
  package), so check every rotated or polarised part in JLCPCB's
  placement preview before paying; no offset table is applied here
  because a wrong guess is worse than a visible one.
- Skipped: footprints marked exclude-from-position-files, parts whose value
  starts with DNP (bom.py's rule, so CPL and BOM list the same parts), and
  mounting holes / fiducials (refs H*, FID*), which have nothing to place.
"""
import csv
import os
import sys

import pcbnew

mm = pcbnew.ToMM


def centre(fp):
    fab = pcbnew.F_Fab if fp.GetLayer() == pcbnew.F_Cu else pcbnew.B_Fab
    box = None
    for item in fp.GraphicalItems():
        if item.GetLayer() == fab and item.GetClass() in ("FP_SHAPE", "PCB_SHAPE"):
            bb = item.GetBoundingBox()
            if box is None:
                box = bb
            else:
                box.Merge(bb)
    if box is None and len(fp.Pads()):
        box = fp.Pads()[0].GetBoundingBox()
        for p in fp.Pads():
            box.Merge(p.GetBoundingBox())
    return box.GetCenter() if box is not None else fp.GetPosition()


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    aux = board.GetDesignSettings().GetAuxOrigin()
    if aux.x or aux.y:
        sys.exit(f"aux origin is {mm(aux.x)},{mm(aux.y)}, not 0,0: check the gerber frame first")
    rows = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if (ref.startswith(("H", "FID")) or fp.IsExcludedFromPosFiles()
                or fp.GetValue().startswith("DNP")):     # same DNP rule as bom.py
            continue
        c = centre(fp)
        rows.append((ref, f"{mm(c.x):.4f}mm", f"{-mm(c.y):.4f}mm",
                     "Top" if fp.GetLayer() == pcbnew.F_Cu else "Bottom",
                     f"{fp.GetOrientationDegrees() % 360:g}"))
    rows.sort(key=lambda r: (r[0].rstrip("0123456789"), int("0" + r[0][len(r[0].rstrip("0123456789")):])))
    name = os.path.splitext(os.path.basename(path))[0]
    out_dir = os.path.join(os.path.dirname(os.path.abspath(path)), "bom")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{name}-cpl.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        w.writerows(rows)
    print(f"cpl: {len(rows)} parts -> {os.path.relpath(out)}")


if __name__ == "__main__":
    main()
