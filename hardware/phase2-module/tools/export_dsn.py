"""Export a Specctra DSN for Freerouting, zone-free, pass-1 copper locked.

Two deliberate choices, both learned the hard way (2026-07-25):

 1. **Zones are stripped from the exported copy.** Freerouting 1.9 and
    2.2.4 both die in `PolylineTrace.combine` (runaway recursion, then a
    HeadlessException from its GUI error handler) on this board's zone
    set — the notched VOUT_INT In2 patch and the AGND pockets are the
    likely trigger. The board's own geometry is clean (no zero-length,
    sub-50 um or duplicate segments — checked). Dropping the zones costs
    nothing: KiCad refills every pour on import (import_ses.py), and the
    pours are all on In1/In2 planes or F.Cu power areas that the signal
    router should not be threading anyway.

 2. **Every existing track/via is locked**, so it exports as `(type fix)`
    and Freerouting returns it untouched. That protects the whole
    pass-1 investment: power pours' via arrays, both gate fan-outs, the
    Kelvin pairs, the DISC_GATE trunk.

The board file on disk is never modified — locking happens on the
in-memory copy only.

Usage: python3 export_dsn.py [out.dsn]
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "..", "phase2-module.kicad_pcb")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "wip", "p2_nz.dsn")


def main():
    board = pcbnew.LoadBoard(BOARD)

    zones = list(board.Zones())
    for z in zones:
        board.Remove(z)

    locked = 0
    for t in board.GetTracks():
        t.SetLocked(True)
        locked += 1

    if not pcbnew.ExportSpecctraDSN(board, OUT):
        sys.exit("ExportSpecctraDSN failed")
    print(f"export_dsn: {locked} copper items locked, {len(zones)} zones "
          f"stripped -> {os.path.relpath(OUT, HERE)}")


if __name__ == "__main__":
    main()
