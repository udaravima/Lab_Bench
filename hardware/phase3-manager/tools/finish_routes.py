"""Finish routing: the 83 remaining connections as hand-planned waypoints.

Route_board/autoroute got this board to 83 unconnected at 0 copper DRC.
This script finishes it deliberately — every net below is a hand-planned
(net, layer, width, waypoints) polyline in the route_board tradition,
derived from the lane surveys (wip/lane_find.py) and the DRC item map
(wip/todo83.txt). Nothing here is algorithmic.

Groups (apply in order; run_drc.py between each; commit each):
  u3      U3 control cluster locals (AGND pocket, y 31-41)
  u10     U10 digital fan-out locals (x 69-99, y 69-89)
  haul    long lanes: U3<->MCU control, CAN/DAC/SLOT_ID trunks, east side
  aux     aux-regulator locals (U8/C52/D5 region)
  rail    5V0 ties
  stitch  plane/pour fragment stitching — LAST, geometry moves with copper

Usage:
  python3 finish_routes.py --list
  python3 finish_routes.py --check u3     # validate vs current copper
  python3 finish_routes.py --apply u3     # add copper, refill zones, save

Entry forms:
  ("net", layer, width, [(x, y), ...])      track polyline (split per segment)
  ("VIA",  net, x, y)                       via (0.6/0.3, F..B)
  ("DEL",  net, layer, x, y)                delete orphan track nearest x,y

Validation: numpy occupancy bitmap (0.125 mm) of all foreign pads/tracks/vias
per layer; same-net copper and earlier entries of the same net don't block;
zone interiors don't block (zones carve on refill; run_drc is the gate).
--check prints CLEAR/BLOCKED per entry; --apply refuses if any entry is
BLOCKED unless --force.
"""
import math
import os
import subprocess
import sys

import numpy as np
import pcbnew
from pcbnew import FromMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "..", "phase3-manager.kicad_pcb")
ORG = 20.0
RES = 0.125
NX, NY = int(100 / RES), int(80 / RES)
VIA_W, VIA_D = 0.6, 0.3
CLEAR = 0.25  # pads carry 0.25 local clearance overrides

F, B = "F.Cu", "B.Cu"

# ---------------------------------------------------------------------------
# Groups. Waypoints are board-relative mm. Comments name the DRC items
# (see wip/todo83.txt) each entry resolves.
# ---------------------------------------------------------------------------

U3 = {  # U3 (LM5143 QFN-40) pad centers, board-relative
    "31": (78.25, 32.10), "32": (77.75, 32.10), "33": (77.25, 32.10),
    "34": (76.75, 32.10), "40": (73.75, 32.10), "28": (78.90, 33.75),
    "29": (78.90, 33.25), "25": (78.90, 35.25), "24": (78.90, 35.75),
    "5": (73.10, 34.75), "15": (75.75, 37.90),
}

GROUPS = {}

GROUPS["u3"] = [
    # ============================================================
    # PS_RT tail re-route. The autorouter's 60 mm round-trip (pin37
    # north around SW1, down x86.12) ended in a pocket "wall" approach
    # (y35.62 + y37.38 + x90.38) that sealed every east-west route in
    # the AGND pocket. Delete the wall pieces; re-route the tail from
    # the surviving (86.12,23.88) north via: B.Cu down x85.7, rise at
    # (85.70,33.55) — the only legal rise slot in the R2/C25/R24 kp
    # lattice — and F.Cu into R26.1. (Full re-route impossible: the
    # C-pad at (76.0,30.5) + DITH vertical seal U3's north lanes.)
    ("DEL", "PS_RT", "F.Cu", 83.38, 36.12, 83.38, 35.62),
    ("DEL", "PS_RT", "F.Cu", 83.38, 35.62, 90.38, 35.62),
    ("DEL", "PS_RT", "F.Cu", 90.38, 35.62, 90.38, 37.38),
    ("DEL", "PS_RT", "F.Cu", 90.38, 37.38, 86.12, 37.38),
    ("DEL", "PS_RT", "F.Cu", 86.12, 37.38, 86.12, 38.00),
    ("DEL", "PS_RT", "F.Cu", 83.38, 36.12, 83.38, 36.50),
    ("DEL", "PS_RT", "VIA", 86.12, 38.00),
    ("DEL", "PS_RT", "B.Cu", 86.12, 38.00, 86.12, 23.88),
    # (tail re-route itself goes to the A* fallback: PS_SS's y37.38/y38.0
    # escape walls R26.1's north side; the (86.12,23.88) north via cluster
    # remains as the A* source)
    # ============================================================
    ("DEL", "PS_COMP", F, 78.00, 37.00, 74.00, 37.00),
    ("DEL", "PS_COMP", F, 74.00, 37.00, 74.00, 34.50),
    # --- PS_DITH: R39.1 -> y35.55 lane east to x94.3, via pair
    # crossing the x95.2 PH_CS_B vertical on B.Cu, into C20.1
    ("VIA", "PS_DITH", 94.30, 35.55),
    ("PS_DITH", F, 0.25, [(89.58, 36.50), (89.58, 35.55), (94.30, 35.55)]),
    ("VIA", "PS_DITH", 96.50, 35.55),
    ("PS_DITH", B, 0.25, [(94.30, 35.55), (96.50, 35.55)]),
    ("PS_DITH", F, 0.25, [(96.50, 35.55), (96.50, 35.00)]),
    # --- PS_EN: pin40 west via (clears the x72.5 stub + DITH kp)
    ("VIA", "PS_EN", 73.15, 31.65),
    ("PS_EN", F, 0.25, [(73.70, 32.10), (73.70, 31.65), (73.15, 31.65)]),
    # --- A* FALLBACK list after this batch applies (sealed pin
    # escapes: RT staircase + C-pad + DITH vert + PH_CS_B + G_HS_A
    # dives own every lane at 0.2 clearance):
    #   PS_VDDA  pin34/36 + C21.1 + R39.2
    #   PS_RES   pin32 -> C19.1
    #   PS_FPWM  pin33 -> (B.Cu haul)
    #   PS_VIN   pin25 -> stub(77.2,29.9)
    #   PS_PGOOD pin24 -> (B.Cu haul)
    #   VOUT_INT pin5 -> F.Cu zone
    #   FB       pin28 -> spine
    #   PS_EN    pin31 -> west via
]

