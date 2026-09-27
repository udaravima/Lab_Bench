"""Engineering change on the routed board: move parts, peel their old routes.

    python3 eco_move.py [board] --find REF X Y [R]    # list legal spots near X,Y
    python3 eco_move.py [board] REF=X,Y,ROT ... [--keep=REF.PAD] [--drop=X,Y]
                                                      # move, peel, save
    python3 finish_routes.py [board] --base=<board>   # reconnect the moved parts

Coordinates are KiCad page mm (board origin at 20,20), ROT in degrees.

Moving a part on a routed board leaves its old tracks dangling at the
old pad positions. This peels them: every track with a dangling end on
a net of a moved part is removed, repeatedly, so a route is eaten back
to the first junction with the rest of its net; a via left joining
nothing across layers goes with it (vias in a same-net fill stay). Nothing else is touched, so finish_routes.py
(with --base set to the peeled board, so no existing copper is ripped)
only has to add the new connections.

--keep=REF.PAD spares that pad's track-to-first-via escape from the peel
(for a fine-pitch pin whose only way out is the one Freerouting found).

--drop=X,Y removes the trackless stitching via at X,Y (one of the ground
grid, to make room).

--find tries every 0.25 mm grid spot and 90-degree rotation within R mm
(default 8) and keeps the ones where the courtyard clears every other
courtyard and each pad clears foreign F.Cu copper (pads, tracks, vias,
pour fills) by 0.25 mm, sorted by distance to X,Y. The part's own old
routes are peeled first, so they do not block their own spot.
"""
import math
import sys

import pcbnew
import shapely
from pcbnew import FromMM
from shapely.geometry import LineString, Point, Polygon

from finish_routes import key, sps_polys

CLEAR = 0.25
GRAVEYARD = []     # removed items must outlive their SWIG proxies, or pcbnew crashes
mm = pcbnew.ToMM


def place(fp, x, y, rot):
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(pcbnew.VECTOR2I(FromMM(x), FromMM(y)))


def escape(board, refpad):
    """Keys of the tracks from pad REF.PAD to its first via, and that via: a
    fine-pitch pin's escape the finishing router could not find again."""
    ref, num = refpad.split(".")
    pad = [p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == num][0]
    net, at, keys = pad.GetNetname(), pad.GetPosition(), set()
    tracks = [t for t in board.GetTracks() if t.GetNetname() == net]
    for _ in range(20):
        for t in tracks:
            if isinstance(t, pcbnew.PCB_VIA):
                if t.GetPosition() == at:
                    return keys | {key(t)}
            elif key(t) not in keys and at in (t.GetStart(), t.GetEnd()):
                keys.add(key(t))
                at = t.GetEnd() if t.GetStart() == at else t.GetStart()
                break
        else:
            break
    sys.exit(f"no track-to-via escape found at {refpad}")


def peel(board, nets, keep=frozenset()):
    """Remove dangling tracks (and emptied vias) of `nets` until none are left."""
    removed = 0
    ends = set()                    # endpoints of peeled tracks: only vias there may go
    while True:
        board.BuildConnectivity()
        conn = board.GetConnectivity()
        gone = []
        for t in board.GetTracks():
            if t.GetNetname() not in nets or key(t) in keep:
                continue
            if isinstance(t, pcbnew.PCB_VIA):
                p = (t.GetPosition().x, t.GetPosition().y)
                layers = {x.GetLayer() for x in conn.GetConnectedTracks(t)}
                if p in ends and len(layers) <= 1 and not in_fill(board, t):
                    gone.append(t)      # joins nothing across layers: a stub
            elif conn.TestTrackEndpointDangling(t, False):
                gone.append(t)
        if not gone:
            return removed
        for t in gone:
            if not isinstance(t, pcbnew.PCB_VIA):
                ends |= {(t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)}
            board.Remove(t)
            GRAVEYARD.append(t)
        removed += len(gone)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def in_fill(board, via):
    return any(z.GetNetname() == via.GetNetname() and z.HitTestFilledArea(L, via.GetPosition())
               for z in board.Zones() for L in (z.GetLayer(),))


def courtyard(fp):
    fp.BuildCourtyardCaches()        # stale after a move otherwise
    polys = sps_polys(fp.GetCourtyard(pcbnew.F_CrtYd))
    return shapely.unary_union(polys) if polys else None


