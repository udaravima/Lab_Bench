"""Layout finishing pass for any board: silk reflow, PS-002, gerbers.

    python3 ../common/finish_board.py BOARD.kicad_pcb [--silk] [--planes]
                                      [--fab] [--force] [--origin X,Y]

  --silk    re-place refdes, save the board
  --planes  PS-002 island advisory (read-only)
  --fab     plot Gerbers + drills into <board_dir>/fab/ and zip them;
            refuses while anything is unconnected unless --force
  no flags  = --silk --planes --fab

Deliberately explicit about the board path: these passes overwrite
copper-adjacent state, and "which board did that touch" should never be
a guess. Run the phase's own run_drc.py afterwards for the numbers.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pcbnew

import layout_qa as qa


def main():
    args = list(sys.argv[1:])

    # Consume --origin and its value BEFORE picking the board path. This used
    # to run after, which broke the space-separated form this script's own
    # usage line documents: "X,Y" is not a flag, so it stayed in the
    # positional list and became the board path, and a trailing bare
    # --origin raised IndexError. Only --origin=X,Y ever worked.
    origin = (0.0, 0.0)
    rest = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--origin" or a.startswith("--origin="):
            if "=" in a:
                v = a.split("=", 1)[1]
            elif i + 1 < len(args):
                i += 1
                v = args[i]
            else:
                sys.exit("--origin needs a value, e.g. --origin 20,20")
            try:
                x, y = (float(t) for t in v.split(","))
            except ValueError:
                sys.exit(f"--origin wants two numbers 'X,Y', got {v!r}")
            origin = (x, y)
        else:
            rest.append(a)
        i += 1

    flags = {a for a in rest if a.startswith("--")}
    paths = [a for a in rest if not a.startswith("--")]
    if not paths:
        sys.exit(__doc__)
    board_path = os.path.abspath(paths[0])

    do_silk = "--silk" in flags
    do_planes = "--planes" in flags
    do_fab = "--fab" in flags
    if not (do_silk or do_planes or do_fab):
        do_silk = do_planes = do_fab = True

    board = pcbnew.LoadBoard(board_path)
    name = os.path.splitext(os.path.basename(board_path))[0]
    bdir = os.path.dirname(board_path)
    w, h = qa.board_extent(board)
    print(f"{name}: {w} x {h} mm, {board.GetCopperLayerCount()} copper layers")

    if do_silk:
        clean, stuck = qa.reflow_refs(board)
        board.Save(board_path)
        print(f"silk: {clean} refs placed clean, {stuck} best-effort")

    if do_planes:
        strays = qa.plane_islands(board, origin)
        loose = [s for s in strays if not s["ties"]]
        print(f"planes: {len(strays)} pad-carrying island(s), "
              f"{len(loose)} without a via of their own")
        for s in strays:
            mark = "NO VIA" if not s["ties"] else f"{s['ties']} ties ok"
            print(f"   {s['net']:<12} {s['layer']:<8} {s['area_mm2']:>7} mm2  "
                  f"{s['pads']} pads  {mark}  @{s['at']}")
        if loose:
            print("   -> advisory: those pads still reach the net through a "
                  "pour arm; a stitch via inside each island is the fix.\n"
                  "      Check the via lands on the correct side of any "
                  "plane seam before adding it.")

    if do_fab:
        u = qa.unconnected(board)
        if u and "--force" not in flags:
            print(f"fab: REFUSED, {u} unconnected item(s) — route first "
                  f"(or --force for a deliberate partial plot)")
            return
        out = os.path.join(bdir, "fab")
        files = qa.plot_fab(board, out, zip_base=os.path.join(bdir, f"{name}-fab"))
        print(f"fab: {len(files)} files -> {os.path.relpath(out, bdir)}/ "
              f"(+ {name}-fab.zip)" + ("   [FORCED: not fab-ready]" if u else ""))


if __name__ == "__main__":
    main()
