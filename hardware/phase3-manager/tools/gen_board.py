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

# U8's library courtyard (labbench LMR36015_RNX, shared with phase 1) is
# 4.4 x 5.4 mm round a 2 x 3 mm body: 1.2 mm of margin, not IPC-7351's
# 0.25. The input caps, L2 and the FB parts belong closer than that -- it
# is what keeps the hot loops short -- so this board replaces it with the
# IPC courtyard: pad/body extent (x +-1.2, y +-1.7) + 0.25 mm. Board-local;
# the shared library footprint (and the routed phase-1 board) are untouched.
COURTYARD_OVERRIDE = {"U8": (1.45, 1.95)}      # ref -> (half-width, half-height)


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
    #
    # ROTATION 180 IS LOAD-BEARING, and so is the x. At rot 0 these parts face
    # U10 with their *PGND* pad, which put a foreign-net pad 0.97 mm from U10's
    # pad column — and at 0.3 mm zone clearance each side that leaves 0.37 mm of
    # nominal channel, too little once the filler rounds the clearance outlines.
    # The F.Cu 3V3 pour was pinched off there: the copper inside U10's pad ring
    # became a 244.6 mm2 ISLAND carrying U10 pad 2, tied to nothing (KiCad
    # reported it as a zone-to-zone unconnected item; check_plane_continuity()
    # below now fails the build on it). Turning both parts round faces U10 with
    # the 3V3 pad instead, so that gap is same-net and the pour flows through
    # it, and it shortens the decoupling path as a bonus: C65 3.73 -> 2.68 mm,
    # C64 6.70 -> 4.79 mm from pad 2. Measured alternatives: leaving rot 0 and
    # shifting 1.0 mm left also heals the plane but costs distance (C65 4.73,
    # C64 7.58); rot 180 alone does NOT (still 2 outlines) — it needs the x too.
    "C65": (57.8, 17.0, 180),     # 100n, nearest the pin (3V3 pad faces U10)
    "C64": (56.5, 20.5, 180),     # 10u bulk

    # === left edge: backplane header ======================================
    "J1":  (5.0, 14.0, 0),        # 1x20, pins y14..62.3

    # === upper-left: CAN + I/O expander + pull-up field ===================
    # Refdes below were re-checked against the netlist before routing (2026-09-27):
    # an earlier pass had labelled parts by their old refdes, which left R64,
    # R72, R76, C69 and eleven others 20-60 mm from the pins they serve.
    # U11 turned 180 so CAN_H/CAN_L (pins 7/6) face J1 pins 7/8 across a
    # clear 5 mm channel, and TXD/RXD (pins 1/4) face U10. route_pairs.py
    # lays the CAN pair in that channel.
    "U11": (15.0, 8.0, 180),      # TCAN1042HGV SOIC-8
    "C66": (14.5, 3.6, 0),        # U11 VIO (3V3) 100n, above pin 5
    "C69": (20.0, 7.4, 90),       # U11 VCC (5V0) 100n, beside pin 3
    "R64": (13.0, 12.6, 0),       # CAN_STB pulldown, below U11 pin 8
    "D7":  (24.0, 8.0, 0),        # LED_STAT
    "D8":  (24.0, 11.0, 0),       # LED_CAN
    "R69": (29.0, 8.0, 0),
    "R70": (29.0, 11.0, 0),
    "U13": (36.0, 11.0, 0),       # TCA9535 TSSOP-24
    "C70": (41.8, 7.6, 90),       # U13 VCC (3V3) 100n, beside pin 24
    "R72": (36.0, 4.0, 0),        # EXP_INT pull-up, above U13 pin 1
    "R62": (28.0, 15.0, 0),       # I2C_SCL pull-up
    "R63": (28.0, 18.0, 0),       # I2C_SDA pull-up
}
# PRESENT0-7 pull-ups (J1 pins 13-20 <-> U13 port 0), two rows of four.
for i, ref in enumerate(["R80", "R81", "R82", "R83", "R84", "R85", "R86", "R87"]):
    PLACEMENT[ref] = (14.0 + 4.0 * (i % 4), 26.0 + 3.0 * (i // 4), 0)
# KEY0-7 pull-ups: one column just right of U13's port-1 pins (13-20), clear
# of U10's courtyard (x>=46), so each KEY net is a straight run down to J5.
for i, ref in enumerate(["R97", "R96", "R95", "R94", "R93", "R92", "R91", "R90"]):
    PLACEMENT[ref] = (44.3, 10.0 + 2.2 * i, 0)

PLACEMENT.update({
    # === lower-left: VBUS -> buck -> 5V0 -> LDO -> 3V3 ====================
    "F1":  (14.0, 43.0, 0),       # blade fuse, courtyard x11..24.9
    "D5":  (31.0, 43.0, 0),       # SMBJ33A, courtyard 7.3 x 4.5
    # U8 buck, laid out round the LMR36015 RNX pinout (route_critical.py
    # draws its copper). Each VIN/PGND pin pair gets its own 1210 input cap
    # right at the pins -- C51 on the west (pins 2/1), C50 on the east
    # (pins 10/11) -- so each hot loop closes in ~2 mm on F.Cu. (An earlier
    # pass had both caps east and L2 12 mm away, which put C50 between the
    # SW pin and the inductor.) SW (pin 12) exits north straight into L2;
    # the output caps sit west of L2's 5V0 pad; C52 (boot) is fed from SW
    # round the west side, BOOT from pin 4 down the south; C53 (VCC) and the
    # FB divider R51/R50 sit under pins 5-7, and AUX_PG leaves east to R52.
    "U8":  (18.0, 55.0, 0),       # LMR36015 VQFN-HR-12
    "C51": (14.65, 54.0, 90),      # 4.7u/50V at pins 2 (VIN) / 1 (PGND)
    "C50": (21.35, 54.0, 90),      # 4.7u/50V at pins 10 (VIN) / 11 (PGND)
    "L2":  (18.0, 50.0, 90),      # 33u 1210: pad1 SW (south), pad2 5V0
    "C54": (14.2, 48.3, 90),      # 5V0 out 22u
    "C55": (10.9, 48.3, 90),
    "C52": (14.2, 57.3, 180),     # BOOT: pad1 BOOT east, pad2 SW west
    "C53": (16.9, 58.5, 270),     # VCC, under pin 5
    "R51": (19.6, 58.5, 270),     # FB bottom, under pin 7
    "R50": (21.9, 57.68, 180),    # FB top, tapped off the 5V0 trunk
    "R52": (25.6, 57.0, 180),     # AUX_PG pull-up
    "U9":  (37.0, 64.0, 0),       # NCP1117-3.3
    "C56": (30.2, 66.3, 180),     # LDO in, at pin 3
    "C57": (44.0, 64.0, 0),       # 3V3 out, at the tab
    "C67x": None,

    # === bottom edge: USB-C + ESD =========================================
    "J3":  (62.0, 76.0, 0),
    # U12 (ESD) sits IN the USB pair's path, turned 180 so its DN pin faces
    # the pair's DN (west) track and DP the DP (east) one: the pair splits
    # round the package and each line touches its clamp with a short stub.
    "U12": (47.525, 69.6, 180),
    "R67": (55.1, 71.2, 180),     # CC1 5.1k, under the USB pair, beside J3.A5
    "R68": (67.8, 69.0, 90),      # CC2 5.1k, beside J3.B5

    # === right: UI headers, encoder, buttons, buzzer ======================
    "J6":  (50.0, 40.0, 90),      # 1x14 LCD, pins x50..83
    "J5":  (50.0, 46.0, 90),      # 1x09 keys, pins x50..70.3
    "J4":  (76.0, 46.0, 90),      # 1x03 UART
    "C73": (50.0, 37.0, 0),       # J6 (LCD) 3V3 100n, above pin 1
    # ENC1 turned 180 so its A/B pins (now x66.5) face the RC network on
    # the right instead of the 5V0 pour; same courtyard x50.5..68, y51.4..65.6.
    "ENC1": (66.5, 61.0, 180),
    "SW1": (75.0, 56.0, 0),       # RESET
    "SW2": (85.0, 56.0, 0),       # BOOT
    "R65": (72.0, 51.0, 0),       # ESP_EN pull-up
    "C68": (77.0, 51.0, 0),       # ESP_EN RC
    "R66": (82.0, 51.0, 0),       # BOOT0 pull-up
    # Encoder conditioning, one row per signal: pull-up, series R, cap.
    "R75": (87.0, 45.0, 0),       # ENC_A_RAW pull-up
    "R77": (92.0, 45.0, 0),       # ENC_A series
    "C74": (97.0, 45.0, 0),       # ENC_A cap
    "R76": (87.0, 48.0, 0),       # ENC_B_RAW pull-up
    "R78": (92.0, 48.0, 0),       # ENC_B series
    "C75": (97.0, 48.0, 0),       # ENC_B cap
    "R79": (87.0, 51.0, 0),       # ENC_SW pull-up
    "C76": (92.0, 51.0, 0),       # ENC_SW cap
    "BZ1": (90.0, 64.0, 0),
    "Q8":  (72.0, 63.0, 0),       # HW_KILL -> HW_EN
    "Q9":  (77.0, 63.0, 0),       # buzzer drive
    "Q10": (82.0, 63.0, 0),       # backlight pre-drive
    "Q11": (72.0, 69.0, 0),       # backlight PMOS
    "D9":  (97.0, 57.0, 0),       # buzzer flyback
    "R98": (77.0, 67.0, 0),       # BUZZ pulldown, under Q9
    "R73": (82.0, 67.0, 0),       # BL_G pull-up, under Q10
    "R71": (72.0, 73.0, 0),       # HW_KILL pulldown
})
PLACEMENT = {k: v for k, v in PLACEMENT.items() if v is not None}

# Top-right corner belongs to the antenna keep-out, so that hole moves down
# to y=38 rather than sitting in the RF zone.
MOUNT_HOLES = [(4.0, 4.0), (4.0, 76.0), (96.0, 76.0), (96.0, 38.0)]
FIDUCIALS = [(10.0, 36.0), (44.0, 34.0), (90.0, 76.0)]  # >=3 for SMD assembly

# Pours. Nothing may enter KEEPOUT: the polygons below are shaped around it.
# F.Cu power pours (net -> polygon). None since the 2026-09-27 re-layout:
# the old 5V0 island (x32..45) held output caps that now sit at L2, and
# 5V0 runs as a 0.8 mm trunk (route_critical.py) instead.
PWR_POURS = {}

EXPECT_IN_POUR = []


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


def _outline_area(poly, i):
    """Shoelace area (mm2) of one filled outline."""
    o = poly.Outline(i)
    pts = [(pcbnew.ToMM(o.CPoint(k).x), pcbnew.ToMM(o.CPoint(k).y))
           for k in range(o.PointCount())]
    a = 0.0
    for k in range(len(pts)):
        x1, y1 = pts[k]
        x2, y2 = pts[(k + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def _in_outline(poly, i, x, y):
    """Point-in-polygon against outline i alone.

    SHAPE_POLY_SET.Contains() tests the whole set, which is exactly the
    question we are NOT asking: we need to know which individual island a
    pad landed on.
    """
    o = poly.Outline(i)
    n = o.PointCount()
    res = False
    j = n - 1
    for k in range(n):
        xk, yk = pcbnew.ToMM(o.CPoint(k).x), pcbnew.ToMM(o.CPoint(k).y)
        xj, yj = pcbnew.ToMM(o.CPoint(j).x), pcbnew.ToMM(o.CPoint(j).y)
        if (yk > y) != (yj > y) and x < (xj - xk) * (y - yk) / (yj - yk) + xk:
            res = not res
        j = k
    return res


def check_plane_continuity(board):
    """Fail if a pour fragmented into an island that carries pads but no tie.

    Must run AFTER the final ZONE_FILLER pass — island geometry is a property
    of the finished copper, not of the zone outlines. A fragment holding no
    pads is normal (the filler carves copper around pads and clearances); a
    fragment holding pads with no via/PTH of its own is a genuine break.
    (With PGND now poured on both layers, a stitch via re-joins such an
    island; when F.Cu was a 3V3 plane, moving the offender was the only fix.)

    This exists because placing U10's decoupling caps pinched the F.Cu 3V3
    pour into two pieces and nothing in the assertion set noticed — the
    board still passed DRC at 0 violations, and the break showed up only as
    one extra unconnected item buried in 174 unrouted signal nets.
    """
    pads = [(p.GetNetname(), pcbnew.ToMM(p.GetPosition().x),
             pcbnew.ToMM(p.GetPosition().y), p)
            for fp in board.GetFootprints() for p in fp.Pads()]
    ties = [(t.GetNetname(), pcbnew.ToMM(t.GetPosition().x),
             pcbnew.ToMM(t.GetPosition().y))
            for t in board.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
    ties += [(n, x, y) for n, x, y, p in pads
             if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD]

    fails = 0
    for z in board.Zones():
        if z.GetIsRuleArea():
            continue
        net = z.GetNetname()
        for layer in z.GetLayerSet().Seq():
            poly = z.GetFilledPolysList(layer)
            if poly.OutlineCount() < 2:
                continue
            ranked = sorted(((_outline_area(poly, i), i)
                             for i in range(poly.OutlineCount())), reverse=True)
            for a, i in ranked[1:]:
                held = [f"{p.GetParent().GetReference()}.{p.GetNumber()}"
                        for n, x, y, p in pads
                        if n == net and p.IsOnLayer(layer)
                        and _in_outline(poly, i, x, y)]
                if not held:
                    continue
                tied = sum(1 for n, x, y in ties
                           if n == net and _in_outline(poly, i, x, y))
                if tied:
                    continue
                o = poly.Outline(i)
                cx = sum(pcbnew.ToMM(o.CPoint(k).x)
                         for k in range(o.PointCount())) / o.PointCount()
                cy = sum(pcbnew.ToMM(o.CPoint(k).y)
                         for k in range(o.PointCount())) / o.PointCount()
                print(f"PLANE BREAK [{net}] on {board.GetLayerName(layer)}: "
                      f"{a:.1f} mm2 island at board-rel "
                      f"({cx - ORG[0]:.1f},{cy - ORG[1]:.1f}) holds {held} "
                      f"with no via/PTH tie")
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
        if ref in COURTYARD_OVERRIDE:
            hw, hh = COURTYARD_OVERRIDE[ref]
            for g in list(fp.GraphicalItems()):
                if g.GetLayer() == pcbnew.F_CrtYd:
                    fp.Remove(g)
            corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
            for k in range(4):
                seg = pcbnew.FP_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
                seg.SetStart0(VECTOR2I(FromMM(corners[k][0]), FromMM(corners[k][1])))
                seg.SetEnd0(VECTOR2I(FromMM(corners[(k + 1) % 4][0]),
                                     FromMM(corners[(k + 1) % 4][1])))
                seg.SetLayer(pcbnew.F_CrtYd)
                seg.SetWidth(FromMM(0.05))
                fp.Add(seg)
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

    # PGND on BOTH layers, notched clear of the antenna. This board was first
    # drawn with F.Cu as a 3V3 plane, but on two layers F.Cu also carries
    # nearly every signal, and the routed tracks cut a top plane into islands
    # that only a track could re-join (the other layer is ground). A ground
    # pour on top instead is re-joined by any stitch via, gives the USB and
    # CAN pairs coplanar ground on their own layer, and 3V3 (under 0.5 A)
    # runs as 0.4 mm tracks. B.Cu stays the reference plane.
    ko_x1, ko_y1, ko_x2, ko_y2 = KEEPOUT
    plane = [(1.0, 1.0), (ko_x1 - 1.0, 1.0), (ko_x1 - 1.0, ko_y2 + 1.0),
             (ko_x2 + 1.0, ko_y2 + 1.0), (ko_x2 + 1.0, 1.0), (W - 1, 1.0),
             (W - 1, H - 1), (1.0, H - 1)]
    zones = [("PGND", pcbnew.B_Cu, 0, plane, "thermal"),
             ("PGND", pcbnew.F_Cu, 0, plane, "thermal")]
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

    # Only meaningful once the copper is final, so it cannot join the
    # placement assertions above. Refuse to write a board whose plane is cut.
    broken = check_plane_continuity(board)
    if broken:
        print(f"gen_board: {broken} plane break(s) — board NOT written")
        sys.exit(1)

    board.Save(OUT)
    print(f"gen_board: {len(comps)} footprints, {len(nets)} nets, "
          f"{len(board.Zones())} zones -> {os.path.relpath(OUT, HERE)}")


if __name__ == "__main__":
    main()
