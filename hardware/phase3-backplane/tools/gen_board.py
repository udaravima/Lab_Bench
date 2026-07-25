"""Generate phase3-backplane.kicad_pcb: 330x100 2-layer 2oz bus backplane.

Single-script board (placement + pours + vias + signal tracks): the board is
simple enough that no separate route_board/autoroute pass is needed.

Geometry: 8 slots at 30mm pitch, slot lines run along Y (module edge = 90mm
side stands perpendicular; module slides +x ~15mm to mate). Slot n at
x = 70+30n: XT60PW-F at (x,12) rot 90 puts its pads at (x+3, 12+/-3.6) --
IDENTICAL y-offsets to the module's XT60PW-M pads (J1 at module-y 12), and
the 1x08 signal socket at (x,60) matches module J5 (pins y60..77.8) 1:1.
Polarity remains the MECHANICAL.md hard gate: footprints say pads 1=+ 2=-
ASSUMED -- continuity-check a mated pair before gerbers. The vertical-header
signal footprints are electrical placeholders; the mated part choice is part
of the same mechanical gate.

Bus copper: F.Cu VBUS band y11.2..21 (pad1 row) + entry pocket, F.Cu PGND
band y2.5..10.4 (pad2 row); B.Cu = full PGND plane with a priority-1 VBUS
mirror band under the F band, stitched. Supply: J30 lug -> RS1||RS2 (2x
0.5mOhm 3920, INA228 Kelvin between them) -> VBUS. Return: J31 lug -> plane.

PRESENT0..7 route as a nested L-bus (turn-x decreases with slot index -- by
construction crossing-free). HW_EN crosses under the PRESENT lanes with one
B.Cu jog. All connectors are PTH, so PGND pins tie to the B plane directly;
only SMD PGND pads get stitch vias.

Run:  python3 gen_board.py wip/bp.net  (writes ../phase3-backplane.kicad_pcb)
"""
import os
import re
import sys

import pcbnew
from pcbnew import FromMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "phase3-backplane.kicad_pcb")
FPDIRS = [os.path.join(HERE, "..", "..", "phase1-module", "lib"),
          "/usr/share/kicad/footprints"]

ORG = (20.0, 20.0)
W, H = 330.0, 100.0
SLOT_X = [70.0 + 30.0 * n for n in range(8)]
SOCK_Y = 60.0               # signal socket pin1 (matches module J5)


def P(x, y):
    return VECTOR2I(FromMM(ORG[0] + x), FromMM(ORG[1] + y))


def parse_netlist(path):
    text = open(path).read()
    comps = {}
    for m in re.finditer(r'\(comp \(ref "([^"]+)"\)\s*\(value "([^"]*)"\)\s*'
                         r'\(footprint "([^"]*)"\)', text):
        comps[m.group(1)] = (m.group(3), m.group(2))
    nets = {}
    for part in re.split(r'\(net \(code "\d+"\) ', text)[1:]:
        name = re.match(r'\(name "([^"]+)"\)', part).group(1).split("/")[-1]
        for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', part):
            nets.setdefault(name, []).append((ref, pin))
    return comps, nets


PLACEMENT = {
    # entry / telemetry (left zone)
    "J30": (26.0, 15.5, 0),       # VBUS+ M6 lug
    "RS1": (41.0, 12.5, 0),       # 0m5 3920: pad1 VBUS_IN, pad2 VBUS
    "RS2": (41.0, 19.5, 0),
    "J31": (28.0, 40.0, 0),       # RETURN M6 lug (B plane)
    "U1":  (33.0, 27.0, 0),       # INA228, Kelvin between the shunts
    "C1":  (33.0, 31.0, 0),       # 3V3 100n
    "C3":  (48.0, 20.2, 270),     # VBUS 100n
    "C2":  (52.0, 31.5, 0),       # 470u/50V bulk
    "D5":  (65.0, 31.5, 270),     # SMBJ33A
    # manager + E-stop
    "J1":  (6.0, 28.0, 0),        # 1x20, pins y28..76.26
    "J2":  (10.0, 92.0, 90),      # E-stop NC, pins (10,92)(12.54,92)
    "R1":  (20.0, 90.5, 0),       # ESTOP_RET -> HW_EN
    # CAN terminators (both physical bus ends)
    "R2":  (57.4, 49.6, 0),     # slot0 end: pad1 up CAN_H, pad2 dn CAN_L
    "R3":  (292.6, 49.6, 0),    # slot7 end
}
for n in range(8):
    PLACEMENT[f"J{10+n}"] = (SLOT_X[n], 12.0, 90)      # XT60PW-F
    PLACEMENT[f"J{20+n}"] = (SLOT_X[n], SOCK_Y, 0)     # 1x08 signal

