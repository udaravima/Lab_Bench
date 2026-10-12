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
W, H = 100.0, 80.0          # board size
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
    "C20": (30.0, 16.9, 270),     # 10u/50V bank straddle: pad1 up (VBUS_F)
    "C75": (34.0, 16.9, 270),
    "C76": (38.0, 16.9, 270),
    "C77": (42.0, 16.9, 270),
    # ---- half bridge: Q1 tab in VBUS_F band, Q2 (rot180) tab right = SW
    "Q1":  (47.5, 10.0, 0),       # tab 44.05..49.65 VBUS_F; sources x50.58 SW
    "Q2":  (47.5, 23.0, 180),     # tab 45.35..50.3 SW; leads x44.42 PGND
    "L1":  (60.57, 15.0, 0),     # 17 mm superset land: pad1 SW (54.17), pad2 VOUT_INT (66.98)
    "RT1": (44.0, 33.0, 0),       # FET NTC below Q2, on AGND side of seam
    "RT2": (61.0, 28.7, 0),       # inductor NTC below L1
    # SW island taps (pad into pour at y<=26.5, other pad below)
    "C27": (55.3, 27.2, 90),      # BST: pad1 dn (28.25)=PS_BST, pad2 up=SW
    "R28": (57.6, 27.2, 90),      # ILIM: pad1 dn=PS_ILIM, pad2 up=SW
    "R17": (52.0, 27.2, 270),     # snub: pad1 up=SW, pad2 dn=SNUB
    "C17": (50.9, 30.4, 270),     # pad1 up=SNUB, pad2 dn=PGND (in bar)
    # ---- output bank straddle
    "C22": (83.16, 6.9, 90),     # top-strip straddle like C78     # 220u poly
    "C78": (74.34, 6.9, 90),    # pad1 dn in VOUT_INT, pad2 up in PGND_TOP strip
    "C23": (71.56, 16.9, 270),     # 22u/25V bank
    "C79": (74.78, 16.9, 270),
    "C80": (78.0, 16.9, 270),
    "C81": (81.22, 16.9, 270),
    "R27": (89.52, 4.4, 90),      # 2512 preload: pad1 dn VOUT_INT, pad2 up PGND_TOP
    # ---- Kelvin shunt + sense amps below it
    "R30": (86.7, 14.8, 0),       # pad1 VOUT_INT (83.74), pad2 VOUT_SW (89.66)
    "U4":  (86.7, 28.8, 90),      # INA240: pin8 (84.79,26.33) faces shunt
    "R31": (79.6, 33.5, 270),     # INA240_OUT -> I_MEAS
    "C31": (79.6, 36.7, 270),     # I_MEAS filter (AGND)
    "C33": (86.8, 21.0, 90),      # U4 5V0, inside the Kelvin pair
    "U5":  (86.7, 40.8, 90),      # INA228
    "C34": (83.6, 40.0, 270),     # U5 3V3
    "NT1": (91.2, 31.0, 0),       # star tie on the seam
    # ---- disconnect pair + LTC7004 + VOUT
    "Q3":  (95.5, 14.0, 270),     # tab VOUT_SW (up); sources y17.08 DISC_SRC; gate (97.41,17.08)
    "Q4":  (95.5, 22.5, 90),      # sources y19.42 DISC_SRC; tab VOUT (down); gate (93.59,19.42)
    "U6":  (95.8, 39.6, 180),     # LTC7004 under J4 (AGND side); gate/source/BST pins face left
    "C41": (91.5, 40.1, 90),      # BST: pad1 dn LTC_BST (U6.9), pad2 up DISC_SRC (U6.8)
    "C42": (97.6, 42.6, 0),       # 5V0 1u below U6.1/2
    "C43": (77.0, 44.0, 270),     # U7 5V0 100n
    "J4":  (96.65, 34.3, 90),     # pad1 VOUT (96.65,34.3), pad2 PGND (96.65,29.3)
    # ---- OVP + disconnect logic (y 33..50)
    "R45": (81.6, 33.5, 270),     # VOUT_INT -> OVP_DIV
    "R46": (81.6, 36.7, 270),
    "C44": (81.6, 39.9, 270),
    "U7":  (79.5, 44.0, 0),       # TLV7011 SC-70-5 (5V0 In2 island)
    "R47": (82.8, 44.5, 270),     # 3V3 -> REF_2V5
    "R48": (82.8, 47.7, 270),
    "Q9":  (79.5, 48.0, 0),       # OVP_TRIP pulls DISC_INP
    "Q7":  (75.5, 48.0, 0),       # EN_KILL pulls DISC_INP
    "R43": (72.0, 48.0, 270),     # OUT_REQ -> DISC_INP
    "R44": (94.5, 42.6, 0),       # DISC_INP -> AGND, below U6.4
    # ---- controller + comp/FB + EN cluster
    "U3":  (47.0, 36.0, 0),       # LM5145: right col = LO/VCC/EP/BST/HO/SW
    "R29": (46.2, 16.6, 270),     # VBUS_F (pad1 in band) -> PS_VIN corridor
    "C28": (47.75, 32.2, 90),     # PS_VIN 100n right on U3.20; pad2 up into PGND bar
    "C29": (52.0, 41.5, 0),       # PS_VCC 2.2u; pad2 PGND
    "C19": (48.2, 41.0, 0),      # ILIM 15p; pad1 taps the ILIM track
    "R1":  (40.2, 34.0, 0),       # FB divider + injection at the FB pin
    "R5":  (40.2, 36.0, 0),
    "R8":  (40.2, 38.0, 0),
    "R2":  (40.2, 40.0, 0),
    "R24": (40.2, 42.0, 0),
    "C24": (40.2, 44.0, 0),
    "C25": (43.2, 36.0, 0),       # 0.62 mm F.Cu channel for U3.5 FB
    "C26": (43.4, 38.5, 0),       # room for U3.8 FPWM escape via
    "R25": (43.4, 40.0, 0),
    "C18": (43.4, 42.0, 0),       # SS
    "R26": (43.4, 44.0, 0),       # RT
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
    "L2":  (12.6, 41.25, 0),      # FNR5040S 5x5: pad1 SW_AUX (west), pad2 5V0 (east)
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
    "R3":  (38.5, 61.5, 0),       # V_REF -> EAV_INV; 1 mm off U1 for its escapes
    "R6":  (38.5, 63.5, 0),       # I_REF -> EAI_INV
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
    "U11": (89.0, 60.0, 0),       # TCAN1042
    "C69": (89.0, 56.3, 0),       # 5V0
    "C70": (89.0, 63.7, 0),       # 3V3
    "J5":  (96.5, 52.7, 0),       # 1x08 runs +y to 70.5
    "R60": (63.5, 73.0, 0),       # VBUS_F -> VBUS_SNS, divider by U10.14 (ADC)
    "R61": (65.0, 74.75, 0),
    "C62": (66.5, 73.0, 0),
    # V_MEAS divider (0.1%) senses VOUT by the output connector
    "R32": (86.0, 46.0, 270),
    "R33": (86.0, 49.2, 270),
    "C32": (87.8, 49.2, 270),
}

