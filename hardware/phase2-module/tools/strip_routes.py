"""Drop the router copper of some nets so they can be re-routed after a stuck net.

usage: strip_routes.py SRC DST NET[,NET] [BASE]   (BASE: the pre-router board;
copper present in BASE, i.e. hand routes, is kept)"""
import sys, pcbnew
src, dst, nets = sys.argv[1], sys.argv[2], set(sys.argv[3].split(","))
def key(t):
    if isinstance(t, pcbnew.PCB_VIA):
        return (t.GetNetname(), "V", t.GetPosition().x, t.GetPosition().y)
    return (t.GetNetname(), t.GetLayer(), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y)
base = {key(t) for t in pcbnew.LoadBoard(sys.argv[4] if len(sys.argv) > 4 else "wip/base.kicad_pcb").GetTracks()}
b = pcbnew.LoadBoard(src); n = 0
for t in list(b.GetTracks()):
    if t.GetNetname() in nets and key(t) not in base:
        b.Remove(t); n += 1
b.Save(dst); print("removed", n)
