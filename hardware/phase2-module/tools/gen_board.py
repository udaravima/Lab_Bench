"""Generate phase2-module.kicad_pcb: netlist-driven placement + power copper.

Same pipeline as phase-1 tools/gen_board.py (see that file and tools/README.md
for the methodology); placement rationale in hardware/LAYOUT.md, working
notes in wip/gen_board_draft.py.

Board: 130x90 mm, 4 layer. Left edge = backplane (J1 XT60 + J5 signals),
right edge = front (J4 XT60). Current flows left->right; phase B mirrors
phase A about y=35 so both SW islands face U3. XT60 courtyards (17x17) are
component keep-outs but copper runs under the shroud freely.

Straps (pads that connect by short trace + vias instead of pour straddle,
added by route_board): C15/C16/C47 pad2, C36 pad1, R27 both, R29/R45/R60
signal pads, R75.1. All are DC or plane-backed nodes; noted per-line.

Run:  python3 gen_board.py wip/p2.net   (writes ../phase2-module.kicad_pcb)
"""
import os
import re
import sys

import pcbnew
from pcbnew import FromMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "phase2-module.kicad_pcb")
FPDIRS = [os.path.join(HERE, "..", "..", "phase1-module", "lib"),
          "/usr/share/kicad/footprints"]

ORG = (20.0, 20.0)
W, H = 130.0, 90.0
SEAM = 67.3                 # PGND (above) / AGND (below) In1+B.Cu split


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
PLACEMENT = {
    # ---- input chain (top-left): J1 -> F1 -> VBUS_FUSED -> R70 -> Q14
    "J1":  (4.5, 12.0, 0),        # pad1 VBUS (7.5,15.6); shroud overhangs -x
    "F1":  (19.0, 15.6, 0),
    "D5":  (36.9, 23.3, 270),     # TVS straddle VBUS_FUSED -> PGND_IN
    "C91": (40.3, 19.3, 270),
    "R70": (44.2, 15.6, 0),       # hot-swap shunt; U12.1/2 Kelvin from pad edges
    "Q14": (54.8, 8.5, 180),     # tab HS_SENSE; source (56.15,10.46) -> VBUS_P
    "R71": (42.4, 19.3, 270),    # UV/OV divider
    "R72": (42.4, 23.0, 270),
    "R73": (42.4, 26.4, 270),
    "U12": (35.0, 31.0, 0),       # LM5069
    "C90": (31.0, 34.5, 0),
    "R74": (39.0, 34.5, 0),
    "R75": (40.5, 31.0, 270),     # PGD pullup; pad1 strap to VBUS_P
    # ---- VBUS_P C-poly + input bank + aux taps
    "R29": (60.0, 55.4, 270),     # pad1 in pour; pad2 PS_VIN escapes B.Cu
    "C6":  (64.7, 17.2, 0),  "C7":  (64.7, 20.6, 0),
    "C8":  (64.7, 24.0, 0),  "C9":  (64.7, 27.4, 0),
    "C14": (61.4, 35.2, 0),
    "C10": (64.7, 43.0, 0),  "C11": (64.7, 46.4, 0),
    "C12": (64.7, 49.8, 0),  "C13": (64.7, 53.2, 0),
    # ---- phase A strip (top)
    "Q1":  (72.0, 9.0, 0),
    "Q2":  (72.0, 22.0, 180),
    "L1":  (85.5, 14.0, 0),
    "C27": (81.0, 26.2, 90),      # BST_A
    "R40": (78.0, 26.2, 270), "C49": (73.6, 27.8, 270),   # DNP snubber A
    "R36": (97.65, 10.0, 0), "R42": (97.65, 13.5, 0),     # phase shunts A
    # ---- phase B strip (mirror y'=70-y)
    "Q12": (72.0, 61.0, 0),
    "Q13": (72.0, 48.0, 180),
    "L3":  (85.5, 56.0, 0),
    "C35": (81.0, 43.77, 270),    # BST_B
    "R41": (78.0, 43.8, 90), "C58": (75.0, 42.2, 90),     # DNP snubber B
    "R37": (97.65, 56.8, 0), "R57": (97.65, 53.4, 0),
    # ---- U3 + compensation (AGND pocket x69..97.6 y31.6..38.9)
    "U3":  (76.0, 35.0, 0),
    "C22": (72.9, 40.55, 270), "C23": (77.9, 40.55, 270),  # PS_VCC
    "C28": (76.0, 29.7, 90),                              # PS_VIN
    "C30": (70.2, 34.9, 90),                                # VCCX
    "RT1": (70.9, 32.6, 0),
    "RT2": (86.0, 41.0, 0),
    "R1":  (81.1, 32.6, 0), "R2": (84.2, 32.6, 0), "R5": (87.3, 32.6, 0),
    "R8":  (90.4, 32.6, 0),
    "C25": (84.2, 34.55, 0), "R24": (87.3, 34.55, 0),
    "C18": (81.1, 36.5, 0), "R26": (84.2, 36.5, 0), "C21": (87.3, 36.5, 0),
    "R39": (90.4, 36.5, 0), "C20": (97.3, 34.55, 0), "C19": (90.4, 34.55, 0),
    "C24": (93.5, 34.55, 0),
    # ---- VOUT_INT column x99..110 y4..58 + PGND_OUT bar y59.6..68.4
    "C38": (98.05, 26.6, 180),    # straddle col <- PGND_A arm
    "C40": (98.05, 30.0, 180),
    "C45": (98.05, 40.4, 180),    # straddle col <- PGND_B arm
    "C46": (98.05, 43.7, 180),
    "C48": (98.05, 47.0, 180),    # straddle col <- PGND_B extension
    "C37": (105.7, 58.9, 270),    # polymer straddle col -> bar
    "C36": (118.0, 66.3, 0),      # polymer on bar; pad1 strap to col
    "C15": (105.6, 8.2, 270),     # polymer in-col; pad2 strap (vias to In1)
    "C16": (106.1, 44.7, 270),    # polymer in-col; pad2 strap
    "C47": (104.9, 18.7, 270),    # MLCC in-col; pad2 strap
    "R27": (104.0, 87.5, 0),       # preload; both pads strapped (DC)
    "R45": (98.3, 37.3, 180),    # OVP tap: pad1 in col; pad2 -> OVP_DIV
    "R60": (58.0, 66.5, 270),     # VBUS_SNS tap
    # ---- Kelvin shunts + INA240 + disconnect (right, clear of J4 keep-out)
    "R30": (107.9, 23.1, 0),      # col -> VOUT_SW
    "R34": (109.3, 27.05, 0),
    "U4":  (104.6, 31.9, 0),      # INA240, Kelvin pairs from shunt pad edges
    "R31": (101.5, 36.7, 0), "C31": (104.7, 36.7, 0), "C33": (107.9, 36.7, 0),
    "Q3":  (115.6, 13.6, 0),       # VOUT_SW -> DISC_SRC
    "Q10": (115.6, 20.6, 0),
    "Q4":  (123.3, 14.0, 180),    # DISC_SRC -> VOUT
    "Q11": (123.3, 21.0, 180),
    "C41": (114.1, 50.7, 0),     # LTC_BST straddle; pad1 -> U6.9 (static, ok)
    "J4":  (123.5, 38.2, 180),    # pads (120.5,34.6 VOUT / 41.8 PGND)
    "R32": (128.4, 53.4, 270),    # V_MEAS tap on VOUT edge strip
    # ---- output AGND pocket x111.5..126.8 y47.6..62
    "U6":  (119.0, 50.7, 180), "C42": (113.6, 48.4, 0),
    "U5":  (119.0, 57.6, 0), "C34": (113.6, 58.2, 0),
    "R33": (125.9, 57.5, 270), "C32": (123.3, 57.5, 270),
    "NT1": (109.5, 70.5, 0),      # PGND/AGND star tie on the seam
    # ---- aux rails (left column)
    "C50": (52.9, 24.0, 180), "C51": (52.9, 27.4, 180),
    "U8":  (47.0, 31.0, 0),
    "C52": (43.5, 31.0, 270), "C53": (43.6, 35.0, 0),
    "L2":  (47.0, 36.8, 270),
    "C54": (43.0, 42.0, 0), "C55": (51.0, 42.0, 0),
    "R50": (53.7, 38.6, 270), "R51": (53.7, 45.6, 270),
    "U9":  (47.0, 50.0, 0),
    "C56": (42.0, 56.0, 0), "C57": (51.0, 56.0, 0),
    # ---- analog band (AGND, y > SEAM)
    "J5":  (2.5, 60.0, 0),
    "U11": (18.0, 71.0, 0), "C69": (12.5, 69.5, 0), "C70": (12.5, 73.0, 0),
    "R61": (58.0, 71.0, 270), "C62": (61.0, 71.0, 270),
    "C3":  (29.5, 75.0, 0), "U1": (34.0, 76.0, 0), "C4": (38.0, 74.2, 0),
    "R3":  (38.2, 76.4, 0), "R6": (38.2, 78.6, 0),
    "U2":  (45.0, 77.0, 0), "C5": (52.0, 74.3, 0),
    "C1":  (41.3, 72.8, 0), "R4": (44.4, 72.8, 0), "D1": (48.3, 72.8, 0),
    "C2":  (41.3, 81.2, 0), "R7": (44.4, 81.2, 0), "D2": (48.3, 81.2, 0),
    "J6":  (30.0, 87.6, 90), "Q8": (36.5, 84.5, 0), "D6": (40.0, 87.5, 270),
    "U10": (74.0, 78.0, 0),
    "C71": (67.3, 71.8, 0), "C72": (80.7, 71.8, 0),
    "C73": (67.3, 84.2, 0), "C74": (80.7, 84.2, 0),
    "C64": (70.9, 70.6, 0), "C65": (77.1, 70.6, 0),
    "Y1":  (64.5, 76.5, 0), "C66": (60.5, 74.8, 0), "C67": (60.5, 78.2, 0),
    "C68": (66.5, 86.5, 0), "R65": (70.0, 86.5, 0),
    "R67": (73.5, 86.5, 0), "R68": (77.0, 86.5, 0),
    "D7":  (69.0, 88.6, 0), "R66": (72.5, 88.6, 0),
    "J3":  (52.0, 87.6, 90), "J2": (88.0, 87.6, 90),
    "R62": (85.0, 69.3, 0), "R63": (85.0, 71.3, 0), "R18": (85.0, 73.3, 0),
    "R16": (85.0, 75.3, 0), "R52": (85.0, 77.3, 0), "R64": (85.0, 79.3, 0),
    "R20": (88.3, 70.0, 0), "Q5": (88.8, 73.3, 0), "Q6": (93.0, 73.3, 0),
    "R19": (95.35, 77.0, 0), "R22": (98.45, 77.0, 0), "R23": (91.4, 70.0, 0),
    "D3":  (88.3, 77.0, 0), "D4": (91.85, 77.0, 0),
    "Q7":  (97.2, 73.3, 0), "Q9": (101.4, 73.3, 0),
    "R43": (94.5, 70.0, 0), "R44": (97.6, 70.0, 0),
    "R46": (100.7, 70.0, 0), "C44": (103.8, 70.0, 0),
    "U7":  (90.0, 80.2, 0), "R47": (93.4, 80.2, 0), "D8": (97.2, 80.2, 0),
    "C43": (86.6, 80.9, 0),
    "U13": (89.3, 83.6, 0), "C39": (99.2, 83.6, 0),
    "R35": (93.0, 83.6, 0), "R38": (96.1, 83.6, 0),
}

