"""Routing pass 2: grid A* autorouter for the remaining signal nets.

STATUS (2026-07-16, work paused — PCB layout deferred until after all
phases' schematics are done): functional but not finished. Last run:
154/187 connections routed, 33 unconnected, 25 hole_near_hole (router vias
placed too close to each other — extend the via self-spacing in add_track_path
the way via_ok already scans a disc), 2 clearance, 8 fails around congested
U3/U10 escapes. The committed .kicad_pcb is the clean routing-pass-1 state
(gen_board.py + route_board.py only); rerun those two scripts before this one.

Loads the board produced by gen_board.py + route_board.py and routes every
still-unconnected pad pair on F.Cu/B.Cu (0.25 mm grid, via cost, direction
bias F=horizontal B=vertical). Obstacles come from existing pads, tracks and
vias with clearance; F.Cu power-pour polygons are keep-out for foreign nets
(their fills would be cut), In1/In2 are planes and never routed.

Nets already tied to a plane/pour connect by dropping a via over the zone.

Run:  python3 autoroute.py           (iterates until no progress)
"""
import heapq
import os

import pcbnew
from pcbnew import FromMM

from gen_board import ORG, W, H, PWR_POURS, point_in_poly, P
from route_board import IN2_PATCHES, in1_net_at, in2_net_at

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "..", "phase1-module.kicad_pcb")

STEP = 0.25          # routing grid, mm
TRACK_W = 0.25
CLEAR = 0.21         # >= netclass clearance 0.2 + margin
VIA_D, VIA_DRILL = 0.6, 0.3
LAYERS = ("F", "B")  # index 0/1

NX, NY = int(W / STEP) + 1, int(H / STEP) + 1


def cells_for_disc(cx, cy, r):
    """Grid cells within radius r of (cx, cy)."""
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


class Grid:
    def __init__(self):
        # blocked[layer][net_blocking] -> we store: cell -> netname or "*" (all nets)
        self.block = [dict(), dict()]      # per layer: (x,y) -> net or "*"
        self.via_block = dict()            # (x,y) -> net or "*"  (through barrels)
        self.pour = dict()                 # F.Cu pour cells: (x,y) -> pour net

    def add(self, layer, cells, net):
        d = self.block[layer]
        for c in cells:
            cur = d.get(c)
            if cur is None:
                d[c] = net
            elif cur != net:
                d[c] = "*"

    def add_via(self, cells, net):
        for c in cells:
            cur = self.via_block.get(c)
            if cur is None:
                self.via_block[c] = net
            elif cur != net:
                self.via_block[c] = "*"

    def free(self, layer, c, net):
        v = self.block[layer].get(c)
        if v is not None and v != net:
            return False
        v = self.via_block.get(c)
        return v is None or v == net

    def via_ok(self, c, net):
        # via barrel needs clearance on both layers within its radius
        for cc in cells_for_disc(c[0] * STEP, c[1] * STEP, 0.68):
            for layer in (0, 1):
                v = self.block[layer].get(cc)
                if v is not None and v != net:
                    return False
            v = self.via_block.get(cc)
            if v is not None and v != net:
                return False
        v = self.pour.get(c)
        if v is not None and v != net:
            return False               # keep foreign vias out of power pours
        return True


def cells_for_bbox(x1, y1, x2, y2):
    out = []
    for gx in range(max(0, int(x1 / STEP)), min(NX - 1, int(x2 / STEP) + 1) + 1):
        for gy in range(max(0, int(y1 / STEP)), min(NY - 1, int(y2 / STEP) + 1) + 1):
            if x1 <= gx * STEP <= x2 and y1 <= gy * STEP <= y2:
                out.append((gx, gy))
    return out


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
            seed(net, cells_for_seg(x1, y1, x2, y2, 0.01), L)
    # F.Cu power pours: foreign nets keep out (pour + clearance margin)
    for pname, poly in PWR_POURS.items():
        pnet = "PGND" if pname.startswith("PGND") else pname
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        for gx in range(int((min(xs) - 0.5) / STEP), int((max(xs) + 0.5) / STEP) + 1):
            for gy in range(int((min(ys) - 0.5) / STEP), int((max(ys) + 0.5) / STEP) + 1):
                if 0 <= gx < NX and 0 <= gy < NY:
                    if point_in_poly(gx * STEP, gy * STEP, poly):
                        g.pour[(gx, gy)] = pnet
    # board margin
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


