"""Routing pass 1 (deterministic): In2 patches, vias, critical hand routes.

Phase-2 adaptation of phase-1 route_board.py. Run AFTER gen_board.py:
    python3 route_board.py
Adds In2 heat/current patches, thermal via arrays, EP/NT1/connector vias,
strap routes for the placement-stage strapped pads, the critical hand
routes, seam-aware power-pad vias and stitching. autoroute handles the rest.

B.Cu lane plan (same-layer crossings checked by construction; F.Cu channels
noted). NE corridor east of U3 (northbound verticals):
  x80.0 G_HS_A | x80.7 CS1 | x81.4 VOUT1 | x82.4 SW1 | x83.4 BST_A
NE horizontals: BST_A y38.55 | BST_B y39.0 | G_LS_A y39.5 (west) |
  CS1 y11.8 / VOUT1 y12.6 (north, nested)
West group: G_HS_B entirely on F (x68.3 channel) | SW2 on F (x71.8) |
  G_LS_B B x74.9->69.8 | BST_B B y39.0 -> x80.9
South of U3: CS2 on F (y33.725 channel -> x95.2) | VOUT2 F (y31.3 channel)
  + B dive x98.3 | PS_VIN B x60.6 / y23.6 / x77.0
Far east: DISC_GATE trunk threads the FET tab gaps (x118.68/x120.22) |
  U5 sense pair x115.9 (VOUT_SW) / x116.6 (VOUT_INT)
"""
import os

import pcbnew
from pcbnew import FromMM, VECTOR2I

from gen_board import (ORG, W, H, SEAM, POCKET_MID, POCKET_OUT, PWR_POURS, P,
                       point_in_poly)

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "..", "phase2-module.kicad_pcb")

VIA_D, VIA_DRILL = 0.6, 0.3

IN2_PATCHES = [
    ("VBUS_FUSED", [(26.5, 13.0), (42.5, 13.0), (42.5, 18.1), (26.5, 18.1)]),
    ("HS_SENSE",   [(45.0, 3.0), (56.0, 3.0), (56.0, 13.2), (45.0, 13.2)]),
    ("VBUS_P",     [(54.5, 3.5), (71.8, 3.5), (71.8, 14.5), (63.4, 14.5),
                    (63.4, 55.5), (71.8, 55.5), (71.8, 66.5), (54.5, 66.5)]),
    ("SW1",        [(72.0, 8.0), (82.4, 8.0), (82.4, 25.0), (72.0, 25.0)]),
    ("SW2",        [(72.0, 45.0), (82.4, 45.0), (82.4, 62.0), (72.0, 62.0)]),
    ("PH_CS_A",    [(89.0, 7.0), (95.8, 7.0), (95.8, 20.0), (89.0, 20.0)]),
    ("PH_CS_B",    [(89.0, 50.0), (95.8, 50.0), (95.8, 63.0), (89.0, 63.0)]),
    ("VOUT_INT",   [(99.5, 4.5), (109.5, 4.5), (109.5, 58.0), (114.5, 58.0),
                    (114.5, 67.5), (99.5, 67.5)]),
    ("VOUT_SW",    [(111.2, 8.5), (115.5, 8.5), (115.5, 30.5), (111.2, 30.5)]),
    ("DISC_SRC",   [(117.5, 8.5), (121.9, 8.5), (121.9, 45.5), (123.5, 45.5),
                    (123.5, 52.0), (113.9, 52.0), (113.9, 45.5),
                    (117.5, 45.5)]),
    ("VOUT",       [(123.3, 8.5), (128.8, 8.5), (128.8, 53.5), (123.3, 53.5)]),
    ("VOUT",       [(117.5, 34.5), (122.9, 34.5), (122.9, 45.2), (117.5, 45.2)]),
]

