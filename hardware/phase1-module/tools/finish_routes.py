"""Routing pass 3: close the last unconnected items with an exact-geometry router.

Run after import_ses.py:
    python3 finish_routes.py [board.kicad_pcb] [--base=pre_freerouting.kicad_pcb]

With --base, copper that is not in the base board (Freerouting's and this
pass's own) may be ripped up when a connection has no free path: the
blocked net is routed through it at a cost, the tracks/vias it crosses
are removed, and their nets go back on the work list. Pass-1 and
fan-out copper (in the base) is never ripped.

Freerouting leaves a handful of connections open (on this board: the
DAC80502 pins boxed in by R3/R6, the LM5145 control pins, and pads that
sit over the *other* In2 rail's region -- a 3V3 pad above the 5V0
column cannot reach its plane with a via drop). The phase-2 grid router
fails the same spots because it approximates pads by bounding boxes on
a 0.125 mm grid. This pass works from the real copper instead:

  * copper islands come from exact Shapely geometry (pads, tracks, vias,
    zone fills per layer, joined through vias and plated holes), so a
    connection is "open" exactly when KiCad would say so;
  * each open net is routed island-to-island by A* on a 0.05 mm grid in a
    window around the two islands, 8-way (45-degree) moves on F.Cu and
    B.Cu, vias allowed anywhere they clear, with every cell tested
    against the buffered foreign copper -- clearance-correct by
    construction, then re-checked by KiCad DRC;
  * an island can also be reached by dropping a via into its In1/In2
    plane fill (with PLANE_MARGIN to the fill edge, so a via can never
    bridge the PGND/AGND seam or the 3V3/5V0 split);
  * foreign F.Cu power pours are obstacles; B.Cu pours are fill-around.

Nets it cannot close are listed, never forced.
"""
import heapq
import math
import os
import sys
from collections import defaultdict

import numpy as np
import pcbnew
import shapely
from pcbnew import FromMM
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points, unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "phase1-module.kicad_pcb")

STEP = 0.05
TRACK_W = 0.2
NECK_W = 0.15        # board minimum; signal nets only, when 0.2 cannot pass
POWER_NETS = {"PGND", "AGND", "3V3", "5V0", "VBUS_F", "VOUT", "VOUT_INT", "SW", "PS_VCC", "PS_VIN"}
VIA_D, VIA_DRILL = 0.6, 0.3
CLEAR = 0.21
HOLE_GAP = 0.3
PLANE_MARGIN = 0.45
WINDOW = 4.0
VIA_COST = 1.5
ZONE_COST = 0.6     # per cell through a foreign F.Cu pour fill
RIP_COST = 0.4      # per 0.05 mm cell through rippable copper
# Boards that reuse this router (phase3-manager/tools/finish_routes.py)
# override these; the defaults keep phase-1 behaviour unchanged.
FILL_AROUND = set()  # nets whose F.Cu pour is plain fill-around: no ZONE_COST
B_COST = 0.0         # extra cost per cell on B.Cu (keeps a B.Cu plane whole)
COPPER = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
ROUTE_LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)
mm = pcbnew.ToMM


def sps_polys(sps):
    out = []
    for i in range(sps.OutlineCount()):
        ol = sps.Outline(i)
        pts = [(mm(ol.CPoint(j).x), mm(ol.CPoint(j).y)) for j in range(ol.PointCount())]
        if len(pts) >= 3:
            out.append(Polygon(pts).buffer(0))
    return out


def key(t):
    if isinstance(t, pcbnew.PCB_VIA):
        return (t.GetNetname(), "V", t.GetPosition().x, t.GetPosition().y)
    return (t.GetNetname(), t.GetLayer(), t.GetStart().x, t.GetStart().y,
            t.GetEnd().x, t.GetEnd().y)


