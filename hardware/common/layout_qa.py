"""Board-agnostic layout finishing passes, shared by every phase.

Three things every board needs once its copper is done, none of which
should be re-implemented per board:

    reflow_refs(board)   silkscreen refdes placement (the silk_* DRC pile)
    plane_islands(board) PS-002: pour islands whose pads have no via tie
    plot_fab(board, out) Gerbers + Excellon, layer set from the board itself

Written against KiCad 7's pcbnew API. Callers are thin wrappers in each
phase's tools/ that supply the board path — see
phase2-module/tools/silk_refs.py for the pattern.

Nothing here mutates a file: callers save. That keeps "which board did I
just overwrite" answerable.
"""
import os
import shutil

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

# ---- silkscreen ----------------------------------------------------------
SILK_CLR = 0.10          # silk-to-anything target (board setup constraint)
SILK_EDGE = 0.15
TEXT_H = 0.8
TEXT_T = 0.12


def _bbox(bb):
    return (ToMM(bb.GetLeft()), ToMM(bb.GetTop()),
            ToMM(bb.GetRight()), ToMM(bb.GetBottom()))


def _grow(b, m):
    return (b[0] - m, b[1] - m, b[2] + m, b[3] + m)


def _hits(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def reflow_refs(board, text_h=TEXT_H):
    """Re-place every footprint reference so it stops colliding.

    Greedy: try spots around the courtyard (growing offsets, same side
    first); accept the first that clears pads, silk graphics, vias, the
    board edge and previously placed refs. If nothing clears, keep the
    least-bad candidate — the DRC count still falls. Returns (clean, stuck).
    """
    edge = board.GetBoardEdgesBoundingBox()
    ex1, ey1, ex2, ey2 = _bbox(edge)

    obs = {0: [], 1: []}          # 0 = front, 1 = back
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            b = _grow(_bbox(pad.GetBoundingBox()), SILK_CLR)
            smd = pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD
            if not smd or pad.IsOnLayer(pcbnew.F_Cu):
                obs[0].append(b)
            if not smd or pad.IsOnLayer(pcbnew.B_Cu):
                obs[1].append(b)
        for gi in fp.GraphicalItems():
            L = gi.GetLayer()
            if L in (pcbnew.F_SilkS, pcbnew.B_SilkS) and not isinstance(
                    gi, pcbnew.PCB_TEXT):
                obs[0 if L == pcbnew.F_SilkS else 1].append(
                    _grow(_bbox(gi.GetBoundingBox()), SILK_CLR))
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            b = _grow(_bbox(t.GetBoundingBox()), SILK_CLR)
            obs[0].append(b)
            obs[1].append(b)

    def badness(side, b):
        n = 0
        if (b[0] < ex1 + SILK_EDGE or b[1] < ey1 + SILK_EDGE or
                b[2] > ex2 - SILK_EDGE or b[3] > ey2 - SILK_EDGE):
            n += 1
        return n + sum(1 for o in obs[side] if _hits(b, o))

    clean = stuck = 0
    for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
        ref = fp.Reference()
        L = ref.GetLayer()
        if L not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            continue
        side = 0 if L == pcbnew.F_SilkS else 1
        ref.SetTextSize(VECTOR2I(FromMM(text_h), FromMM(text_h)))
        ref.SetTextThickness(FromMM(TEXT_T))
        ref.SetTextAngle(pcbnew.EDA_ANGLE(0, pcbnew.DEGREES_T))

        cy = fp.GetCourtyard(pcbnew.F_CrtYd if side == 0 else pcbnew.B_CrtYd)
        cb = (_bbox(cy.BBox()) if cy.OutlineCount()
              else _bbox(fp.GetBoundingBox(False, False)))
        cx, cyy = (cb[0] + cb[2]) / 2, (cb[1] + cb[3]) / 2
        half = text_h / 2 + 0.15

        cands = []
        for d in (0.15, 0.45, 0.8, 1.2, 1.7, 2.3):
            cands += [
                (cx, cb[1] - d - half), (cx, cb[3] + d + half),
                (cb[0] - d - 1.0, cyy), (cb[2] + d + 1.0, cyy),
                (cb[0] - d, cb[1] - d - half), (cb[2] + d, cb[1] - d - half),
                (cb[0] - d, cb[3] + d + half), (cb[2] + d, cb[3] + d + half),
            ]
        best, best_n = None, None
        for (x, y) in cands:
            ref.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
            n = badness(side, _bbox(ref.GetBoundingBox()))
            if n == 0:
                best, best_n = (x, y), 0
                break
            if best_n is None or n < best_n:
                best, best_n = (x, y), n
        ref.SetPosition(VECTOR2I(FromMM(best[0]), FromMM(best[1])))
        obs[side].append(_grow(_bbox(ref.GetBoundingBox()), SILK_CLR))
        if best_n == 0:
            clean += 1
        else:
            stuck += 1
    return clean, stuck


# ---- plane integrity (PS-002) -------------------------------------------
def _inside(poly, i, x, y):
    """Point-in-polygon against outline i alone.

    SHAPE_POLY_SET.Contains() tests the whole set; the island question
    needs one outline at a time.
    """
    o = poly.Outline(i)
    n = o.PointCount()
    res = False
    j = n - 1
    for k in range(n):
        xk, yk = ToMM(o.CPoint(k).x), ToMM(o.CPoint(k).y)
        xj, yj = ToMM(o.CPoint(j).x), ToMM(o.CPoint(j).y)
        if (yk > y) != (yj > y) and x < (xj - xk) * (y - yk) / (yj - yk) + xk:
            res = not res
        j = k
    return res


def _area(poly, i):
    o = poly.Outline(i)
    pts = [(ToMM(o.CPoint(k).x), ToMM(o.CPoint(k).y))
           for k in range(o.PointCount())]
    a = 0.0
    for k in range(len(pts)):
        x1, y1 = pts[k]
        x2, y2 = pts[(k + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def plane_islands(board, origin=(0.0, 0.0)):
    """Report pour islands. Returns list of dicts, one per stray island.

    An island holding pads is only a genuine return-path problem when it
    contains no via/PTH of its own — otherwise it ties down to the plane
    and KiCad's connectivity (rightly) calls those pads connected.
    """
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    pads = [(p.GetNetname(), ToMM(p.GetPosition().x), ToMM(p.GetPosition().y), p)
            for fp in board.GetFootprints() for p in fp.Pads()]
    ties = [(t.GetNetname(), ToMM(t.GetPosition().x), ToMM(t.GetPosition().y))
            for t in board.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
    ties += [(n, x, y) for n, x, y, p in pads
             if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD]

    out = []
    for z in board.Zones():
        net = z.GetNetname() or "<none>"
        for layer in z.GetLayerSet().Seq():
            poly = z.GetFilledPolysList(layer)
            if poly.OutlineCount() < 2:
                continue
            ranked = sorted(((_area(poly, i), i)
                             for i in range(poly.OutlineCount())), reverse=True)
            for area, i in ranked[1:]:
                held = sum(1 for n, x, y, p in pads
                           if n == net and p.IsOnLayer(layer)
                           and _inside(poly, i, x, y))
                if not held:
                    continue
                tied = sum(1 for n, x, y in ties
                           if n == net and _inside(poly, i, x, y))
                o = poly.Outline(i)
                cx = sum(ToMM(o.CPoint(k).x)
                         for k in range(o.PointCount())) / o.PointCount()
                cy = sum(ToMM(o.CPoint(k).y)
                         for k in range(o.PointCount())) / o.PointCount()
                out.append({
                    "net": net, "layer": board.GetLayerName(layer),
                    "area_mm2": round(area, 1), "pads": held, "ties": tied,
                    "at": (round(cx - origin[0], 1), round(cy - origin[1], 1)),
                })
    return out


# ---- fabrication outputs -------------------------------------------------
def plot_fab(board, outdir, zip_base=None):
    """Plot Gerbers + merged Excellon drills. Layer set from the board.

    RS-274X, no X2 attributes, no Protel extensions — what JLCPCB's
    parser wants. Returns the list of files written.
    """
    ncu = board.GetCopperLayerCount()
    copper = [(pcbnew.F_Cu, "F_Cu")]
    if ncu >= 4:
        copper += [(pcbnew.In1_Cu, "In1_Cu"), (pcbnew.In2_Cu, "In2_Cu")]
    copper += [(pcbnew.B_Cu, "B_Cu")]
    layers = copper + [
        (pcbnew.F_Paste, "F_Paste"), (pcbnew.B_Paste, "B_Paste"),
        (pcbnew.F_SilkS, "F_Silkscreen"), (pcbnew.B_SilkS, "B_Silkscreen"),
        (pcbnew.F_Mask, "F_Mask"), (pcbnew.B_Mask, "B_Mask"),
        (pcbnew.Edge_Cuts, "Edge_Cuts"),
    ]

    if os.path.isdir(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir)

    pc = pcbnew.PLOT_CONTROLLER(board)
    po = pc.GetPlotOptions()
    po.SetOutputDirectory(outdir)
    po.SetPlotFrameRef(False)
    po.SetUseGerberProtelExtensions(False)
    po.SetUseGerberX2format(False)
    po.SetIncludeGerberNetlistInfo(False)
    po.SetCreateGerberJobFile(True)
    po.SetSubtractMaskFromSilk(True)
    po.SetDrillMarksType(0)
    po.SetSkipPlotNPTH_Pads(False)
    po.SetMirror(False)
    po.SetAutoScale(False)
    po.SetScale(1.0)

    for lid, name in layers:
        pc.SetLayer(lid)
        pc.OpenPlotfile(name, pcbnew.PLOT_FORMAT_GERBER, name)
        if not pc.PlotLayer():
            raise RuntimeError(f"plot failed on {name}")
    pc.ClosePlot()

    dw = pcbnew.EXCELLON_WRITER(board)
    dw.SetOptions(False, False, board.GetDesignSettings().GetAuxOrigin(), True)
    dw.SetFormat(True, pcbnew.EXCELLON_WRITER.DECIMAL_FORMAT, 3, 3)
    dw.CreateDrillandMapFilesSet(outdir, True, True)

    if zip_base:
        shutil.make_archive(zip_base, "zip", outdir)
    return sorted(os.listdir(outdir))


def board_extent(board):
    """(width, height) mm of Edge_Cuts — the sanity check on any plot."""
    bb = board.GetBoardEdgesBoundingBox()
    return round(ToMM(bb.GetWidth()), 2), round(ToMM(bb.GetHeight()), 2)


def unconnected(board):
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount(False)
