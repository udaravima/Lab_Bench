"""Generate phase1-module.kicad_pcb: netlist-driven placement + power copper.

Reads the netlist exported from the schematic (single source of truth for
components and connectivity), places every footprint from the hand-authored
PLACEMENT table, builds the 4-layer stack, split ground planes, power pours,
stitching vias and the critical hand routes. Signal routing is done by
autoroute.py afterwards; verification is kicad-cli pcb drc.

Board coordinate system: board origin (0,0) = top-left corner of the outline,
+x right, +y down, mm. Absolute page offset ORG is added on emission.

Run:  python3 gen_board.py <netlist.net>   (writes ../phase1-module.kicad_pcb)
"""
import os
import re
import sys

import pcbnew
from pcbnew import FromMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "phase1-module.kicad_pcb")
FPDIRS = [os.path.join(HERE, "..", "lib"), "/usr/share/kicad/footprints"]

ORG = (20.0, 20.0)          # page position of board origin
W, H = 120.0, 80.0          # board size
SEAM = 31.0                 # y of PGND/AGND plane split (x > AUXW)
AUXW = 30.0                 # aux-rail column width (PGND region below seam)


def P(x, y):
    return VECTOR2I(FromMM(ORG[0] + x), FromMM(ORG[1] + y))


# ---------------------------------------------------------------- netlist --
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