class Copper:
    """Every copper item as (net, layer, geometry, kind, obj); kinds pad/track/via/zone.

    `rippable` holds the track/via objects not present in the base board
    (i.e. the Freerouting / this-pass copper), which the router may rip up."""
    def __init__(self, board, base_keys=None):
        self.items = []
        self.holes = []
        base_keys = base_keys or set()
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                net = pad.GetNetname() or f"<nc {fp.GetReference()}.{pad.GetNumber()}>"
                polys = sps_polys(pad.GetEffectivePolygon())
                through = pad.GetDrillSize().x > 0
                if through:
                    self.holes.append((mm(pad.GetPosition().x), mm(pad.GetPosition().y),
                                       mm(pad.GetDrillSize().x) / 2))
                for L in COPPER:
                    if pad.IsOnLayer(L) or (through and pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH):
                        for g in polys:
                            self.items.append((net, L, g, "pad", None))
        for t in board.GetTracks():
            net = t.GetNetname()
            if isinstance(t, pcbnew.PCB_VIA):
                x, y = mm(t.GetPosition().x), mm(t.GetPosition().y)
                self.holes.append((x, y, mm(t.GetDrillValue()) / 2))
                c = Point(x, y).buffer(mm(t.GetWidth()) / 2, 16)
                obj = None if key(t) in base_keys else t
                for L in COPPER:
                    self.items.append((net, L, c, "via", obj))
            else:
                g = LineString([(mm(t.GetStart().x), mm(t.GetStart().y)),
                                (mm(t.GetEnd().x), mm(t.GetEnd().y))]).buffer(mm(t.GetWidth()) / 2, 8)
                obj = None if key(t) in base_keys else t
                self.items.append((net, t.GetLayer(), g, "track", obj))
        for z in board.Zones():
            if z.GetIsRuleArea():
                continue     # keep-outs have no fill (asserts in KiCad 7)
            for g in sps_polys(z.GetFilledPolysList(z.GetLayer())):
                self.items.append((z.GetNetname(), z.GetLayer(), g, "zone", None))

    def islands(self, net):
        """Connected groups of this net's items (union-find over touching geometry)."""
        idx = [i for i, it in enumerate(self.items) if it[0] == net]
        parent = {i: i for i in idx}

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        by_layer = defaultdict(list)
        for i in idx:
            by_layer[self.items[i][1]].append(i)
        for L, ids in by_layer.items():
            geoms = [self.items[i][2] for i in ids]
            tree = shapely.STRtree(geoms)
            for a, b in zip(*tree.query(geoms, predicate="intersects")):
                if a < b:
                    ra, rb = find(ids[a]), find(ids[b])
                    if ra != rb:
                        parent[ra] = rb
        # vias / PTH pads: same object on every layer -> tie by identical geometry
        groups = defaultdict(list)
        for i in idx:
            if self.items[i][3] in ("via", "pad"):
                groups[self.items[i][2].wkb].append(i)
        for ids in groups.values():
            for a in ids[1:]:
                ra, rb = find(a), find(ids[0])
                if ra != rb:
                    parent[ra] = rb
        out = defaultdict(list)
        for i in idx:
            out[find(i)].append(i)
        return list(out.values())


