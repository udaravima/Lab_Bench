"""Generate phase3-manager.kicad_pcb: 100x80 2-layer rack-controller board.

Single-script board in the phase3-backplane style (placement + pours +
vias + tracks), because a 2-layer board with 86 mostly-3-node nets does
not need the phase-2 autoroute machinery.

FLOOR PLAN — driven by one hard constraint and one mating constraint:

  * **U10 antenna keep-out.** ESP32-S3-WROOM-1's footprint carries a
    48 x 21 mm keep-out (its own courtyard is 48 x 41 mm, far bigger than
    the 18 x 25.5 mm module). The antenna faces the TOP edge, so most of
    that rectangle hangs off-board; the on-board remainder
    (KEEPOUT below) must stay copper-free — no pour, no track, no via.
    check_keepout() asserts that, because an RF keep-out that quietly
    fills with ground pour is the classic way to detune a WROOM antenna.
  * **J1 mates the backplane.** Backplane J1 is a 1x20 vertical at its
    x=6, pins y28..76.26 (phase3-backplane/tools/gen_board.py). Manager
    J1 sits on the LEFT edge so the two face each other.

Everything else follows from keeping the switching supply away from the
antenna and the analog-free digital fan-out short:

    top strip  y<17.3   antenna keep-out (copper-free), U10 above it
    left edge  x~5      J1 backplane header (20 pins, y16..64.3)
    SW zone    lower-left, x14..46 y52..77: VBUS in -> F1 -> D5 -> U8
               buck -> L2 -> 5V0 -> U9 LDO -> 3V3, diagonally opposite
               the antenna
    mid band   y28..50: U13 TCA9535 + its 16 pull-ups, U11 CAN
    right      UI headers (J6 LCD, J5 keys), ENC1, buttons, buzzer
    bottom     J3 USB-C on the edge + U12 ESD

MECHANICAL.md puts the display on standoffs above the board and wires
the encoder/keys to the panel, so only J3 (USB-C) and J1 need true edge
access; the other headers are internal.

Run:  python3 gen_board.py wip/mgr.net   (writes ../phase3-manager.kicad_pcb)
"""
import os
import re
import sys

import pcbnew
from pcbnew import FromMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "phase3-manager.kicad_pcb")
FPDIRS = [os.path.join(HERE, "..", "..", "phase1-module", "lib"),
          "/usr/share/kicad/footprints"]

ORG = (20.0, 20.0)
W, H = 100.0, 80.0

# On-board part of U10's antenna keep-out: nothing conductive in here.
# U10 sits at y=21, so the footprint's keep-out (-27.75..-6.75 in its own
# frame) lands at y -6.75..14.25 — everything above y=0 is off-board.
KEEPOUT = (46.0, 0.0, 94.0, 14.3)          # x1, y1, x2, y2

# U10's courtyard (48 x 41 mm) is the ANTENNA keep-out, not the module body
# (18 x 25.5). Decoupling belongs at the module's pads, which is inside that
# oversized rectangle but well clear of the antenna — check_keepout() is the
# constraint that actually matters, and these are asserted against it.
COURTYARD_EXEMPT = {("C64", "U10"), ("C65", "U10")}


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