def find(board, ref, x0, y0, r):
    fp = board.FindFootprintByReference(ref)
    nets = {p.GetNetname() for p in fp.Pads()}
    place(fp, 300, 300, 0)          # off the board, then peel its routes
    peel(board, nets)
    courts = [c for f in board.GetFootprints() if f.GetReference() != ref
              for c in [courtyard(f)] if c is not None]
    foreign = []
    for f in board.GetFootprints():
        if f.GetReference() == ref:
            continue
        for p in f.Pads():
            if p.IsOnLayer(pcbnew.F_Cu):
                for g in sps_polys(p.GetEffectivePolygon()):
                    foreign.append((p.GetNetname(), g))
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            g = Point(mm(t.GetPosition().x), mm(t.GetPosition().y)).buffer(mm(t.GetWidth()) / 2)
        elif t.GetLayer() == pcbnew.F_Cu:
            g = LineString([(mm(t.GetStart().x), mm(t.GetStart().y)),
                            (mm(t.GetEnd().x), mm(t.GetEnd().y))]).buffer(mm(t.GetWidth()) / 2)
        else:
            continue
        foreign.append((t.GetNetname(), g))
    for z in board.Zones():
        if z.GetLayer() == pcbnew.F_Cu:
            for g in sps_polys(z.GetFilledPolysList(pcbnew.F_Cu)):
                foreign.append((z.GetNetname(), g))
    ctree = shapely.STRtree(courts)
    ftree = shapely.STRtree([g for _, g in foreign])
    hits = []
    n = int(r / 0.25)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = x0 + i * 0.25, y0 + j * 0.25
            if math.hypot(x - x0, y - y0) > r:
                continue
            for rot in (0, 90, 180, 270):
                place(fp, x, y, rot)
                c = courtyard(fp)
                if c is not None and len(ctree.query(c, predicate="intersects")):
                    continue
                ok = True
                for p in fp.Pads():
                    pg = shapely.unary_union(sps_polys(p.GetEffectivePolygon())).buffer(CLEAR)
                    for k in ftree.query(pg, predicate="intersects"):
                        if foreign[k][0] != p.GetNetname():
                            ok = False
                            break
                    if not ok:
                        break
                if ok:
                    hits.append((math.hypot(x - x0, y - y0), x, y, rot))
    for d, x, y, rot in sorted(hits)[:25]:
        print(f"{ref}={x:.2f},{y:.2f},{rot}   ({d:.2f} mm)")


def main():
    args = sys.argv[1:]
    path = args.pop(0) if args and args[0].endswith(".kicad_pcb") else "../phase1-module.kicad_pcb"
    board = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    if args and args[0] == "--find":
        ref, x, y = args[1], float(args[2]), float(args[3])
        find(board, ref, x, y, float(args[4]) if len(args) > 4 else 8.0)
        return
    keep = set()
    for a in [a for a in args if a.startswith("--keep=")]:
        keep |= escape(board, a[7:])
    for a in [a for a in args if a.startswith("--drop=")]:
        x, y = map(float, a[7:].split(","))
        board.BuildConnectivity()
        conn = board.GetConnectivity()
        vias = [t for t in board.GetTracks() if isinstance(t, pcbnew.PCB_VIA)
                and abs(mm(t.GetPosition().x) - x) < 0.01 and abs(mm(t.GetPosition().y) - y) < 0.01
                and not conn.GetConnectedTracks(t)]
        if len(vias) != 1:
            sys.exit(f"--drop: no trackless (stitching) via at {x},{y}")
        board.Remove(vias[0])
        GRAVEYARD.append(vias[0])
    args = [a for a in args if not a.startswith(("--keep=", "--drop="))]
    nets = set()
    for a in args:
        ref, xyr = a.split("=")
        x, y, rot = map(float, xyr.split(","))
        fp = board.FindFootprintByReference(ref)
        nets |= {p.GetNetname() for p in fp.Pads()}
        place(fp, x, y, rot)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    n = peel(board, nets, keep)
    print(f"eco_move: moved {len(args)} part(s), peeled {n} track/via item(s)")
    board.Save(path)


if __name__ == "__main__":
    main()
