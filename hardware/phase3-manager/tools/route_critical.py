"""Routing pass 1: hand-drawn critical copper, locked, before autorouting.

Run after gen_board.py, before export_dsn.py:
    python3 route_critical.py [board.kicad_pcb]

Everything here is exported to Freerouting as fixed copper (export_dsn.py
locks it), so the router works round it and never rips it up.

DIFFERENTIAL PAIRS. Freerouting has no notion of a pair: it routes USB_DP
and USB_DN (and CAN_H / CAN_L) as two unrelated nets, on whatever paths and
layers are cheapest. So the long runs are drawn here as coupled,
length-matched tracks on F.Cu over the B.Cu ground.

  USB (ESP32-S3 is full-speed only, 12 Mbit/s): U10 pins 13/14 exit west,
  run along y~31, and turn south down the x~47.5 channel between the buck
  area and the J6/J5 header ends -- the only way past two rows of 2.54 mm
  headers without splitting the pair round a pin. At y67 the pair splits
  round U12 (ESD, turned 180 so its clamp pins face the right lines), each
  line touching its clamp with a <1 mm stub, re-joins, runs east along y70
  and turns down into J3. J3's A/B rows interleave DP and DN (B7 DN, A6 DP,
  A7 DN, B6 DP), so DP joins A6-B6 with a U over the pin row and DN joins
  B7-A7 with a U under it. 0.25 mm / 0.2 mm gap. Controlled 90-ohm
  impedance is not achievable on 1.6 mm two-layer stock and is not needed
  at full speed; the pair is kept coupled and matched instead. The J3 end
  is tied to the USB4105 land pattern (J3 = GCT USB4105-GF-A): redraw it
  if the footprint changes.

  CAN (500 kbit/s): J1 pins 7/8 -> U11 pins 7/6, up the clear x~9 channel.
  U11 is turned 180 in gen_board.py so its bus pins face J1. The two nets
  have to cross once given the two pinouts; they do it at J1, where both
  leave the through-hole pins on B.Cu and via up past each other.

AUX BUCK (U8, LMR36015, 24-30 V -> 5 V). An autorouter treats SW as just
another net: the first autorouted pass ran it 0.2 mm wide round C50 with two
vias. Drawn here instead:

  * each input cap's VIN and PGND pads tie straight to their own pin pair
    (C51: pins 2/1 west, C50: pins 10/11 east), so each hot loop closes in
    about 2 mm on F.Cu, with two PGND vias per cap into the B.Cu plane;
  * SW (pin 12) runs 0.6 mm straight north into L2, and 0.3 mm round the
    west side to C52 (boot cap) -- the boot cap carries gate charge only;
  * VBUS_F comes 0.8 mm from F1 down x23.6 to C50; C51 (west) is reached by
    one 0.6 mm B.Cu jumper under the south side of U8, since the SW-to-C52
    run encloses it on F.Cu;
  * 5V0 leaves L2 0.8 mm into C54/C55, and a 0.6 mm trunk runs down the west
    channel and back east along y61.6 to the FB divider (R50) -- the rest
    of the 5V0 net (U9, U11, BZ1) hangs off that trunk via the router;
  * VBUS from J1 pins 1/2 runs 0.8 mm down x7 to F1.

The small-signal pins of U8 (BOOT, VCC, FB, PG, AGND) are left to the
routers, which handle these escapes on exact geometry.
"""
import os
import sys

import pcbnew
from pcbnew import FromMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "phase3-manager.kicad_pcb")
ORG = (20.0, 20.0)
VIA_D, VIA_DRILL = 0.6, 0.3
F, B = pcbnew.F_Cu, pcbnew.B_Cu


def T(layer, w, *pts):
    return ("T", layer, w, list(pts))


def V(x, y):
    return ("V", (x, y))