def route(cu, net, src, dst, board_bb, rip=False, protect=(), w=None):
    """A* from island src to island dst.

    Returns (path, victims): path is a list of ('T', layer, pts) / ('V', xy);
    victims are the rippable foreign track/via objects the path runs
    through (only when rip=True; each blocked cell then costs RIP_COST
    extra instead of being a wall)."""
    TRACK_W = w or globals()["TRACK_W"]
    items = cu.items
    geo = lambda ids, L: [items[i][2] for i in ids if items[i][1] == L]
    # window: the (small) source island plus the nearest point of the
    # destination -- the destination may be a whole In1/In2 plane
    sg = unary_union([items[i][2] for i in src])
    dg = unary_union([items[i][2] for i in dst])
    near = nearest_points(sg, dg)[1]
    minx, miny, maxx, maxy = unary_union([sg, near]).bounds
    x1, y1 = max(minx - WINDOW, board_bb[0] + 0.6), max(miny - WINDOW, board_bb[1] + 0.6)
    x2, y2 = min(maxx + WINDOW, board_bb[2] - 0.6), min(maxy + WINDOW, board_bb[3] - 0.6)
    nx, ny = int((x2 - x1) / STEP) + 1, int((y2 - y1) / STEP) + 1
    xs = x1 + np.arange(nx) * STEP
    ys = y1 + np.arange(ny) * STEP
    GX, GY = np.meshgrid(xs, ys, indexing="ij")
    win = Polygon([(x1 - 2, y1 - 2), (x2 + 2, y1 - 2), (x2 + 2, y2 + 2), (x1 - 2, y2 + 2)])

    def mask(geoms, r):
        g = [x.buffer(r, 8) for x in geoms if x.intersects(win.buffer(r))]
        if not g:
            return np.zeros((nx, ny), bool)
        return shapely.contains_xy(unary_union(g), GX, GY)

    def soft(it):
        return rip and it[4] is not None and it[0] not in protect
    foreign = {L: [it[2] for it in items if it[1] == L and it[0] != net
                   and it[3] != "zone" and not soft(it)]
               for L in ROUTE_LAYERS}
    # foreign F.Cu power-pour fills: crossable at ZONE_COST per cell (KiCad
    # refills around the track), so a pin walled in by a pour can still
    # get out -- but the router minimises the cut
    pour = mask([it[2] for it in items if it[1] == pcbnew.F_Cu and it[0] != net
                 and it[3] == "zone" and it[0] not in FILL_AROUND], CLEAR + TRACK_W / 2)
    pour_via = mask([it[2] for it in items if it[1] == pcbnew.F_Cu and it[0] != net
                     and it[3] == "zone" and it[0] not in FILL_AROUND], CLEAR + VIA_D / 2)
    softg = {L: [it[2] for it in items if it[1] == L and it[0] != net and soft(it)]
             for L in ROUTE_LAYERS}
    track_ok = {L: ~mask(foreign[L], CLEAR + TRACK_W / 2) for L in ROUTE_LAYERS}
    track_soft = {L: mask(softg[L], CLEAR + TRACK_W / 2) for L in ROUTE_LAYERS}
    via_ok = track_ok[pcbnew.F_Cu] & track_ok[pcbnew.B_Cu]
    via_ok &= ~mask(foreign[pcbnew.F_Cu] + foreign[pcbnew.B_Cu], CLEAR + VIA_D / 2)
    via_soft = mask(softg[pcbnew.F_Cu] + softg[pcbnew.B_Cu], CLEAR + VIA_D / 2)
    holes = [Point(hx, hy).buffer(hr) for hx, hy, hr in cu.holes]
    via_ok &= ~mask(holes, VIA_DRILL / 2 + HOLE_GAP)
    # no via-in-pad, any net
    pads = [it[2] for it in items if it[3] == "pad" and it[1] == pcbnew.F_Cu]
    via_ok &= ~mask(pads, CLEAR + VIA_D / 2)
    # foreign inner planes are fine (antipad), but never land a via in a
    # foreign F.Cu pour region -- covered by foreign[F_Cu]

    def goal_mask(ids):
        m = {}
        for L in ROUTE_LAYERS:
            g = geo(ids, L)
            m[L] = mask([x.buffer(-0.02) for x in g if not x.buffer(-0.02).is_empty], 0) \
                if g else np.zeros((nx, ny), bool)
        inner = [items[i][2] for i in ids if items[i][1] in (pcbnew.In1_Cu, pcbnew.In2_Cu)
                 and items[i][3] == "zone"]
        vm = np.zeros((nx, ny), bool)
        for z in inner:
            s = z.buffer(-PLANE_MARGIN)
            if not s.is_empty:
                vm |= shapely.contains_xy(s, GX, GY)
        return m, vm & via_ok
    smask, svia = goal_mask(src)
    tmask, tvia = goal_mask(dst)

    tpts = np.argwhere(tmask[pcbnew.F_Cu] | tmask[pcbnew.B_Cu] | tvia)
    if not len(tpts):
        return None, []
    tx, ty = tpts[:, 0].mean(), tpts[:, 1].mean()
    LI = {pcbnew.F_Cu: 0, pcbnew.B_Cu: 1}
    LL = ROUTE_LAYERS
    ok = [track_ok[LL[0]], track_ok[LL[1]]]
    sm = [track_soft[LL[0]], track_soft[LL[1]]]
    tm = [tmask[LL[0]], tmask[LL[1]]]

    def h(i, j):
        return 0.6 * math.hypot(i - tx, j - ty) * STEP

    openq, best, came = [], {}, {}
    tie = 0
    for L in LL:
        for i, j in np.argwhere(smask[L]):
            s = (LI[L], int(i), int(j))
            best[s] = 0.0
            heapq.heappush(openq, (h(i, j), 0.0, tie, s, None))
            tie += 1
    # starting by a via dropped into the source's plane
    for i, j in np.argwhere(svia):
        for l in (0, 1):
            s = (l, int(i), int(j))
            if s not in best:
                best[s] = VIA_COST
                heapq.heappush(openq, (VIA_COST + h(i, j), VIA_COST, tie, s, ("PV", l)))
                tie += 1
    moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
             (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    goal = None
    n = 0
    while openq:
        f, c, _, s, par = heapq.heappop(openq)
        if s in came:
            continue
        came[s] = par
        l, i, j = s
        n += 1
        if n > 3_000_000:
            break
        if tm[l][i, j]:
            goal = s
            break
        if tvia[i, j] and via_ok[i, j]:
            came[("GV", l, i, j)] = s
            goal = ("GV", l, i, j)
            break
        for di, dj, w in moves:
            a, b = i + di, j + dj
            if not (0 <= a < nx and 0 <= b < ny) or not ok[l][a, b]:
                continue
            if di and dj and not (ok[l][i + di, j] and ok[l][i, j + dj]):
                continue   # no corner cutting past an obstacle
            nc = c + w * STEP + (RIP_COST if sm[l][a, b] else 0.0) \
                + (ZONE_COST if l == 0 and pour[a, b] else 0.0) \
                + (B_COST if l == 1 else 0.0)
            ns = (l, a, b)
            if nc < best.get(ns, 1e18):
                best[ns] = nc
                heapq.heappush(openq, (nc + h(a, b), nc, tie, ns, s))
                tie += 1
        if via_ok[i, j]:
            ns = (1 - l, i, j)
            nc = c + VIA_COST + (RIP_COST * 8 if via_soft[i, j] else 0.0) \
                + (ZONE_COST * 8 if pour_via[i, j] else 0.0)
            if nc < best.get(ns, 1e18):
                best[ns] = nc
                heapq.heappush(openq, (nc + h(i, j), nc, tie, ns, s))
                tie += 1
    if goal is None:
        return None, []
    path = []
    s = goal
    while s is not None and not (isinstance(s, tuple) and s[0] == "PV"):
        path.append(s)
        s = came.get(s)
    start_via = isinstance(s, tuple) and s[0] == "PV"
    path.reverse()
    out = []
    xy = lambda i, j: (round(float(xs[i]), 4), round(float(ys[j]), 4))
    if start_via:
        out.append(("V", xy(path[0][1], path[0][2])))
    run = []
    prev_l = None
    for st in path:
        if st[0] == "GV":
            if len(run) > 1:
                out.append(("T", LL[prev_l], run))
            out.append(("V", xy(st[2], st[3])))
            run = []
            break
        l, i, j = st
        if prev_l is not None and l != prev_l:
            if len(run) > 1:
                out.append(("T", LL[prev_l], run))
            out.append(("V", xy(i, j)))
            run = []
        run.append(xy(i, j))
        prev_l = l
    if len(run) > 1:
        out.append(("T", LL[prev_l], run))
    victims = []
    if rip:
        body = {L: [] for L in ROUTE_LAYERS}
        for it in out:
            if it[0] == "T":
                body[it[1]].append(LineString(it[2]).buffer(TRACK_W / 2 + CLEAR - 0.005)
                                   if len(it[2]) > 1 else Point(it[2][0]).buffer(TRACK_W / 2 + CLEAR))
            else:
                for L in ROUTE_LAYERS:
                    body[L].append(Point(it[1]).buffer(VIA_D / 2 + CLEAR - 0.005))
        for L in ROUTE_LAYERS:
            if not body[L]:
                continue
            u = unary_union(body[L])
            for it in items:
                if it[1] == L and it[0] != net and soft(it) and it[2].intersects(u):
                    if all(key(v) != key(it[4]) for v in victims):
                        victims.append(it[4])
    return out, victims


def simplify(pts):
    """Drop collinear interior points."""
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for k in range(1, len(pts) - 1):
        ax, ay = out[-1]
        bx, by = pts[k]
        cx, cy = pts[k + 1]
        if abs((bx - ax) * (cy - by) - (by - ay) * (cx - bx)) > 1e-9:
            out.append(pts[k])
    out.append(pts[-1])
    return out


def commit(board, nets, net, res, w=TRACK_W):
    code = nets[net]
    for it in res:
        if it[0] == "T":
            pts = simplify(it[2])
            for a, b in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(FromMM(a[0]), FromMM(a[1])))
                t.SetEnd(pcbnew.VECTOR2I(FromMM(b[0]), FromMM(b[1])))
                t.SetWidth(FromMM(w))
                t.SetLayer(it[1])
                t.SetNetCode(code)
                board.Add(t)
        else:
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(FromMM(it[1][0]), FromMM(it[1][1])))
            v.SetDrill(FromMM(VIA_DRILL))
            v.SetWidth(FromMM(VIA_D))
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNetCode(code)
            board.Add(v)


