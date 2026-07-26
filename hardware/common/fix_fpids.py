"""Restore library nicknames on generated footprints (lib_footprint_issues).

The board generators add footprints by name only, so every footprint on
every generated board carries an empty FPID library nickname. KiCad then
reports, once per footprint:

    lib_footprint_issues: The current configuration does not include the
    library ''.

Harmless for fabrication — gerbers plot from the board's own geometry —
but it buries the DRC report (39 on the backplane, 180 on phase-2) and,
more importantly, it means KiCad cannot diff a board footprint against
its library, so silent library drift would go unnoticed. That matters
here: a land-pattern bug in LM5143 was already caught once by hand.

This resolves each footprint's item name against the project library
first, then the system libraries, and writes the nickname back. Names
that resolve nowhere are listed and left alone (never guessed).

    python3 ../common/fix_fpids.py BOARD.kicad_pcb [--dry-run]
"""
import os
import sys

import pcbnew

PROJECT_LIBS = [
    ("labbench", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "phase1-module", "lib", "labbench.pretty")),
]
SYSTEM_DIR = "/usr/share/kicad/footprints"


def build_index():
    """item name -> nickname. Project libs win over system libs."""
    idx = {}
    for nick, path in PROJECT_LIBS:
        if not os.path.isdir(path):
            continue
        for f in os.listdir(path):
            if f.endswith(".kicad_mod"):
                idx.setdefault(f[:-10], nick)
    if os.path.isdir(SYSTEM_DIR):
        for d in sorted(os.listdir(SYSTEM_DIR)):
            if not d.endswith(".pretty"):
                continue
            nick = d[:-7]
            for f in os.listdir(os.path.join(SYSTEM_DIR, d)):
                if f.endswith(".kicad_mod"):
                    idx.setdefault(f[:-10], nick)
    return idx


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if not args:
        sys.exit(__doc__)
    path = os.path.abspath(args[0])

    idx = build_index()
    board = pcbnew.LoadBoard(path)

    fixed, already, missing = 0, 0, []
    for fp in board.GetFootprints():
        fid = fp.GetFPID()
        if fid.GetLibNickname().wx_str():
            already += 1
            continue
        item = fid.GetLibItemName().wx_str()
        nick = idx.get(item)
        if not nick:
            missing.append((fp.GetReference(), item))
            continue
        fp.SetFPID(pcbnew.LIB_ID(nick, item))
        fixed += 1

    print(f"fix_fpids: {fixed} nickname(s) resolved, {already} already set, "
          f"{len(missing)} unresolved")
    for ref, item in missing:
        print(f"   UNRESOLVED {ref}: {item}")
    if fixed and not dry:
        board.Save(path)
        print("saved")
    elif dry:
        print("(dry run, not saved)")


if __name__ == "__main__":
    main()
