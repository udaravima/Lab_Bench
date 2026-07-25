"""Silk cleanup: re-place reference designators so they stop colliding
with pads, outlines, vias, each other and the board edge (the ~150
silk_* DRC warnings). Deterministic greedy pass:

  for every footprint reference (F/B silk), try candidate spots around
  the courtyard (same side first, growing offsets); a spot is good when
  the text bbox + 0.1 mm clears every obstacle. If nothing clears, keep
  the least-bad candidate (fewest overlaps) — the DRC count still drops.

Text is normalised to 0.8 mm / 0.12 mm so the dense areas have a chance.
Run AFTER autoroute (vias are obstacles):  python3 silk_refs.py
Then run_drc.py to confirm.
"""
import os

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "..", "phase2-module.kicad_pcb")

CLR = 0.10              # silk-to-anything clearance target (board setup)
EDGE = 0.15
TEXT_H = 0.8
TEXT_T = 0.12


def bbox_mm(bb):
    return (ToMM(bb.GetLeft()), ToMM(bb.GetTop()),
            ToMM(bb.GetRight()), ToMM(bb.GetBottom()))


def grow(b, m):
    return (b[0] - m, b[1] - m, b[2] + m, b[3] + m)


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def main():
    board = pcbnew.LoadBoard(BOARD)
    edge = board.GetBoardEdgesBoundingBox()
    ex1, ey1, ex2, ey2 = bbox_mm(edge)

    # ---- obstacles per side: pads, silk lines, vias --------------------
    obs = {0: [], 1: []}        # 0 = F, 1 = B
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            b = grow(bbox_mm(pad.GetBoundingBox()), CLR)
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
                    grow(bbox_mm(gi.GetBoundingBox()), CLR))
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            b = grow(bbox_mm(t.GetBoundingBox()), CLR)
            obs[0].append(b)
            obs[1].append(b)

    def bad(side, b):
        n = 0
        if b[0] < ex1 + EDGE or b[1] < ey1 + EDGE or \
           b[2] > ex2 - EDGE or b[3] > ey2 - EDGE:
            n += 1
        for o in obs[side]:
            if overlaps(b, o):
                n += 1
        return n

    moved = stuck = 0
    for fp in sorted(board.GetFootprints(),
                     key=lambda f: f.GetReference()):
        ref = fp.Reference()
        L = ref.GetLayer()
        if L not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            continue
        side = 0 if L == pcbnew.F_SilkS else 1
        ref.SetTextSize(VECTOR2I(FromMM(TEXT_H), FromMM(TEXT_H)))
        ref.SetTextThickness(FromMM(TEXT_T))
        ref.SetTextAngle(pcbnew.EDA_ANGLE(0, pcbnew.DEGREES_T))

        cy = fp.GetCourtyard(pcbnew.F_CrtYd if side == 0 else pcbnew.B_CrtYd)
        cb = bbox_mm(cy.BBox()) if cy.OutlineCount() else \
            bbox_mm(fp.GetBoundingBox(False, False))
        cx, cyy = (cb[0] + cb[2]) / 2, (cb[1] + cb[3]) / 2
        half_h = TEXT_H / 2 + 0.15

        orig = ref.GetPosition()
        cands = []
        for d in (0.15, 0.45, 0.8, 1.2, 1.7, 2.3):
            cands += [
                (cx, cb[1] - d - half_h),           # above
                (cx, cb[3] + d + half_h),           # below
                (cb[0] - d - 1.0, cyy),             # left
                (cb[2] + d + 1.0, cyy),             # right
                (cb[0] - d, cb[1] - d - half_h),    # corners
                (cb[2] + d, cb[1] - d - half_h),
                (cb[0] - d, cb[3] + d + half_h),
                (cb[2] + d, cb[3] + d + half_h),
            ]
        best, best_n = None, None
        for (x, y) in cands:
            ref.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
            n = bad(side, bbox_mm(ref.GetBoundingBox()))
            if n == 0:
                best, best_n = (x, y), 0
                break
            if best_n is None or n < best_n:
                best, best_n = (x, y), n
        if best_n == 0:
            moved += 1
        else:
            stuck += 1
        ref.SetPosition(VECTOR2I(FromMM(best[0]), FromMM(best[1])))
        # the placed text becomes an obstacle for the rest
        obs[side].append(grow(bbox_mm(ref.GetBoundingBox()), CLR))
        del orig

    board.Save(BOARD)
    print(f"silk_refs: {moved} clean, {stuck} best-effort (see DRC)")


if __name__ == "__main__":
    main()