MOUNT_HOLES = [(4.0, 4.0), (W - 4.0, 47.0), (4.0, H - 4.0), (W - 4.0, H - 4.0)]
FIDUCIALS = [(10.0, 2.2), (88.0, 77.8), (2.5, 45.0)]   # audit FD-001


# ------------------------------------------------------------------ zones --
# (net, layer, priority, [(x,y)...], pad_connection)
# The LTC7004 cluster sits below the seam on the AGND side, so the plain
# PGND/AGND split serves every part (the 120 x 80 layout needed an AGND
# pocket carved into the power strip; see branch phase1-120x80).
PWR_POURS = {  # name -> F.Cu polygon (also used by pour-connection checks)
    "VBUS_F":   [(12.0, 5.0), (49.6, 5.0), (49.6, 16.0), (12.0, 16.0)],
    "PGND_IN":  [(10.0, 17.3), (44.9, 17.3), (44.9, 30.0), (10.0, 30.0)],
    "PGND_TOP": [(66.0, 0.8), (91.4, 0.8), (91.4, 3.9), (66.0, 3.9)],
    "PGND_BAR": [(38.0, 30.0), (54.4, 30.0), (54.4, 31.7), (38.0, 31.7)],
    "SW":       [(50.5, 8.6), (56.9, 8.6), (56.9, 19.0), (58.4, 19.0),
                 (58.4, 26.5), (47.0, 26.5), (47.0, 19.0), (50.5, 19.0)],
    # stepped: full width under the top-strip caps and R27, then stops at
    # R30 pad1 so the Kelvin VOUT_INT lead leaves from the bare pad edge
    "VOUT_INT": [(64.3, 5.0), (91.4, 5.0), (91.4, 9.3), (83.8, 9.3),
                 (83.8, 16.0), (64.3, 16.0)],
    "PGND_OUT": [(70.0, 17.3), (83.0, 17.3), (83.0, 30.0), (70.0, 30.0)],
    # right column, top to bottom: R30 pad2 + Q3 tab, the source-to-source
    # band (notched at the two gate pads: Q3 top right, Q4 bottom left),
    # then Q4's tab wrapping J4.2 (PGND) down to J4.1, clear of NT1.
    "VOUT_SW":  [(89.6, 10.0), (99.5, 10.0), (99.5, 16.4), (89.6, 16.4)],
    "DISC_SRC": [(92.9, 16.65), (96.75, 16.65), (96.75, 18.25), (98.1, 18.25),
                 (98.1, 20.0), (94.25, 20.0), (94.25, 18.25), (92.9, 18.25)],
    "VOUT":     [(91.2, 20.2), (99.5, 20.2), (99.5, 37.0), (93.0, 37.0),
                 (93.0, 27.0), (91.2, 27.0)],
}
# In2 5V0 islands outside the aux column (priority 1 over the 3V3 plane):
# U4/C33 inside the Kelvin pair, U6/C42, U7/C43, U11/C69.
IN2_5V0 = [
    [(85.0, 17.2), (88.6, 17.2), (88.6, 30.6), (85.0, 30.6)],
    [(90.4, 37.6), (99.5, 37.6), (99.5, 44.2), (90.4, 44.2)],
    [(75.6, 42.4), (81.2, 42.4), (81.2, 45.6), (75.6, 45.6)],
    [(84.5, 53.5), (93.5, 53.5), (93.5, 68.0), (84.5, 68.0)],
]


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
        # In2: logic power distribution
        ("5V0", IN2, 0, [(0.5, 0.5), (AUXW, 0.5), (AUXW, H - 0.5), (0.5, H - 0.5)], "thermal"),
        ("5V0", IN2, 0, [(AUXW, 56.0), (56.0, 56.0), (56.0, H - 0.5), (AUXW, H - 0.5)], "thermal"),
        *[("5V0", IN2, 1, poly, "thermal") for poly in IN2_5V0],
        ("3V3", IN2, 0, [(AUXW, SEAM), (W - 0.5, SEAM), (W - 0.5, H - 0.5),
                         (56.0, H - 0.5), (56.0, 56.0), (AUXW, 56.0)], "thermal"),
        # B.Cu ground fills (mirror the In1 split, tracks push through)
        ("PGND", B, 0, pgnd_l, "thermal"),
        ("AGND", B, 0, agnd_r, "thermal"),
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
    ("R27", "1", "VOUT_INT"), ("R27", "2", "PGND_TOP"),
    ("R30", "1", "VOUT_INT"), ("R30", "2", "VOUT_SW"),
    ("Q3", "2", "VOUT_SW"), ("Q3", "3", "DISC_SRC"),
    ("Q4", "3", "DISC_SRC"), ("Q4", "2", "VOUT"),
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
    """Courtyard overlap / board-edge report on the real F.CrtYd polygons
    (bounding boxes flag false overlaps: L1's box, round mounting holes)."""
    from shapely.geometry import Polygon, box
    crt = []
    for fp in board.GetFootprints():
        fp.BuildCourtyardCaches()
        ps = fp.GetCourtyard(pcbnew.F_CrtYd)
        polys = []
        for k in range(ps.OutlineCount()):
            ol = ps.Outline(k)
            pts = [(pcbnew.ToMM(ol.CPoint(i).x), pcbnew.ToMM(ol.CPoint(i).y))
                   for i in range(ol.PointCount())]
            if len(pts) >= 3:
                polys.append(Polygon(pts).buffer(0))
        if polys:
            crt.append((fp.GetReference(), polys))
    fails = 0
    for i in range(len(crt)):
        for j in range(i + 1, len(crt)):
            (r1, a), (r2, b) = crt[i], crt[j]
            area = sum(p.intersection(q).area for p in a for q in b)
            if area > 1e-4:
                print(f"CRTYD {r1}<->{r2} overlap {area:.3f} mm^2")
                fails += 1
    # board edge check (terminal blocks J1/J4 legitimately overhang for wire entry)
    edge = box(ORG[0], ORG[1], ORG[0] + W, ORG[1] + H)
    for ref, polys in crt:
        if ref in ("J1", "J4"):
            continue
        if any(not edge.contains(p) for p in polys):
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