GROUPS["u10"] = [
    # 3V3 U10.48 <-> F.Cu stub (70.1,70.6): straight north from pad 48
    ("3V3", F, 0.30, [(71.25, 73.84), (71.25, 73.20), (70.10, 72.05),
                      (70.10, 70.60)]),
    # 3V3 U10.36 <-> via (78.8,71.8): escape west then north
    ("3V3", F, 0.30, [(77.42, 75.25), (76.90, 75.25), (76.90, 74.20),
                      (78.82, 72.30), (78.82, 71.80)]),
    # AGND U10.47 <-> F.Cu stub (71.7,70.6)
    ("AGND", F, 0.30, [(71.75, 73.84), (71.75, 73.20), (71.68, 71.40),
                       (71.68, 70.60)]),
    # AGND U10.19<->23 bottom-edge jumper + 23 -> via (80.0,81.5)
    ("AGND", F, 0.30, [(74.25, 82.16), (74.25, 82.75), (76.25, 82.75),
                       (76.25, 82.16)]),
    ("AGND", F, 0.30, [(76.25, 82.75), (80.00, 82.75), (80.00, 81.50)]),
    # AGND via (79.0,70.6) <-> C72.2 (81.5,71.8)
    ("AGND", F, 0.30, [(79.00, 70.60), (79.00, 71.30), (80.90, 71.30),
                       (80.90, 71.80), (81.48, 71.80)]),
    # I2C_SDA R63.2 -> U10.30: pad-row escape west, F.Cu lane y74.0
    ("I2C_SDA", F, 0.25, [(78.16, 78.25), (77.40, 78.25), (77.40, 74.00),
                          (85.82, 74.00), (85.82, 71.30)]),      # + R63.2 @85.8,71.3
    # I2C_SCL R62.2 -> U10.31: same lane, drops at x84.9 (R62.2 @85.8,69.3)
    ("I2C_SCL", F, 0.25, [(78.16, 77.75), (77.15, 77.75), (77.15, 74.25),
                          (84.90, 74.25), (84.90, 69.60), (85.82, 69.30)]),
    # CAN_STB: B.Cu stub (81.6,74.5) -> U10.32
    ("CAN_STB", F, 0.25, [(78.16, 77.25), (77.65, 77.25), (77.65, 74.50),
                          (81.60, 74.50)]),
    # NTC_FET R67.2 -> U10.16 (bottom escapes south)
    ("NTC_FET", F, 0.25, [(72.75, 82.16), (72.75, 83.20), (74.30, 84.70),
                          (74.30, 86.50)]),
    # NTC_IND stub (77.8,86.9) -> U10.17
    ("NTC_IND", F, 0.25, [(73.25, 82.16), (73.25, 84.00), (77.80, 86.40),
                          (77.80, 86.90)]),
    # SWCLK U10.38 -> J2.3: north escape, east lane y73.0, south drop
    ("SWCLK", F, 0.25, [(76.25, 73.84), (76.25, 73.10), (91.20, 73.10),
                        (93.08, 75.00), (93.08, 87.60)]),
    # AUX_PG U10.42 <-> R52.2 (85.8,77.3)
    ("AUX_PG", F, 0.25, [(74.25, 73.84), (74.25, 73.20), (79.00, 73.20),
                         (79.00, 76.90), (85.82, 76.90), (85.82, 77.30)]),
    # V_MEAS U10.8 <-> U13.2 (88.2,83.6): west escape, lane y83.1, east
    ("V_MEAS", F, 0.25, [(69.84, 78.75), (69.10, 78.75), (69.10, 83.10),
                         (87.40, 83.10), (87.40, 83.60), (88.16, 83.60)]),
    # I_MEAS R35.1 (92.2,83.6) -> F.Cu trunk end (96.4,64.0)
    ("VIA", "I_MEAS", 96.40, 64.30),
    ("I_MEAS", F, 0.30, [(92.18, 83.60), (92.18, 84.00), (96.40, 79.60),
                         (96.40, 64.30)]),
    # HW_EN U10.43 -> B.Cu stub (73.1,63.9): north escape, via, B.Cu up
    ("VIA", "HW_EN", 73.75, 73.20),
    ("HW_EN", F, 0.25, [(73.75, 73.84), (73.75, 73.20)]),
    ("HW_EN", B, 0.30, [(73.75, 73.20), (73.75, 66.00), (73.12, 65.40),
                        (73.12, 63.90)]),
    # HW_EN R19.1 (94.5,77.0) -> B.Cu stub (84.0,72.8)
    ("VIA", "HW_EN", 84.00, 72.80),
    ("HW_EN", F, 0.25, [(94.53, 77.00), (94.53, 76.60), (84.90, 76.60),
                        (84.90, 73.60), (84.00, 72.80)]),
]