MOUNT_HOLES = [(4.0, 32.0), (126.0, 4.5), (4.0, 86.0), (126.0, 86.0)]
FIDUCIALS = [(10.0, 2.2), (120.0, 87.8), (2.5, 45.0)]


# ------------------------------------------------------------------ zones --
POCKET_MID = [(69.0, 31.6), (97.6, 31.6), (97.6, 38.9), (69.0, 38.9)]
POCKET_OUT = [(111.5, 47.6), (126.8, 47.6), (126.8, 62.0), (111.5, 62.0)]

PWR_POURS = {
    "VBUS":       [(5.5, 12.5), (21.0, 12.5), (21.0, 18.5), (5.5, 18.5)],
    "VBUS_FUSED": [(26.0, 12.5), (43.0, 12.5), (43.0, 18.6), (26.0, 18.6)],
    "PGND_IN":    [(28.0, 19.6), (52.5, 19.6), (52.5, 27.0), (28.0, 27.0)],
    "HS_SENSE":   [(44.5, 2.5), (56.5, 2.5), (56.5, 13.5), (48.0, 13.5),
                   (48.0, 17.5), (44.5, 17.5)],
    "VBUS_P":     [(57.5, 3.0), (72.3, 3.0), (72.3, 15.0), (63.9, 15.0),
                   (63.9, 55.0), (72.3, 55.0), (72.3, 67.0), (54.0, 67.0),
                   (54.0, 15.0), (57.5, 15.0)],
    "PGND_AUX":   [(42.0, 21.0), (52.6, 21.0), (52.6, 45.0), (42.0, 45.0)],
    "PGND_A":     [(64.5, 16.3), (71.2, 16.3), (71.2, 26.1), (83.5, 26.1),
                   (83.5, 25.2), (97.0, 25.2), (97.0, 31.0), (64.5, 31.0)],
    "PGND_MID_L": [(64.0, 30.2), (69.5, 30.2), (69.5, 40.0), (64.0, 40.0)],
    "PGND_B":     [(64.5, 39.0), (97.0, 39.0), (97.0, 48.6), (83.5, 48.6),
                   (83.5, 44.8), (71.2, 44.8), (71.2, 53.7), (64.5, 53.7)],
    "SW1":        [(75.0, 7.6), (81.4, 7.6), (81.4, 18.0), (82.9, 18.0),
                   (82.9, 25.5), (71.5, 25.5), (71.5, 18.0), (75.0, 18.0)],
    "SW2":        [(75.0, 63.1), (81.4, 63.1), (81.4, 52.0), (82.9, 52.0),
                   (82.9, 44.5), (71.5, 44.5), (71.5, 52.0), (75.0, 52.0)],
    "PH_CS_A":    [(88.5, 6.0), (96.3, 6.0), (96.3, 21.0), (88.5, 21.0)],
    "PH_CS_B":    [(88.5, 49.0), (96.3, 49.0), (96.3, 64.0), (88.5, 64.0)],
    "VOUT_INT":   [(99.0, 4.0), (110.0, 4.0), (110.0, 58.0), (99.0, 58.0)],
    "PGND_OUT":   [(99.0, 59.6), (122.5, 59.6), (122.5, 68.4), (99.0, 68.4)],
    "VOUT_SW":    [(110.7, 8.0), (116.0, 8.0), (116.0, 31.0), (110.7, 31.0)],
    "DISC_SRC":   [(117.0, 8.0), (122.4, 8.0), (122.4, 31.0), (117.0, 31.0)],
    "VOUT":       [(122.8, 8.0), (129.3, 8.0), (129.3, 54.0), (127.5, 54.0),
                   (127.5, 46.0), (117.0, 46.0), (117.0, 34.0), (122.8, 34.0)],
}