MOUNT_HOLES = [(10.0, 8.0), (85.0, 5.0), (205.0, 5.0), (320.0, 8.0),
               (30.0, 92.0), (320.0, 92.0)]
FIDUCIALS = [(15.0, 55.0), (315.0, 55.0), (165.0, 2.2)]

PWR_POURS = {
    "VBUS_IN": [(20.0, 8.0), (38.0, 8.0), (38.0, 23.0), (20.0, 23.0)],
    "VBUS":    [(39.0, 11.2), (300.0, 11.2), (300.0, 21.0), (66.0, 21.0),
                (66.0, 38.5), (39.0, 38.5)],
    "PGND_N":  [(60.0, 2.5), (302.0, 2.5), (302.0, 10.4), (60.0, 10.4)],
    "PGND_LUG": [(20.0, 33.0), (36.0, 33.0), (36.0, 47.0), (20.0, 47.0)],
}

EXPECT_IN_POUR = (
    [(f"J{10+n}", "1", "VBUS") for n in range(8)] +
    [(f"J{10+n}", "2", "PGND_N") for n in range(8)] +
    [("RS1", "1", "VBUS_IN"), ("RS1", "2", "VBUS"),
     ("RS2", "1", "VBUS_IN"), ("RS2", "2", "VBUS"),
     ("J30", "1", "VBUS_IN"), ("J31", "1", "PGND_LUG"),
     ("C3", "1", "VBUS"), ("C2", "1", "VBUS"), ("D5", "1", "VBUS")]
)

F, B = "F.Cu", "B.Cu"
# J1 pin y: 28 + 2.54*(k-1);  J2x pin y: 60 + 2.54*(k-1)
J1Y = {k: 28.0 + 2.54 * (k - 1) for k in range(1, 21)}
SKY = {k: SOCK_Y + 2.54 * (k - 1) for k in range(1, 9)}

