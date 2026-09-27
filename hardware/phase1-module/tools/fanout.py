"""Routing pass 1b: plane-pin fan-out with exact clearance geometry.

Run after route_board.py and before export_dsn.py / Freerouting:
    python3 fanout.py [board.kicad_pcb]

route_board's pad-via pass tries three spots per pad and rejects them
with a coarse `too_close()` (0.85 mm + the neighbour pad's *largest*
half-size). On the fine-pitch parts that rejects every spot, so U10's
3V3/AGND pins, U1, U2, U11 and U7 were left with no path to their plane
-- and Freerouting, handed those pins as ordinary connections, could not
escape them either: they were most of its 41 leftovers.

This pass does the escape the way a layout engineer would, before the
signal router runs: for every SMD pad on a plane net (PGND, AGND, 3V3,
5V0) that has no copper yet, try stub+via candidates in order of length
-- along the pad's long axis outward, then inward (a via under an LQFP
body is ordinary practice), then the other axis and the diagonals --
and take the first that passes an exact Shapely clearance check against
every foreign pad, track, via, hole and F.Cu power fill. The via must
land inside the pad's own plane fill (In1 for PGND/AGND, In2 for
3V3/5V0), well clear of the fill edge, so it can never bridge the
PGND/AGND seam. When no via fits, a pad may instead strap to an
adjacent same-net pad that already has one (U10 pins 20/21).
"""
import math
import os
import sys

import pcbnew
from pcbnew import FromMM
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "phase1-module.kicad_pcb")

PLANE_NETS = {"PGND": pcbnew.In1_Cu, "AGND": pcbnew.In1_Cu,
              "3V3": pcbnew.In2_Cu, "5V0": pcbnew.In2_Cu}
VIA_D, VIA_DRILL = 0.6, 0.3
STUB_W = 0.25
CLEAR = 0.22          # netclass 0.2 + margin
HOLE_GAP = 0.3        # hole-to-hole edge (rule 0.25)
PLANE_MARGIN = 0.45   # via centre inside its plane fill by at least this
EDGE = 0.8
LANE = 1.0            # escape lane kept clear past each fine-pitch pin's tip

# Placement nudges (mm), applied before fan-out. The committed board's
# placement no longer regenerates from gen_board.py (its courtyard check
# now fails on L1/C23), so these small moves live here, with the reason:
NUDGES = {
    # opens a 0.62 mm F.Cu channel between C25.2 (PS_COMP) and U3's left
    # pin column so U3.5 FB can drop to C26.2; C25's courtyard still
    # clears R5's by 0.04 mm
    "C25": (-0.2, 0.0),
    # R3/R6 sat 0.6 mm off U1's right pin tips, walling in I_REF, DAC_SDI
    # and DAC_NSYNC; 1 mm more room fits the escapes and their vias
    "R3": (1.0, 0.0),
    "R6": (1.0, 0.0),
    # gives U3.8's escape via 0.27 mm to C26.2 (see ESCAPES); C26's
    # courtyard still clears R25's by 0.04 mm
    "C26": (0.0, 0.5),
}

# PTH pads joined to their B.Cu pour solid instead of by thermal spokes.
# J2.5 (SWD header AGND) sits 3.2 mm off the bottom edge with SWCLK and
# SWDIO running under it on B.Cu and NRST beside it, so the AGND pour
# gets one spoke in and DRC flags a starved thermal. The pin is also on
# the In1 AGND plane; a solid B.Cu join on a 1 mm header pin still
# hand-solders fine.
SOLID_PADS = {("J2", "5")}

# Hand-placed signal escapes: (ref, pad, via x, y board-relative mm), a
# straight F.Cu stub from the pad centre to a through via. U3's left pins
# sit over route_board's 0.64 mm LO_G run on B.Cu (x 45.2) and between
# the RT/COMP/FB routes, so no router finds SS and FPWM a way out; the
# spot just left of LO_G is the only via site that clears everything.
# Checked by the same clearance test as the automatic fan-out.
ESCAPES = [
    ("U3", "3", 44.35, 34.75),    # PS_SS
    ("U3", "8", 44.30, 37.45),    # PS_FPWM (dropped 0.2 to leave FB its lane)
]

