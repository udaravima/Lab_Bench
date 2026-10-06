# Phase-2 board pipeline

The schematic side (gen_phase2.py, check_netlist.py, check_footprints.py)
follows `hardware/phase1-module/tools/README.md`. The schematics are
hand-owned since 2026-07-19: **never rerun gen_phase2.py**. The board side
consumes the netlist, not the `.kicad_sch`.

Run everything with the KiCad 7 Python (`python3.12` on the cloud image,
where plain `python3` may be a different interpreter without pcbnew/numpy).

## Scripts

| Script | Role |
|---|---|
| `gen_board.py` | Netlist -> placed 130 x 90 4-layer board: PLACEMENT table (board-relative mm), In1 PGND/AGND split with the AGND pocket, In2 3V3/5V0 zones and heat patches, F.Cu power pours, pour/courtyard/edge checks |
| `route_board.py` | Pass-1 hand copper: the LM5143 (U3) corner fan-out, VOUT2/COMP2 inside U3's pad ring, gate drives, Kelvin pairs, U4 analog ground, output-cap PGND vias, plane/stitch vias |
| `fanout.py` | Phase-1 port: plane-net via drops and escapes for pads walled in by a foreign pour |
| `export_dsn.py` / `import_ses.py` | Freerouting round trip (zone-free DSN, own SES parser; import refuses to save if unconnected went up) |
| `finish_routes.py` | Shapely A* finisher for what Freerouting leaves open. `--inner=1` also routes on In2, `--only=` / `--first=` pick nets, `--base=` enables rip-up of copper not in the base board, `--budget=` caps attempts. Tracks stay 0.85 mm off the edge (`EDGE_KEEP`) |
| `check_planes.py` | PS-002 plane-island advisory |
| `run_drc.py` | DRC via pcbnew `WriteDRCReport`; always exits 0, read its output |
| `autoroute.py`, `silk_refs.py`, `gen_gerbers.py` | Superseded by the steps below and `hardware/common/` (kept for reference) |

## How the committed board was routed (2026-09-27)

```bash
cd hardware/phase2-module/tools
python3.12 gen_board.py wip/p2.net           # placement + pours
python3.12 route_board.py                    # pass-1 hand copper
python3.12 fanout.py ../phase2-module.kicad_pcb
cp ../phase2-module.kicad_pcb wip/base.kicad_pcb     # rip-up base: hand copper only
python3.12 export_dsn.py wip/p2.dsn ../phase2-module.kicad_pcb
xvfb-run -a java -Xss64m -jar freerouting-1.9.0.jar \
    -de wip/p2.dsn -do wip/p2.ses -mp 20 -mt 1 -oit 20   # -oit bounds the optimizer
python3.12 import_ses.py wip/p2.ses ../phase2-module.kicad_pcb   # ~148 -> ~32 open
python3.12 finish_routes.py ../phase2-module.kicad_pcb --inner=1 --base=wip/base.kicad_pcb
```

That left EAI_INJ open plus a few edge-hugging routes. They were closed on
the routed board by hand ECOs, which the `.kicad_pcb` now carries (it is the
source of truth after routing, as on phase-1):

- 5V0 copper Freerouting ran along the board edge was removed and re-routed.
- EAI_INJ escapes: a 0.5 mm via at R8.1 with a B.Cu run south, the PS_DITH
  via moved clear of it, and a via escape at D2.3.
- CAN_TX's router copper fenced the MCU area on B.Cu, so it was stripped
  (`strip_routes.py`), then `finish_routes.py --inner=1 --only=EAI_INJ,CAN_TX`
  routed EAI_INJ first and CAN_TX after it.

Rip-up across the whole board (`--base=` with no `--only`) cascades on this
board: one pass went from 1 open to 10. Strip one blocking net and re-route
it after the stuck net instead.

## Engineering changes on the routed board

The 2026-10-06 L2 change (1210 -> 5 x 5 mm FNR5040S, as on the manager)
was an ECO, not a re-route:

```bash
python3 ../../common/eco_swap_fp.py ../phase2-module.kicad_pcb L2 \
    Inductor_SMD:L_Changjiang_FNR5040S 68.4 57.45 270
```

The bigger pads swallow the old SW_AUX via (68.85, 55.4) and 5V0 via
(68.575, 59.175), so the two F.Cu stubs that reached them from the old pads
were deleted and a 0.3 mm 5V0 stub ties C55's via (68.6, 60.4) to pad 2.
Then zone refill, `finish_board --silk --planes`, `run_drc.py`, `--fab` and
`common/cpl.py`. `gen_board.py` PLACEMENT carries the new position.

## Finishing

```bash
python3.12 ../../common/fix_fpids.py ../phase2-module.kicad_pcb
python3.12 ../../common/finish_board.py ../phase2-module.kicad_pcb --silk --planes
python3.12 check_planes.py ../phase2-module.kicad_pcb      # PS-002 clear
python3.12 run_drc.py ../phase2-module.kicad_pcb           # 0 unconnected, 0 errors
python3.12 ../../common/finish_board.py ../phase2-module.kicad_pcb --fab
(cd ../.. && python3.12 common/cpl.py phase2-module/phase2-module.kicad_pcb)
```

DRC result on the committed board: 0 unconnected, 0 errors, 19 warnings
(14 silk, 4 vias that the DRC sees on one layer only, 1 In2 PS_DITH stub
end). Removing those 4 vias opens a connection, so they stay.