# -------------------------------------------------------------- placement --
# ref: (x, y, rot), F.Cu side. Rotation facts (measured, not assumed):
#   2-pad passives rot 0: pad1 left; rot 90: pad1 DOWN; rot 270: pad1 UP.
#   PowerFET rot 0: drain tab LEFT, gate top-right, sources right column.
#   Pin headers / fuse / Phoenix: pin1 AT ORIGIN; rot 0 runs +y / +x (fuse);
#   rot 90 header runs +x; Phoenix rot 270: pin2 below pin1.
PLACEMENT = {
    # ---- input chain: J1 -> F1 -> VBUS_F pour; TVS + bank straddle the bands
    "J1":  (5.0, 13.0, 270),      # pad1 VBUS (5,10), pad2 PGND (5,15)
    "F1":  (10.8, 6.5, 0),         # pad1 VBUS (5,6.5) -> J1.1; pad2 (13,6.5) in pour
    "D5":  (13.0, 16.9, 270),     # SMBJ33A: pad1 VBUS_F band, pad2 PGND band
    "C21": (22.3, 16.9, 270),     # 220u/50V straddle
    "C20": (30.0, 16.9, 270),     # 22u/50V bank straddle: pad1 up (VBUS_F)
    "C75": (34.0, 16.9, 270),
    "C76": (38.0, 16.9, 270),
    "C77": (42.0, 16.9, 270),
    # ---- half bridge: Q1 tab in VBUS_F band, Q2 (rot180) tab right = SW
    "Q1":  (47.5, 10.0, 0),       # tab 44.05..49.65 VBUS_F; sources x50.58 SW
    "Q2":  (47.5, 23.0, 180),     # tab 45.35..50.3 SW; leads x44.42 PGND
    "L1":  (61.0, 15.0, 0),       # pad1 SW (56.7), pad2 VOUT_INT (65.3)
    "RT1": (44.0, 33.0, 0),       # FET NTC below Q2, on AGND side of seam
    "RT2": (61.0, 28.7, 0),       # inductor NTC below L1
    # SW island taps (pad into pour at y<=26.5, other pad below)
    "C27": (54.5, 27.2, 90),      # BST: pad1 dn (28.25)=PS_BST, pad2 up=SW
    "R28": (56.5, 27.2, 90),      # ILIM: pad1 dn=PS_ILIM, pad2 up=SW
    "R17": (52.0, 27.2, 270),     # snub: pad1 up=SW, pad2 dn=SNUB
    "C17": (52.3, 30.4, 270),     # pad1 up=SNUB, pad2 dn=PGND (in bar)
    # ---- output bank straddle
    "C22": (86.2, 6.9, 90),      # top-strip straddle like C78     # 220u poly
    "C78": (75.5, 6.9, 90),     # pad1 dn in VOUT_INT, pad2 up in PGND_TOP strip
    "C23": (69.6, 16.9, 270),     # 22u/25V bank
    "C79": (73.3, 16.9, 270),
    "C80": (77.0, 16.9, 270),
    "C81": (80.7, 16.9, 270),
    "R27": (84.7, 17.2, 270),     # 2512 preload straddle
    # ---- Kelvin shunt + sense amps below it
    "R30": (94.5, 10.0, 0),       # pad1 VOUT_INT (91.54), pad2 VOUT_SW (97.46)
    "U4":  (94.5, 24.0, 90),      # INA240: pin8 (92.59,21.53) faces shunt
    "R31": (98.5, 29.0, 0),       # INA240_OUT -> I_MEAS
    "C31": (102.2, 29.0, 0),      # I_MEAS filter (AGND pocket)
    "C33": (98.0, 19.5, 0),       # U4 5V0
    "U5":  (94.5, 36.0, 90),      # INA228
    "C34": (90.5, 36.0, 270),     # U5 3V3
    "NT1": (94.5, 31.2, 0),       # star tie on the seam
    # ---- disconnect pair + LTC7004 + VOUT
    "Q3":  (102.9, 10.0, 0),      # tab VOUT_SW; sources 105.98 DISC_SRC
    "Q4":  (111.7, 10.0, 180),    # tab VOUT 109.55..115.16; sources 108.62
    "U6":  (107.0, 22.0, 0),      # LTC7004 under the pair (AGND pocket)
    "C41": (107.7, 16.6, 90),     # BST: pad1 dn=LTC_BST, pad2 up in DISC pour
    "C42": (102.0, 25.5, 270),    # 5V0 1u   (pad2 dn AGND pocket)
    "C43": (92.8, 45.5, 270),    # moved to U7 (audit DC-001)    # 5V0 100n
    "J4":  (116.5, 27.0, 90),    # pad1 VOUT (116.5,22), pad2 PGND (116.5,27)
    # ---- OVP + disconnect logic (y 33..50)
    "R45": (84.0, 33.0, 270),     # VOUT_INT (B.Cu tap) -> OVP_DIV
    "R46": (84.0, 38.0, 270),
    "C44": (87.0, 38.0, 270),
    "U7":  (94.0, 42.0, 0),       # TLV7011 (5V0 pocket at x92..103)
    "R47": (104.5, 42.5, 270),    # 3V3 -> REF_2V5
    "R48": (104.5, 48.5, 270),
    "Q9":  (89.0, 47.0, 0),       # OVP_TRIP pulls DISC_INP
    "Q7":  (108.0, 45.5, 0),      # EN_KILL pulls DISC_INP
    "R43": (102.0, 46.0, 270),    # OUT_REQ -> DISC_INP
    "R44": (111.5, 45.5, 270),    # DISC_INP -> AGND
    # ---- controller + comp/FB + EN cluster
    "U3":  (47.0, 36.0, 0),       # LM5145: right col = LO/VCC/EP/BST/HO/SW
    "R29": (46.2, 16.6, 270),     # VBUS_F (pad1 in band) -> PS_VIN corridor
    "C28": (50.5, 32.4, 90),      # PS_VIN 100n; pad2 up into PGND bar
    "C29": (52.0, 41.5, 0),       # PS_VCC 2.2u; pad2 PGND
    "C19": (50.6, 39.5, 0),       # ILIM 15p; pad2 PGND
    "R1":  (40.5, 34.0, 0),       # FB divider + injection at the FB pin
    "R5":  (40.5, 36.0, 0),
    "R8":  (40.5, 38.0, 0),
    "R2":  (40.5, 40.0, 0),
    "R24": (40.5, 42.0, 0),
    "C24": (40.5, 44.0, 0),
    "C25": (43.8, 36.0, 0),
    "C26": (43.8, 38.0, 0),
    "R25": (43.8, 40.0, 0),
    "C18": (43.8, 42.0, 0),       # SS
    "R26": (43.8, 44.0, 0),       # RT
    "R20": (31.0, 34.0, 0),       # EN chain
    "R21": (34.5, 34.0, 0),
    "Q5":  (31.5, 38.0, 0),
    "Q6":  (35.5, 38.0, 0),
    "R19": (31.0, 42.0, 0),
    "R22": (34.5, 42.0, 0),
    "R23": (31.0, 45.0, 0),
    "D3":  (34.4, 46.2, 0),
    "D4":  (38.0, 46.2, 0),
    # ---- aux rails (left column, PGND region)
    "U8":  (13.0, 35.0, 0),       # LMR36015
    "C50": (8.2, 32.2, 0),       # tight to U8 VIN (audit SW-003)
    "C51": (8.2, 35.6, 0),
    "C52": (17.0, 32.5, 270),     # AUX_BOOT up / SW_AUX down
    "C53": (17.5, 37.5, 0),       # AUX_VCC
    "L2":  (13.0, 41.0, 0),       # pad1 SW_AUX, pad2 5V0
    "C54": (19.0, 41.0, 0),
    "C55": (19.0, 44.6, 0),
    "R50": (14.0, 45.5, 0),
    "R51": (14.0, 48.0, 0),
    "U9":  (11.5, 53.0, 0),       # NCP1117: GND(8.35,50.7) 3V3(14.65,53) 5V0(8.35,55.3)
    "C56": (7.5, 59.5, 0),
    "C57": (15.5, 59.5, 0),
    "J6":  (9.6, 74.0, 90),       # fan: 5V0 + FAN_NEG
    "Q8":  (14.0, 70.2, 0),
    "D6":  (17.5, 73.0, 270),     # pad1 up 5V0, pad2 dn FAN_NEG
    # ---- control core analog (DAC + error amps)
    "U1":  (34.0, 62.0, 0),       # DAC80502
    "C3":  (30.0, 61.0, 0),
    "C4":  (37.5, 59.5, 0),       # REFIO
    "R3":  (37.5, 61.5, 0),       # V_REF -> EAV_INV
    "R6":  (37.5, 63.5, 0),       # I_REF -> EAI_INV
    "U2":  (44.0, 62.0, 0),       # OPA2333
    "C5":  (49.3, 61.0, 0),       # 5V0
    "C1":  (41.0, 58.5, 0),       # EAV integrator
    "R4":  (44.5, 58.5, 0),
    "D1":  (48.0, 58.5, 0),
    "C2":  (48.5, 65.5, 0),       # EAI integrator
    "R7":  (52.0, 65.5, 0),
    "D2":  (55.5, 65.5, 0),
    # ---- MCU + support
    "U10": (70.0, 62.0, 0),       # LQFP-48
    "C71": (63.3, 55.8, 0),
    "C72": (76.7, 55.8, 0),
    "C73": (63.3, 68.2, 0),
    "C74": (76.7, 68.2, 0),
    "C64": (67.0, 54.0, 0),
    "C65": (73.0, 54.0, 0),
    "Y1":  (61.5, 60.5, 0),       # at PF0/PF1 (pins 5/6, x 65.84)
    "C66": (56.8, 59.0, 0),
    "C67": (56.8, 62.0, 0),
    "C68": (63.0, 70.5, 0),       # NRST
    "R65": (67.0, 70.5, 0),       # BOOT0
    "R67": (71.0, 70.5, 0),       # NTC pullups
    "R68": (74.5, 70.5, 0),
    "R62": (80.0, 55.0, 270),     # I2C pullups (toward U5)
    "R63": (82.5, 55.0, 270),
    "R18": (80.0, 59.0, 0),       # PGOOD pullup
    "R16": (80.0, 61.5, 0),       # FPWM pulldown
    "R52": (83.5, 61.5, 0),       # AUX_PG pullup
    "R64": (80.0, 64.0, 0),       # CAN_STB pulldown
    "D7":  (66.0, 76.8, 0),       # status LED, bottom edge
    "R66": (70.0, 76.8, 0),
    "J3":  (26.0, 76.8, 90),      # UART, runs +x to 31.1
    "J2":  (40.0, 76.8, 90),      # SWD, runs +x to 50.2
    # ---- CAN + backplane + VBUS telemetry divider
    "U11": (98.0, 60.0, 0),       # TCAN1042
    "C69": (93.0, 56.5, 0),       # 5V0 (pocket)
    "C70": (93.0, 63.5, 0),       # 3V3
    "J5":  (116.5, 50.0, 0),      # 1x08 runs +y to 67.8
    "R60": (101.5, 51.5, 270),    # VBUS_F -> VBUS_SNS
    "R61": (104.0, 56.0, 270),
    "C62": (107.0, 56.0, 270),
    # V_MEAS divider (0.1%) senses VOUT at the output connector corner
    "R32": (110.5, 34.0, 270),
    "R33": (110.5, 40.0, 270),
    "C32": (107.5, 40.0, 270),
}

