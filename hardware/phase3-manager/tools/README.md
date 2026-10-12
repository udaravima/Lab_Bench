# Phase-3 manager board: generation and routing pipeline

Same approach as `hardware/phase1-module/tools/` (read its README for the
philosophy and the pcbnew API notes). Two copper layers, 100 x 80 mm,
ESP32-S3-WROOM-1 manager.

## Full rebuild

Run from this directory with KiCad 7.0.11's Python (on Ubuntu 24.04 that
is `python3.12`; the repo's `python3` may be a different interpreter).

```bash
kicad-cli sch export netlist -o wip/mgr.net ../phase3-manager.kicad_sch
python3 check_netlist.py wip/mgr.net          # all nets OK
python3 check_footprints.py wip/mgr.net       # all OK
python3 gen_board.py wip/mgr.net              # placement + pours + keep-outs
python3 route_critical.py                     # USB/CAN pairs, buck power copper (locked)
cp ../phase3-manager.kicad_pcb wip/base.kicad_pcb   # base for rip-up protection
python3 export_dsn.py wip/mgr.dsn
xvfb-run -a java -Xss64m -jar freerouting-1.9.0.jar \
    -de wip/mgr.dsn -dr freerouting.rules -do wip/mgr.ses -mp 20 -mt 1
python3 ../../phase1-module/tools/import_ses.py wip/mgr.ses ../phase3-manager.kicad_pcb
python3 finish_routes.py --base=wip/base.kicad_pcb   # closes the last few
python3 stitch.py                             # PGND stitch vias, F.Cu <-> B.Cu
python3 ../../common/fix_fpids.py ../phase3-manager.kicad_pcb
python3 ../../common/finish_board.py ../phase3-manager.kicad_pcb --silk --planes
python3 run_drc.py                            # 0 unconnected, 0 errors
python3 ../../common/finish_board.py ../phase3-manager.kicad_pcb --fab
```

Freerouting is not deterministic, so a rerun gives a different (equally
DRC-clean) result. Everything placed by hand lives in `gen_board.py`
PLACEMENT, so rerunning it always reproduces the committed placement; no
script after it moves a part.

### Engineering changes on the routed board

A part change does not need the full rebuild (Freerouting would reshuffle
every net). The 2026-10-05 L2 change (1210 -> 5x5 mm FNR5040S) was done as
an ECO: update PLACEMENT and the affected ROUTES first, so a rebuild still
reproduces the board; then on the committed board swap the footprint, move
the parts, delete only the touched nets' copper (SW_AUX, the 5V0 head,
PRESENT4-7), redraw the ROUTES items locked, and run
`finish_routes.py --base=<fresh gen_board + route_critical board>`, then
`stitch.py` **fragment pass only** (rerunning its 5 mm grid on a stitched
board doubles every grid via, 1 mm from the first), `fix_fpids`,
`finish_board --silk --planes`, `run_drc.py`, `--fab` and `common/cpl.py`.

## Scripts

| Script | Role |
|---|---|
| `gen_board.py` | Netlist -> placed board: PLACEMENT table, PGND pours on both layers, antenna rule area, placement/keep-out/courtyard/plane-continuity assertions |
| `route_critical.py` | Pass 1, locked: USB pair (through the U12 ESD clamp into J3), CAN pair, and the U8 buck's power copper (VIN/PGND at each input cap, SW, 5V0 trunk, VBUS, VBUS_F) |
| `export_dsn.py` | Specctra export: locked copper as `fix`, B.Cu PGND as a plane, F.Cu PGND dropped, power net classes, keep-outs round fiducials and the board edge |
| `freerouting.rules` | Freerouting layer costs: B.Cu traces cost 4-6x F.Cu so B.Cu stays a near-solid ground plane with short jumpers |
| `finish_routes.py` | Pass 3: phase-1's exact-geometry router with two-layer settings |
| `stitch.py` | Pass 4: a PGND via in every F.Cu pour fragment, then a 5 mm grid |
| `run_drc.py` | DRC via pcbnew (KiCad 7 has no CLI drc) |

`import_ses.py` is phase-1's, run with explicit paths.

## Why the board looks the way it does

- **Ground on both layers.** The board was first drawn with F.Cu as a 3V3
  plane. On two layers F.Cu also carries most signals, and routing cuts a
  top plane into islands only a track can re-join. PGND on top is re-joined
  by any stitch via; 3V3 (under 0.5 A) runs as 0.4 mm tracks.
- **B.Cu is expensive for the router** (`freerouting.rules`): the first
  unweighted run put 1.4 m of track on B.Cu and cut the ground plane into
  large pieces; weighted, it is about 0.57 m of short jumpers.
- **The pairs are drawn by hand** because Freerouting routes each half of a
  pair as an unrelated net. The ESP32-S3's USB is full-speed only, so the
  pair is coupled and matched rather than impedance-controlled (90 ohm is
  not achievable on 1.6 mm two-layer stock).
- **The buck is drawn by hand** because an autorouter treats SW as just
  another net (first pass: 0.2 mm wide, two vias, round C50).
