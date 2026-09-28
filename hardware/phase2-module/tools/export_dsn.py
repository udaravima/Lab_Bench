"""Export a Specctra DSN of the phase-2 board for Freerouting.

Port of phase1-module/tools/export_dsn.py (2026-09-27). The earlier
zone-free phase-2 export (2026-07-25) sent Freerouting into a 2 h grind
in PolylineTrace.normalize; this one, with every pour replaced by its
priority-cut *filled* outline and the router run as

    xvfb-run -a java -Xss64m -jar freerouting-1.9.0.jar \
        -de wip/p2.dsn -do wip/p2.ses -mp 20 -mt 1 -oit 5

finishes autorouting in ~17 min and optimisation in ~3 min. `-oit 5`
matters: without it the optimiser ran past 25 min and nothing was saved.

Differences from KiCad's stock export, each for a reason:

 1. **Every existing track/via is locked** so it exports as `(type fix)`
    and comes back untouched: the pass-1 copper from route_board.py (Kelvin
    pair, gate fan-out, via arrays) is not the router's to rip up.
 2. **In1/In2 become `(type power)` layers**, and every plane polygon
    (inner planes and F.Cu power pours alike) is replaced by the zone's
    *filled* outline. KiCad exports zone outlines,
    which overlap (In1 PGND vs the AGND pocket, In2 3V3 vs 5V0) because
    priority resolves them only at fill time. Freerouting would read an
    overlap as one conductor serving two nets. The filled outlines are
    already priority-cut and clearance-shrunk, so a via dropped inside one
    really lands on that net.
 3. **B.Cu ground pours are dropped** from the export: they are
    fill-around copper, and as conduction areas they would block the whole
    bottom layer for signals. KiCad refills them around the new tracks.
 4. F.Cu power pours export as their fills, twice: as a plane (so the
    pads inside count as connected) and as an F.Cu keepout. Freerouting
    treats a conduction area on a signal layer as free space for other
    nets, and without the keepout it ran VOUT_INT 17 mm through the PGND
    pour and cut the DISC_SRC source-to-source pour in two with the
    DISC_GATE trace. Pads that sit inside a foreign pour (Q3/Q4 gates,
    U6's gate/source pins) get their via stubs from fanout.py first, so
    the keepout never walls in a pin the router still has to reach.

The board file is never modified.

Usage: python3 export_dsn.py [out.dsn] [board.kicad_pcb]
"""
import os
import re
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "phase2-module.kicad_pcb")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "wip", "p2.dsn")


def um(v):
    return round(pcbnew.ToMM(v) * 1000, 1)


def main():
    board = pcbnew.LoadBoard(BOARD)
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    planes = []
    for z in board.Zones():
        lname = board.GetLayerName(z.GetLayer())
        if lname not in ("F.Cu", "In1.Cu", "In2.Cu"):
            continue
        polys = z.GetFilledPolysList(z.GetLayer())
        for i in range(polys.OutlineCount()):
            ol = polys.Outline(i)
            pts = [ol.CPoint(j) for j in range(ol.PointCount())]
            pts.append(pts[0])
            coords = " ".join(f"{um(p.x)} {-um(p.y)}" for p in pts)
            planes.append(f'    (plane "{z.GetNetname()}" (polygon {lname} 0 {coords}))')
            if lname == "F.Cu":
                planes.append(f'    (keepout "" (polygon F.Cu 0 {coords}))')

    for t in board.GetTracks():
        t.SetLocked(True)
    tmp = OUT + ".tmp"
    if not pcbnew.ExportSpecctraDSN(board, tmp):
        sys.exit("ExportSpecctraDSN failed")
    text = open(tmp).read()
    os.remove(tmp)

    # drop every stock (plane ...); the filled outlines replace them
    text = re.sub(r"    \(plane [^\n]*\(polygon (?:[^()]|\n)*?\)\)\n", "", text)
    at = text.index("\n    (via ")
    text = text[:at] + "\n" + "\n".join(planes) + text[at:]
    for lname in ("In1.Cu", "In2.Cu"):
        text = text.replace(f"(layer {lname}\n      (type signal)",
                            f"(layer {lname}\n      (type power)")
    open(OUT, "w").write(text)
    print(f"export_dsn: {len(planes)} filled plane outlines -> {os.path.relpath(OUT, HERE)}")


if __name__ == "__main__":
    main()
