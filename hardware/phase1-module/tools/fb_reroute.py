"""Re-route Phase-1's VOUT_INT FB sense run >= 5.5 mm from every SW copper item.

    python3 fb_reroute.py        # after finish_routes.py, before silk/planes

Freerouting has no spacing rule between two particular nets, and on the
100 x 80 board it ran the FB run 0.25 mm past the SW island. This rips the
run between the R1/R25 island and the output side (VOUT_INT signal tracks
between x 43.2 and 65 mm, plus two of its vias), puts a keep-out of SW
copper grown by 5.5 mm on every routing layer, and lets finish_routes'
A* router join the two islands again. Check the result with run_drc.py.
The rip list is specific to the committed routing; re-check it if the
board is re-routed.
"""
import sys
sys.path.insert(0, ".")
import pcbnew
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
import finish_routes as fr

KEEP = 5.5
BOARD = "../phase1-module.kicad_pcb"
mm = pcbnew.ToMM
board = pcbnew.LoadBoard(BOARD)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
G = []
# 1. rip the FB run between the output pour and the R1/R25 island
for t in list(board.GetTracks()):
    if t.GetNetname() != "VOUT_INT":
        continue
    if isinstance(t, pcbnew.PCB_VIA):
        x, y = mm(t.GetPosition().x) - 20, mm(t.GetPosition().y) - 20
        if (round(x, 2), round(y, 2)) in {(48.42, 42.13), (46.42, 41.08)}:
            board.Remove(t); G.append(t)
        continue
    if mm(t.GetWidth()) >= 1:
        continue
    xs = [mm(p.x) - 20 for p in (t.GetStart(), t.GetEnd())]
    if min(xs) >= 43.2 and max(xs) <= 65.0:
        board.Remove(t); G.append(t)
print("ripped", len(G))
# 2. SW keep-out geometry (page mm), every copper layer
sw = []
for t in board.GetTracks():
    if t.GetNetname() == "SW":
        if isinstance(t, pcbnew.PCB_VIA):
            sw.append(Point(mm(t.GetPosition().x), mm(t.GetPosition().y)).buffer(mm(t.GetWidth()) / 2))
        else:
            sw.append(LineString([(mm(t.GetStart().x), mm(t.GetStart().y)),
                                  (mm(t.GetEnd().x), mm(t.GetEnd().y))]).buffer(mm(t.GetWidth()) / 2))
for fp in board.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname() == "SW":
            sw += fr.sps_polys(p.GetEffectivePolygon())
for z in board.Zones():
    if z.GetNetname() == "SW":
        sw += fr.sps_polys(z.GetFilledPolysList(z.GetLayer()))
keep = unary_union(sw).buffer(KEEP - 0.2)   # route() adds clearance + half width

class Cu(fr.Copper):
    def __init__(self, b, base_keys=None):
        super().__init__(b, base_keys)
        for L in fr.ROUTE_LAYERS:
            self.items.append(("<sw keep-out>", L, keep, "pad", None))

cu = Cu(board)
isl = cu.islands("VOUT_INT")
isl.sort(key=len, reverse=True)
print("islands", [len(i) for i in isl])
assert len(isl) == 2
bb = board.GetBoardEdgesBoundingBox()
bbx = (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()))
fr.WINDOW = 40
res, _ = fr.route(cu, "VOUT_INT", isl[1], isl[0], bbx)
assert res, "no path"
nets = {ni.GetNetname(): ni.GetNetCode() for ni in board.GetNetsByName().values()}
fr.commit(board, nets, "VOUT_INT", res)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
fr.tidy(board, set())
board.Save(BOARD)
print("routed:", res)
