"""Import a Freerouting Specctra session onto the pass-1 board.

Workflow:

    python3 export_dsn.py            # planes as power layers, pass-1 copper locked
    xvfb-run -a java -Xss64m -jar freerouting-1.9.0.jar \\
         -de wip/p1.dsn -do wip/p1.ses -mp 8 -mt 1
    python3 import_ses.py            # <- here: import, refill, verify
    python3 run_drc.py

Why a hand parser: KiCad 7's `pcbnew.ImportSpecctraSES(path)` takes no
board argument and imports into the GUI frame's board, so from a headless
script it has nothing to import into (phase-2's import_ses.py passes a
board and dies with a TypeError before doing anything). The session's
`network_out` block is small and regular: per net, `(wire (path LAYER W
x y ...))` and `(via PADSTACK x y)`, in the session's own resolution with
y pointing up. Only the router's new copper is in it; the locked pass-1
wires stay on the board untouched.

Refuses to save if unconnected went up.

Usage: python3 import_ses.py [session.ses] [board.kicad_pcb]
"""
import os
import re
import sys

import pcbnew
from pcbnew import FromMM

HERE = os.path.dirname(os.path.abspath(__file__))
SES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "wip", "p1.ses")
BOARD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "phase1-module.kicad_pcb")

VIA_D, VIA_DRILL = 0.6, 0.3


def parse(text):
    """Tiny s-expression reader -> nested lists of strings."""
    toks = re.findall(r'\(|\)|"[^"]*"|[^\s()]+', text)
    stack = [[]]
    for t in toks:
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(t.strip('"'))
    return stack[0][0]


def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def unconnected(board):
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount(False)


def main():
    board = pcbnew.LoadBoard(BOARD)
    before = unconnected(board)
    ses = parse(open(SES).read())
    routes = find(ses, "routes")[0]
    res = find(routes, "resolution")[0]
    scale = {"um": 1e-3, "mm": 1.0, "mil": 0.0254}[res[1]] / float(res[2])
    nets = board.GetNetsByName()
    layers = {board.GetLayerName(l): l for l in (pcbnew.F_Cu, pcbnew.B_Cu)}

    def pt(x, y):
        return pcbnew.VECTOR2I(FromMM(float(x) * scale), FromMM(-float(y) * scale))

    n_t = n_v = 0
    for net in find(find(routes, "network_out")[0], "net"):
        code = nets[net[1]].GetNetCode()
        for w in find(net, "wire"):
            path = find(w, "path")[0]
            lay, width, xy = path[1], float(path[2]) * scale, path[3:]
            if lay not in layers:
                sys.exit(f"route on unexpected layer {lay} (net {net[1]})")
            pts = [pt(xy[i], xy[i + 1]) for i in range(0, len(xy), 2)]
            for a, b in zip(pts, pts[1:]):
                if (a - b).EuclideanNorm() < FromMM(0.01):
                    continue        # Freerouting's sub-10 um slivers: DRC calls them dangling
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(a)
                t.SetEnd(b)
                t.SetWidth(FromMM(width))
                t.SetLayer(layers[lay])
                t.SetNetCode(code)
                board.Add(t)
                n_t += 1
        for v in find(net, "via"):
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pt(v[2], v[3]))
            via.SetDrill(FromMM(VIA_DRILL))
            via.SetWidth(FromMM(VIA_D))
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            via.SetNetCode(code)
            board.Add(via)
            n_v += 1

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    after = unconnected(board)
    print(f"import_ses: +{n_t} tracks, +{n_v} vias; unconnected {before} -> {after}")
    if after > before:
        sys.exit("REFUSING to save: unconnected went UP")
    board.Save(BOARD)


if __name__ == "__main__":
    main()
