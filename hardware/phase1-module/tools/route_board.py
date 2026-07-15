"""Routing pass 1 (deterministic): heat patches, vias, critical hand routes.

Run AFTER gen_board.py (loads its output in place):
    python3 route_board.py
Adds:
  - In2.Cu same-net patches under the F.Cu power pours (heat + current)
  - thermal via arrays on FET tabs / L1 pads (F pour -> In2 patch)
  - EP vias (U3, U6), NT1 star-tie vias, J1/J4 PGND via clusters
  - seam-aware power-pad vias (PGND/AGND -> In1+B fills, 5V0/3V3 -> In2)
  - critical tracks: Kelvin sense pair, HO/LO/SW gate routes, BST, ILIM,
    VIN corridor, snubber, VBUS input link, aux VBUS_F trunk, 3V3 trunk
  - PGND/AGND stitching grids (collision-filtered)
autoroute.py then handles the remaining signal nets.
"""
import os

import pcbnew
from pcbnew import FromMM, VECTOR2I

from gen_board import ORG, W, H, SEAM, AUXW, POCKET, PWR_POURS, P, point_in_poly

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "..", "phase1-module.kicad_pcb")

VIA_D, VIA_DRILL = 0.6, 0.3

# ---- In2 same-net heat/current patches (priority 2 beats 5V0 column/pocket)
IN2_PATCHES = [
    ("VBUS_F",   [(13.0, 5.5), (49.0, 5.5), (49.0, 15.5), (13.0, 15.5)]),
    ("SW",       [(47.5, 9.0), (56.5, 9.0), (56.5, 26.0), (47.5, 26.0)]),
    ("VOUT_INT", [(65.0, 5.5), (91.0, 5.5), (91.0, 15.5), (65.0, 15.5)]),
    ("VOUT_SW",  [(97.8, 5.5), (104.3, 5.5), (104.3, 15.5), (97.8, 15.5)]),
    ("DISC_SRC", [(105.9, 5.5), (109.5, 5.5), (109.5, 15.5), (105.9, 15.5)]),
    ("VOUT",     [(110.9, 5.5), (119.0, 5.5), (119.0, 28.5), (110.9, 28.5)]),
]

# ---- explicit vias: (net, x, y)
VIAS = [
    # FET tab / L1 thermal arrays (F.Cu pour <-> In2 patch)
    *[("VBUS_F", x, y) for x in (45.4, 47.0, 48.6) for y in (9.0, 11.0)],
    *[("SW", x, y) for x in (47.9, 49.5) for y in (21.8, 24.2)],
    *[("SW", 55.9, y) for y in (12.0, 18.0, 24.5)],
    *[("VOUT_INT", 65.8, y) for y in (11.0, 14.5)],       # L1.2 / pour tie
    *[("VOUT_SW", x, y) for x in (100.5, 102.0, 103.5) for y in (9.0, 11.0)],
    *[("DISC_SRC", x, y) for x in (106.6, 108.6) for y in (13.5,)],
    *[("VOUT", x, y) for x in (111.2, 112.7, 114.2) for y in (9.0, 11.0)],
    # exposed pads (AGND): U3 at (47,36), U6 at (107,22) [AGND pocket]
    *[("AGND", x, y) for x in (46.55, 47.45) for y in (35.55, 36.45)],
    *[("AGND", x, 22.0) for x in (106.6, 107.4)],
    # NT1 star tie
    ("AGND", 96.6, 32.6), ("PGND", 98.6, 29.8),
    # connector grounds
    ("PGND", 3.6, 16.4), ("PGND", 6.4, 16.4),              # J1.2
    ("PGND", 115.2, 20.6), ("PGND", 117.8, 20.6),          # J4.2
    # output PGND band + top strip + bar ties into In1
    *[("PGND", x, 2.4) for x in (70.0, 78.0, 86.0)],       # PGND_TOP strip
    *[("PGND", x, 30.9) for x in (40.5, 44.0, 47.5, 54.0)],  # bar
    # VBUS_F pour -> In2 patch stitching (also carries aux feed)
    *[("VBUS_F", x, y) for x in (16.0, 24.0, 32.0, 40.0) for y in (6.5, 13.0)],
    ("VBUS_F", 13.0, 14.5),                                # aux trunk tap
    ("VBUS_F", 9.0, 28.6),                                 # aux trunk drop
    *[("VOUT_INT", x, y) for x in (70.0, 78.0, 86.0) for y in (6.5, 13.0)],
]