GROUPS["haul"] = [
    # PS_EN trunk: via (79.55,32.1) -> B.Cu corridor x79.6 (y41-53/54-58/61-66,
    # weave at y57-61 phase-B copper) -> analog region -> stub (88.2,70.0)
    ("PS_EN", B, 0.30, [(79.55, 32.10), (79.55, 39.00), (79.30, 41.00),
                        (79.30, 53.00), (79.55, 54.20), (79.55, 57.20),
                        (80.10, 58.60), (80.10, 60.90), (79.55, 62.00),
                        (79.55, 66.00), (79.90, 68.60), (88.20, 68.60),
                        (88.20, 70.00)]),
    # PS_FPWM: U3.33 north escape -> via west of DITH vert -> B.Cu down the
    # x81.4 corridor -> analog -> stub (82.1,75.2)
    ("VIA", "PS_FPWM", 77.25, 31.62),
    ("PS_FPWM", F, 0.25, [(77.25, 32.10), (77.25, 31.62)]),
    ("PS_FPWM", B, 0.30, [(77.25, 31.62), (77.25, 30.30), (81.40, 26.10),
                          (81.40, 41.00), (81.30, 42.50), (81.30, 53.00),
                          (81.40, 54.20), (81.40, 58.50), (81.90, 59.60),
                          (81.90, 61.20), (81.40, 62.40), (81.40, 66.00),
                          (82.10, 66.90), (82.10, 75.20)]),
    # PS_PGOOD: U3.24 east escape -> via -> B.Cu x82.4 -> stub (77.9,71.5)
    ("VIA", "PS_PGOOD", 79.90, 35.75),
    ("PS_PGOOD", F, 0.25, [(78.90, 35.75), (79.90, 35.75)]),
    ("PS_PGOOD", B, 0.30, [(79.90, 35.75), (79.90, 36.30), (82.40, 39.00),
                           (82.40, 53.00), (82.60, 54.20), (82.60, 58.40),
                           (82.00, 59.80), (82.00, 61.40), (82.40, 62.60),
                           (82.40, 66.00), (77.90, 70.40), (77.90, 71.50)]),
    # EAV_INJ D1.3 (49.3,72.8) -> R5.1 (86.5,32.6): B.Cu trunk lane y68.9,
    # east to x79.6 corridor, north to pocket
    ("VIA", "EAV_INJ", 49.30, 72.80),
    ("VIA", "EAV_INJ", 85.60, 33.30),
    ("EAV_INJ", B, 0.30, [(49.30, 72.80), (49.30, 68.90), (79.00, 68.90),
                          (79.00, 66.00), (78.60, 62.00), (78.60, 58.40),
                          (78.20, 57.00), (78.20, 54.00), (78.40, 41.00),
                          (78.40, 38.60), (85.60, 33.90), (85.60, 33.30)]),
    ("EAV_INJ", F, 0.25, [(85.60, 33.30), (85.60, 32.60), (86.48, 32.60)]),
    # EAI_INJ D2.3 (49.3,81.2) -> R8.1 (89.6,32.6): parallel lane y71.6,
    # east to x82.9 corridor, north
    ("VIA", "EAI_INJ", 49.30, 81.20),
    ("VIA", "EAI_INJ", 88.90, 34.90),
    ("EAI_INJ", B, 0.30, [(49.30, 81.20), (49.30, 71.60), (82.90, 71.60),
                          (82.90, 66.00), (83.30, 62.00), (83.30, 58.40),
                          (83.70, 57.00), (83.70, 53.50), (83.30, 42.50),
                          (83.30, 39.50), (88.90, 36.30), (88.90, 34.90)]),
    ("EAI_INJ", F, 0.25, [(88.90, 34.90), (88.90, 33.60), (89.58, 33.60),
                          (89.58, 32.60)]),
    # CAN_RX U11.4 (15.5,72.9) -> U10.33: B.Cu lane y69.2 west trunk
    ("VIA", "CAN_RX", 15.50, 72.90),
    ("VIA", "CAN_RX", 78.16, 76.75),
    ("CAN_RX", B, 0.30, [(15.50, 72.90), (15.50, 69.20), (76.80, 69.20),
                         (76.80, 76.75), (78.16, 76.75)]),
    # CAN_TX U11.1 (15.5,69.1) -> U10.34: lane y68.6
    ("VIA", "CAN_TX", 15.50, 69.10),
    ("VIA", "CAN_TX", 78.16, 76.25),
    ("CAN_TX", B, 0.30, [(15.50, 69.10), (15.50, 68.60), (77.60, 68.60),
                         (77.60, 76.25), (78.16, 76.25)]),
    # DAC_SCLK U1.6 (34.9,77.0) -> U10.13: lane y71.3
    ("VIA", "DAC_SCLK", 34.90, 77.00),
    ("VIA", "DAC_SCLK", 71.25, 82.16),
    ("DAC_SCLK", B, 0.30, [(34.90, 77.00), (34.90, 71.30), (70.20, 71.30),
                           (70.20, 83.50), (71.25, 83.50), (71.25, 82.16)]),
    # DAC_SDI U1.8 (34.9,76.0) -> U10.15: lane y70.5
    ("VIA", "DAC_SDI", 34.90, 76.00),
    ("VIA", "DAC_SDI", 72.25, 82.16),
    ("DAC_SDI", B, 0.30, [(34.90, 76.00), (34.90, 70.50), (69.60, 70.50),
                          (69.60, 84.20), (72.25, 84.20), (72.25, 82.16)]),
    # SLOT_ID0/1/2 J5 pads 4/5/6 (2.5, 67.6/70.2/72.7) -> U10.25/26/27:
    # nested lanes y69.8/71.0/72.2 (each turns down at decreasing x)
    ("VIA", "SLOT_ID0", 2.50, 67.60),
    ("VIA", "SLOT_ID0", 78.16, 80.75),
    ("SLOT_ID0", B, 0.30, [(2.50, 67.60), (2.50, 69.80), (78.90, 69.80),
                           (78.90, 80.75), (78.16, 80.75)]),
    ("VIA", "SLOT_ID1", 2.50, 70.16),
    ("VIA", "SLOT_ID1", 78.16, 80.25),
    ("SLOT_ID1", B, 0.30, [(2.50, 70.16), (2.50, 71.00), (78.50, 71.00),
                           (78.50, 80.25), (78.16, 80.25)]),
    ("VIA", "SLOT_ID2", 2.50, 72.70),
    ("VIA", "SLOT_ID2", 78.16, 79.75),
    ("SLOT_ID2", B, 0.30, [(2.50, 72.70), (2.50, 72.20), (78.10, 72.20),
                           (78.10, 79.75), (78.16, 79.75)]),
    # AUX_PG U8.8 (47.9,31.7) -> U10.42: west region lane y66.8 on B.Cu
    ("VIA", "AUX_PG", 47.90, 31.70),
    ("AUX_PG", B, 0.30, [(47.90, 31.70), (47.90, 40.00), (66.50, 58.60),
                         (66.50, 66.80), (74.25, 66.80), (74.25, 72.40),
                         (74.25, 73.20)]),
    ("AUX_PG", F, 0.25, [(74.25, 73.20), (74.25, 73.84)]),
    # INA_ALERT U10.44 -> U5.3 (116.8,57.6): east lane y73.0 to x98.2 drop
    ("VIA", "INA_ALERT", 98.20, 57.60),
    ("INA_ALERT", F, 0.25, [(73.25, 73.84), (73.25, 73.00), (97.20, 73.00),
                            (97.20, 57.60), (98.20, 57.60)]),
    # I2C_SDA U5.4 (116.8,58.1) -> R63.2 (85.8,71.3): B.Cu x99.1 drop
    ("VIA", "I2C_SDA", 116.80, 58.10),
    ("VIA", "I2C_SDA", 85.82, 71.30),
    ("I2C_SDA", B, 0.30, [(116.80, 58.10), (116.80, 59.40), (99.10, 59.40),
                          (99.10, 70.90), (85.82, 70.90), (85.82, 71.30)]),
    # DISC_INP U6.4 (121.2,50.2) -> F.Cu stub (101.6,71.6): east side drop
    ("VIA", "DISC_INP", 121.20, 50.20),
    ("DISC_INP", B, 0.30, [(121.20, 50.20), (121.20, 56.20), (101.60, 56.20),
                           (101.60, 71.60)]),
    # V_MEAS 3rd: stub (123.6,56.6) -> U13.2 (88.2,83.6)
    ("VIA", "V_MEAS", 123.60, 56.60),
    ("VIA", "V_MEAS", 88.16, 83.60),
    ("V_MEAS", B, 0.30, [(123.60, 56.60), (123.60, 57.40), (99.60, 57.40),
                         (99.60, 82.20), (88.16, 82.20), (88.16, 83.60)]),
    # V_REF U1.2 (33.1,75.5) -> R3.1 (37.4,76.4): short F.Cu hop
    ("V_REF", F, 0.25, [(33.10, 75.50), (34.60, 75.50), (34.60, 76.40),
                        (37.38, 76.40)]),
]

