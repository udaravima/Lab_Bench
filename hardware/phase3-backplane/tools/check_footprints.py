"""Assert footprint integrity of the exported netlist (see common/netcheck.py).

Usage: python3 check_footprints.py <netlist.net>   (run after check_netlist.py)
The footprint library is shared with phase1-module.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
from netcheck import run_fpcheck  # noqa: E402

FPDIRS = [os.path.join(HERE, "..", "..", "phase1-module", "lib"),
          "/usr/share/kicad/footprints"]

if __name__ == "__main__":
    sys.exit(1 if run_fpcheck(sys.argv[1], FPDIRS) else 0)
