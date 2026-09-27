"""Routing pass 3 for the manager: phase-1's exact-geometry router, 2-layer settings.

    python3 finish_routes.py [board.kicad_pcb] [--base=pre_freerouting.kicad_pcb]

Runs hardware/phase1-module/tools/finish_routes.py (read its docstring)
with this board's differences:

  * two copper layers, so no In1/In2 plane drops;
  * PGND is poured on both layers and is fill-around: crossing the F.Cu
    ground pour costs nothing extra, while the 5V0 buck-output island keeps
    phase-1's pour cost so the router goes round it where it can;
  * each B.Cu cell costs extra, so closing a connection prefers F.Cu and
    the B.Cu ground plane under the USB/CAN pairs stays as whole as it can.
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "phase1-module", "tools"))
import finish_routes as fr  # noqa: E402

fr.BOARD = os.path.join(HERE, "..", "phase3-manager.kicad_pcb")
fr.COPPER = (pcbnew.F_Cu, pcbnew.B_Cu)
fr.POWER_NETS = {"PGND", "3V3", "5V0", "VBUS", "VBUS_F", "SW_AUX"}
fr.FILL_AROUND = {"PGND"}
fr.B_COST = 0.05

if __name__ == "__main__":
    fr.main()