VIAS = [
    *[("HS_SENSE", x, y) for x in (50.0, 53.0) for y in (6.0, 11.0)],
    ("HS_SENSE", 46.5, 12.5),
    *[("VBUS_FUSED", x, 15.6) for x in (28.5, 33.0)],
    *[("VBUS_P", x, y) for x in (69.2, 71.2) for y in (7.8, 10.2)],
    *[("VBUS_P", x, y) for x in (69.2, 71.2) for y in (59.8, 62.2)],
    *[("VBUS_P", 58.5, y) for y in (5.5, 12.0)],
    *[("VBUS_P", 62.4, y) for y in (17.2, 21.3, 43.0, 50.0)],
    *[("VBUS_P", 56.5, y) for y in (24.0, 43.0, 58.0, 64.5)],
    *[("SW1", x, y) for x in (76.0, 79.0) for y in (10.0, 13.0)],
    *[("SW1", x, y) for x in (73.0, 74.6) for y in (20.3, 22.6)],
    ("SW1", 77.6, 16.4),
    *[("SW2", x, y) for x in (76.8, 79.4) for y in (58.2, 60.6)],
    *[("SW2", x, y) for x in (73.0, 74.6) for y in (45.6, 47.9)],
    ("SW2", 77.6, 53.6),
    *[("PH_CS_A", x, y) for x in (90.5, 93.2) for y in (11.0, 16.5)],
    *[("PH_CS_B", x, y) for x in (90.5, 93.2) for y in (53.5, 59.0)],
    *[("VOUT_INT", 100.6, y) for y in (6.0, 16.0, 33.0, 42.0, 51.0)],
    *[("VOUT_INT", 108.8, y) for y in (6.0, 16.0, 42.5, 51.0)],
    *[("VOUT_SW", x, y) for x in (112.3, 114.2) for y in (12.0, 19.0)],
    ("DISC_SRC", 120.6, 12.0), ("DISC_SRC", 118.4, 24.4),
    ("DISC_SRC", 118.3, 27.5), ("DISC_SRC", 121.3, 27.5),
    *[("VOUT", x, y) for x in (124.4, 126.6) for y in (11.0, 18.0)],
    *[("VOUT", 125.2, y) for y in (32.6, 43.5)],
    ("VOUT", 128.6, 49.0),
    *[("AGND", x, y) for x in (75.55, 76.45) for y in (34.55, 35.45)],
    *[("AGND", x, 50.7) for x in (118.75, 119.25)],
    ("AGND", 109.0, 71.6), ("PGND", 110.0, 66.7),
    ("PGND", 6.2, 6.5), ("PGND", 8.8, 6.5),
    ("PGND", 119.3, 43.4), ("PGND", 121.7, 43.4),
]