def route_net(g, net, sources, targets, allow_via_targets):
    """A* from source cells to target set. States: (layer, x, y)."""
    tset = targets
    if not tset:
        return None
    txs = [t[0] for t in tset]
    tys = [t[1] for t in tset]
    bx1, bx2, by1, by2 = min(txs), max(txs), min(tys), max(tys)

    def h(x, y):
        dx = bx1 - x if x < bx1 else (x - bx2 if x > bx2 else 0)
        dy = by1 - y if y < by1 else (y - by2 if y > by2 else 0)
        return (dx + dy) * STEP * 0.98

    openq = []
    best = {}
    for (L, x, y) in sources:
        s = (L, x, y)
        best[s] = 0
        heapq.heappush(openq, (h(x, y), 0, s, None))
    came = {}
    seen_goal = None
    expansions = 0
    while openq and expansions < 500000:
        f, cost, state, parent = heapq.heappop(openq)
        if best.get(state, 1e18) < cost - 1e-9:
            continue
        came[state] = parent
        L, x, y = state
        expansions += 1
        if (x, y, L) in tset or ((x, y, 2) in tset and g.via_ok((x, y), net)):
            seen_goal = state
            if (x, y, L) not in tset:          # needs a via into a plane
                came[("VIA", x, y)] = state
                seen_goal = ("VIA", x, y)
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx_, ny_ = x + dx, y + dy
            if not (0 <= nx_ < NX and 0 <= ny_ < NY):
                continue
            c = (nx_, ny_)
            if not g.free(L, c, net):
                continue
            step_cost = STEP * (1.4142 if dx and dy else 1.0)
            if L == 0:
                pnet = g.pour.get(c)
                if pnet is not None and pnet != net:
                    step_cost *= 6.0
            # direction bias: F horizontal, B vertical
            if L == 0 and dy and not dx:
                step_cost *= 1.25
            if L == 1 and dx and not dy:
                step_cost *= 1.25
            ncost = cost + step_cost
            ns = (L, nx_, ny_)
            if ncost < best.get(ns, 1e18) - 1e-9:
                best[ns] = ncost
                heapq.heappush(openq, (ncost + h(nx_, ny_), ncost, ns, state))
        # layer change
        if g.via_ok((x, y), net):
            ns = (1 - L, x, y)
            ncost = cost + 3.0
            if ncost < best.get(ns, 1e18) - 1e-9:
                best[ns] = ncost
                heapq.heappush(openq, (ncost + h(x, y), ncost, ns, state))
    if seen_goal is None:
        return None
    # reconstruct
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

    # figure out unconnected pad pairs from connectivity
    conn = board.GetConnectivity()
    todo = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            net = pad.GetNetname()
            if not net or net.startswith("unconnected"):
                continue
            todo.setdefault(net, []).append(pad)

    g, net_copper = build_grid(board)

    # plane/zone target rectangles per net
    plane_regions = {}
    for pname, poly in PWR_POURS.items():
        pnet = "PGND" if pname.startswith("PGND") else pname
        plane_regions.setdefault(pnet, []).append((poly, 0))       # F.Cu pour
    for net, poly in IN2_PATCHES:
        plane_regions.setdefault(net, []).append((poly, 2))        # via into plane
    plane_regions.setdefault("PGND", []).append(
        ([(1, 1), (W - 1, 1), (W - 1, 30.5), (1, 30.5)], 2))
    plane_regions.setdefault("AGND", []).append(
        ([(31, 32), (W - 1, 32), (W - 1, H - 1), (31, H - 1)], 2))
    plane_regions.setdefault("5V0", []).append(
        ([(1, 1), (29, 1), (29, H - 1), (1, H - 1)], 2))
    plane_regions.setdefault("5V0", []).append(
        ([(93, 19), (102, 19), (102, 67), (93, 67)], 2))
    plane_regions.setdefault("5V0", []).append(
        ([(31, 57), (55, 57), (55, H - 1), (31, H - 1)], 2))
    plane_regions.setdefault("3V3", []).append(
        ([(57, 32), (W - 1, 32), (W - 1, H - 1), (57, H - 1)], 2))

    def pad_cells(pad):
        x = pcbnew.ToMM(pad.GetPosition().x) - ORG[0]
        y = pcbnew.ToMM(pad.GetPosition().y) - ORG[1]
        gx, gy = round(x / STEP), round(y / STEP)
        L = 0 if pad.IsOnLayer(pcbnew.F_Cu) else 1
        # source cells along the pad long axis (safe escape corridor)
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
        return srcs, (L, gx, gy), (x, y)

    def add_track_path(net, path, entry_xy, exit_xy):
        pts = []
        for s in path:
            if s[0] == "VIA":
                continue
            pts.append(s)
        # emit segments, collapsing collinear runs; add vias on layer change
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
        # entry/exit exact stubs (grid point -> pad centre)
        for (gxy, pxy, L) in (entry_xy, exit_xy):
            if gxy is None:
                continue
            if abs(gxy[0] - pxy[0]) > 1e-3 or abs(gxy[1] - pxy[1]) > 1e-3:
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(P(*gxy))
                t.SetEnd(P(*pxy))
                t.SetWidth(FromMM(TRACK_W))
                t.SetLayer(lay[L])
                t.SetNetCode(netcode)
                board.Add(t)
        return items

    routed = failed = 0
    fails = []
    for net in sorted(todo, key=lambda n: len(todo[n])):
        pads = todo[net]
        # connected component seeds: first pad + everything conn says is joined
        # simple approach: route pad i to the union of (pads[0..i-1] cells +
        # routed copper of this net + plane regions)
        regions = plane_regions.get(net, [])
        base_targets = set()
        for poly, kind in regions:
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            for gx in range(int(min(xs) / STEP) + 2, int(max(xs) / STEP) - 1):
                for gy in range(int(min(ys) / STEP) + 2, int(max(ys) / STEP) - 1):
                    if point_in_poly(gx * STEP, gy * STEP, poly):
                        base_targets.add((gx, gy, kind))
        done_cells = set(base_targets)
        done_cells |= net_copper.get(net, set())
        for i, pad in enumerate(pads):
            src, (L, gx, gy), (px, py) = pad_cells(pad)
            if i == 0 and not done_cells:
                done_cells.add((gx, gy, L))
                continue
            if any(s in done_cells for s in ((sx, sy, sl) for sl, sx, sy in src)):
                continue
            path = route_net(g, net, src, done_cells, True)
            if path is None:
                failed += 1
                fails.append((net, pcbnew.Cast_to_FOOTPRINT(pad.GetParentFootprint()).GetReference(), "no path"))
                done_cells.add((gx, gy, L))
                continue
            start = path[0]
            end = path[-1] if path[-1][0] != "VIA" else path[-2]
            items = add_track_path(
                net, path,
                ((start[1] * STEP, start[2] * STEP), (px, py), start[0]),
                (None, None, None))
            routed += 1
            # add new copper to grid + targets
            for it in items:
                if it[0] == "T":
                    cells = cells_for_seg(*it[2], *it[3], TRACK_W / 2 + CLEAR + TRACK_W / 2)
                    g.add(it[1], cells, net)
                    for s in cells:
                        pass
                    for cx, cy in cells_for_seg(*it[2], *it[3], 0.01):
                        done_cells.add((cx, cy, it[1]))
                else:
                    cells = cells_for_disc(*it[1], VIA_D / 2 + CLEAR + TRACK_W / 2)
                    g.add(0, cells, net)
                    g.add(1, cells, net)
                    g.add_via(cells_for_disc(*it[1], VIA_D / 2 + 0.2 + CLEAR), net)
            done_cells.add((gx, gy, L))

    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"autoroute: {routed} routed, {failed} failed")
    for f in fails[:20]:
        print("  FAIL", f)


if __name__ == "__main__":
    main()