# Hand routes (net, width, board-relative points): the one connection no
# router closes. U3.5 FB drops through the 0.62 mm channel between C25.2
# and U3's pin tips (x 44.74, 0.21 mm each side), runs left under C25.2
# at y 36.8 (0.225 mm below it, 0.25 mm above U3.8's escape via) and
# rises into C25.1, which is already on the FB node. Checked at the
# 0.2 mm board rule; DRC re-checks it.
HAND_ROUTES = [
    ("FB", 0.2, [(45.35, 35.75), (44.74, 35.75), (44.74, 36.8), (42.43, 36.8), (42.43, 36.3)]),
]
mm = pcbnew.ToMM


def sps_polys(sps):
    out = []
    for i in range(sps.OutlineCount()):
        ol = sps.Outline(i)
        pts = [(mm(ol.CPoint(j).x), mm(ol.CPoint(j).y)) for j in range(ol.PointCount())]
        if len(pts) >= 3:
            out.append(Polygon(pts).buffer(0))
    return out


class Obstacles:
    """Per-layer foreign-copper index: geometry tagged with its net."""
    def __init__(self):
        self.items = {pcbnew.F_Cu: [], pcbnew.B_Cu: []}
        self.holes = []
        self.trees = {}

    def add(self, layer, geom, net, kind="copper"):
        self.items[layer].append((geom, net, kind))
        self.trees.pop(layer, None)

    def clear_of(self, layer, geom, net, clr=CLEAR, pads_only=False, zones=True):
        items = self.items[layer]
        if layer not in self.trees:
            self.trees[layer] = STRtree([g for g, _, _ in items])
        for i in self.trees[layer].query(geom.buffer(clr)):
            g, n, kind = items[i]
            if pads_only and kind != "pad":
                continue
            if not zones and kind == "zone":
                continue
            if n != net and g.distance(geom) < clr:
                return False
        return True

    def hole_ok(self, x, y):
        r = VIA_DRILL / 2
        return all(math.hypot(x - hx, y - hy) >= r + hr + HOLE_GAP
                   for hx, hy, hr in self.holes)


def build(board):
    ob = Obstacles()
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            net = pad.GetNetname() or "<none>"
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                if pad.IsOnLayer(layer):
                    for g in sps_polys(pad.GetEffectivePolygon()):
                        ob.add(layer, g, net, kind="pad")
            if pad.GetDrillSize().x > 0:
                ob.holes.append((mm(pad.GetPosition().x), mm(pad.GetPosition().y),
                                 mm(pad.GetDrillSize().x) / 2))
    for t in board.GetTracks():
        net = t.GetNetname() or "<none>"
        if isinstance(t, pcbnew.PCB_VIA):
            x, y = mm(t.GetPosition().x), mm(t.GetPosition().y)
            c = Point(x, y).buffer(mm(t.GetWidth()) / 2)
            ob.add(pcbnew.F_Cu, c, net)
            ob.add(pcbnew.B_Cu, c, net)
            ob.holes.append((x, y, mm(t.GetDrillValue()) / 2))
        elif t.GetLayer() in ob.items:
            g = LineString([(mm(t.GetStart().x), mm(t.GetStart().y)),
                            (mm(t.GetEnd().x), mm(t.GetEnd().y))]).buffer(mm(t.GetWidth()) / 2)
            ob.add(t.GetLayer(), g, net)
    # F.Cu power pours are real copper; B.Cu pours are fill-around
    for z in board.Zones():
        if z.GetLayer() == pcbnew.F_Cu:
            for g in sps_polys(z.GetFilledPolysList(pcbnew.F_Cu)):
                ob.add(pcbnew.F_Cu, g, z.GetNetname(), kind="zone")
    return ob