F, B = "F.Cu", "B.Cu"
TRACKS = [
    # ---- straps from the placement stage
    ("VBUS_FUSED", F, 1.2, [(36.9, 21.15), (36.9, 17.8)]),            # D5.1
    ("VOUT_INT", F, 1.0, [(113.8, 66.3), (112.9, 65.7)]),             # C36.1
    ("VOUT_INT", F, 0.8, [(101.04, 87.5), (100.6, 86.8)]),            # R27.1
    ("VOUT_INT", B, 0.8, [(100.6, 86.8), (100.6, 66.9)]),
    ("PGND", F, 0.8, [(106.96, 87.5), (107.4, 86.7)]),                # R27.2
    ("PGND", B, 0.8, [(107.4, 86.7), (107.4, 67.0)]),
    # ---- NT1 tie
    ("AGND", F, 0.5, [(109.0, 70.5), (109.0, 71.6)]),
    ("PGND", F, 0.5, [(110.0, 70.5), (110.0, 66.7)]),
    # ---- J1.2 / J4.2 stubs
    ("PGND", F, 2.0, [(7.5, 8.4), (6.2, 6.5)]),
    ("PGND", F, 2.0, [(7.5, 8.4), (8.8, 6.5)]),
    ("PGND", F, 2.0, [(120.5, 41.8), (119.3, 43.4)]),
    ("PGND", F, 2.0, [(120.5, 41.8), (121.7, 43.4)]),
    # ---- phase A gate fan-out (NE corridor)
    ("G_HS_A", F, 0.3, [(78.9, 36.25), (79.45, 36.5), (78.9, 36.75)]),
    ("G_HS_A", F, 0.3, [(79.45, 36.5), (79.55, 35.7), (79.9, 35.3)]),
    ("G_HS_A", B, 0.64, [(79.9, 35.3), (80.3, 34.9), (80.3, 7.6),
                         (75.0, 7.6), (74.6, 7.2)]),
    ("G_HS_A", F, 0.4, [(74.6, 7.2), (75.08, 7.095)]),
    ("SW1", F, 0.3, [(78.9, 37.25), (79.9, 37.55)]),
    ("SW1", B, 0.4, [(79.9, 37.55), (82.55, 37.55), (82.55, 24.8)]),
    ("G_LS_A", F, 0.3, [(77.25, 37.9), (77.5, 38.15), (77.75, 37.9)]),
    ("G_LS_A", B, 0.3, [(77.5, 38.15), (77.5, 39.7), (70.2, 39.7),
                        (70.2, 26.6), (68.6, 25.5)]),
    ("G_LS_A", F, 0.4, [(68.6, 25.5), (68.92, 23.905)]),
    ("BST_A", F, 0.3, [(78.25, 37.9), (78.25, 38.25), (79.4, 38.25),
                       (79.9, 38.5)]),
    ("BST_A", B, 0.3, [(79.9, 38.5), (83.55, 38.5), (83.55, 27.6)]),
    ("BST_A", F, 0.3, [(83.55, 27.6), (81.05, 27.0), (81.0, 26.975)]),
    # ---- phase A current sense pair (CS1 = PH_CS_A, VOUT1 = VOUT_INT)
    ("PH_CS_A", F, 0.3, [(78.9, 34.25), (80.6, 34.25), (80.85, 34.1)]),
    ("PH_CS_A", B, 0.3, [(80.85, 34.1), (81.05, 33.8), (81.05, 11.8),
                         (95.7, 11.8)]),
    ("PH_CS_A", F, 0.3, [(95.7, 11.8), (96.19, 11.675)]),
    ("VOUT_INT", F, 0.3, [(78.9, 34.75), (81.75, 34.75)]),
    ("VOUT_INT", B, 0.3, [(81.75, 34.75), (81.7, 34.4), (81.7, 12.6),
                          (99.6, 12.6)]),
    # ---- phase B gate fan-out (west group)
    ("G_HS_B", F, 0.3, [(73.1, 36.25), (72.4, 36.5), (73.1, 36.75)]),
    ("G_HS_B", F, 0.3, [(72.4, 36.5), (68.05, 36.5), (68.05, 57.0),
                        (75.9, 57.0), (75.9, 58.6), (75.08, 59.095)]),
    ("SW2", F, 0.4, [(73.1, 37.25), (72.4, 37.85), (71.8, 38.5),
                     (71.8, 43.6), (72.3, 44.6)]),
    ("G_LS_B", F, 0.3, [(74.25, 37.9), (74.5, 38.4), (74.75, 37.9)]),
    ("G_LS_B", F, 0.3, [(74.5, 38.4), (75.9, 40.55), (76.3, 41.05)]),
    ("G_LS_B", B, 0.4, [(76.3, 41.05), (76.3, 41.3), (69.6, 47.4),
                        (68.6, 50.4), (68.6, 51.0)]),
    ("G_LS_B", F, 0.4, [(68.6, 51.0), (68.92, 49.905)]),
    ("BST_B", F, 0.3, [(73.75, 37.9), (73.75, 39.6), (73.9, 40.35)]),
    ("BST_B", B, 0.3, [(73.9, 40.35), (80.9, 40.35), (80.9, 41.9)]),
    ("BST_B", F, 0.3, [(80.9, 41.9), (81.0, 42.945)]),
    # ---- phase B current sense pair (F channels through the pocket)
    ("PH_CS_B", F, 0.3, [(73.1, 33.75), (72.3, 33.6)]),
    ("PH_CS_B", B, 0.3, [(72.3, 33.6), (72.9, 33.0), (78.8, 31.55),
                         (79.4, 31.0)]),
    ("PH_CS_B", F, 0.25, [(79.4, 31.0), (80.3, 31.3), (94.3, 31.3),
                          (95.2, 32.2), (95.2, 55.1), (96.05, 55.1)]),
    
    # ---- PS_VIN corridor: R29.2 -> C28.1 (pin 25 joins via autoroute)
    ("PS_VIN", F, 0.5, [(60.0, 56.225), (59.6, 55.6)]),
    ("PS_VIN", B, 0.5, [(59.6, 55.6), (59.6, 23.6), (74.6, 23.6)]),
    ("PS_VIN", B, 0.4, [(74.6, 23.6), (77.0, 26.0), (77.0, 29.5),
                        (77.2, 29.9)]),
    ("PS_VIN", F, 0.4, [(77.2, 29.9), (76.5, 30.3), (76.0, 30.49)]),
    # ---- U4 Kelvin from R30/R34 (INA240)
    ("VOUT_INT", F, 0.3, [(105.55, 23.5), (106.9, 25.5), (106.9, 29.4),
                          (107.3, 30.0)]),
    ("VOUT_SW", F, 0.3, [(110.7, 24.85), (110.5, 25.4)]),
    ("VOUT_SW", B, 0.3, [(110.5, 25.4), (102.6, 25.4), (101.2, 26.6),
                         (101.2, 28.6)]),
    ("VOUT_SW", F, 0.3, [(101.2, 28.6), (101.9, 29.6), (101.9, 30.0)]),
    # ---- U5 senses (INA228)
    ("VOUT", F, 0.25, [(121.925, 57.6), (122.4, 57.6), (122.4, 59.9),
                      (127.9, 59.9), (127.9, 53.6)]),
    ("VOUT_SW", F, 0.3, [(121.2, 57.1), (122.2, 57.1), (122.2, 56.6)]),
    ("VOUT_SW", B, 0.3, [(122.2, 56.6), (122.2, 56.2), (115.9, 56.2),
                         (115.9, 29.9), (115.3, 29.3)]),
    ("VOUT_INT", F, 0.3, [(121.2, 56.6), (121.7, 55.9), (121.7, 55.5)]),
    ("VOUT_INT", B, 0.3, [(121.7, 55.5), (116.6, 55.5), (116.6, 26.3),
                          (109.3, 26.4)]),
    # ---- LM5069: SENSE Kelvin + HS_GATE
    ("HS_SENSE", F, 0.3, [(47.16, 17.4), (47.16, 18.9)]),
    ("HS_SENSE", B, 0.3, [(47.16, 18.9), (44.0, 22.0), (36.0, 27.5),
                          (33.5, 29.2)]),
    ("HS_SENSE", F, 0.3, [(33.5, 29.2), (32.8, 30.0)]),
    ("HS_GATE", F, 0.3, [(37.2, 30.0), (38.1, 29.4)]),
    ("HS_GATE", B, 0.4, [(38.1, 29.4), (50.5, 19.5), (58.0, 13.5),
                         (61.8, 11.5)]),
    ("HS_GATE", F, 0.3, [(61.8, 11.5), (62.45, 11.04)]),
    # ---- DISC_GATE: taps threaded through the FET tab gaps + trunk to U6
    ("DISC_GATE", F, 0.3, [(118.68, 9.6), (118.68, 11.695)]),
    ("DISC_GATE", F, 0.3, [(118.68, 16.6), (118.68, 18.695)]),
    ("DISC_GATE", F, 0.3, [(120.22, 17.4), (120.22, 15.905)]),
    ("DISC_GATE", F, 0.3, [(120.22, 24.6), (120.22, 22.905)]),
    ("DISC_GATE", B, 0.4, [(118.68, 9.6), (118.68, 16.6), (120.22, 17.4),
                           (120.22, 24.6), (120.22, 27.0), (117.2, 30.0),
                           (117.2, 48.3), (117.9, 49.0)]),
    ("DISC_GATE", F, 0.3, [(116.075, 49.7), (115.6, 49.95), (116.075, 50.2)]),
    ("DISC_GATE", F, 0.3, [(117.9, 49.0), (116.2, 49.1), (115.6, 49.55),
                           (115.6, 49.95)]),
    # ---- U6 support: TS to In2 patch, C41 links
    ("DISC_SRC", F, 0.4, [(116.075, 50.7), (114.9, 50.2), (114.6, 50.0)]),
    ("DISC_SRC", F, 0.4, [(114.875, 50.7), (114.6, 50.0)]),
    ("LTC_BST", F, 0.3, [(113.325, 50.7), (113.3, 52.5), (115.4, 52.5),
                         (115.6, 51.9), (116.1, 51.2)]),
    # ---- 3V3 trunk
    ("3V3", F, 1.2, [(50.15, 50.0), (50.15, 68.5)]),
]
EXTRA_VIAS = [
    ("G_HS_A", 79.9, 35.3), ("G_HS_A", 74.6, 7.2),
    ("SW1", 79.9, 37.55), ("SW1", 82.55, 24.8),
    ("G_LS_A", 77.5, 38.15), ("G_LS_A", 68.6, 25.5),
    ("BST_A", 79.9, 38.5), ("BST_A", 83.55, 27.6),
    ("PH_CS_A", 80.85, 34.1), ("PH_CS_A", 95.7, 11.8),
    ("VOUT_INT", 81.75, 34.75), ("VOUT_INT", 99.6, 12.6),
    ("G_LS_B", 76.3, 41.05), ("G_LS_B", 68.6, 51.0),
    ("BST_B", 73.9, 40.35), ("BST_B", 80.9, 41.9),
    ("VOUT_INT", 94.6, 31.3), ("VOUT_INT", 99.2, 54.6),
    ("PS_VIN", 59.6, 55.6), ("PS_VIN", 77.2, 29.9),
    ("VOUT_SW", 110.5, 25.4), ("VOUT_SW", 101.2, 28.6),
    ("VOUT_SW", 122.2, 56.6), ("VOUT_SW", 115.3, 29.3),
    ("VOUT_INT", 121.7, 55.5), ("VOUT_INT", 109.3, 26.4),
    ("HS_SENSE", 47.16, 18.9), ("HS_SENSE", 33.5, 29.2),
    ("HS_GATE", 38.1, 29.4), ("HS_GATE", 61.8, 11.5),
    ("DISC_GATE", 118.68, 9.6), ("DISC_GATE", 118.68, 16.6),
    ("DISC_GATE", 120.22, 17.4), ("DISC_GATE", 120.22, 24.6),
    ("DISC_GATE", 117.9, 49.0),
     ("DISC_SRC", 114.6, 50.0),
    ("VOUT_INT", 112.9, 65.7),
    ("VOUT_INT", 100.6, 86.8), ("VOUT_INT", 100.6, 66.9),
    ("PGND", 107.4, 86.7), ("PGND", 107.4, 67.0),
    ("3V3", 50.15, 68.5),
]