# ---- placement -----------------------------------------------------------
# (x, y, rotation). Header pin1 is at the given point; pins run +y at rot 0.
PLACEMENT = {
    # === U10: antenna to the TOP edge, keep-out mostly off-board ==========
    "U10": (70.0, 21.0, 0),       # pads y14.3..32.7; courtyard to y34.5
    # U10's 3V3 pin is pad 2 at (61.2, 17.0) — the TOP-left of the module, not
    # the bottom. An earlier pass parked these at y=36 and left the module
    # 19.3 mm from its own decoupling (EMC DC-002). They belong beside pad 2,
    # which means inside U10's oversized courtyard — that rectangle is the
    # antenna keep-out, not a physical exclusion, and both sit below it.
    "C65": (58.3, 17.0, 0),       # 100n, nearest the pin
    "C64": (57.0, 20.5, 0),       # 10u bulk

    # === left edge: backplane header ======================================
    "J1":  (5.0, 14.0, 0),        # 1x20, pins y14..62.3

    # === upper-left: CAN + I/O expander + pull-up field ===================
    "U11": (15.0, 8.0, 0),        # TCAN1042HGV SOIC-8
    "C66": (15.0, 14.0, 0),
    "R76": (22.0, 4.0, 0),        # CAN_STB pulldown
    "D7":  (22.0, 8.0, 0),        # LED_STAT
    "D8":  (22.0, 11.0, 0),       # LED_CAN
    "R69": (27.0, 8.0, 0),
    "R70": (27.0, 11.0, 0),
    "U13": (36.0, 11.0, 0),       # TCA9535 TSSOP-24
    "C69": (36.0, 18.0, 0),
    "R62": (28.0, 15.0, 0),       # I2C_SDA pull-up
    "R63": (28.0, 18.0, 0),       # I2C_SCL pull-up
    "R64": (28.0, 21.0, 0),       # EXP_INT pull-up
}
_PU = ["R77", "R78", "R79", "R80", "R81", "R82", "R83", "R84",
       "R85", "R86", "R87", "R90", "R91", "R92", "R93", "R94"]