def zone_polys():
    F, B = pcbnew.F_Cu, pcbnew.B_Cu
    IN1, IN2 = pcbnew.In1_Cu, pcbnew.In2_Cu
    pgnd = [(0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, SEAM), (0.5, SEAM)]
    agnd = [(0.5, SEAM), (W - 0.5, SEAM), (W - 0.5, H - 0.5), (0.5, H - 0.5)]
    zones = [
        ("PGND", IN1, 0, pgnd, "thermal"),
        ("AGND", IN1, 0, agnd, "thermal"),
        ("AGND", IN1, 1, POCKET_MID, "thermal"),
        ("AGND", IN1, 1, POCKET_OUT, "thermal"),
        # In2 logic power (extents provisional; refined with route_board)
        ("5V0", IN2, 0, [(36.0, 20.0), (54.0, 20.0), (54.0, 62.0), (36.0, 62.0)], "thermal"),
        ("5V0", IN2, 1, [(28.0, 68.0), (58.0, 68.0), (58.0, 89.4), (28.0, 89.4)], "thermal"),
        ("5V0", IN2, 1, [(85.0, 66.0), (113.0, 66.0), (113.0, 87.0), (85.0, 87.0)], "thermal"),
        ("5V0", IN2, 1, [(108.0, 44.0), (128.0, 44.0), (128.0, 62.0), (108.0, 62.0)], "thermal"),
        ("5V0", IN2, 1, [(94.0, 28.0), (112.0, 28.0), (112.0, 40.0), (94.0, 40.0)], "thermal"),
        ("3V3", IN2, 0, [(0.5, SEAM), (W - 0.5, SEAM), (W - 0.5, H - 0.5), (0.5, H - 0.5)], "thermal"),
        ("PGND", B, 0, pgnd, "thermal"),
        ("AGND", B, 0, agnd, "thermal"),
        ("AGND", B, 1, POCKET_MID, "thermal"),
        ("AGND", B, 1, POCKET_OUT, "thermal"),
    ]
    for name, poly in PWR_POURS.items():
        net = {"PGND_IN": "PGND", "PGND_AUX": "PGND", "PGND_A": "PGND",
               "PGND_B": "PGND", "PGND_MID_L": "PGND", "PGND_OUT": "PGND"}.get(name, name)
        net = {"SW1": "SW1", "SW2": "SW2"}.get(name, net)
        zones.append((net, F, 2, poly, "full"))
    return zones