GROUPS["aux"] = [
    # AUX_BOOT C52.1 (43.5,30.2) -> U8.4 (46.1,31.7)
    ("AUX_BOOT", F, 0.25, [(43.50, 30.22), (44.90, 30.22), (46.10, 31.40),
                           (46.10, 31.68)]),
    # VBUS_P B.Cu stub (41.9,30.1) -> U8.2 (46.1,30.5) + U8.10 (47.9,30.5)
    ("VBUS_P", B, 0.40, [(41.90, 30.12), (43.00, 30.12), (44.20, 31.20),
                         (46.10, 31.20), (46.10, 30.52)]),
    ("VBUS_P", F, 0.25, [(46.10, 30.52), (46.10, 30.90), (46.50, 31.20),
                         (47.90, 31.20), (47.90, 30.52)]),
    # HS_PGD U8.9 (47.9,31.2) -> stub (40.5,31.0)
    ("HS_PGD", F, 0.25, [(47.88, 31.18), (47.20, 31.90), (43.80, 31.90),
                         (40.90, 31.00), (40.50, 31.00)]),
]

GROUPS["rail"] = [
    # 5V0 ties. Local pairs first, then the R22 -> via(111.7,48.4) riser.
    ("5V0", F, 0.40, [(28.00, 73.38), (28.00, 74.60), (34.00, 80.60),
                      (39.20, 80.60), (39.38, 80.00), (39.38, 56.00),
                      (39.38, 56.00)]),   # west: trk(28,73.4) -> via(39.4,56)
    ("5V0", F, 0.40, [(47.20, 76.02), (48.60, 76.02), (48.60, 74.30),
                      (50.12, 74.30)]),   # via(50.1,74.3) -> U2.8
    ("5V0", F, 0.30, [(85.82, 80.90), (87.60, 80.90), (87.60, 82.70),
                      (90.42, 82.70)]),   # C43.1 -> U13.5
    ("5V0", F, 0.30, [(90.44, 82.65), (91.00, 82.10), (91.00, 79.50)]),  # U13.5 -> trk(91,79.5)
    ("5V0", F, 0.30, [(91.00, 79.50), (91.00, 78.00), (88.10, 71.20),
                      (87.50, 70.02)]),   # trk(91,79.5) -> R20.1
    ("5V0", F, 0.30, [(92.58, 80.20), (92.58, 80.60), (97.62, 77.60),
                      (97.62, 77.02)]),   # R47.1 -> R22.1
    # R22.1 -> via (111.7,48.4): B.Cu riser east side
    ("VIA", "5V0", 111.72, 48.40),
    ("5V0", B, 0.40, [(97.62, 77.02), (97.62, 77.60), (111.72, 63.50),
                      (111.72, 48.40)]),
    # U3.6 5V0: stub (107.1,36.4) -> west lane y36.9 to U3.6 (73.1,35.25)
    ("5V0", F, 0.30, [(107.12, 36.38), (107.12, 36.90), (104.00, 36.90),
                      (104.00, 37.30), (73.60, 37.30), (73.60, 35.25),
                      (73.12, 35.25)]),
    # stub (107.1,36.4) second fragment -> via (111.7,48.4) (In2 5V0 patch
    # at x121-132/y49-60 does not reach; tie through B.Cu)
    ("5V0", B, 0.40, [(107.12, 36.38), (107.12, 42.00), (111.72, 46.60),
                      (111.72, 48.40)]),
]

