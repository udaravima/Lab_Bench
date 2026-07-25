"""Routing pass 2: grid A* autorouter for the remaining signal nets.

Phase-2 adaptation of phase-1 autoroute.py with its header fix-list applied:
  - via hole-to-hole spacing is enforced net-independently (the phase-1
    router allowed same-net vias to overlap holes -> 25 hole_near_hole);
    every existing/new via and PTH hole repels new router vias by
    hole_r + drill/2 + 0.3.
  - plane/pour targets are computed from in1_net_at()/in2_net_at() cell
    maps (single precompute) instead of hand-listed rectangles, so the
    AGND pockets and the notched In2 patches are honoured automatically.

Loads the board produced by gen_board.py + route_board.py and routes every
still-unconnected pad on F.Cu/B.Cu (0.125 mm grid, via cost, direction bias
F=horizontal B=vertical). Obstacles: pads, tracks, vias with clearance;
F.Cu power-pour polygons are keep-out for foreign nets. Nets tied to a
plane/patch connect by dropping a via over the zone region.

Run:  python3 autoroute.py           (after gen_board.py + route_board.py)
"""
import heapq
import os

import pcbnew
from pcbnew import FromMM

from gen_board import ORG, W, H, PWR_POURS, point_in_poly, P
from route_board import in1_net_at, in2_net_at

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "..", "phase2-module.kicad_pcb")

STEP = 0.125
TRACK_W = 0.25
CLEAR = 0.21
VIA_D, VIA_DRILL = 0.6, 0.3
NX, NY = int(W / STEP) + 1, int(H / STEP) + 1
FREE, ALL = 0, 255


def cells_for_disc(cx, cy, r):
    out = []
    ir = int(r / STEP) + 1
    gx, gy = round(cx / STEP), round(cy / STEP)
    for dx in range(-ir, ir + 1):
        for dy in range(-ir, ir + 1):
            x, y = gx + dx, gy + dy
            if 0 <= x < NX and 0 <= y < NY:
                if ((x * STEP - cx) ** 2 + (y * STEP - cy) ** 2) <= r * r:
                    out.append((x, y))
    return out


def cells_for_seg(x1, y1, x2, y2, r):
    out = set()
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    n = max(1, int(length / (STEP / 2)))
    for i in range(n + 1):
        t = i / n
        out.update(cells_for_disc(x1 + t * (x2 - x1), y1 + t * (y2 - y1), r))
    return out


def cells_for_bbox(x1, y1, x2, y2):
    out = []
    for gx in range(max(0, int(x1 / STEP)), min(NX - 1, int(x2 / STEP) + 1) + 1):
        for gy in range(max(0, int(y1 / STEP)), min(NY - 1, int(y2 / STEP) + 1) + 1):
            if x1 <= gx * STEP <= x2 and y1 <= gy * STEP <= y2:
                out.append((gx, gy))
    return out


class Grid:
    """Flat bytearray grid: 0 = free, 1..253 = net id, 255 = all-nets block."""
    def __init__(self):
        n = NX * NY
        self.block = [bytearray(n), bytearray(n)]
        self.via_blk = bytearray(n)
        self.pourA = bytearray(n)
        self.holes = []
        self.nid = {}

    def net_id(self, net):
        i = self.nid.get(net)
        if i is None:
            i = len(self.nid) + 1
            if i > 253:
                raise RuntimeError("net id overflow")
            self.nid[net] = i
        return i

    def _mark(self, arr, cells, nid):
        for (x, y) in cells:
            i = x * NY + y
            cur = arr[i]
            if cur == 0:
                arr[i] = nid
            elif cur != nid:
                arr[i] = ALL

    def add(self, layer, cells, net):
        self._mark(self.block[layer], cells, ALL if net == "*" else self.net_id(net))

    def add_via(self, cells, net):
        self._mark(self.via_blk, cells, ALL if net == "*" else self.net_id(net))

    def add_pour(self, cells, net):
        self._mark(self.pourA, cells, self.net_id(net))

    def add_hole(self, x, y, hole_r):
        self.holes.append((x, y, hole_r + VIA_DRILL / 2 + 0.3))

    def free(self, layer, c, nid):
        i = c[0] * NY + c[1]
        v = self.block[layer][i]
        if v and v != nid:
            return False
        v = self.via_blk[i]
        return v == 0 or v == nid

    def via_ok(self, c, nid):
        cx, cy = c[0] * STEP, c[1] * STEP
        for hx, hy, hr in self.holes:
            if (hx - cx) ** 2 + (hy - cy) ** 2 < hr * hr:
                return False
        for (x, y) in cells_for_disc(cx, cy, 0.68):
            i = x * NY + y
            for layer in (0, 1):
                v = self.block[layer][i]
                if v and v != nid:
                    return False
            v = self.via_blk[i]
            if v and v != nid:
                return False
        i = c[0] * NY + c[1]
        v = self.pourA[i]
        if v and v != nid:
            return False
        return True


