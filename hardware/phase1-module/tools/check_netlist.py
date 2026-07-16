"""Assert generated-schematic connectivity against gen_phase1.EXPECTED_NETS.

Usage: python3 check_netlist.py <netlist.net>
The netlist comes from: kicad-cli sch export netlist -o out.net phase1-module.kicad_sch
Logic lives in hardware/common/netcheck.py (shared with phase2-module).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "common"))
from netcheck import run_netcheck, parse_nets  # noqa: E402,F401 (parse_nets re-exported)
from gen_phase1 import EXPECTED_NETS           # noqa: E402

if __name__ == "__main__":
    sys.exit(1 if run_netcheck(sys.argv[1], EXPECTED_NETS) else 0)