STITCH = (
    [("PGND", x, y) for x in range(30, 53, 6) for y in (21.5, 25.5)] +
    [("PGND", x, y) for x in (66, 75, 84, 93) for y in (28.2, 41.6)] +
    [("PGND", x, y) for x in (46, 54, 62, 70, 78, 86, 94) for y in (65.8,)] +
    [("PGND", 3, y) for y in (6, 14, 22, 30, 38, 46, 54, 62)] +
    [("PGND", x, 2.2) for x in (46, 60, 74, 88, 102)] +
    [("AGND", x, y) for x in range(8, 127, 9) for y in (70.5, 76.0, 81.5, 87.0)] +
    [("AGND", x, y) for x in (71, 79, 87, 95) for y in (33.4, 37.2)] +
    [("AGND", x, y) for x in (113, 117.5, 122, 126) for y in (48.6, 54.5, 60.4)]
)


def in1_net_at(x, y):
    if point_in_poly(x, y, POCKET_MID) or point_in_poly(x, y, POCKET_OUT):
        return "AGND"
    return "PGND" if y < SEAM else "AGND"


IN2_5V0 = [
    [(36.0, 20.0), (54.0, 20.0), (54.0, 62.0), (36.0, 62.0)],
    [(28.0, 68.0), (58.0, 68.0), (58.0, 89.4), (28.0, 89.4)],
    [(85.0, 66.0), (113.0, 66.0), (113.0, 87.0), (85.0, 87.0)],
    [(108.0, 44.0), (128.0, 44.0), (128.0, 62.0), (108.0, 62.0)],
    [(94.0, 28.0), (112.0, 28.0), (112.0, 40.0), (94.0, 40.0)],
]