def plane_fill(board, net):
    polys = []
    for z in board.Zones():
        if z.GetNetname() == net and z.GetLayer() == PLANE_NETS[net]:
            polys += sps_polys(z.GetFilledPolysList(z.GetLayer()))
    return polys


def nudge(board):
    """Apply NUDGES and SOLID_PADS; refuse any part that already has copper on its pads."""
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    for fp in board.GetFootprints():
        d = NUDGES.get(fp.GetReference())
        if not d:
            continue
        if any(len(conn.GetConnectedTracks(p)) for p in fp.Pads()):
            sys.exit(f"nudge {fp.GetReference()}: pads already routed, fix PLACEMENT instead")
        fp.Move(pcbnew.VECTOR2I(FromMM(d[0]), FromMM(d[1])))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if (fp.GetReference(), p.GetNumber()) in SOLID_PADS:
                p.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)


def add_lanes(board, ob):
    """Escape lanes of fine-pitch pins: pad centre -> LANE mm past its outer
    tip, as foreign copper for other nets' fan-out stubs and vias."""
    for fp in board.GetFootprints():
        pads = [p for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
        fx, fy = mm(fp.GetPosition().x), mm(fp.GetPosition().y)
        for p in pads:
            x, y = mm(p.GetPosition().x), mm(p.GetPosition().y)
            if not any(q is not p and math.hypot(mm(q.GetPosition().x) - x,
                                                 mm(q.GetPosition().y) - y) < 0.66
                       for q in pads):
                continue
            bb = p.GetBoundingBox()
            w, h = mm(bb.GetWidth()), mm(bb.GetHeight())
            if abs(w - h) < 0.05:
                continue            # square/EP pads have no single escape axis
            if w > h:
                sgn = 1 if x >= fx else -1
                end = (x + sgn * (w / 2 + LANE), y)
            else:
                sgn = 1 if y >= fy else -1
                end = (x, y + sgn * (h / 2 + LANE))
            ob.add(pcbnew.F_Cu, LineString([(x, y), end]).buffer(STUB_W / 2),
                   p.GetNetname() or "<nc>", kind="lane")


def main():
    board = pcbnew.LoadBoard(BOARD)
    nudge(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    nets = board.GetNetsByName()
    ob = build(board)
    fills = {n: plane_fill(board, n) for n in PLANE_NETS}
    bb = board.GetBoardEdgesBoundingBox()
    bx1, by1, bx2, by2 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())

    def in_plane(net, x, y):
        p = Point(x, y)
        return any(f.contains(p) and f.exterior.distance(p) >= PLANE_MARGIN
                   for f in fills[net])

    def in_own_pour(pad):
        p = Point(mm(pad.GetPosition().x), mm(pad.GetPosition().y))
        for z in board.Zones():
            if z.GetLayer() == pcbnew.F_Cu and z.GetNetname() == pad.GetNetname():
                if any(g.contains(p) for g in sps_polys(z.GetFilledPolysList(pcbnew.F_Cu))):
                    return True
        return False

    pour_outlines = []
    for z in board.Zones():
        if z.GetLayer() == pcbnew.F_Cu:
            o = z.Outline().Outline(0)
            pour_outlines.append((z.GetNetname(), Polygon(
                [(mm(o.CPoint(j).x), mm(o.CPoint(j).y)) for j in range(o.PointCount())])))

    def enclosed(pad):
        p = Point(mm(pad.GetPosition().x), mm(pad.GetPosition().y))
        return any(n != pad.GetNetname() and poly.contains(p) for n, poly in pour_outlines)

    todo = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            net = pad.GetNetname()
            if not net or net.startswith("unconnected") or \
                    pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            if len(conn.GetConnectedTracks(pad)) or in_own_pour(pad):
                continue
            if net in PLANE_NETS:
                todo.append((fp, pad, True))
            elif enclosed(pad):
                todo.append((fp, pad, False))

    def commit(net, layer, pts, via, w=STUB_W):
        code = nets[net].GetNetCode()
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(FromMM(a[0]), FromMM(a[1])))
            t.SetEnd(pcbnew.VECTOR2I(FromMM(b[0]), FromMM(b[1])))
            t.SetWidth(FromMM(w))
            t.SetLayer(layer)
            t.SetNetCode(code)
            board.Add(t)
            ob.add(layer, LineString([a, b]).buffer(w / 2), net)
        if via:
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(FromMM(via[0]), FromMM(via[1])))
            v.SetDrill(FromMM(VIA_DRILL))
            v.SetWidth(FromMM(VIA_D))
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNetCode(code)
            board.Add(v)
            c = Point(via).buffer(VIA_D / 2)
            ob.add(pcbnew.F_Cu, c, net)
            ob.add(pcbnew.B_Cu, c, net)
            ob.holes.append((via[0], via[1], VIA_DRILL / 2))

    from gen_board import ORG
    for ref, num, vx, vy in ESCAPES:
        fp = board.FindFootprintByReference(ref)
        pad = [p for p in fp.Pads() if p.GetNumber() == num][0]
        net = pad.GetNetname()
        x, y = mm(pad.GetPosition().x), mm(pad.GetPosition().y)
        vx, vy = vx + ORG[0], vy + ORG[1]
        via = Point(vx, vy).buffer(VIA_D / 2)
        stub = LineString([(x, y), (vx, vy)]).buffer(0.1)
        if not (ob.clear_of(pcbnew.F_Cu, via, net, clr=0.2005)
                and ob.clear_of(pcbnew.B_Cu, via, net, clr=0.2005)
                and ob.clear_of(pcbnew.F_Cu, stub, net, clr=0.2005) and ob.hole_ok(vx, vy)):
            sys.exit(f"escape {ref}.{num} ({net}) does not clear -- fix ESCAPES")
        commit(net, pcbnew.F_Cu, [(x, y), (vx, vy)], (vx, vy), 0.2)
    for net, w, pts in HAND_ROUTES:
        pts = [(x + ORG[0], y + ORG[1]) for x, y in pts]
        g = LineString(pts).buffer(w / 2)
        if not ob.clear_of(pcbnew.F_Cu, g, net, clr=0.2005):
            sys.exit(f"hand route {net} does not clear -- fix HAND_ROUTES")
        commit(net, pcbnew.F_Cu, pts, None, w)
    # lanes go in after the hand escapes: those are placed deliberately
    # inside their neighbours' lanes
    add_lanes(board, ob)


    def ep_strap(fp, pad):
        """Straight inward stub onto a same-net pad of the same part (the
        exposed pad), when one is within 1.2 mm -- shorter than any via."""
        x, y = mm(pad.GetPosition().x), mm(pad.GetPosition().y)
        for q in fp.Pads():
            if q is pad or q.GetNetname() != pad.GetNetname():
                continue
            poly = sps_polys(q.GetEffectivePolygon())
            if not poly:
                continue
            p = Point(x, y)
            d = poly[0].distance(p)
            if 0 < d < 1.2:
                tgt = nearest_points(poly[0], p)[0]
                # land 0.1 mm inside the target pad, along the same line
                tx, ty = tgt.x + (tgt.x - x) / d * 0.1, tgt.y + (tgt.y - y) / d * 0.1
                return [(x, y), (tx, ty)]
        return None

    def candidates(fp, pad):
        x, y = mm(pad.GetPosition().x), mm(pad.GetPosition().y)
        fx, fy = mm(fp.GetPosition().x), mm(fp.GetPosition().y)
        bbx = pad.GetBoundingBox()
        horiz = bbx.GetWidth() >= bbx.GetHeight()
        ox, oy = x - fx, y - fy
        if horiz:
            axis = [(1 if ox >= 0 else -1, 0), (-1 if ox >= 0 else 1, 0)]
            other = [(0, 1), (0, -1)]
        else:
            axis = [(0, 1 if oy >= 0 else -1), (0, -1 if oy >= 0 else 1)]
            other = [(1, 0), (-1, 0)]
        diag = [(s * math.sqrt(.5), t * math.sqrt(.5)) for s in (1, -1) for t in (1, -1)]
        out = []
        for rank, dirs in enumerate((axis[:1], axis[1:], other, diag)):
            for dx, dy in dirs:
                for k in range(8, 61):          # 0.4 .. 3.0 mm
                    d = k * 0.05
                    out.append((d + rank * 0.35, (x, y), (x + dx * d, y + dy * d)))
        # dog-leg: out along the axis past the pad end, then sideways
        half = max(mm(bbx.GetWidth()), mm(bbx.GetHeight())) / 2
        for dx, dy in axis[:1]:
            for k in range(0, 12):
                d1 = half + 0.1 + k * 0.1
                kx, ky = x + dx * d1, y + dy * d1
                for sx, sy in other:
                    for j in range(6, 31):
                        d2 = j * 0.1
                        out.append((d1 + d2 + 0.6, (x, y), (kx, ky), (kx + sx * d2, ky + sy * d2)))
        out.sort(key=lambda c: c[0])
        return out

    placed, strapped, failed = 0, 0, []
    for fp, pad, to_plane in todo:
        net = pad.GetNetname()
        zones = to_plane        # an enclosed pad's stub may cut the pour it sits in
        ok = False
        pts = ep_strap(fp, pad)
        if pts and ob.clear_of(pcbnew.F_Cu, LineString(pts).buffer(STUB_W / 2), net):
            commit(net, pcbnew.F_Cu, pts, None)
            strapped += 1
            continue
        for cand in candidates(fp, pad):
            pts = list(cand[1:])
            vx, vy = pts[-1]
            if not (bx1 + EDGE < vx < bx2 - EDGE and by1 + EDGE < vy < by2 - EDGE):
                continue
            if (to_plane and not in_plane(net, vx, vy)) or not ob.hole_ok(vx, vy):
                continue
            via = Point(vx, vy).buffer(VIA_D / 2)
            if not (ob.clear_of(pcbnew.F_Cu, via, net, zones=zones)
                    and ob.clear_of(pcbnew.B_Cu, via, net)):
                continue
            if not ob.clear_of(pcbnew.F_Cu, via, None, pads_only=True):
                continue            # no via-in-pad, even same-net: solder wicks down it
            stub = LineString(pts).buffer(STUB_W / 2)
            if not ob.clear_of(pcbnew.F_Cu, stub, net, zones=zones):
                continue
            commit(net, pcbnew.F_Cu, pts, (vx, vy))
            placed += 1
            ok = True
            break
        if not ok:
            failed.append((fp, pad))
    todo = [(fp, pad) for fp, pad, _ in todo]

    # strap leftovers to an adjacent same-net pad that now has copper
    board.BuildConnectivity()
    for fp, pad in failed[:]:
        net = pad.GetNetname()
        x, y = mm(pad.GetPosition().x), mm(pad.GetPosition().y)
        best = None
        for other in fp.Pads():
            if other is pad or other.GetNetname() != net:
                continue
            ox, oy = mm(other.GetPosition().x), mm(other.GetPosition().y)
            d = math.hypot(ox - x, oy - y)
            if d > 1.6:
                continue
            seg = LineString([(x, y), (ox, oy)]).buffer(STUB_W / 2)
            if ob.clear_of(pcbnew.F_Cu, seg, net) and (best is None or d < best[0]):
                best = (d, (ox, oy))
        if best:
            commit(net, pcbnew.F_Cu, [(x, y), best[1]], None)
            strapped += 1
            failed.remove((fp, pad))

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    board.Save(BOARD)
    print(f"fanout: {len(todo)} plane pads open, {placed} via stubs, {strapped} straps, "
          f"{len(failed)} left for the router; unconnected now "
          f"{board.GetConnectivity().GetUnconnectedCount(False)}")
    for fp, pad in failed:
        print(f"  left: {fp.GetReference()}.{pad.GetNumber()} {pad.GetNetname()}")


if __name__ == "__main__":
    main()