# ---- critical tracks: (net, layer, width_mm, [(x,y)...])
F, B = "F.Cu", "B.Cu"
TRACKS = [
    # input link J1.1 -> F1.1 (VBUS)
    ("VBUS", F, 2.5, [(5.0, 13.0), (5.0, 8.2), (6.7, 6.5), (10.8, 6.5)]),
    # J1.2 / J4.2 pad stubs to their via pairs
    ("PGND", F, 2.0, [(5.0, 18.0), (3.6, 19.6)]),
    ("PGND", F, 2.0, [(5.0, 18.0), (6.4, 19.6)]),
    ("PGND", F, 2.0, [(116.5, 22.0), (115.2, 20.6)]),
    ("PGND", F, 2.0, [(116.5, 22.0), (117.8, 20.6)]),
    # Kelvin sense pair (0.3 mm): R30 inner edges -> U4 -> U5
    ("VOUT_INT", F, 0.3, [(92.2, 10.0), (92.59, 12.0), (92.59, 21.53)]),
    ("VOUT_INT", F, 0.3, [(92.59, 21.53), (91.6, 22.5), (91.6, 31.0)]),
    ("VOUT_INT", F, 0.24, [(91.6, 31.0), (93.5, 31.9), (93.5, 33.8)]),
    ("VOUT_SW", F, 0.3, [(96.8, 10.0), (96.6, 12.0), (96.6, 19.0),
                         (97.6, 20.0), (97.6, 26.8), (96.8, 27.9),
                         (92.59, 27.9), (92.59, 26.47)]),
    ("VOUT_SW", F, 0.24, [(94.0, 27.9), (94.0, 33.8)]),
    # NT1 stubs to its vias
    ("AGND", F, 0.5, [(97.0, 31.2), (96.6, 32.6)]),
    ("PGND", F, 0.5, [(98.0, 31.2), (98.6, 29.8)]),
    # LM5145 right-column fan-out: short stubs to a staggered via fan,
    # then B.Cu runs with non-crossing verticals.
    ("SW", F, 0.24, [(48.65, 34.25), (49.6, 32.35)]),
    ("SW", B, 0.64, [(49.6, 32.35), (49.0, 31.5), (49.0, 26.0)]),
    ("HO_G", F, 0.24, [(48.65, 34.75), (49.9, 34.75), (50.4, 33.9)]),
    ("HO_G", B, 0.64, [(50.4, 33.9), (50.6, 32.9), (50.6, 6.8), (50.58, 6.8)]),
    ("HO_G", F, 0.64, [(50.58, 6.8), (50.58, 8.09)]),
    ("PS_BST", F, 0.24, [(48.65, 35.25), (51.6, 35.25)]),
    ("PS_BST", B, 0.4, [(51.6, 35.25), (51.6, 36.6), (54.9, 36.6), (54.9, 28.25)]),
    ("PS_BST", F, 0.4, [(54.9, 28.25), (55.3, 28.25)]),
    ("LO_G", F, 0.24, [(48.65, 37.25), (50.6, 37.25)]),
    ("LO_G", B, 0.64, [(50.6, 37.25), (45.2, 37.9), (45.2, 28.3), (44.42, 26.9)]),
    ("LO_G", F, 0.64, [(44.42, 26.9), (44.42, 24.91)]),
    # PGND pin 12 escapes east around the fan into the bar
    ("PGND", F, 0.24, [(48.65, 37.75), (48.65, 38.9)]),
    ("PGND", F, 0.4, [(48.65, 38.9), (52.6, 38.9), (53.9, 37.6), (53.9, 31.5)]),
    # C19 ground return joins the C29 B.Cu run
    ("PGND", F, 0.4, [(48.95, 41.0), (49.6, 41.6)]),
    ("PGND", B, 0.5, [(49.6, 41.6), (53.4, 40.6)]),
    # ILIM: R28.1 -> pin11 (below the comp cluster)
    ("PS_ILIM", F, 0.3, [(57.6, 28.25), (57.6, 43.2), (47.75, 43.2), (47.75, 38.15)]),
    # snubber link
    ("SNUB", F, 0.4, [(52.0, 28.02), (50.9, 29.0), (50.9, 29.58)]),
    # VIN corridor: R29.2 down to pin20 (C28.1 joins via autoroute)
    ("PS_VIN", F, 0.6, [(46.2, 17.65), (46.2, 18.4)]),
    ("PS_VIN", B, 0.6, [(46.2, 18.4), (46.2, 32.6)]),
    ("PS_VIN", F, 0.6, [(46.2, 32.6), (47.75, 32.9), (47.75, 33.85)]),
    # C29/C19 PGND returns via B.Cu to the PGND region
    ("PGND", F, 0.5, [(52.75, 41.5), (53.4, 40.6)]),
    ("PGND", B, 0.5, [(53.4, 40.6), (55.8, 40.6), (55.8, 29.5)]),
    # aux VBUS_F trunk (pour via -> B.Cu -> aux corner)
    ("VBUS_F", B, 1.5, [(13.0, 14.5), (11.0, 17.0), (11.0, 26.5), (9.0, 28.6)]),
    ("VBUS_F", F, 1.0, [(9.0, 28.6), (6.72, 30.6), (6.72, 32.2)]),
    # 3V3 trunk: U9 output east to the In2 3V3 zone
    ("3V3", F, 1.2, [(14.65, 53.0), (28.0, 53.0), (31.0, 50.5)]),
    ("3V3", F, 0.8, [(14.65, 53.0), (14.02, 58.7), (14.02, 59.5)]),
]
EXTRA_VIAS = [
    ("SW", 49.6, 32.35), ("SW", 49.0, 26.0),
    ("HO_G", 50.4, 33.9), ("HO_G", 50.58, 6.8),
    ("PS_BST", 51.6, 35.25), ("PS_BST", 54.9, 28.25),
    ("LO_G", 50.6, 37.25), ("LO_G", 44.42, 26.9),
    ("PS_VIN", 46.2, 18.4), ("PS_VIN", 46.2, 32.6),
    ("PGND", 53.4, 40.6), ("PGND", 55.8, 29.5), ("PGND", 49.6, 41.6),
    ("3V3", 31.0, 50.5),
]