def build_grid(board):
    g = Grid()
    net_copper = {}

    def seed(net, cells, L):
        s = net_copper.setdefault(net, set())
        for c in cells:
            s.add((c[0], c[1], L))

    lay = {pcbnew.F_Cu: 0, pcbnew.B_Cu: 1}
    infl = CLEAR + TRACK_W / 2
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            x1 = pcbnew.ToMM(bb.GetLeft()) - ORG[0] - infl
            y1 = pcbnew.ToMM(bb.GetTop()) - ORG[1] - infl
            x2 = pcbnew.ToMM(bb.GetRight()) - ORG[0] + infl
            y2 = pcbnew.ToMM(bb.GetBottom()) - ORG[1] + infl
            net = pad.GetNetname() or "*"
            cells = cells_for_bbox(x1, y1, x2, y2)
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                if pad.IsOnLayer(pcbnew.F_Cu):
                    g.add(0, cells, net)
                if pad.IsOnLayer(pcbnew.B_Cu):
                    g.add(1, cells, net)
            else:
                g.add(0, cells, net)
                g.add(1, cells, net)
                g.add_via(cells_for_bbox(x1 - 0.2, y1 - 0.2, x2 + 0.2, y2 + 0.2), net)
                g.add_hole(pcbnew.ToMM(pad.GetPosition().x) - ORG[0],
                           pcbnew.ToMM(pad.GetPosition().y) - ORG[1],
                           pcbnew.ToMM(pad.GetDrillSize().x) / 2)
    for t in board.GetTracks():
        net = t.GetNetname() or "*"
        if isinstance(t, pcbnew.PCB_VIA):
            x = pcbnew.ToMM(t.GetPosition().x) - ORG[0]
            y = pcbnew.ToMM(t.GetPosition().y) - ORG[1]
            r = pcbnew.ToMM(t.GetWidth()) / 2 + infl
            cells = cells_for_disc(x, y, r)
            g.add(0, cells, net)
            g.add(1, cells, net)
            g.add_via(cells_for_disc(x, y, r + 0.2), net)
            g.add_hole(x, y, VIA_DRILL / 2)
            gc = (round(x / STEP), round(y / STEP))
            seed(net, [gc], 0)
            seed(net, [gc], 1)
        else:
            L = lay.get(t.GetLayer())
            if L is None:
                continue
            x1 = pcbnew.ToMM(t.GetStart().x) - ORG[0]
            y1 = pcbnew.ToMM(t.GetStart().y) - ORG[1]
            x2 = pcbnew.ToMM(t.GetEnd().x) - ORG[0]
            y2 = pcbnew.ToMM(t.GetEnd().y) - ORG[1]
            r = pcbnew.ToMM(t.GetWidth()) / 2 + infl
            g.add(L, cells_for_seg(x1, y1, x2, y2, r), net)
            # 0.07 > half a diagonal cell: off-grid route_board tracks
            # (0.025 mm coords) still seed their nearest cell row
            seed(net, cells_for_seg(x1, y1, x2, y2, 0.07), L)
    g.pour_cells = {}
    for pname, poly in PWR_POURS.items():
        pnet = "PGND" if pname.startswith("PGND") else pname
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        cells = []
        for gx in range(int((min(xs) - 0.5) / STEP), int((max(xs) + 0.5) / STEP) + 1):
            for gy in range(int((min(ys) - 0.5) / STEP), int((max(ys) + 0.5) / STEP) + 1):
                if 0 <= gx < NX and 0 <= gy < NY:
                    if point_in_poly(gx * STEP, gy * STEP, poly):
                        cells.append((gx, gy))
        g.add_pour(cells, pnet)
        g.pour_cells.setdefault(pnet, []).extend(cells)
    edge = []
    m = int(0.5 / STEP)
    for gx in range(NX):
        for gy in list(range(m + 1)) + list(range(NY - m - 1, NY)):
            edge.append((gx, gy))
    for gy in range(NY):
        for gx in list(range(m + 1)) + list(range(NX - m - 1, NX)):
            edge.append((gx, gy))
    g.add(0, edge, "*")
    g.add(1, edge, "*")
    g.add_via(edge, "*")
    return g, net_copper