# removed items stay referenced: letting SWIG garbage-collect a removed
# board item frees it under the board's feet
GRAVEYARD = []


def rip_chains(board, base_keys, victims):
    """Remove each victim together with the whole rippable route it belongs
    to (touching rippable copper of the same net), so no stubs are left."""
    cu = Copper(board, base_keys)
    want = {key(v) for v in victims}
    by_net = defaultdict(list)
    for i, it in enumerate(cu.items):
        if it[4] is not None:
            by_net[it[0]].append(i)
    gone = set()
    for net, ids in by_net.items():
        seeds = [i for i in ids if key(cu.items[i][4]) in want]
        if not seeds:
            continue
        chain, stack = set(), list(seeds)
        while stack:
            a = stack.pop()
            if a in chain:
                continue
            chain.add(a)
            ga, La, ka = cu.items[a][2], cu.items[a][1], key(cu.items[a][4])
            for b in ids:
                if b in chain:
                    continue
                gb, Lb = cu.items[b][2], cu.items[b][1]
                if key(cu.items[b][4]) == ka or (La == Lb and ga.intersects(gb)):
                    stack.append(b)
        for i in chain:
            k = key(cu.items[i][4])
            if k not in gone:
                gone.add(k)
                GRAVEYARD.append(cu.items[i][4])
                board.Remove(cu.items[i][4])
    return gone