def in2_net_at(x, y):
    for net, poly in IN2_PATCHES:
        if point_in_poly(x, y, poly):
            return net
    for poly in IN2_5V0:
        if point_in_poly(x, y, poly):
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

    def seg_dist(px, py, ax, ay, bx, by):
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy
        t = 0 if L2 == 0 else max(0, min(1, ((px - ax) * vx + (py - ay) * vy) / L2))
        dx, dy = px - (ax + t * vx), py - (ay + t * vy)
        return (dx * dx + dy * dy) ** 0.5

    all_vias = [(v.GetNetname(), pcbnew.ToMM(v.GetPosition().x) - ORG[0],
                 pcbnew.ToMM(v.GetPosition().y) - ORG[1])
                for v in board.GetTracks() if isinstance(v, pcbnew.PCB_VIA)]

    def too_close(x, y, net, dist=0.85):
        p = P(x, y)
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                same = pad.GetNetname() == net
                # holes repel any via regardless of net
                if pad.GetDrillSize().x > 0:
                    d = (pad.GetPosition() - p).EuclideanNorm()
                    if d < FromMM(0.75 + pcbnew.ToMM(pad.GetDrillSize().x) / 2
                                  + max(pcbnew.ToMM(pad.GetSize().x),
                                        pcbnew.ToMM(pad.GetSize().y)) / 2):
                        return True
                if same:
                    continue
                d = (pad.GetPosition() - p).EuclideanNorm()
                if d < FromMM(dist + max(pcbnew.ToMM(pad.GetSize().x),
                                         pcbnew.ToMM(pad.GetSize().y)) / 2):
                    return True
        for n, vx, vy in all_vias:
            if n != net and (vx - x) ** 2 + (vy - y) ** 2 < 1.2 ** 2:
                return True
        for t in board.GetTracks():
            if isinstance(t, pcbnew.PCB_VIA) or t.GetNetname() == net:
                continue
            ax = pcbnew.ToMM(t.GetStart().x) - ORG[0]
            ay = pcbnew.ToMM(t.GetStart().y) - ORG[1]
            bx = pcbnew.ToMM(t.GetEnd().x) - ORG[0]
            by = pcbnew.ToMM(t.GetEnd().y) - ORG[1]
            if seg_dist(x, y, ax, ay, bx, by) < dist + pcbnew.ToMM(t.GetWidth()) / 2:
                return True
        return False

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
                continue
            if any(n == net and (vx - x) ** 2 + (vy - y) ** 2 < 1.6 ** 2
                   for n, vx, vy in all_vias):
                continue
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