def route_net(g, net, sources, targets, pocket_map=None, allowed_mask=0):
    tset = targets
    if not tset:
        return None
    nid = g.net_id(net)
    txs = [t[0] for t in tset]
    tys = [t[1] for t in tset]
    bx1, bx2, by1, by2 = min(txs), max(txs), min(tys), max(tys)

    def h(x, y):
        dx = bx1 - x if x < bx1 else (x - bx2 if x > bx2 else 0)
        dy = by1 - y if y < by1 else (y - by2 if y > by2 else 0)
        return (dx + dy) * STEP * 0.98

    openq = []
    best = {}
    tie = 0
    for (L, x, y) in sources:
        s = (L, x, y)
        best[s] = 0
        tie += 1
        heapq.heappush(openq, (h(x, y), 0, tie, s, None))
    came = {}
    seen_goal = None
    expansions = 0
    while openq and expansions < 1400000:
        f, cost, _, state, parent = heapq.heappop(openq)
        if best.get(state, 1e18) < cost - 1e-9:
            continue
        came[state] = parent
        L, x, y = state
        expansions += 1
        if (x, y, L) in tset or ((x, y, 2) in tset and g.via_ok((x, y), nid)):
            seen_goal = state
            if (x, y, L) not in tset:
                came[("VIA", x, y)] = state
                seen_goal = ("VIA", x, y)
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx_, ny_ = x + dx, y + dy
            if not (0 <= nx_ < NX and 0 <= ny_ < NY):
                continue
            c = (nx_, ny_)
            if not g.free(L, c, nid):
                continue
            step_cost = STEP
            if L == 0:
                pv = g.pourA[nx_ * NY + ny_]
                if pv and pv != nid:
                    step_cost *= 6.0
            if pocket_map:
                pk = pocket_map.get(c, 0)
                if pk and (pk & ~allowed_mask):
                    step_cost *= 3.0    # foreign fine-pitch escape lanes
            if L == 0 and dy and not dx:
                step_cost *= 1.25
            if L == 1 and dx and not dy:
                step_cost *= 1.25
            ncost = cost + step_cost
            ns = (L, nx_, ny_)
            if ncost < best.get(ns, 1e18) - 1e-9:
                best[ns] = ncost
                tie += 1
                heapq.heappush(openq, (ncost + h(nx_, ny_), ncost, tie, ns, state))
        if g.via_ok((x, y), nid):
            ns = (1 - L, x, y)
            ncost = cost + 3.0
            if ncost < best.get(ns, 1e18) - 1e-9:
                best[ns] = ncost
                tie += 1
                heapq.heappush(openq, (ncost + h(x, y), ncost, tie, ns, state))
    if seen_goal is None:
        return None
    path = []
    s = seen_goal
    while s is not None:
        path.append(s)
        s = came.get(s)
    path.reverse()
    return path


