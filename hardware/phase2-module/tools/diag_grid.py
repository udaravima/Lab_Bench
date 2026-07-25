"""Diagnose autoroute 'no path' fails: rebuild the obstacle grid on the
CLEAN pass-1 board (run gen_board+route_board first, NOT the autorouted
board) and report, for each failed pad of interest, whether its source
cells can expand at all.  python3 diag_grid.py
"""
import pcbnew

import autoroute as ar

FAILED = [
    ("PS_VDDA", "C21"), ("PS_VDDA", "U3"), ("PS_DITH", "U3"),
    ("PS_COMP", "U3"), ("PS_RT", "R26"), ("PS_SS", "C18"),
    ("DAC_REFIO", "U1"), ("I_REF", "U1"),
    ("I2C_SDA", "U10"), ("NRST", "U10"), ("UART_RX", "U10"),
    ("EAV_INV", "R3"), ("REF_2V5", "U7"), ("PS_VCC", "C22"),
]


def main():
    board = pcbnew.LoadBoard(ar.BOARD)
    board.BuildConnectivity()
    g, net_copper = ar.build_grid(board)

    pads = {}
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            pads.setdefault((pad.GetNetname(), ref), []).append(pad)

    for key in FAILED:
        plist = pads.get(key)
        if not plist:
            print(key, "NOT FOUND")
            continue
        for pad in plist:
            x = pcbnew.ToMM(pad.GetPosition().x) - ar.ORG[0]
            y = pcbnew.ToMM(pad.GetPosition().y) - ar.ORG[1]
            gx, gy = round(x / ar.STEP), round(y / ar.STEP)
            L = 0 if pad.IsOnLayer(pcbnew.F_Cu) else 1
            nid = g.net_id(key[0])
            bb = pad.GetBoundingBox()
            w = pcbnew.ToMM(bb.GetWidth())
            h = pcbnew.ToMM(bb.GetHeight())
            n = int(max(w, h) / 2 / ar.STEP)
            srcs = [(gx, gy)]
            for k in range(1, n + 1):
                if w >= h:
                    srcs += [(gx - k, gy), (gx + k, gy)]
                else:
                    srcs += [(gx, gy - k), (gx, gy + k)]
            free_src = [c for c in srcs if g.free(L, c, nid)]
            exits = set()
            for c in srcs:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    cc = (c[0] + dx, c[1] + dy)
                    if cc not in srcs and g.free(L, cc, nid):
                        exits.add(cc)
            offg = (abs(x / ar.STEP - gx) > 1e-6, abs(y / ar.STEP - gy) > 1e-6)
            print(f"{key[0]:>10s} {key[1]:<4s} pad@({x:7.3f},{y:7.3f}) "
                  f"grid_off={offg} L={L} srcs={len(srcs)} "
                  f"free_src={len(free_src)} exit_cells={len(exits)}")


if __name__ == "__main__":
    main()