GROUPS["stitch"] = [
    # AGND fragment/pad ties — via down to the B.Cu/In1 AGND mirror at each
    # spot (all south of SEAM 67.3 or inside the AGND pockets; WRONG SIDE
    # = PGND SHORT, verified per item below)
    ("VIA", "AGND", 14.62, 70.40),   # orphan stub pair far west (71.7,32.2 region is U3.3's own)
    ("VIA", "AGND", 71.70, 70.60),   # U10.47 cluster already tied in u10; this ties the F stub
    ("VIA", "AGND", 96.45, 54.55),   # U3.35 pocket stub pair
    ("VIA", "AGND", 104.40, 57.80),  # trk(102.1,33.8)-trk(105.5,37.1) east stubs
    ("VIA", "AGND", 84.60, 38.30),   # trk(84.1,36.9)F-trk(84.6,38.8)B pair
    ("VIA", "AGND", 86.90, 37.60),   # trk(86.9,37.8)B -> C21.2(88.1,36.5)
    ("VIA", "AGND", 116.90, 57.10),  # C34.2(114.4,58.2)-trk(116.8,57.1)
    ("VIA", "AGND", 121.15, 50.20),  # U6.3<->U6.5 (OUT pocket, x131.5-146.8 board-rel=111.5-126.8)
    ("VIA", "AGND", 118.60, 57.75),  # U5.7(121.2,58.1)-via(118.5,57.4)
    # PGND zone islands (F.Cu pours, same priority — stitched through to
    # the In1/B planes with a via inside each island)
    ("VIA", "PGND", 42.00, 21.00),
    ("VIA", "PGND", 64.00, 30.20),
    ("VIA", "PGND", 64.50, 39.00),
    ("VIA", "PGND", 76.80, 37.90),   # also serves U3.17 pad-to-zone
    # 3V3 In2 zone island + SW1 F.Cu zone island
    ("VIA", "3V3", 60.00, 80.00),
    ("VIA", "SW1", 75.00, 7.60),
]