MOUNT_HOLES = [(4.0, 4.0), (W - 4.0, 36.0), (4.0, H - 4.0), (W - 4.0, H - 4.0)]
FIDUCIALS = [(10.0, 2.2), (110.0, 77.8), (2.5, 45.0)]   # audit FD-001


# ------------------------------------------------------------------ zones --
# (net, layer, priority, [(x,y)...], pad_connection)
# The AGND "pocket" carves an island out of the PGND regions (higher priority
# wins) so the LTC7004 cluster -- AGND-referenced but living in the power
# strip -- gets correct plane reference without through-via shorts.
POCKET = [(100.0, 16.5), (112.5, 16.5), (112.5, SEAM + 0.2), (100.0, SEAM + 0.2)]
PWR_POURS = {  # name -> F.Cu polygon (also used by pour-connection checks)
    "VBUS_F":   [(12.0, 5.0), (49.6, 5.0), (49.6, 16.0), (12.0, 16.0)],
    "PGND_IN":  [(10.0, 17.3), (44.9, 17.3), (44.9, 30.0), (10.0, 30.0)],
    "PGND_TOP": [(66.0, 0.8), (91.0, 0.8), (91.0, 3.9), (66.0, 3.9)],
    "PGND_BAR": [(38.0, 30.0), (53.0, 30.0), (53.0, 31.7), (38.0, 31.7)],
    "SW":       [(50.5, 8.6), (56.9, 8.6), (56.9, 26.5), (47.0, 26.5),
                 (47.0, 19.0), (50.5, 19.0)],   # trimmed north (audit SW-002)
    "VOUT_INT": [(64.3, 5.0), (91.7, 5.0), (91.7, 16.0), (64.3, 16.0)],
    "PGND_OUT": [(66.0, 17.3), (91.0, 17.3), (91.0, 30.0), (66.0, 30.0)],
    "VOUT_SW":  [(97.4, 5.0), (104.7, 5.0), (104.7, 16.0), (97.4, 16.0)],
    "DISC_SRC": [(105.5, 5.0), (109.9, 5.0), (109.9, 16.0), (105.5, 16.0)],
    "VOUT":     [(110.5, 5.0), (119.5, 5.0), (119.5, 29.0), (108.0, 29.0),
                 (108.0, 21.0), (110.5, 21.0)],
}


