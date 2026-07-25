"""Import a Freerouting Specctra session back onto the pass-1 board.

Workflow (the DSN is exported zone-free — KiCad refills the pours here,
and Freerouting chokes on this board's notched zone polygons):

    python3 gen_board.py wip/p2.net
    python3 route_board.py
    python3 export_dsn.py            # zone-free, pass-1 copper locked
    java -jar freerouting.jar --gui.enabled=false \
         -de wip/p2_nz.dsn -do wip/p2_nz.ses -mp 10
    python3 import_ses.py            # <- here: import, refill, verify
    python3 run_drc.py

The pass-1 copper leaves KiCad as `(type fix)` wires, so Freerouting
returns it untouched in the session; this script checks that the count
came back before saving, because a session that dropped the fixed wires
would silently destroy the hand-routed power/gate/Kelvin work.

Usage: python3 import_ses.py [session.ses]
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "..", "phase2-module.kicad_pcb")
SES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "wip", "p2_nz.ses")

# pass-1 copper that must survive the round trip (route_board's own count)
MIN_PASS1_TRACKS = 400


def stats(board):
    t = v = 0
    for x in board.GetTracks():
        if isinstance(x, pcbnew.PCB_VIA):
            v += 1
        else:
            t += 1
    return t, v


def unconnected(board):
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount()


def main():
    board = pcbnew.LoadBoard(BOARD)
    before_t, before_v = stats(board)
    before_u = unconnected(board)
    print(f"before: {before_t} tracks, {before_v} vias, {before_u} unconnected")

    if not os.path.exists(SES):
        sys.exit(f"no session file: {SES}")
    if not pcbnew.ImportSpecctraSES(board, SES):
        sys.exit("ImportSpecctraSES failed")

    after_t, after_v = stats(board)
    after_u = unconnected(board)
    print(f"after:  {after_t} tracks, {after_v} vias, {after_u} unconnected")

    if after_t + after_v < MIN_PASS1_TRACKS:
        sys.exit(f"REFUSING to save: only {after_t + after_v} copper items "
                 f"came back — the session dropped the fixed pass-1 routes")
    if after_u > before_u:
        sys.exit(f"REFUSING to save: unconnected went UP ({before_u} -> {after_u})")

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"saved. unconnected {before_u} -> {after_u}")


if __name__ == "__main__":
    main()