# Signal plan (crossing-free by construction):
#   F.Cu: CAN_H trunk y51, HW_EN trunk y53 (southmost F -> its slot stubs
#         cross nothing), 3V3 spine at x4.4/x3 west of J1, VBUS manager feed
#         around the north of the VBUS_IN pour.
#   B.Cu: CAN_L trunk y49.2 (stubs land on the PTH socket pins directly),
#         3V3-to-C1 run, HW_EN jog under the PRESENT lane bus.
#   CAN_H slot stubs drop to B through a via ON the trunk so they can pass
#   under the HW_EN trunk; outer-lane-serves-deeper-pin keeps fans clean.
TRACKS = [
    # VBUS feed to the manager header (around the VBUS_IN pour, into the band)
    ("VBUS", F, 2.0, [(6.0, J1Y[2]), (6.0, J1Y[1])]),
    ("VBUS", F, 2.0, [(6.0, J1Y[1]), (15.0, J1Y[1]), (15.0, 5.6),
                      (38.5, 5.6), (40.5, 7.5), (40.5, 11.5)]),
    # 3V3 spine: J1.10 west to the edge, south to the E-stop
    ("3V3", F, 0.4, [(6.0, J1Y[10]), (4.4, J1Y[10] - 1.0), (3.0, 53.0),
                     (3.0, 90.2), (4.8, 92.0), (10.0, 92.0)]),
    ("3V3", B, 0.4, [(6.0, J1Y[10]), (3.6, 49.6), (3.6, 31.81),
                     (28.6, 31.81)]),
    ("3V3", F, 0.3, [(28.6, 31.81), (32.175, 31.0)]),
    ("3V3", F, 0.3, [(32.175, 31.0), (34.8, 28.6), (35.2, 28.15)]),
    # E-stop chain: J2(NC) -> R1 -> HW_EN, B jog under the PRESENT bus
    ("ESTOP_RET", F, 0.4, [(12.54, 92.0), (17.8, 92.0), (19.175, 90.9),
                           (19.175, 90.5)]),
    ("HW_EN", F, 0.4, [(20.825, 90.5), (22.0, 89.6), (22.0, 89.4)]),
    ("HW_EN", B, 0.4, [(22.0, 89.4), (22.0, 80.4)]),
    ("HW_EN", F, 0.4, [(22.0, 80.4), (22.0, 53.0)]),
    # west links to the manager
    ("CAN_H", B, 0.3, [(6.0, J1Y[7]), (9.6, J1Y[7]), (9.6, 47.8),
                       (52.0, 47.8), (54.5, 49.0)]),
    ("CAN_H", F, 0.3, [(54.5, 49.0), (54.5, 51.0), (58.0, 51.0)]),
    ("CAN_L", B, 0.3, [(6.0, J1Y[8]), (8.6, J1Y[8]), (8.6, 50.2),
                       (56.4, 50.2), (58.8, 49.4), (58.8, 49.2)]),
    ("HW_EN", B, 0.4, [(6.0, J1Y[9]), (7.4, J1Y[9]), (7.4, 56.0),
                       (20.8, 56.0), (22.0, 55.4)]),
    # trunks across the slot field
    ("CAN_H", F, 0.3, [(58.0, 51.0), (292.0, 51.0)]),
    ("CAN_L", B, 0.3, [(58.8, 49.2), (293.0, 49.2)]),
    ("HW_EN", F, 0.4, [(22.0, 53.0), (282.6, 53.0)]),
    # CAN terminators (R2 west / R3 east; pad1 up = CAN_H, pad2 dn = CAN_L)
    ("CAN_H", F, 0.3, [(56.575, 49.6), (56.575, 51.0)]),
    ("CAN_L", F, 0.3, [(58.5, 49.6), (59.4, 49.6)]),
    ("CAN_L", B, 0.3, [(59.4, 49.6), (59.8, 49.2)]),
    ("CAN_H", F, 0.3, [(291.775, 49.6), (291.775, 51.0)]),
    ("CAN_L", F, 0.3, [(293.1, 49.6), (294.2, 49.6)]),
    ("CAN_L", B, 0.3, [(294.2, 49.6), (293.8, 49.2), (293.0, 49.2)]),
    # I2C to INA228
    ("I2C_SDA", F, 0.3, [(6.0, J1Y[11]), (7.6, 52.9), (7.6, 29.6),
                         (28.9, 29.6), (28.9, 27.5), (30.075, 27.5)]),
    ("I2C_SCL", F, 0.3, [(6.0, J1Y[12]), (8.3, 55.4), (8.3, 30.4),
                         (29.5, 30.4), (30.1, 28.4), (30.5, 28.15)]),
    # INA228 shunt Kelvin (tap between RS1 and RS2 pads)
    ("VBUS_IN", F, 0.3, [(35.0, 16.0), (34.2, 16.8), (34.2, 24.6),
                         (34.4, 26.0), (34.475, 26.0)]),
    ("VBUS", F, 0.3, [(44.81, 16.0), (47.0, 16.9), (47.0, 23.6),
                      (37.4, 26.5), (35.925, 26.5)]),
    ("VBUS", F, 0.3, [(39.6, 27.0), (35.925, 27.0)]),
    # explicit PGND stitches for the SMD pads (PTH pads reach the B plane)
    ("PGND", F, 0.3, [(30.8, 26.5), (30.8, 26.0), (31.6, 24.9),
                      (31.6, 24.4)]),                       # U1.1+U1.2
    ("PGND", F, 0.3, [(35.925, 27.5), (38.1, 27.7), (38.6, 28.0)]),  # U1.7
    ("PGND", F, 0.3, [(33.825, 31.0), (35.4, 31.0), (35.8, 31.0)]),  # C1.2
    ("PGND", F, 0.4, [(58.25, 31.5), (59.6, 31.5)]),        # C2.2
    ("PGND", F, 0.4, [(48.0, 20.975), (48.0, 22.6)]),       # C3.2
    ("PGND", F, 0.4, [(65.0, 33.65), (65.0, 35.2)]),        # D5.2
]
EXTRA_VIAS = [
    ("HW_EN", 22.0, 89.4), ("HW_EN", 22.0, 80.4), ("HW_EN", 22.0, 55.4),
    ("CAN_H", 54.5, 49.0),
    ("3V3", 28.6, 31.81),
    ("CAN_L", 59.4, 49.6), ("CAN_L", 294.2, 49.6),
    ("PGND", 31.6, 24.4), ("PGND", 38.6, 28.0), ("PGND", 35.8, 31.0),
    ("PGND", 59.6, 31.5), ("PGND", 48.0, 22.6), ("PGND", 65.0, 35.2),
]