def main():
    board = pcbnew.LoadBoard(BOARD)
    board.BuildConnectivity()
    nets = {ni.GetNetname(): ni for ni in board.GetNetsByName().values() if ni.GetNetname()}

    todo = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            net = pad.GetNetname()
            if not net or net.startswith("unconnected"):
                continue
            todo.setdefault(net, []).append(pad)

    g, net_copper = build_grid(board)

    # fine-pitch pockets (QFN/LQFP/WSON/MSOP escape fields): foreign nets
    # pay 3x to travel there so through-traffic cannot consume the escape
    # lanes (the U3/U1/U10 'no path' cluster was exactly that)
    pocket_map = {}
    net_pockets = {}
    bit = 1
    for fp in board.GetFootprints():
        pos = {}
        fine = False
        for pad in fp.Pads():
            x = pcbnew.ToMM(pad.GetPosition().x) - ORG[0]
            y = pcbnew.ToMM(pad.GetPosition().y) - ORG[1]
            for (ox, oy), onet in pos.items():
                if onet != pad.GetNetname() and \
                        (ox - x) ** 2 + (oy - y) ** 2 < 0.66 ** 2:
                    fine = True
            pos[(x, y)] = pad.GetNetname()
        if not fine:
            continue
        xs = [p[0] for p in pos]
        ys = [p[1] for p in pos]
        for c in cells_for_bbox(min(xs) - 1.0, min(ys) - 1.0,
                                max(xs) + 1.0, max(ys) + 1.0):
            pocket_map[c] = pocket_map.get(c, 0) | bit
        for net in pos.values():
            if net:
                net_pockets[net] = net_pockets.get(net, 0) | bit
        bit <<= 1

    # per-net plane cells (In1 / In2), inverted once so the route loop is a
    # dict lookup instead of a 750k-cell scan per net
    print("precomputing plane maps...")
    plane_cells = {}
    for gx in range(NX):
        for gy in range(NY):
            x, y = gx * STEP, gy * STEP
            for pnet in (in1_net_at(x, y), in2_net_at(x, y)):
                if pnet:
                    plane_cells.setdefault(pnet, set()).add((gx, gy, 2))

    def pad_cells(pad):
        x = pcbnew.ToMM(pad.GetPosition().x) - ORG[0]
        y = pcbnew.ToMM(pad.GetPosition().y) - ORG[1]
        gx, gy = round(x / STEP), round(y / STEP)
        L = 0 if pad.IsOnLayer(pcbnew.F_Cu) else 1
        bb = pad.GetBoundingBox()
        w = pcbnew.ToMM(bb.GetWidth())
        hgt = pcbnew.ToMM(bb.GetHeight())
        srcs = [(L, gx, gy)]
        n = int(max(w, hgt) / 2 / STEP)
        for k in range(1, n + 1):
            if w >= hgt:
                srcs += [(L, gx - k, gy), (L, gx + k, gy)]
            else:
                srcs += [(L, gx, gy - k), (L, gx, gy + k)]
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            srcs += [(1 - L, sx, sy) for (sl, sx, sy) in list(srcs)]
        return srcs, (L, gx, gy), (x, y), w >= hgt

    # pads that board connectivity already reports as connected (route_board
    # copper) are targets, not route jobs -- kills the false 'no path' fails
    conn = board.GetConnectivity()
    for net, pads in todo.items():
        s = net_copper.setdefault(net, set())
        for pad in pads:
            if len(conn.GetConnectedTracks(pad)) == 0:
                continue
            srcs, _, _, _ = pad_cells(pad)
            for (sl, sx, sy) in srcs:
                s.add((sx, sy, sl))

    def add_track_path(net, path, entry):
        pts = [s for s in path if s[0] != "VIA"]

        def mm(s):
            return (round(s[1] * STEP, 3), round(s[2] * STEP, 3))
        items = []
        prev = pts[0]
        seg_start = mm(prev)
        direction = None
        for s in pts[1:]:
            if s[0] != prev[0]:
                if mm(prev) != seg_start:
                    items.append(("T", prev[0], seg_start, mm(prev)))
                items.append(("V", mm(prev)))
                seg_start = mm(prev)
                direction = None
                prev = s
                continue
            d = (s[1] - prev[1], s[2] - prev[2])
            if direction is not None and d != direction:
                items.append(("T", prev[0], seg_start, mm(prev)))
                seg_start = mm(prev)
            direction = d
            prev = s
        if mm(prev) != seg_start:
            items.append(("T", prev[0], seg_start, mm(prev)))
        if path[-1][0] == "VIA":
            items.append(("V", mm(prev)))
        gxy, pxy, L, horiz = entry
        # snap the landing at the source pad onto the pad's long axis: the
        # source cell rounds up to 0.0625 mm off-centre, which clips the
        # 0.5 mm-pitch neighbour (same geometry as the entry-stub knee)
        if items and items[0][0] == "T":
            (ax, ay), (bx, by) = items[0][2], items[0][3]
            if horiz and abs(ax - bx) < 1e-9 and abs(ay - pxy[1]) < STEP:
                items[0] = ("T", items[0][1], (ax, pxy[1]), (bx, by))
                gxy = (ax, pxy[1])
            elif not horiz and abs(ay - by) < 1e-9 and abs(ax - pxy[0]) < STEP:
                items[0] = ("T", items[0][1], (pxy[0], ay), (bx, by))
                gxy = (pxy[0], ay)
        netcode = nets[net].GetNetCode()
        lay = (pcbnew.F_Cu, pcbnew.B_Cu)
        for it in items:
            if it[0] == "T":
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(P(*it[2]))
                t.SetEnd(P(*it[3]))
                t.SetWidth(FromMM(TRACK_W))
                t.SetLayer(lay[it[1]])
                t.SetNetCode(netcode)
                board.Add(t)
            else:
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(P(*it[1]))
                v.SetDrill(FromMM(VIA_DRILL))
                v.SetWidth(FromMM(VIA_D))
                v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetNetCode(netcode)
                board.Add(v)
        if gxy is not None and (abs(gxy[0] - pxy[0]) > 1e-3 or abs(gxy[1] - pxy[1]) > 1e-3):
            # constrain the stub to the pad's long axis: snap the off-axis
            # grid rounding over the pad itself, run to centre on the axis
            # (a diagonal stub clips the neighbour at 0.5 mm pitch)
            knee = (gxy[0], pxy[1]) if horiz else (pxy[0], gxy[1])
            for a, b in ((gxy, knee), (knee, pxy)):
                if abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6:
                    continue
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(P(*a))
                t.SetEnd(P(*b))
                t.SetWidth(FromMM(TRACK_W))
                t.SetLayer(lay[L])
                t.SetNetCode(netcode)
                board.Add(t)
        return items

    def net_extent(net):
        xs, ys = [], []
        for pad in todo[net]:
            xs.append(pcbnew.ToMM(pad.GetPosition().x))
            ys.append(pcbnew.ToMM(pad.GetPosition().y))
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    routed = failed = 0
    fails = []
    # local nets first: pocket-internal hops must claim their escape lanes
    # before the long-haul nets sweep through
    for net in sorted(todo, key=lambda n: (net_extent(n), len(todo[n]))):
        pads = todo[net]
        base_targets = set()
        for (gx, gy) in g.pour_cells.get(net, ()):
            base_targets.add((gx, gy, 0))
        base_targets |= plane_cells.get(net, set())
        done_cells = set(base_targets)
        done_cells |= net_copper.get(net, set())
        for i, pad in enumerate(pads):
            src, (L, gx, gy), (px, py), horiz = pad_cells(pad)
            if i == 0 and not done_cells:
                done_cells.add((gx, gy, L))
                continue
            if any((sx, sy, sl) in done_cells for sl, sx, sy in src):
                continue
            path = route_net(g, net, src, done_cells, pocket_map,
                             net_pockets.get(net, 0))
            if path is None:
                failed += 1
                fails.append((net, pcbnew.Cast_to_FOOTPRINT(
                    pad.GetParentFootprint()).GetReference(), "no path"))
                done_cells.add((gx, gy, L))
                continue
            start = path[0]
            items = add_track_path(
                net, path,
                ((start[1] * STEP, start[2] * STEP), (px, py), start[0],
                 horiz))
            routed += 1
            for it in items:
                if it[0] == "T":
                    cells = cells_for_seg(*it[2], *it[3],
                                          TRACK_W / 2 + CLEAR + TRACK_W / 2)
                    g.add(it[1], cells, net)
                    for cx, cy in cells_for_seg(*it[2], *it[3], 0.01):
                        done_cells.add((cx, cy, it[1]))
                else:
                    cells = cells_for_disc(*it[1], VIA_D / 2 + CLEAR + TRACK_W / 2)
                    g.add(0, cells, net)
                    g.add(1, cells, net)
                    g.add_via(cells_for_disc(*it[1], VIA_D / 2 + 0.2 + CLEAR), net)
                    g.add_hole(it[1][0], it[1][1], VIA_DRILL / 2)
                    done_cells.add((round(it[1][0] / STEP),
                                    round(it[1][1] / STEP), 0))
                    done_cells.add((round(it[1][0] / STEP),
                                    round(it[1][1] / STEP), 1))
            done_cells.add((gx, gy, L))

    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"autoroute: {routed} routed, {failed} failed")
    for f in fails[:40]:
        print("  FAIL", f)


if __name__ == "__main__":
    main()