# ---- stitching grids (collision-filtered at runtime)
STITCH = (
    [("PGND", x, y) for x in range(14, 45, 6) for y in (19.5, 24.0, 28.5)] +
    [("PGND", x, y) for x in range(68, 91, 6) for y in (19.5, 24.0, 28.5)] +
    [("PGND", x, y) for x in (3, 9, 15, 21, 27) for y in (44, 52, 60, 68, 76)] +
    [("PGND", 3, y) for y in (4, 10, 16, 22, 28, 36)] +
    [("AGND", x, y) for x in range(33, 118, 11) for y in (33.5, 48.5, 57.5, 73.5)]
)


def in1_net_at(x, y):
    if point_in_poly(x, y, POCKET):
        return "AGND"
    if y < SEAM or x < AUXW:
        return "PGND"
    return "AGND"


def in2_net_at(x, y):
    for net, poly in IN2_PATCHES:
        if point_in_poly(x, y, poly):
            return net
    if x < AUXW:
        return "5V0"
    if point_in_poly(x, y, [(92, 18), (103, 18), (103, 68), (92, 68)]):
        return "5V0"
    if point_in_poly(x, y, [(AUXW, 56), (56, 56), (56, H - 0.5), (AUXW, H - 0.5)]):
        return "5V0"
    if y > SEAM:
        return "3V3"
    return None