# per-slot stubs: HW_EN stays on F (southmost F trunk = crossing-free);
# CAN_H dives to B at the trunk to pass under HW_EN; CAN_L is B end-to-end.
for n, sx in enumerate(SLOT_X):
    TRACKS += [
        ("CAN_H", B, 0.3, [(sx - 1.3, 51.0), (sx - 1.3, 58.8), (sx, 60.0)]),
        ("CAN_L", B, 0.3, [(sx + 1.3, 49.2), (sx + 1.3, 61.3),
                           (sx, SKY[2])]),
        ("HW_EN", F, 0.3, [(sx + 2.6, 53.0), (sx + 2.6, 63.8),
                           (sx + 1.0, 65.0), (sx, SKY[3])]),
    ]
    EXTRA_VIAS.append(("CAN_H", sx - 1.3, 51.0))
    # PRESENT nested L-bus: lane y = 83.4+0.7n, turn-x = 15.2-0.8n
    lane_y = 83.4 + 0.7 * n
    turn_x = 15.2 - 0.8 * n
    TRACKS += [
        (f"PRESENT{n}", F, 0.3, [(sx, SKY[7]), (sx + 1.2, SKY[7] + 1.2),
                                 (sx + 1.2, lane_y - 1.2), (sx, lane_y),
                                 (turn_x, lane_y), (turn_x, J1Y[13 + n]),
                                 (6.0, J1Y[13 + n])]),
    ]

# VBUS F<->B stitching rows (skip near slot pads and legs)
VIAS = []
for xs in range(44, 299, 8):
    for y in (12.3, 19.7):
        if any(abs(xs - (sx + 3)) < 4.5 or abs(xs - (sx - 3)) < 4.5
               for sx in SLOT_X):
            continue
        VIAS.append(("VBUS", float(xs), y))
VIAS += [("VBUS_IN", x, y) for x in (22.5, 32.0) for y in (9.5, 21.5)]