# ---------------------------------------------------------------------------
# machinery
# ---------------------------------------------------------------------------

_kernels = {}


def kernel(r):
    if r not in _kernels:
        yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
        _kernels[r] = (yy * yy + xx * xx) <= r * r
    return _kernels[r]


class Occupancy:
    """Per-layer foreign-copper bitmap. zone interiors don't block."""

    def __init__(self, board):
        self.b = board
        self.layers = {board.GetLayerName(i): i for i in range(pcbnew.PCB_LAYER_ID_COUNT)
                       if board.GetLayerName(i)}
        self.bmp = {}

    def layer(self, name):
        if name in self.bmp:
            return self.bmp[name]
        lid = self.layers[name]
        m = np.zeros((NY, NX), dtype=bool)

        def seg(xs, ys, xe, ye, w):
            r = max(0, int(round((w / 2 + CLEAR) / RES)))
            n = max(1, int(math.hypot(xe - xs, ye - ys) / (RES / 2)))
            ts = np.linspace(0, 1, n + 1)
            cx = np.round((xs + (xe - xs) * ts) / RES).astype(int)
            cy = np.round((ys + (ye - ys) * ts) / RES).astype(int)
            for x, y in zip(cx, cy):
                x, y = int(x), int(y)
                if r == 0:
                    if 0 <= x < NX and 0 <= y < NY:
                        m[y, x] = True
                    continue
                xl, xh = max(0, x - r), min(NX - 1, x + r)
                yl, yh = max(0, y - r), min(NY - 1, y + r)
                if xl > xh or yl > yh:
                    continue
                m[yl:yh + 1, xl:xh + 1] |= kernel(r)[yl - y + r:yh - y + r + 1,
                                                    xl - x + r:xh - x + r + 1]

        for t in self.b.GetTracks():
            if not t.IsOnLayer(lid):
                continue
            s, e = t.GetStart(), t.GetEnd()
            x1, y1 = mm(s.x), mm(s.y)
            x2, y2 = mm(e.x), mm(e.y)
            if t.Type() == pcbnew.PCB_VIA_T:
                seg(x1, y1, x1, y1, pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) + 0.25)
            else:
                seg(x1, y1, x2, y2, pcbnew.ToMM(t.GetWidth()))
        for fp in self.b.GetFootprints():
            for p in fp.Pads():
                if not p.IsOnLayer(lid):
                    continue
                bb = p.GetBoundingBox()
                x1 = int(round(mm(bb.GetX()) / RES)) - 2
                y1 = int(round(mm(bb.GetY()) / RES)) - 2
                x2 = int(round((mm(bb.GetX()) + pcbnew.ToMM(bb.GetWidth())) / RES)) + 2
                y2 = int(round((mm(bb.GetY()) + pcbnew.ToMM(bb.GetHeight())) / RES)) + 2
                m[max(0, y1):min(NY, y2 + 1), max(0, x1):min(NX, x2 + 1)] = True
        self.bmp[name] = m
        return m

    def blocked(self, layer, xs, ys, xe, ye, w):
        m = self.layer(layer)
        r = max(0, int(round((w / 2) / RES)))
        n = max(1, int(math.hypot(xe - xs, ye - ys) / (RES / 2)))
        ts = np.linspace(0, 1, n + 1)
        for x, y in zip(np.round((xs + (xe - xs) * ts) / RES).astype(int),
                        np.round((ys + (ye - ys) * ts) / RES).astype(int)):
            x, y = int(x), int(y)
            if r == 0:
                if 0 <= x < NX and 0 <= y < NY and m[y, x]:
                    return (x * RES, y * RES)
            else:
                xl, xh = max(0, x - r), min(NX - 1, x + r)
                yl, yh = max(0, y - r), min(NY - 1, y + r)
                if xl <= xh and yl <= yh and m[yl:yh + 1, xl:xh + 1].any():
                    return (x * RES, y * RES)
        return None

    def stamp(self, layer, xs, ys, xe, ye, w):
        """Mark proposed copper as foreign for LATER entries (different nets
        check before their own stamp; same-net re-checks stay unaffected)."""
        m = self.layer(layer)
        r = max(0, int(round((w / 2 + CLEAR) / RES)))
        n = max(1, int(math.hypot(xe - xs, ye - ys) / (RES / 2)))
        ts = np.linspace(0, 1, n + 1)
        for x, y in zip(np.round((xs + (xe - xs) * ts) / RES).astype(int),
                        np.round((ys + (ye - ys) * ts) / RES).astype(int)):
            x, y = int(x), int(y)
            if r == 0:
                if 0 <= x < NX and 0 <= y < NY:
                    m[y, x] = True
                continue
            xl, xh = max(0, x - r), min(NX - 1, x + r)
            yl, yh = max(0, y - r), min(NY - 1, y + r)
            if xl <= xh and yl <= yh:
                m[yl:yh + 1, xl:xh + 1] |= kernel(r)[yl - y + r:yh - y + r + 1,
                                                    xl - x + r:xh - x + r + 1]