def main():
    board = pcbnew.LoadBoard(BOARD)
    nets = {ni.GetNetname(): ni for ni in board.GetNetsByName().values()
            if ni.GetNetname()}

    layer_id = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}

    def add_via(net, x, y):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(P(x, y))
        v.SetDrill(FromMM(VIA_DRILL))
        v.SetWidth(FromMM(VIA_D))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNetCode(nets[net].GetNetCode())
        board.Add(v)

    def add_track(net, layer, width, pts):
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(P(*a))
            t.SetEnd(P(*b))
            t.SetWidth(FromMM(width))
            t.SetLayer(layer_id[layer])
            t.SetNetCode(nets[net].GetNetCode())
            board.Add(t)

    # In2 patches
    for net, poly in IN2_PATCHES:
        z = pcbnew.ZONE(board)
        z.SetLayer(pcbnew.In2_Cu)
        z.SetNetCode(nets[net].GetNetCode())
        z.SetAssignedPriority(2) if hasattr(z, "SetAssignedPriority") else z.SetPriority(2)
        o = z.Outline()
        o.NewOutline()
        for x, y in poly:
            o.Append(FromMM(ORG[0] + x), FromMM(ORG[1] + y))
        z.SetMinThickness(FromMM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        board.Add(z)

    for net, x, y in VIAS + EXTRA_VIAS:
        add_via(net, x, y)
    for net, layer, width, pts in TRACKS:
        add_track(net, layer, width, pts)

    # occupancy for collision-filtered via placement
    def seg_dist(px, py, ax, ay, bx, by):
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy
        t = 0 if L2 == 0 else max(0, min(1, ((px - ax) * vx + (py - ay) * vy) / L2))
        dx, dy = px - (ax + t * vx), py - (ay + t * vy)
        return (dx * dx + dy * dy) ** 0.5

    def too_close(x, y, net, dist=0.85):
        p = P(x, y)
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetname() == net:
                    continue
                d = (pad.GetPosition() - p).EuclideanNorm()
                if d < FromMM(dist + max(pcbnew.ToMM(pad.GetSize().x),
                                         pcbnew.ToMM(pad.GetSize().y)) / 2):
                    return True
        for t in board.GetTracks():
            if t.GetNetname() == net:
                continue
            ax = pcbnew.ToMM(t.GetStart().x) - ORG[0]
            ay = pcbnew.ToMM(t.GetStart().y) - ORG[1]
            bx = pcbnew.ToMM(t.GetEnd().x) - ORG[0]
            by = pcbnew.ToMM(t.GetEnd().y) - ORG[1]
            if seg_dist(x, y, ax, ay, bx, by) < dist + pcbnew.ToMM(t.GetWidth()) / 2:
                return True
        return False

    # seam-aware power-pad vias (PGND/AGND/5V0/3V3)
    all_vias = [(v.GetNetname(), pcbnew.ToMM(v.GetPosition().x) - ORG[0],
                 pcbnew.ToMM(v.GetPosition().y) - ORG[1])
                for v in board.GetTracks() if isinstance(v, pcbnew.PCB_VIA)]

    def stub_hits_pad(x1, y1, x2, y2, net, width):
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetname() == net:
                    continue
                px = pcbnew.ToMM(pad.GetPosition().x) - ORG[0]
                py = pcbnew.ToMM(pad.GetPosition().y) - ORG[1]
                half = max(pcbnew.ToMM(pad.GetSize().x), pcbnew.ToMM(pad.GetSize().y)) / 2
                if seg_dist(px, py, x1, y1, x2, y2) < half + width / 2 + 0.25:
                    return True
        return False

    placed = 0
    for fp in board.GetFootprints():
        fx = pcbnew.ToMM(fp.GetPosition().x) - ORG[0]
        fy = pcbnew.ToMM(fp.GetPosition().y) - ORG[1]
        for pad in fp.Pads():
            net = pad.GetNetname()
            if net not in ("PGND", "AGND", "5V0", "3V3"):
                continue
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            x = pcbnew.ToMM(pad.GetPosition().x) - ORG[0]
            y = pcbnew.ToMM(pad.GetPosition().y) - ORG[1]
            plane = in1_net_at(x, y) if net in ("PGND", "AGND") else in2_net_at(x, y)
            if plane != net:
                continue        # wrong region -> autorouter's problem
            if any(n == net and (vx - x) ** 2 + (vy - y) ** 2 < 1.6 ** 2
                   for n, vx, vy in all_vias):
                continue        # a same-net via already serves this spot
            # outward direction from footprint centre, dominant axis first
            ox, oy = x - fx, y - fy
            if abs(ox) >= abs(oy):
                cands = [(1.1 if ox >= 0 else -1.1, 0),
                         (1.0 if ox >= 0 else -1.0, 0.8),
                         (1.0 if ox >= 0 else -1.0, -0.8)]
            else:
                cands = [(0, 1.1 if oy >= 0 else -1.1),
                         (0.8, 1.0 if oy >= 0 else -1.0),
                         (-0.8, 1.0 if oy >= 0 else -1.0)]
            for dx, dy in cands:
                vx, vy = x + dx, y + dy
                if not (0.8 < vx < W - 0.8 and 0.8 < vy < H - 0.8):
                    continue
                if too_close(vx, vy, net):
                    continue
                vplane = in1_net_at(vx, vy) if net in ("PGND", "AGND") else in2_net_at(vx, vy)
                if vplane != net:
                    continue
                if stub_hits_pad(x, y, vx, vy, net, 0.4):
                    continue
                pour_conflict = False
                for pname, poly in PWR_POURS.items():
                    pnet = "PGND" if pname.startswith("PGND") else pname
                    if pnet != net and point_in_poly(vx, vy, poly):
                        pour_conflict = True
                        break
                if pour_conflict:
                    continue
                add_via(net, vx, vy)
                add_track(net, "F.Cu", 0.4, [(x, y), (vx, vy)])
                all_vias.append((net, vx, vy))
                placed += 1
                break

    # stitching grids
    stitched = 0
    for net, x, y in STITCH:
        if in1_net_at(x, y) != net:
            continue
        conflict = False
        for pname, poly in PWR_POURS.items():
            pnet = "PGND" if pname.startswith("PGND") else pname
            if pnet != net and point_in_poly(x, y, poly):
                conflict = True
                break
        if conflict or too_close(x, y, net, dist=1.0):
            continue
        if any(n == net and (vx - x) ** 2 + (vy - y) ** 2 < 2.0 ** 2
               for n, vx, vy in all_vias):
            continue
        add_via(net, x, y)
        all_vias.append((net, x, y))
        stitched += 1

    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"route_board: {len(VIAS) + len(EXTRA_VIAS)} fixed vias, {placed} pad vias, "
          f"{stitched} stitches, {len(TRACKS)} track runs, {len(IN2_PATCHES)} In2 patches")


if __name__ == "__main__":
    main()