def prune_dangling(board, base_keys):
    """Delete rippable tracks with a free end and vias tied to < 2 things,
    until nothing changes. Returns the affected nets."""
    touched = set()
    while True:
        cu = Copper(board, base_keys)
        by = defaultdict(list)
        for i, it in enumerate(cu.items):
            by[(it[0], it[1])].append(i)
        dead = {}
        for i, it in enumerate(cu.items):
            obj = it[4]
            if obj is None or key(obj) in dead:
                continue
            others = lambda L: [cu.items[j] for j in by[(it[0], L)]
                                if cu.items[j][4] is None or key(cu.items[j][4]) != key(obj)]
            if it[3] == "track":
                for end in (obj.GetStart(), obj.GetEnd()):
                    p = Point(mm(end.x), mm(end.y)).buffer(0.01)
                    if not any(o[2].intersects(p) for o in others(it[1])):
                        dead[key(obj)] = obj
                        break
            elif it[3] == "via" and it[1] == pcbnew.F_Cu:
                n = 0
                for L in COPPER:
                    g = [o for o in others(L) if o[2].intersects(it[2])]
                    n += 1 if g else 0
                if n < 2:
                    dead[key(obj)] = obj
        if not dead:
            return touched
        for obj in dead.values():
            touched.add(obj.GetNetname())
            GRAVEYARD.append(obj)
            board.Remove(obj)


