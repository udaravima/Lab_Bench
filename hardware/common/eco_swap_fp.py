"""Engineering change on a routed board: swap one footprint for another land.

    python3.12 common/eco_swap_fp.py BOARD REF LIB:NAME X Y ROT

X, Y are KiCad page mm (the generated boards put their origin at 20,20),
ROT in degrees. The new footprint is loaded from the system library (or
the project's labbench.pretty), placed at X, Y, ROT and given the old
footprint's reference, value, fields (sheet name included), schematic path and,
pad number by pad number, its nets. The old footprint is removed. Tracks
are not touched: re-attach them with the board's ECO script and check
with run_drc.py.

Used for the 2026-10-06 phase-1 / phase-2 L2 change (1210 -> FNR5040S),
the same land change PR #16 made on the manager.
"""
import os
import sys

import pcbnew
from pcbnew import FromMM

HERE = os.path.dirname(os.path.abspath(__file__))
LIBS = {"labbench": os.path.join(HERE, "..", "phase1-module", "lib", "labbench.pretty")}
SYSTEM_DIR = "/usr/share/kicad/footprints"
GRAVEYARD = []


def load(fpid):
    nick, name = fpid.split(":")
    path = LIBS.get(nick, os.path.join(SYSTEM_DIR, nick + ".pretty"))
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        sys.exit(f"cannot load {fpid} from {path}")
    fp.SetFPID(pcbnew.LIB_ID(nick, name))
    return fp


def swap(board, ref, fpid, x, y, rot):
    old = board.FindFootprintByReference(ref)
    if old is None:
        sys.exit(f"{ref} not on board")
    new = load(fpid)
    nets = {p.GetNumber(): p.GetNet() for p in old.Pads()}
    missing = set(nets) - {p.GetNumber() for p in new.Pads()}
    if missing:
        sys.exit(f"{fpid} has no pad(s) {sorted(missing)} for {ref}")
    new.SetReference(ref)
    new.SetValue(old.GetValue())
    for k, v in old.GetProperties().items():
        new.SetProperty(k, v)
    new.SetPath(old.GetPath())
    new.SetAttributes(old.GetAttributes())
    new.Reference().SetVisible(old.Reference().IsVisible())
    new.Value().SetVisible(old.Value().IsVisible())
    board.Add(new)
    new.SetOrientationDegrees(rot)
    new.SetPosition(pcbnew.VECTOR2I(FromMM(x), FromMM(y)))
    for p in new.Pads():
        if p.GetNumber() in nets:
            p.SetNet(nets[p.GetNumber()])
    new.SetLocked(old.IsLocked())
    board.Remove(old)
    GRAVEYARD.append(old)   # removed items must outlive their SWIG proxies


def main():
    if len(sys.argv) != 7:
        sys.exit(__doc__)
    path, ref, fpid = sys.argv[1:4]
    x, y, rot = map(float, sys.argv[4:7])
    board = pcbnew.LoadBoard(path)
    swap(board, ref, fpid, x, y, rot)
    board.Save(path)
    for p in board.FindFootprintByReference(ref).Pads():
        q = p.GetPosition()
        print(f"{ref}.{p.GetNumber()} {p.GetNetname()} at "
              f"({pcbnew.ToMM(q.x):.2f}, {pcbnew.ToMM(q.y):.2f})")


if __name__ == "__main__":
    main()
