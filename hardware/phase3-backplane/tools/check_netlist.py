"""Assert generated-schematic connectivity against gen_backplane.EXPECTED_NETS.

Usage: python3 check_netlist.py <netlist.net>
Logic lives in hardware/common/netcheck.py.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "common"))
from netcheck import run_netcheck, parse_nets  # noqa: E402,F401
from gen_backplane import EXPECTED_NETS        # noqa: E402

if __name__ == "__main__":
    sys.exit(1 if run_netcheck(sys.argv[1], EXPECTED_NETS) else 0)
