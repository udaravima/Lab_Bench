"""Export a Specctra DSN of the manager board for Freerouting.

Same approach as phase1-module/tools/export_dsn.py, adapted to two layers:

 1. **Existing copper is locked** and exports as `(type fix)`: the USB and
    CAN pairs and buck copper from route_critical.py are not the router's
    to rip up.
 2. **B.Cu PGND stays a `(plane ...)`** (KiCad's stock export). On a signal
    layer Freerouting treats a conduction area as free space for other
    nets, and pads/vias touching it as connected to PGND, which is what a
    ground pour that refills around tracks is. finish_routes.py and
    stitch.py re-join any islands the routed B.Cu jumpers carve out.
 3. **The F.Cu PGND pour is dropped**: it is fill-around copper; exported,
    it would read as a second conduction area on the signal layer. Any
    other F.Cu pour (none today) would export as its fill, as a plane.
 4. **Net classes**: power nets get wider tracks than the 0.2 mm default.
 5. **Keepouts Freerouting cannot infer**: a ring round each fiducial
    (KiCad gives fiducials a 0.5 mm local clearance; the DSN carries only
    the 1 mm pad) and a band inside the board edge (KiCad's edge clearance
    is 0.5 mm; Freerouting only keeps the 0.2 mm track clearance).

The board file is never modified.

Usage: python3 export_dsn.py [out.dsn] [board.kicad_pcb]
"""
import os
import re
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "phase3-manager.kicad_pcb")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "wip", "mgr.dsn")

# width in um; nets not listed keep the 200 um default
FID_KEEPOUT_UM = 2600     # diameter: 1 mm pad + 0.5 mm clearance + track margin
EDGE_KEEPOUT_UM = 600

CLASSES = {
    "vbus": (600, ["VBUS", "VBUS_F", "SW_AUX"]),
    "rail": (400, ["3V3", "5V0", "PGND"]),
}


def um(v):
    return round(pcbnew.ToMM(v) * 1000, 1)


def main():
    board = pcbnew.LoadBoard(BOARD)
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    planes = []
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetLayer() != pcbnew.F_Cu or z.GetNetname() == "PGND":
            continue
        polys = z.GetFilledPolysList(z.GetLayer())
        for i in range(polys.OutlineCount()):
            ol = polys.Outline(i)
            pts = [ol.CPoint(j) for j in range(ol.PointCount())]
            pts.append(pts[0])
            coords = " ".join(f"{um(p.x)} {-um(p.y)}" for p in pts)
            planes.append(f'    (plane "{z.GetNetname()}" (polygon F.Cu 0 {coords}))')

    for fp in board.GetFootprints():
        if fp.GetReference().startswith("FID"):
            x, y = um(fp.GetPosition().x), -um(fp.GetPosition().y)
            for lname in ("F.Cu", "B.Cu"):
                planes.append(f'    (keepout "" (circle {lname} {FID_KEEPOUT_UM} {x} {y}))')
    bb = board.GetBoardEdgesBoundingBox()
    x1, y1, x2, y2 = um(bb.GetLeft()), -um(bb.GetTop()), um(bb.GetRight()), -um(bb.GetBottom())
    e = EDGE_KEEPOUT_UM
    for lname in ("F.Cu", "B.Cu"):
        for rx1, ry1, rx2, ry2 in ((x1, y1, x2, y1 - e), (x1, y2 + e, x2, y2),
                                   (x1, y1, x1 + e, y2), (x2 - e, y1, x2, y2)):
            planes.append(f'    (keepout "" (rect {lname} {rx1} {ry1} {rx2} {ry2}))')

    for t in board.GetTracks():
        t.SetLocked(True)
    tmp = OUT + ".tmp"
    if not pcbnew.ExportSpecctraDSN(board, tmp):
        sys.exit("ExportSpecctraDSN failed")
    text = open(tmp).read()
    os.remove(tmp)

    # drop every stock F.Cu plane (PGND pour, 5V0 outline); keep B.Cu PGND
    text = re.sub(r"    \(plane [^\n]*\(polygon F\.Cu (?:[^()]|\n)*?\)\)\n", "", text)
    at = text.index("\n    (via ")
    text = text[:at] + "\n" + "\n".join(planes) + text[at:]

    # pull the listed nets out of kicad_default into their own classes
    m = re.search(r'\(class kicad_default ""(.*?)\n      \(circuit', text, re.S)
    names = m.group(1).split()
    moved = {n for _, nets in CLASSES.values() for n in nets}
    missing = moved - set(names)
    if missing:
        sys.exit(f"nets not in kicad_default: {sorted(missing)}")
    keep = " ".join(n for n in names if n not in moved)
    text = text[:m.start(1)] + " " + keep + text[m.end(1):]
    via = re.search(r"\(circuit\s*\(use_via [^)]*\)\s*\)", text[m.start():]).group(0)
    extra = []
    for name, (w, nets) in CLASSES.items():
        extra.append(f'    (class {name} {" ".join(nets)}\n      {via}\n'
                     f'      (rule\n        (width {w})\n        (clearance 200.1)\n      )\n    )')
    # insert after the kicad_default class block closes
    close = text.index("\n    )", text.index("(class kicad_default")) + len("\n    )")
    text = text[:close] + "\n" + "\n".join(extra) + text[close:]
    open(OUT, "w").write(text)
    print(f"export_dsn: {len(planes)} plane/keepout entries, "
          f"{len(moved)} nets in power classes -> {os.path.relpath(OUT, HERE)}")


if __name__ == "__main__":
    main()
