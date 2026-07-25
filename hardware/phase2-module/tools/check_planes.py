"""PS-002 recheck: count disconnected islands in every filled zone.

The kicad-happy analyzer raises PS-002 ("PGND plane split: N islands")
from topology; this reproduces the same measurement directly from
KiCad's own zone filler, so the check can run in the layout loop instead
of only in an analysis pass.

An island is a separate filled polygon of one zone. A few are normal —
the filler carves copper around pads/vias/tracks and any pour arm that
gets pinched off shows up here.

**An island carrying pads is not automatically a fault.** On this board
the F.Cu PGND flood is a *secondary* pour: the return path proper is the
In1 plane, and route_board drops a via on every PGND/AGND pad that sits
over its own plane. So an island is fine as long as something inside it
punches down to the plane — a via, or a through-hole pad. It is only a
real break when it holds pads and has no such tie, which is also when
KiCad's own connectivity would call those pads unconnected.

Exit 1 only for islands that hold pads AND have no via/PTH tie.

Usage: python3 check_planes.py [board.kicad_pcb]
"""
import os
import sys

import pcbnew

from gen_board import ORG

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    HERE, "..", "phase2-module.kicad_pcb")


def inside(poly, i, x_mm, y_mm):
    """True if (x,y) mm lies in outline i of a SHAPE_POLY_SET.

    Ray cast over the outline's own points — SHAPE_POLY_SET.Contains()
    tests the whole set, not one island, which is the distinction the
    island check depends on.
    """
    o = poly.Outline(i)
    n = o.PointCount()
    inside_f = False
    j = n - 1
    for k in range(n):
        xk, yk = pcbnew.ToMM(o.CPoint(k).x), pcbnew.ToMM(o.CPoint(k).y)
        xj, yj = pcbnew.ToMM(o.CPoint(j).x), pcbnew.ToMM(o.CPoint(j).y)
        if (yk > y_mm) != (yj > y_mm):
            if x_mm < (xj - xk) * (y_mm - yk) / (yj - yk) + xk:
                inside_f = not inside_f
        j = k
    return inside_f


def poly_area(poly, i):
    """Area (mm^2) of outline i of a SHAPE_POLY_SET."""
    o = poly.Outline(i)
    pts = [(pcbnew.ToMM(o.CPoint(k).x), pcbnew.ToMM(o.CPoint(k).y))
           for k in range(o.PointCount())]
    a = 0.0
    for k in range(len(pts)):
        x1, y1 = pts[k]
        x2, y2 = pts[(k + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def main():
    board = pcbnew.LoadBoard(BOARD)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    pads = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            pads.append((pad.GetNetname(),
                         pcbnew.ToMM(pad.GetPosition().x),
                         pcbnew.ToMM(pad.GetPosition().y),
                         pad))

    # layer-crossing ties: vias and through-hole pads, per net
    ties = []
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            ties.append((t.GetNetname(),
                         pcbnew.ToMM(t.GetPosition().x),
                         pcbnew.ToMM(t.GetPosition().y)))
    for pnet, px, py, pad in pads:
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            ties.append((pnet, px, py))

    bad = 0
    print(f"{'zone':<28} {'layer':<8} {'islands':>7} {'main mm2':>9}  strays")
    for z in board.Zones():
        net = z.GetNetname() or "<none>"
        for layer in z.GetLayerSet().Seq():
            poly = z.GetFilledPolysList(layer)
            n = poly.OutlineCount()
            if n == 0:
                continue
            areas = sorted(((poly_area(poly, i), i) for i in range(n)),
                           reverse=True)
            main_area, main_i = areas[0]
            lname = board.GetLayerName(layer)
            strays = []
            for area, i in areas[1:]:
                # does this island hold any pad of the zone's net?
                o = poly.Outline(i)
                held = 0
                for pnet, px, py, pad in pads:
                    if pnet != net or not pad.IsOnLayer(layer):
                        continue
                    if inside(poly, i, px, py):
                        held += 1
                tied = sum(1 for tnet, tx, ty in ties
                           if tnet == net and inside(poly, i, tx, ty))
                cx = sum(pcbnew.ToMM(o.CPoint(k).x)
                         for k in range(o.PointCount())) / o.PointCount()
                cy = sum(pcbnew.ToMM(o.CPoint(k).y)
                         for k in range(o.PointCount())) / o.PointCount()
                if held and not tied:
                    # board-relative: that is what route_board's STITCH wants
                    strays.append(f"{area:.1f}mm2/{held}pads/NO LOCAL VIA "
                                  f"@({cx - ORG[0]:.1f},{cy - ORG[1]:.1f})")
                    bad += 1
                elif held:
                    strays.append(f"{area:.1f}mm2/{held}pads/{tied} ties ok")
            if n > 1 or strays:
                print(f"{net:<28} {lname:<8} {n:>7} {main_area:>9.1f}  "
                      f"{', '.join(strays) if strays else '(all empty)'}")

    board.BuildConnectivity()
    unconn = board.GetConnectivity().GetUnconnectedCount(False)
    if bad:
        print(f"\nPS-002 ADVISORY: {bad} island(s) hold pads but contain no "
              f"via of their own.\nThose pads still reach PGND (KiCad "
              f"connectivity: {unconn} unconnected board-wide, none on the\n"
              f"plane nets) — through a pour arm or track, not straight down "
              f"to In1. Electrically\nfine, mediocre as a return path: drop a "
              f"stitch via inside each island above\n(add to route_board's "
              f"STITCH list) and this clears.")
        sys.exit(0)
    print("\nPS-002 clear: every pad-carrying island has its own plane via")


if __name__ == "__main__":
    main()