def mm(v):
    return pcbnew.ToMM(v) - ORG


def validate(group, board):
    dels = [e for e in GROUPS[group] if e[0] == "DEL"]
    ok, bad = 0, []
    for entry in GROUPS[group]:
        if entry[0] == "VIA":
            _, net, x, y = entry
            occ2 = net_occupancy(None, board, net, dels)  # fresh copy minus net
            hit = occ2.blocked_all(x, y, VIA_W)
            where = hit
        elif entry[0] == "DEL":
            print(f"CLEAR   DEL {entry[1]}")
            ok += 1
            continue
        else:
            net, layer, w, pts = entry
            occ2 = net_occupancy(None, board, net, dels)
            where = None
            for a, b2 in zip(pts, pts[1:]):
                where = occ2.blocked(layer, a[0], a[1], b2[0], b2[1], w)
                if where:
                    break
        if where is None:
            ok += 1
            desc = entry[0] if entry[0] in ("VIA", "DEL") else f"{entry[0]} {entry[1]}"
            print(f"CLEAR   {desc}")
        else:
            bad.append((entry, where))
            print(f"BLOCKED {entry[0] if entry[0] in ('VIA','DEL') else entry[0]}: {where}")
    return ok, bad


def net_occupancy(occ, board, net, dels=()):
    """Analytic clearance checker for candidate copper of `net`.

    Checks exact point-to-geometry distance along the candidate centerline
    against every foreign track (segment+width), via (circle) and pad
    (rectangle) on the candidate's layer. No rasterization, no quantization
    false-positives at exactly-legal clearances.
    """
    TRKCLR = 0.2    # netclass default clearance

    class View:
        def __init__(self, board, net, dels=()):
            self.net = net
            self.dels = dels  # ((net,layer,x1,y1,x2,y2),...) removed by this batch
            self.board = board
            self.layers = {board.GetLayerName(i): i for i in range(pcbnew.PCB_LAYER_ID_COUNT)
                           if board.GetLayerName(i)}
            self.items = {}

        def _items(self, layer):
            if layer in self.items:
                return self.items[layer]
            lid = self.layers[layer]
            segs, vias, pads = [], [], []
            for t in self.board.GetTracks():
                if not t.IsOnLayer(lid) or t.GetNetname() == self.net:
                    continue
                s, e = t.GetStart(), t.GetEnd()
                x1, y1 = mm(s.x), mm(s.y)
                x2, y2 = mm(e.x), mm(e.y)
                if any(d[1] == t.GetNetname()
                       and ((d[2] == "VIA" and t.Type() == pcbnew.PCB_VIA_T
                             and abs(d[3] - x1) < 0.1 and abs(d[4] - y1) < 0.1)
                            or (d[2] == layer and t.Type() != pcbnew.PCB_VIA_T
                                and abs(d[3] - x1) < 0.1 and abs(d[4] - y1) < 0.1
                                and abs(d[5] - x2) < 0.1 and abs(d[6] - y2) < 0.1))
                       for d in self.dels):
                    continue
                if t.Type() == pcbnew.PCB_VIA_T:
                    vias.append((x1, y1, pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2))
                else:
                    segs.append((x1, y1, x2, y2, pcbnew.ToMM(t.GetWidth()) / 2))
            for fp in self.board.GetFootprints():
                for p in fp.Pads():
                    if not p.IsOnLayer(lid) or p.GetNetname() == self.net:
                        continue
                    bb = p.GetBoundingBox()
                    try:
                        local = p.GetLocalClearance()
                    except Exception:
                        local = None
                    clr = pcbnew.ToMM(local) if local is not None and local >= 0 else TRKCLR
                    pads.append((mm(bb.GetX()), mm(bb.GetY()),
                                 mm(bb.GetX()) + pcbnew.ToMM(bb.GetWidth()),
                                 mm(bb.GetY()) + pcbnew.ToMM(bb.GetHeight()), clr))
            self.items[layer] = (np.array(segs).reshape(-1, 5) if segs else np.zeros((0, 5)),
                                 np.array(vias).reshape(-1, 3) if vias else np.zeros((0, 3)),
                                 np.array(pads).reshape(-1, 5) if pads else np.zeros((0, 5)))
            return self.items[layer]

        def _hit(self, layer, px, py, half):
            """Nearest violation for a sample point, or None."""
            segs, vias, pads = self._items(layer)
            # tracks: distance to segment minus half-widths
            if segs.size:
                x1, y1, x2, y2, hw = segs.T
                dx, dy = x2 - x1, y2 - y1
                L2 = dx * dx + dy * dy
                L2 = np.where(L2 == 0, 1e-12, L2)
                t = np.clip(((px - x1) * dx + (py - y1) * dy) / L2, 0, 1)
                d = np.hypot(px - (x1 + t * dx), py - (y1 + t * dy)) - hw - half
                i = int(np.argmin(d))
                if d[i] < TRKCLR - 1e-9:
                    return (f"track@({x1[i]:.2f},{y1[i]:.2f})-({x2[i]:.2f},{y2[i]:.2f}) w={2*hw[i]:.2f}", round(d[i], 3))
            if vias.size:
                vx, vy, vr = vias.T
                d = np.hypot(vx - px, vy - py) - vr - half
                i = int(np.argmin(d))
                if d[i] < TRKCLR - 1e-9:
                    return (f"via@({vx[i]:.2f},{vy[i]:.2f})", round(d[i], 3))
            if pads.size:
                rx1, ry1, rx2, ry2, pclr = pads.T
                ddx = np.maximum(np.maximum(rx1 - px, px - rx2), 0.0)
                ddy = np.maximum(np.maximum(ry1 - py, py - ry2), 0.0)
                d = np.hypot(ddx, ddy) - half
                i = int(np.argmin(d - pclr))
                if d[i] < pclr[i] - 1e-9:
                    return (f"pad rect=({rx1[i]:.2f},{ry1[i]:.2f})-({rx2[i]:.2f},{ry2[i]:.2f})", round(d[i], 3))
            return None

        def blocked(self, layer, xs, ys, xe, ye, w):
            half = w / 2
            n = max(1, int(math.hypot(xe - xs, ye - ys) / 0.05))
            ts = np.linspace(0, 1, n + 1)
            for x, y in zip(xs + (xe - xs) * ts, ys + (ye - ys) * ts):
                hit = self._hit(layer, float(x), float(y), half)
                if hit:
                    return (f"{hit[0]} d={hit[1]} at ({x:.2f},{y:.2f})")
            return None

        def blocked_all(self, x, y, w):
            for layer in ("F.Cu", "B.Cu"):
                r = self.blocked(layer, x, y, x, y, w)
                if r:
                    return f"{layer}: {r}"
            return None

    return View(board, net, tuple(d for d in dels))