EXPECT_IN_POUR = [
    ("J1", "1", "VBUS"), ("F1", "1", "VBUS"), ("F1", "2", "VBUS_FUSED"),
    ("D5", "2", "PGND_IN"),
    ("C91", "1", "VBUS_FUSED"), ("C91", "2", "PGND_IN"),
    ("R71", "1", "VBUS_FUSED"),
    ("R70", "1", "VBUS_FUSED"), ("R70", "2", "HS_SENSE"),
    ("Q14", "2", "HS_SENSE"), ("Q14", "3", "VBUS_P"),
    ("R29", "1", "VBUS_P"), ("R60", "1", "VBUS_P"),
    ("C6", "1", "VBUS_P"), ("C6", "2", "PGND_A"),
    ("C7", "1", "VBUS_P"), ("C7", "2", "PGND_A"),
    ("C8", "1", "VBUS_P"), ("C8", "2", "PGND_A"),
    ("C9", "1", "VBUS_P"), ("C9", "2", "PGND_A"),
    ("C10", "1", "VBUS_P"), ("C10", "2", "PGND_B"),
    ("C11", "1", "VBUS_P"), ("C11", "2", "PGND_B"),
    ("C12", "1", "VBUS_P"), ("C12", "2", "PGND_B"),
    ("C13", "1", "VBUS_P"), ("C13", "2", "PGND_B"),
    ("C14", "1", "VBUS_P"), ("C14", "2", "PGND_MID_L"),
    ("C50", "1", "VBUS_P"), ("C50", "2", "PGND_AUX"),
    ("C51", "1", "VBUS_P"), ("C51", "2", "PGND_AUX"),
    ("Q1", "2", "VBUS_P"), ("Q1", "3", "SW1"),
    ("Q2", "2", "SW1"), ("Q2", "3", "PGND_A"),
    ("Q12", "2", "VBUS_P"), ("Q12", "3", "SW2"),
    ("Q13", "2", "SW2"), ("Q13", "3", "PGND_B"),
    ("L1", "1", "SW1"), ("L1", "2", "PH_CS_A"),
    ("L3", "1", "SW2"), ("L3", "2", "PH_CS_B"),
    ("C27", "2", "SW1"), ("C35", "2", "SW2"),
    ("R40", "1", "SW1"), ("R41", "1", "SW2"),
    ("C49", "2", "PGND_A"), ("C58", "2", "PGND_B"),
    ("C28", "2", "PGND_A"), ("C22", "2", "PGND_B"), ("C23", "2", "PGND_B"),
    ("R36", "1", "PH_CS_A"), ("R36", "2", "VOUT_INT"),
    ("R42", "1", "PH_CS_A"), ("R42", "2", "VOUT_INT"),
    ("R37", "1", "PH_CS_B"), ("R37", "2", "VOUT_INT"),
    ("R57", "1", "PH_CS_B"), ("R57", "2", "VOUT_INT"),
    ("C38", "1", "VOUT_INT"), ("C38", "2", "PGND_A"),
    ("C40", "1", "VOUT_INT"), ("C40", "2", "PGND_A"),
    ("C45", "1", "VOUT_INT"), ("C45", "2", "PGND_B"),
    ("C46", "1", "VOUT_INT"), ("C46", "2", "PGND_B"),
    ("C48", "1", "VOUT_INT"), ("C48", "2", "PGND_B"),
    ("C37", "1", "VOUT_INT"), ("C37", "2", "PGND_OUT"),
    ("C36", "2", "PGND_OUT"),
    ("C15", "1", "VOUT_INT"), ("C16", "1", "VOUT_INT"),
    ("C47", "1", "VOUT_INT"),
    ("R45", "1", "VOUT_INT"),
    ("R30", "1", "VOUT_INT"), ("R30", "2", "VOUT_SW"),
    ("R34", "1", "VOUT_INT"), ("R34", "2", "VOUT_SW"),
    ("Q3", "2", "VOUT_SW"), ("Q3", "3", "DISC_SRC"),
    ("Q10", "2", "VOUT_SW"), ("Q10", "3", "DISC_SRC"),
    ("Q4", "3", "DISC_SRC"), ("Q4", "2", "VOUT"),
    ("Q11", "3", "DISC_SRC"), ("Q11", "2", "VOUT"),
    ("J4", "1", "VOUT"), ("R32", "1", "VOUT"),
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
    for ref, bb in boxes:
        if ref in ("J1", "J4"):   # XT60 shrouds overhang the edge by design
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

    board = pcbnew.NewBoard(OUT)
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

    corners = [(0, 0), (W, 0), (W, H), (0, H)]
    for i in range(4):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(P(*corners[i]))
        seg.SetEnd(P(*corners[(i + 1) % 4]))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(FromMM(0.1))
        board.Add(seg)

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