def zone_polys():
    F, B = pcbnew.F_Cu, pcbnew.B_Cu
    IN1, IN2 = pcbnew.In1_Cu, pcbnew.In2_Cu
    pgnd_l = [(0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, SEAM), (AUXW, SEAM),
              (AUXW, H - 0.5), (0.5, H - 0.5)]                    # L-shape
    agnd_r = [(AUXW, SEAM), (W - 0.5, SEAM), (W - 0.5, H - 0.5), (AUXW, H - 0.5)]
    zones = [
        # inner ground planes (split at SEAM/AUXW, joined only through NT1)
        ("PGND", IN1, 0, pgnd_l, "thermal"),
        ("AGND", IN1, 0, agnd_r, "thermal"),
        ("AGND", IN1, 1, POCKET, "thermal"),
        # In2: logic power distribution
        ("5V0", IN2, 0, [(0.5, 0.5), (AUXW, 0.5), (AUXW, H - 0.5), (0.5, H - 0.5)], "thermal"),
        ("5V0", IN2, 0, [(AUXW, 56.0), (56.0, 56.0), (56.0, H - 0.5), (AUXW, H - 0.5)], "thermal"),
        ("5V0", IN2, 1, [(92.0, 18.0), (103.0, 18.0), (103.0, 68.0), (92.0, 68.0)], "thermal"),
        ("3V3", IN2, 0, [(AUXW, SEAM), (W - 0.5, SEAM), (W - 0.5, H - 0.5),
                         (56.0, H - 0.5), (56.0, 56.0), (AUXW, 56.0)], "thermal"),
        # B.Cu ground fills (mirror the In1 split, tracks push through)
        ("PGND", B, 0, pgnd_l, "thermal"),
        ("AGND", B, 0, agnd_r, "thermal"),
        ("AGND", B, 1, POCKET, "thermal"),
    ]
    for name, poly in PWR_POURS.items():
        net = {"PGND_IN": "PGND", "PGND_BAR": "PGND", "PGND_OUT": "PGND", "PGND_TOP": "PGND"}.get(name, name)
        zones.append((net, F, 2, poly, "full"))
    return zones


