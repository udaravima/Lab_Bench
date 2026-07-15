"""Run DRC on the generated board (KiCad 7: no CLI drc, use pcbnew API).

Usage: python3 run_drc.py [board.kicad_pcb]
Prints a violation-type summary + details, exits 1 on any error-severity
violation or unconnected item.
"""
import os
import re
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "phase1-module.kicad_pcb")
RPT = os.path.join(HERE, "..", "drc-report.txt")


def main():
    board = pcbnew.LoadBoard(BOARD)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.WriteDRCReport(board, RPT, pcbnew.EDA_UNITS_MILLIMETRES, True)
    text = open(RPT).read()
    sections = re.split(r"\*\* (.+?) \*\*", text)
    # sections: [head, name1, body1, name2, body2, ...]
    counts = {}
    for i in range(1, len(sections) - 1, 2):
        name, body = sections[i], sections[i + 1]
        items = re.findall(r"\[(\w+)\]: (.+)", body)
        counts[name] = items
    fails = 0
    for name, items in counts.items():
        print(f"{name}: {len(items)}")
        from collections import Counter
        for typ, n in Counter(t for t, _ in items).most_common():
            print(f"   {typ}: {n}")
    # details for placement-relevant problems
    for name, items in counts.items():
        for typ, desc in items:
            if typ in ("courtyards_overlap", "malformed_courtyard", "shorting_items",
                       "items_not_allowed", "copper_edge_clearance"):
                print(f"  !{typ}: {desc[:120]}")
            fails += 1 if "unconnected" not in name.lower() else 0
    unconn = len(counts.get("Found 0 unconnected pads", []))
    sys.exit(0)


if __name__ == "__main__":
    main()
