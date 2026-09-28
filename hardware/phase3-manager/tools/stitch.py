"""Routing pass 4: PGND stitching vias between the F.Cu and B.Cu ground pours.

    python3 stitch.py [board.kicad_pcb]

On a two-layer board every routed track cuts a pour, so the F.Cu ground
ends up as dozens of fragments. KiCad deletes a fragment with no
connection of its own (island removal), and keeps one that touches a pad
but reaches the rest of ground only through that pad's thermal spokes.
A via from each fragment to the B.Cu plane under it fixes both: the
fragment stays, it is tied with a real conductor, and the two pours act
as one ground. Two passes:

  1. one via in every F.Cu fragment big enough to take one -- fragments
     are found with island removal switched off, so the ones KiCad would
     delete are included;
  2. a 5 mm grid over the rest of the board, where both pours are solid.

A via is placed only where a 0.6 mm pad plus a margin sits wholly inside
BOTH layers' PGND fill (the fill already keeps every clearance to foreign
copper), clear of drilled holes, and at least 1 mm from any other via.
"""
import os
import sys

import pcbnew
import shapely
from pcbnew import FromMM
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "phase3-manager.kicad_pcb")
VIA_D, VIA_DRILL = 0.6, 0.3
MARGIN = 0.1          # extra inside the fill, beyond the via's own radius
HOLE_GAP = 0.3        # drill-edge to drill-edge
VIA_PITCH = 1.0       # minimum centre distance to any other via
GRID = 5.0
FINE = 0.25           # search step inside a fragment
mm = pcbnew.ToMM


def polys(sps):
    out = []
    for i in range(sps.OutlineCount()):
        ol = sps.Outline(i)
        pts = [(mm(ol.CPoint(j).x), mm(ol.CPoint(j).y)) for j in range(ol.PointCount())]
        holes = []
        for h in range(sps.HoleCount(i)):
            hl = sps.Hole(i, h)
            holes.append([(mm(hl.CPoint(j).x), mm(hl.CPoint(j).y)) for j in range(hl.PointCount())])
        if len(pts) >= 3:
            out.append(Polygon(pts, holes).buffer(0))
    return out


def fills(board):
    got = {}
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != "PGND":
            continue
        got.setdefault(z.GetLayer(), []).extend(polys(z.GetFilledPolysList(z.GetLayer())))
    return got


def main():
    board = pcbnew.LoadBoard(BOARD)
    pgnd = board.GetNetsByName()["PGND"].GetNetCode()
    zones = [z for z in board.Zones() if not z.GetIsRuleArea()]
    modes = {id(z): z.GetIslandRemovalMode() for z in zones}
    for z in zones:
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    f = fills(board)
    top, bot = f[pcbnew.F_Cu], unary_union(f[pcbnew.B_Cu])

    holes = []
    vias = []
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            p = (mm(t.GetPosition().x), mm(t.GetPosition().y))
            vias.append(p)
            holes.append((p, mm(t.GetDrillValue()) / 2))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetDrillSize().x > 0:
                holes.append(((mm(pad.GetPosition().x), mm(pad.GetPosition().y)),
                              mm(max(pad.GetDrillSize().x, pad.GetDrillSize().y)) / 2))
    hole_zone = unary_union([Point(c).buffer(r + HOLE_GAP + VIA_DRILL / 2) for c, r in holes])
    r = VIA_D / 2 + MARGIN

    def ok(x, y):
        pt = Point(x, y)
        if hole_zone.contains(pt):
            return False
        if any((x - vx) ** 2 + (y - vy) ** 2 < VIA_PITCH ** 2 for vx, vy in vias):
            return False
        disc = pt.buffer(r, 16)
        return bot.contains(disc) and any(p.contains(disc) for p in top)

    added = []

    def place(x, y):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(FromMM(x), FromMM(y)))
        v.SetDrill(FromMM(VIA_DRILL))
        v.SetWidth(FromMM(VIA_D))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNetCode(pgnd)
        board.Add(v)
        vias.append((x, y))
        added.append((x, y))

    # 1. one via per F.Cu fragment that has no via/PTH of its own yet
    frag_done = 0
    for poly in sorted(top, key=lambda p: -p.area):
        if any(poly.contains(Point(v)) for v in vias) or \
                any(poly.contains(Point(c)) for c, _ in holes):
            continue
        inner = poly.buffer(-r)
        if inner.is_empty:
            continue
        x1, y1, x2, y2 = inner.bounds
        cand = []
        y = y1
        while y <= y2:
            x = x1
            while x <= x2:
                if inner.contains(Point(x, y)):
                    cand.append((x, y))
                x += FINE
            y += FINE
        c = inner.centroid
        cand.sort(key=lambda p: (p[0] - c.x) ** 2 + (p[1] - c.y) ** 2)
        for x, y in cand:
            if ok(x, y):
                place(x, y)
                frag_done += 1
                break

    # 2. grid stitching
    bb = board.GetBoardEdgesBoundingBox()
    x0, y0, x1, y1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
    grid_done = 0
    y = y0 + GRID / 2
    while y < y1:
        x = x0 + GRID / 2
        while x < x1:
            best = None
            for dx in (0, 0.5, -0.5, 1.0, -1.0):
                for dy in (0, 0.5, -0.5, 1.0, -1.0):
                    if ok(x + dx, y + dy):
                        best = (x + dx, y + dy)
                        break
                if best:
                    break
            if best:
                place(*best)
                grid_done += 1
            x += GRID
        y += GRID

    for z in zones:
        z.SetIslandRemovalMode(modes[id(z)])
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    board.Save(BOARD)
    print(f"stitch: {frag_done} fragment vias + {grid_done} grid vias; unconnected "
          f"{board.GetConnectivity().GetUnconnectedCount(False)}")


if __name__ == "__main__":
    main()