# Pads that MUST land inside their F.Cu pour (mechanical placement check).
# (ref, pad, pour) -- pad centre must be inside PWR_POURS[pour].
EXPECT_IN_POUR = [
    ("F1", "2", "VBUS_F"), ("D5", "1", "VBUS_F"), ("D5", "2", "PGND_IN"),
    ("C21", "1", "VBUS_F"), ("C21", "2", "PGND_IN"),
    ("C20", "1", "VBUS_F"), ("C20", "2", "PGND_IN"),
    ("C75", "1", "VBUS_F"), ("C75", "2", "PGND_IN"),
    ("C76", "1", "VBUS_F"), ("C76", "2", "PGND_IN"),
    ("C77", "1", "VBUS_F"), ("C77", "2", "PGND_IN"),
    ("Q1", "2", "VBUS_F"), ("Q1", "3", "SW"),
    ("Q2", "2", "SW"), ("Q2", "3", "PGND_IN"),
    ("R29", "1", "VBUS_F"),
    ("L1", "1", "SW"), ("L1", "2", "VOUT_INT"),
    ("C27", "2", "SW"), ("R28", "2", "SW"), ("R17", "1", "SW"),
    ("C17", "2", "PGND_BAR"), ("C28", "2", "PGND_BAR"),
    ("C22", "1", "VOUT_INT"), ("C22", "2", "PGND_TOP"),
    ("C78", "1", "VOUT_INT"), ("C78", "2", "PGND_TOP"),
    ("C23", "1", "VOUT_INT"), ("C23", "2", "PGND_OUT"),
    ("C79", "1", "VOUT_INT"), ("C79", "2", "PGND_OUT"),
    ("C80", "1", "VOUT_INT"), ("C80", "2", "PGND_OUT"),
    ("C81", "1", "VOUT_INT"), ("C81", "2", "PGND_OUT"),
    ("R27", "1", "VOUT_INT"), ("R27", "2", "PGND_OUT"),
    ("R30", "1", "VOUT_INT"), ("R30", "2", "VOUT_SW"),
    ("Q3", "2", "VOUT_SW"), ("Q3", "3", "DISC_SRC"),
    ("Q4", "3", "DISC_SRC"), ("Q4", "2", "VOUT"),
    ("C41", "2", "DISC_SRC"),
    ("J4", "1", "VOUT"),
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
    """Fast bbox overlap report on F.CrtYd; placement iteration aid."""
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
                print(f"CRTYD {r1}<->{r2} overlap {pcbnew.ToMM(ox):.2f}x{pcbnew.ToMM(oy):.2f}mm")
                fails += 1
    # board edge check (terminal blocks J1/J4 legitimately overhang for wire entry)
    for ref, bb in boxes:
        if ref in ("J1", "J4"):
            continue
        if (pcbnew.ToMM(bb[0]) < ORG[0] or pcbnew.ToMM(bb[1]) < ORG[1]
                or pcbnew.ToMM(bb[2]) > ORG[0] + W or pcbnew.ToMM(bb[3]) > ORG[1] + H):
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


# ------------------------------------------------------------------ build --
def load_fp(fpid):
    lib, name = fpid.split(":", 1)
    for d in FPDIRS:
        path = os.path.join(d, f"{lib}.pretty")
        if os.path.exists(os.path.join(path, f"{name}.kicad_mod")):
            return pcbnew.FootprintLoad(path, name)
    raise KeyError(fpid)


def main():
    comps, nets = parse_netlist(sys.argv[1])

    board = pcbnew.NewBoard(OUT)   # BOARD() without a project segfaults ZONE_FILLER
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(FromMM(1.6))
    ds.m_TrackMinWidth = FromMM(0.15)
    ds.m_ViasMinSize = FromMM(0.5)
    ds.m_MinThroughDrill = FromMM(0.3)
    ds.m_MinClearance = FromMM(0.15)

    netinfo = {}
    for name in sorted(nets):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni

    # footprints
    missing = [r for r in comps if r not in PLACEMENT]
    extra = [r for r in PLACEMENT if r not in comps]
    if missing or extra:
        print(f"placement table mismatch: missing={sorted(missing)} extra={sorted(extra)}")
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

    # outline
    corners = [(0, 0), (W, 0), (W, H), (0, H)]
    for i in range(4):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(P(*corners[i]))
        seg.SetEnd(P(*corners[(i + 1) % 4]))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(FromMM(0.1))
        board.Add(seg)

    # zones
    for net, layer, prio, pts, conn in zone_polys():
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNetCode(netinfo[net].GetNetCode())
        z.SetAssignedPriority(prio) if hasattr(z, "SetAssignedPriority") else z.SetPriority(prio)
        outline = z.Outline()
        outline.NewOutline()
        for x, y in pts:
            outline.Append(FromMM(ORG[0] + x), FromMM(ORG[1] + y))
        z.SetMinThickness(FromMM(0.25))
        z.SetLocalClearance(FromMM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if conn == "full"
                           else pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(FromMM(0.3))
        z.SetThermalReliefSpokeWidth(FromMM(0.4))
        z.SetIsFilled(False)
        board.Add(z)

    board.BuildConnectivity()
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())

    board.Save(OUT)
    print(f"gen_board: {len(comps)} footprints, {len(nets)} nets, "
          f"{len(board.Zones())} zones -> {os.path.relpath(OUT, HERE)}")


if __name__ == "__main__":
    main()