def point_in_poly(x, y, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def check_courtyards(board):
    boxes = []
    for fp in board.GetFootprints():
        bb = None
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.F_CrtYd:
                b = g.GetBoundingBox()
                if bb is None:
                    bb = [b.GetLeft(), b.GetTop(), b.GetRight(), b.GetBottom()]
                else:
                    bb = [min(bb[0], b.GetLeft()), min(bb[1], b.GetTop()),
                          max(bb[2], b.GetRight()), max(bb[3], b.GetBottom())]
        if bb:
            boxes.append((fp.GetReference(), bb))
    fails = 0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (r1, a), (r2, b) = boxes[i], boxes[j]
            ox = min(a[2], b[2]) - max(a[0], b[0])
            oy = min(a[3], b[3]) - max(a[1], b[1])
            if ox > 0 and oy > 0:
                print(f"CRTYD {r1}<->{r2} overlap "
                      f"{pcbnew.ToMM(ox):.2f}x{pcbnew.ToMM(oy):.2f}mm")
                fails += 1
    for ref, bb in boxes:
        if ref.startswith("J1") and ref != "J1":
            continue                       # XT60 shrouds overhang by design
        if (pcbnew.ToMM(bb[0]) < ORG[0] or pcbnew.ToMM(bb[1]) < ORG[1]
                or pcbnew.ToMM(bb[2]) > ORG[0] + W
                or pcbnew.ToMM(bb[3]) > ORG[1] + H):
            print(f"CRTYD {ref} extends past board edge")
            fails += 1
    return fails


def check_pours(board):
    pads = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            pads.setdefault((fp.GetReference(), pad.GetNumber()), []).append(pad)
    fails = 0
    for ref, num, pour in EXPECT_IN_POUR:
        poly = PWR_POURS[pour]
        for pad in pads.get((ref, num), []):
            x = pcbnew.ToMM(pad.GetPosition().x) - ORG[0]
            y = pcbnew.ToMM(pad.GetPosition().y) - ORG[1]
            if not point_in_poly(x, y, poly):
                print(f"POUR FAIL {ref}.{num} at ({x:.2f},{y:.2f}) not in {pour}")
                fails += 1
    return fails


def load_fp(fpid):
    lib, name = fpid.split(":", 1)
    for d in FPDIRS:
        path = os.path.join(d, f"{lib}.pretty")
        if os.path.exists(os.path.join(path, f"{name}.kicad_mod")):
            return pcbnew.FootprintLoad(path, name)
    raise KeyError(fpid)


def main():
    comps, nets = parse_netlist(sys.argv[1])
    board = pcbnew.NewBoard(OUT)
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(FromMM(1.6))
    ds.m_TrackMinWidth = FromMM(0.2)
    ds.m_ViasMinSize = FromMM(0.6)
    ds.m_MinThroughDrill = FromMM(0.3)
    ds.m_MinClearance = FromMM(0.2)

    netinfo = {}
    for name in sorted(nets):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni

    missing = [r for r in comps if r not in PLACEMENT]
    extra = [r for r in PLACEMENT if r not in comps]
    if missing or extra:
        print(f"placement mismatch: missing={sorted(missing)} extra={sorted(extra)}")
        sys.exit(1)
    padnet = {}
    for name, nodes in nets.items():
        for ref, pin in nodes:
            padnet[(ref, pin)] = name
    for ref, (fpid, value) in sorted(comps.items()):
        fp = load_fp(fpid)
        fp.SetReference(ref)
        fp.SetValue(value)
        x, y, rot = PLACEMENT[ref]
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            net = padnet.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(netinfo[net])
        board.Add(fp)
    for i, (x, y) in enumerate(MOUNT_HOLES):
        fp = load_fp("MountingHole:MountingHole_3.2mm_M3")
        fp.SetReference(f"H{i+1}")
        fp.SetValue("M3")
        fp.SetPosition(P(x, y))
        board.Add(fp)
    for i, (x, y) in enumerate(FIDUCIALS):
        fp = load_fp("Fiducial:Fiducial_1mm_Mask2mm")
        fp.SetReference(f"FID{i+1}")
        fp.SetValue("Fiducial")
        fp.SetPosition(P(x, y))
        board.Add(fp)

    fails = check_pours(board) + check_courtyards(board)
    if fails:
        print(f"gen_board: {fails} placement failures")
        sys.exit(1)

    corners = [(0, 0), (W, 0), (W, H), (0, H)]
    for i in range(4):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(P(*corners[i]))
        seg.SetEnd(P(*corners[(i + 1) % 4]))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(FromMM(0.1))
        board.Add(seg)

    zones = [("PGND", pcbnew.B_Cu, 0,
              [(1.0, 1.0), (W - 1, 1.0), (W - 1, H - 1), (1.0, H - 1)],
              "thermal"),
             ("VBUS", pcbnew.B_Cu, 1,
              [(39.0, 11.2), (300.0, 11.2), (300.0, 21.0), (39.0, 21.0)],
              "full"),
             ("VBUS_IN", pcbnew.B_Cu, 1, PWR_POURS["VBUS_IN"], "full")]
    for name, poly in PWR_POURS.items():
        net = "PGND" if name.startswith("PGND") else name
        zones.append((net, pcbnew.F_Cu, 2, poly, "full"))
    for net, layer, prio, pts, conn in zones:
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNetCode(netinfo[net].GetNetCode())
        z.SetAssignedPriority(prio) if hasattr(z, "SetAssignedPriority") else z.SetPriority(prio)
        o = z.Outline()
        o.NewOutline()
        for x, y in pts:
            o.Append(FromMM(ORG[0] + x), FromMM(ORG[1] + y))
        z.SetMinThickness(FromMM(0.3))
        z.SetLocalClearance(FromMM(0.3))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if conn == "full"
                           else pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(FromMM(0.4))
        z.SetThermalReliefSpokeWidth(FromMM(0.5))
        z.SetIsFilled(False)
        board.Add(z)

    layer_id = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    for net, layer, width, pts in TRACKS:
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(P(*a))
            t.SetEnd(P(*b))
            t.SetWidth(FromMM(width))
            t.SetLayer(layer_id[layer])
            t.SetNetCode(netinfo[net].GetNetCode())
            board.Add(t)
    for net, x, y in VIAS + EXTRA_VIAS:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(P(x, y))
        v.SetDrill(FromMM(0.4))
        v.SetWidth(FromMM(0.8))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNetCode(netinfo[net].GetNetCode())
        board.Add(v)
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(OUT)
    print(f"gen_board: {len(comps)} footprints, {len(nets)} nets, "
          f"{len(board.Zones())} zones -> {os.path.relpath(OUT, HERE)}")


if __name__ == "__main__":
    main()