def tidy(board, base_keys):
    """Drop zero-length segments, and router tracks KiCad calls dangling
    (Freerouting re-emits pass-1 stubs as half-length duplicates ending
    mid-track) when removing them costs no connection."""
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    before = conn.GetUnconnectedCount(False)
    n = 0
    for t in list(board.GetTracks()):
        if isinstance(t, pcbnew.PCB_VIA):
            continue
        if t.GetStart() == t.GetEnd():
            GRAVEYARD.append(t)
            board.Remove(t)
            n += 1
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    for t in list(board.GetTracks()):
        if isinstance(t, pcbnew.PCB_VIA) or key(t) in base_keys:
            continue
        if conn.TestTrackEndpointDangling(t, False):
            board.Remove(t)
            board.BuildConnectivity()
            conn = board.GetConnectivity()
            if conn.GetUnconnectedCount(False) > before:
                board.Add(t)
                board.BuildConnectivity()
                conn = board.GetConnectivity()
            else:
                GRAVEYARD.append(t)
                n += 1
    print(f"tidy: removed {n} zero-length / dangling segment(s)")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--base=")]
    base = [a[7:] for a in sys.argv[1:] if a.startswith("--base=")]
    board_path = args[0] if args else BOARD
    # Load the base BEFORE the board: pcbnew.LoadBoard switches the active
    # project, and a base outside the project dir has none -- loaded second,
    # it swapped the board's rules for KiCad defaults, which Save() then
    # wrote into the real .kicad_pro (min drill 0.3, hole clearance 0.25...).
    base_keys = set()
    if base:
        base_keys = {key(t) for t in pcbnew.LoadBoard(base[0]).GetTracks()}
    board = pcbnew.LoadBoard(board_path)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    bb = board.GetBoardEdgesBoundingBox()
    board_bb = (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()))
    # net codes as plain ints, taken before any edit: SWIG net-map proxies
    # went stale after board.Remove() and returned raw SwigPyObjects
    nets = {ni.GetNetname(): ni.GetNetCode() for ni in board.GetNetsByName().values()}
    names = sorted({n for n in nets if n
                    and not n.startswith("unconnected")})
    ripped_count = defaultdict(int)
    added, failed = 0, {}
    work = list(names)
    budget = 400
    while work and budget:
        net = work.pop(0)
        cu = Copper(board, base_keys)
        isl = cu.islands(net)
        if len(isl) < 2:
            continue
        budget -= 1
        isl.sort(key=len, reverse=True)
        src = isl[0]
        s_geom = unary_union([cu.items[i][2] for i in src])
        others = sorted(isl[1:], key=lambda d: unary_union(
            [cu.items[i][2] for i in d]).distance(s_geom))
        res, victims, w = None, [], TRACK_W
        for w in (TRACK_W, NECK_W):
            for dst in others:
                res, _ = route(cu, net, dst, src, board_bb, w=w)
                if res:
                    break
            if res or net in POWER_NETS:
                break
        if not res:
            # the largest island may be boxed in (a fine-pitch pin's escape
            # via); join two of the others first and come back for it
            pairs = sorted(((a, b) for i, a in enumerate(others) for b in others[i + 1:]),
                           key=lambda p: unary_union([cu.items[i][2] for i in p[0]]).distance(
                               unary_union([cu.items[i][2] for i in p[1]])))
            for a, b in pairs:
                res, _ = route(cu, net, a, b, board_bb, w=TRACK_W)
                if res:
                    w = TRACK_W
                    break
        if not res and base_keys:
            # rip-up: let the path run through Freerouting copper of nets
            # that have not already been ripped too often, then requeue them
            protect = {n for n, k in ripped_count.items() if k >= 3}
            w = TRACK_W
            res, victims = route(cu, net, others[0], src, board_bb, rip=True, protect=protect)
        if not res:
            failed[net] = len(isl)
            continue
        failed.pop(net, None)
        vn = sorted({v.GetNetname() for v in victims})
        for n in vn:
            ripped_count[n] += 1
            if n not in work:
                work.append(n)
        nrip = len(rip_chains(board, base_keys, victims)) if victims else 0
        commit(board, nets, net, res, w)
        added += 1
        work.insert(0, net)          # finish this net's other islands next
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        print(f"  routed {net}: {sum(1 for r in res if r[0] == 'V')} via(s)"
              + (f", ripped {nrip} item(s) of {', '.join(vn)}" if victims else ""),
              flush=True)
        if not work and base_keys:
            for n in prune_dangling(board, base_keys):
                work.append(n)
            pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    if base_keys:
        prune_dangling(board, base_keys)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    tidy(board, base_keys)
    board.BuildConnectivity()
    board.Save(board_path)
    print(f"finish_routes: {added} connections added; unconnected now "
          f"{board.GetConnectivity().GetUnconnectedCount(False)}")
    for net, k in failed.items():
        print(f"  FAILED {net} ({k} islands)")


if __name__ == "__main__":
    main()