def layer_id(board, name):
    for i in range(pcbnew.PCB_LAYER_ID_COUNT):
        if board.GetLayerName(i) == name:
            return i
    raise KeyError(name)


def apply(group, board):
    nets = {n.GetNetname(): n for n in board.GetNetsByName().values() if n.GetNetname()}
    all_tracks = list(board.Tracks()) if not callable(getattr(board, "Tracks", None)) else list(board.GetTracks())
    try:
        all_tracks = list(board.GetTracks())
    except TypeError:
        pass
    n_tracks = n_vias = 0
    for entry in GROUPS[group]:
        if entry[0] == "VIA":
            _, net, x, y = entry
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(P(x, y))
            v.SetDrill(FromMM(VIA_D))
            v.SetWidth(FromMM(VIA_W))
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetNetCode(nets[net].GetNetCode())
            board.Add(v)
            n_vias += 1
        elif entry[0] == "DEL":
            if entry[2] == "VIA":
                _, net, _, vx, vy = entry
                for t in all_tracks:
                    if t.Type() != pcbnew.PCB_VIA_T or t.GetNetname() != net:
                        continue
                    s = t.GetStart()
                    if abs(mm(s.x) - vx) < 0.1 and abs(mm(s.y) - vy) < 0.1:
                        board.Remove(t)
                continue
            _, net, layer, x1, y1, x2, y2 = entry
            lid = layer_id(board, layer)
            for t in all_tracks:
                if t.GetNetname() != net or not t.IsOnLayer(lid) or t.Type() == pcbnew.PCB_VIA_T:
                    continue
                s, e = t.GetStart(), t.GetEnd()
                if (abs(mm(s.x) - x1) < 0.1 and abs(mm(s.y) - y1) < 0.1
                        and abs(mm(e.x) - x2) < 0.1 and abs(mm(e.y) - y2) < 0.1):
                    board.Remove(t)
        else:
            net, layer, w, pts = entry
            lid = layer_id(board, layer)
            for a, b2 in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(P(a[0], a[1]))
                t.SetEnd(P(b2[0], b2[1]))
                t.SetWidth(FromMM(w))
                t.SetLayer(lid)
                t.SetNetCode(nets[net].GetNetCode())
                board.Add(t)
                n_tracks += 1
    return n_tracks, n_vias


def P(x, y):
    return VECTOR2I(FromMM(ORG + x), FromMM(ORG + y))


def main():
    if "--list" in sys.argv:
        for g, items in GROUPS.items():
            sig = sum(1 for e in items if e[0] != "DEL")
            print(f"{g:8s} {len(items):3d} entries ({sig} copper)")
        return
    mode = "check"
    if "--apply" in sys.argv:
        mode = "apply"
    force = "--force" in sys.argv
    group = sys.argv[-1]
    if group not in GROUPS:
        sys.exit(f"unknown group {group}")
    board = pcbnew.LoadBoard(BOARD)
    board.BuildConnectivity()
    if mode == "check":
        ok, bad = validate(group, board)
        print(f"\n{ok}/{len(GROUPS[group])} clear, {len(bad)} blocked")
        sys.exit(1 if bad else 0)
    # apply: validate first unless forced
    ok, bad = validate(group, board)
    if bad and not force:
        sys.exit(f"refusing: {len(bad)} blocked entries (use --force)")
    nt, nv = apply(group, board)
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"applied {group}: +{nt} tracks, +{nv} vias -> {BOARD}")


if __name__ == "__main__":
    main()
