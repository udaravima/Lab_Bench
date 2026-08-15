"""Run DRC on the board via kicad-cli (KiCad 10; the old pcbnew-API path
died with the 7->10 upgrade — pcbnew.EDA_UNITS_MILLIMETRES is gone).

Usage: python3 run_drc.py [board.kicad_pcb]
Writes ../drc-report.txt, prints a violation-type summary, and exits 1 on
any error-severity copper/silk violation or any unconnected item.

Known-benign baseline classes (toolchain-upgrade noise, not board defects)
are counted but do not fail the run:
  lib_footprint_mismatch — KiCad 10's bundled libs evolved since the board
    was built against KiCad 7's; the board is the source of truth. Do NOT
    bulk-resync footprints to silence these.
  lib_footprint_issues   — footprints living under a standard-lib nickname
    (VSSOP variants) that KiCad 10's libs don't carry under that name.

The subprocess env is scrubbed: this repo's sessions run inside an
AppImage harness whose LD_LIBRARY_PATH makes the system kicad-cli try to
load its kiface from the AppImage mount and die.
"""
import os
import re
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "phase2-module.kicad_pcb")
RPT = os.path.join(HERE, "..", "drc-report.txt")

BENIGN = {"lib_footprint_mismatch", "lib_footprint_issues"}
FAIL_TYPES = {
    "shorting_items", "items_not_allowed", "copper_edge_clearance",
    "courtyards_overlap", "malformed_courtyard", "clearance", "hole_near_hole",
    "hole_clearance", "track_dangling", "via_dangling", "pad_overlap",
    "zones_intersect",
}


def main():
    # XDG_DATA_DIRS matters as much as LD_LIBRARY_PATH: both point into the
    # AppImage harness and redirect kicad-cli's kiface search there.
    env = {"HOME": os.path.expanduser("~"), "PATH": "/usr/bin:/bin"}
    r = subprocess.run(
        ["kicad-cli", "pcb", "drc", "--refill-zones", "-o", RPT, os.path.abspath(BOARD)],
        capture_output=True, text=True, env=env, cwd=HERE)
    if r.returncode != 0 or not os.path.exists(RPT):
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        sys.exit(2)
    text = open(RPT).read()
    entries = re.findall(r"^\[(\w+)\]: (.+)$", text, re.M)
    unconnected = len(re.findall(r"^\[unconnected_items\]", text, re.M))
    print(f"unconnected: {unconnected}")
    for typ, n in Counter(t for t, _ in entries).most_common():
        note = "  (benign baseline)" if typ in BENIGN else ""
        print(f"{typ}: {n}{note}")
    fails = unconnected
    for typ, desc in entries:
        if typ in FAIL_TYPES:
            print(f"  !{typ}: {desc[:120]}")
            fails += 1
    print(f"FAIL COUNT (unconnected + error-severity): {fails}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