for i, ref in enumerate(_PU):
    PLACEMENT[ref] = (14.0 + 4.0 * (i % 4), 26.0 + 3.0 * (i // 4), 0)

PLACEMENT.update({
    # === lower-left: VBUS -> buck -> 5V0 -> LDO -> 3V3 ====================
    "F1":  (14.0, 43.0, 0),       # blade fuse, courtyard x11..24.9
    "D5":  (31.0, 43.0, 0),       # SMBJ33A, courtyard 7.3 x 4.5
    # Buck hot loop: these MUST hug U8's VIN (pads 9/10 at x18.9) and PGND
    # (pads 1/11). An earlier pass had them 23 mm away at x39/x44 — EMC SW-003
    # "large hot loop", the classic buck layout error: the di/dt loop area sets
    # radiated emissions and switch-node ringing.
    "C50": (23.0, 54.5, 0),       # 4.7u/50V input, hard against U8
    "C51": (23.0, 50.5, 0),
    "R71": (14.0, 48.5, 0),       # EN divider
    "R52": (19.0, 48.5, 0),
    "U8":  (18.0, 55.0, 0),       # LMR36015 VQFN-HR-12
    "L2":  (29.0, 55.0, 0),       # 33u 1210
    "C52": (13.0, 60.0, 0),       # BOOT
    "C53": (18.0, 60.0, 0),       # VCC
    "R50": (24.0, 60.0, 0),       # FB top
    "R51": (24.0, 63.0, 0),       # FB bottom
    "C54": (36.0, 55.0, 0),       # 5V0 out 22u
    "C55": (41.5, 55.0, 0),
    "U9":  (37.0, 64.0, 0),       # NCP1117-3.3, fed straight from C54/C55
    "C56": (30.0, 60.0, 0),       # LDO in
    "C57": (44.0, 60.0, 0),       # 3V3 out
    "R73": (14.0, 65.0, 0),       # AUX_PG pull-up
    "R98": (14.0, 68.0, 0),
    "C67x": None,

    # === bottom edge: USB-C + ESD =========================================
    "J3":  (62.0, 76.0, 0),
    "U12": (52.0, 71.0, 0),
    "R67": (46.0, 70.0, 0),       # CC1 5.1k
    "R68": (46.0, 73.0, 0),       # CC2 5.1k

    # === right: UI headers, encoder, buttons, buzzer ======================
    "J6":  (50.0, 40.0, 90),      # 1x14 LCD, pins x50..83
    "J5":  (50.0, 46.0, 90),      # 1x09 keys, pins x50..70.3
    "J4":  (76.0, 46.0, 90),      # 1x03 UART
    "ENC1": (52.0, 56.0, 0),      # courtyard x50.5..68, y51.4..65.6
    "SW1": (75.0, 56.0, 0),       # RESET
    "SW2": (85.0, 56.0, 0),       # BOOT
    "R72": (72.0, 51.0, 0),       # EN pull-up
    "C68": (77.0, 51.0, 0),
    "R75": (82.0, 51.0, 0),       # BOOT0 pull-up
    "R95": (87.0, 51.0, 0),       # ENC_A
    "R96": (92.0, 51.0, 0),       # ENC_B
    "R97": (97.0, 51.0, 0),       # ENC_SW
    "C70": (87.0, 45.0, 0),       # ENC RC
    "C73": (92.0, 45.0, 0),
    "C74": (97.0, 45.0, 0),
    "BZ1": (90.0, 64.0, 0),
    "Q8":  (72.0, 63.0, 0),       # buzzer drive
    "Q9":  (77.0, 63.0, 0),       # HW_KILL
    "Q10": (82.0, 63.0, 0),       # backlight pre-drive
    "Q11": (72.0, 69.0, 0),       # backlight PMOS
    "D9":  (97.0, 57.0, 0),       # buzzer flyback
    "R65": (72.0, 73.0, 0),
    "R66": (87.0, 73.0, 0),
    "C75": (77.0, 73.0, 0),
    "C76": (82.0, 73.0, 0),
})
PLACEMENT = {k: v for k, v in PLACEMENT.items() if v is not None}

# Top-right corner belongs to the antenna keep-out, so that hole moves down
# to y=38 rather than sitting in the RF zone.
MOUNT_HOLES = [(4.0, 4.0), (4.0, 76.0), (96.0, 76.0), (96.0, 38.0)]
FIDUCIALS = [(10.0, 36.0), (44.0, 34.0), (90.0, 76.0)]  # >=3 for SMD assembly

# Pours. Nothing may enter KEEPOUT: the polygons below are shaped around it.
PWR_POURS = {
    # 5V0 island: buck output caps -> LDO input, one contiguous piece
    "5V0": [(32.5, 52.0), (45.0, 52.0), (45.0, 62.0), (39.5, 62.0),
            (39.5, 66.5), (32.5, 66.5)],
}

EXPECT_IN_POUR = [
    ("C54", "1", "5V0"), ("C55", "1", "5V0"), ("U9", "3", "5V0"),
]


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
                bb = ([b.GetLeft(), b.GetTop(), b.GetRight(), b.GetBottom()]
                      if bb is None else
                      [min(bb[0], b.GetLeft()), min(bb[1], b.GetTop()),
                       max(bb[2], b.GetRight()), max(bb[3], b.GetBottom())])
        if bb:
            boxes.append((fp.GetReference(), bb))
    fails = 0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (r1, a), (r2, b) = boxes[i], boxes[j]
            if (r1, r2) in COURTYARD_EXEMPT or (r2, r1) in COURTYARD_EXEMPT:
                continue
            ox = min(a[2], b[2]) - max(a[0], b[0])
            oy = min(a[3], b[3]) - max(a[1], b[1])
            if ox > 0 and oy > 0:
                print(f"CRTYD {r1}<->{r2} overlap "
                      f"{pcbnew.ToMM(ox):.2f}x{pcbnew.ToMM(oy):.2f}mm")
                fails += 1
    for ref, bb in boxes:
        if ref in ("U10", "J3"):
            # U10: the oversized courtyard IS the antenna keep-out, which
            # deliberately hangs off the top edge.
            # J3: USB-C is an edge receptacle — its shell overhangs by design.
            continue
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


def check_keepout(board):
    """No pad, track or via inside U10's antenna keep-out (RF, not cosmetic)."""
    x1, y1, x2, y2 = KEEPOUT
    fails = 0
    for fp in board.GetFootprints():
        if fp.GetReference() == "U10":
            continue                     # its own pads are north of the zone
        for pad in fp.Pads():
            x = pcbnew.ToMM(pad.GetPosition().x) - ORG[0]
            y = pcbnew.ToMM(pad.GetPosition().y) - ORG[1]
            if x1 <= x <= x2 and y1 <= y <= y2:
                print(f"KEEPOUT {fp.GetReference()}.{pad.GetNumber()} "
                      f"at ({x:.1f},{y:.1f}) inside antenna zone")
                fails += 1
    for t in board.GetTracks():
        for pt in (t.GetStart(), t.GetEnd()):
            x = pcbnew.ToMM(pt.x) - ORG[0]
            y = pcbnew.ToMM(pt.y) - ORG[1]
            if x1 <= x <= x2 and y1 <= y <= y2:
                print(f"KEEPOUT copper [{t.GetNetname()}] at ({x:.1f},{y:.1f})")
                fails += 1
                break
    for name, poly in PWR_POURS.items():
        for (px, py) in poly:
            if x1 <= px <= x2 and y1 <= py <= y2:
                print(f"KEEPOUT pour {name} vertex ({px},{py}) inside zone")
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
    # 0.2 mm, not 0.3: the stock ESP32-S3-WROOM-1 footprint stitches its
    # thermal pad with 0.2 mm holes. CONFIRM the fab quotes 0.2 mm drilling
    # for this 2-layer stackup before ordering — it is above JLC's cheapest
    # process on some quotes.
    ds.m_MinThroughDrill = FromMM(0.2)
    ds.m_MinClearance = FromMM(0.2)
    # The GCT USB-C receptacle's own NPTH-to-pad spacing is 0.194 mm; that is
    # the part's geometry, not a layout choice, so the board rule matches it.
    ds.m_HoleClearance = FromMM(0.15)
    # A 0603 pad on a plane legitimately gets one spoke.
    ds.m_MinResolvedSpokes = 1

    netinfo = {}
    for name in sorted(nets):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni

    missing = sorted(r for r in comps if r not in PLACEMENT)
    extra = sorted(r for r in PLACEMENT if r not in comps)
    if missing or extra:
        print(f"placement mismatch:\n  missing={missing}\n  extra={extra}")
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

    fails = check_pours(board) + check_courtyards(board) + check_keepout(board)
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

    # B.Cu = PGND plane, F.Cu = 3V3 plane, both notched clear of the antenna
    ko_x1, ko_y1, ko_x2, ko_y2 = KEEPOUT
    plane = [(1.0, 1.0), (ko_x1 - 1.0, 1.0), (ko_x1 - 1.0, ko_y2 + 1.0),
             (ko_x2 + 1.0, ko_y2 + 1.0), (ko_x2 + 1.0, 1.0), (W - 1, 1.0),
             (W - 1, H - 1), (1.0, H - 1)]
    zones = [("PGND", pcbnew.B_Cu, 0, plane, "thermal"),
             ("3V3", pcbnew.F_Cu, 0, plane, "thermal")]
    for name, poly in PWR_POURS.items():
        zones.append((name, pcbnew.F_Cu, 2, poly, "full"))
    for net, layer, prio, pts, conn in zones:
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNetCode(netinfo[net].GetNetCode())
        (z.SetAssignedPriority(prio) if hasattr(z, "SetAssignedPriority")
         else z.SetPriority(prio))
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

    # Board-level RULE AREA over the antenna. The ESP32 footprint carries its
    # own keep-out, but that one does NOT stop the zone filler (verified: with
    # the planes deliberately flooded full-board, 8 filled-copper vertices
    # landed inside it). Without this, the antenna is protected only by the
    # hand-shaped pour polygons above — and one refill in KiCad after someone
    # edits a pour would flood it with copper and detune the module, silently.
    ka = pcbnew.ZONE(board)
    ka.SetIsRuleArea(True)
    ka.SetDoNotAllowCopperPour(True)
    ka.SetDoNotAllowTracks(True)
    ka.SetDoNotAllowVias(True)
    ka.SetDoNotAllowPads(True)
    ka.SetLayerSet(pcbnew.LSET(pcbnew.F_Cu).AddLayer(pcbnew.B_Cu))
    ko = ka.Outline()
    ko.NewOutline()
    for x, y in [(KEEPOUT[0], KEEPOUT[1]), (KEEPOUT[2], KEEPOUT[1]),
                 (KEEPOUT[2], KEEPOUT[3]), (KEEPOUT[0], KEEPOUT[3])]:
        ko.Append(FromMM(ORG[0] + x), FromMM(ORG[1] + y))
    board.Add(ka)

    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(OUT)
    print(f"gen_board: {len(comps)} footprints, {len(nets)} nets, "
          f"{len(board.Zones())} zones -> {os.path.relpath(OUT, HERE)}")


if __name__ == "__main__":
    main()