# net -> items; board-relative mm. T = (layer, width, points), V = via.
ROUTES = {
    # ---- differential pairs --------------------------------------------
    "USB_DN": [T(F, 0.25, (61.25, 30.98), (48.30, 30.98), (47.30, 31.98), (47.30, 67.30),
                 (46.00, 68.60), (46.00, 70.50), (46.50, 71.00), (50.80, 71.00),
                 (51.575, 70.225), (60.75, 70.225), (61.25, 70.725), (61.25, 72.32)),
               T(F, 0.2, (61.25, 72.32), (61.25, 73.00), (61.45, 73.20), (61.99, 73.20),
                 (62.25, 72.94), (62.25, 72.32)),                           # B7 -> A7
               T(F, 0.25, (46.00, 70.10), (46.785, 70.10))],              # stub to U12.5
    "USB_DP": [T(F, 0.25, (61.25, 32.25), (59.90, 32.25), (59.08, 31.43), (48.486, 31.43),
                 (47.75, 32.166), (47.75, 67.30), (49.05, 68.60), (49.05, 69.10),
                 (51.00, 69.10), (51.675, 69.775), (61.05, 69.775), (61.75, 70.475),
                 (61.75, 72.32)),
               T(F, 0.2, (61.75, 71.69), (62.00, 71.44), (62.56, 71.44), (62.75, 71.63),
                 (62.75, 72.32)),                                            # A6 -> B6
               T(F, 0.25, (49.05, 69.10), (48.265, 69.10))],              # stub to U12.3
    # U12's own GND and 3V3 pins sit between the split lines: one via each
    "U12_GND": [T(F, 0.25, (46.785, 69.10), (47.00, 68.80), (47.50, 68.30)), V(47.50, 68.30)],
    "U12_3V3": [T(F, 0.25, (48.265, 70.10), (50.00, 70.05)), V(50.00, 70.05)],
    "CAN_H": [T(B, 0.25, (5.00, 29.24), (9.20, 29.24)), V(9.20, 29.24),
              T(F, 0.25, (9.20, 29.24), (9.20, 9.34), (9.90, 8.64), (12.52, 8.64))],
    "CAN_L": [T(B, 0.25, (5.00, 31.78), (8.50, 31.78)), V(8.50, 31.78),
              T(F, 0.25, (8.50, 31.78), (8.50, 8.06), (9.20, 7.36), (12.52, 7.36))],

    # ---- aux buck power stage ----------------------------------------------
    "VBUS": [T(F, 0.8, (5.00, 14.00), (5.00, 16.50), (6.40, 16.50), (7.00, 17.10),
               (7.00, 40.00), (12.50, 40.00), (12.50, 42.00))],
    "VBUS_F": [T(F, 0.8, (24.00, 43.00), (27.60, 43.00)),                  # F1.2 -> D5.1
               T(F, 0.8, (23.60, 44.50), (23.60, 55.48), (22.30, 55.48)),  # F1.2 -> C50.1
               T(F, 0.3, (18.90, 54.525), (20.20, 54.525), (20.20, 55.20)),  # pin 10
               T(F, 0.25, (18.90, 55.175), (20.10, 55.175)),                 # pin 9 (EN)
               T(F, 0.3, (17.10, 54.525), (15.80, 54.525), (15.80, 55.20)),  # pin 2 -> C51.1
               V(23.60, 56.40), T(F, 0.8, (23.60, 55.48), (23.60, 56.40)),
               T(B, 0.6, (23.60, 56.40), (23.60, 59.80), (12.95, 59.80), (12.95, 55.50)),
               V(12.95, 55.50), T(F, 0.6, (12.95, 55.50), (13.60, 55.50))],
    "SW_AUX": [T(F, 0.25, (18.00, 54.00), (18.00, 53.30)),
               T(F, 0.6, (18.00, 53.30), (18.00, 51.40)),
               T(F, 0.3, (17.00, 51.40), (16.50, 50.90), (12.00, 50.90), (12.00, 57.30),
                 (13.42, 57.30))],
    "5V0": [T(F, 0.8, (18.00, 49.20), (10.90, 49.20)),
            T(F, 0.6, (10.90, 49.78), (9.20, 49.78), (8.80, 50.18), (8.80, 61.60),
              (22.72, 61.60), (22.72, 57.68))],
    "PGND": [T(F, 0.3, (17.10, 53.875), (16.40, 53.875), (15.80, 52.90)),  # pin 1 -> C51.2
             T(F, 0.3, (18.90, 53.875), (19.60, 53.875), (20.20, 52.90)),  # pin 11 -> C50.2
             V(13.90, 51.60), V(15.50, 51.60), V(20.60, 51.55), V(22.00, 51.55),
             T(F, 0.4, (13.90, 51.60), (13.90, 52.52)), T(F, 0.4, (15.50, 51.60), (15.50, 52.52)),
             T(F, 0.4, (20.60, 51.55), (20.60, 52.52)), T(F, 0.4, (22.00, 51.55), (22.00, 52.52)),
             V(14.20, 45.60), V(10.90, 45.60),
             T(F, 0.4, (14.20, 45.60), (14.20, 46.82)), T(F, 0.4, (10.90, 45.60), (10.90, 46.82))],
}

PAIRS = (("USB_DP", "USB_DN"), ("CAN_H", "CAN_L"))
# ROUTES keys that are labels for part of a net rather than the net itself
NET_ALIAS = {"U12_GND": "PGND", "U12_3V3": "3V3"}


def P(x, y):
    return VECTOR2I(FromMM(ORG[0] + x), FromMM(ORG[1] + y))


def length(items):
    n = 0.0
    for it in items:
        if it[0] == "T":
            pts = it[3]
            n += sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
                     for a, b in zip(pts, pts[1:]))
    return n


def main():
    board = pcbnew.LoadBoard(BOARD)
    nets = board.GetNetsByName()
    # idempotent on a fresh gen_board output: refuse to stack copper
    if any(True for _ in board.GetTracks()):
        sys.exit("route_critical: board already has tracks -- rerun gen_board.py first")
    n_t = n_v = 0
    for net, items in ROUTES.items():
        code = nets[NET_ALIAS.get(net, net)].GetNetCode()
        for it in items:
            if it[0] == "T":
                _, layer, w, pts = it
                for a, b in zip(pts, pts[1:]):
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(P(*a))
                    t.SetEnd(P(*b))
                    t.SetWidth(FromMM(w))
                    t.SetLayer(layer)
                    t.SetNetCode(code)
                    t.SetLocked(True)
                    board.Add(t)
                    n_t += 1
            else:
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(P(*it[1]))
                v.SetDrill(FromMM(VIA_DRILL))
                v.SetWidth(FromMM(VIA_D))
                v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetLayerPair(F, B)
                v.SetNetCode(code)
                v.SetLocked(True)
                board.Add(v)
                n_v += 1
    for a, b in PAIRS:
        la, lb = length(ROUTES[a]), length(ROUTES[b])
        print(f"route_critical: {a} {la:.2f} mm, {b} {lb:.2f} mm (skew {abs(la - lb):.2f} mm)")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"route_critical: {n_t} tracks, {n_v} vias (locked)")


if __name__ == "__main__":
    main()
