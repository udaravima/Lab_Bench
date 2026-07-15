# Schematic / PCB generation pipeline

Everything in this KiCad project is **generated and machine-verified** — no
hand edits to `.kicad_sch`/`.kicad_pcb` (they'd be overwritten). The pipeline
exists so that every electrical claim is checked mechanically instead of by
eyeball; it has caught >15 real hardware bugs before any board was ordered.

## Philosophy

1. **Never trust memory for pinouts.** Every vendor symbol/footprint is
   diffed against its local datasheet (docs/datasheets/, gitignored) before
   merging. Package quirks found this way: LM5145 pin 15 is a real perimeter
   pin named "EP" (isolated, die pad is pad 21); DAC80502 DRX has **no**
   exposed pad; LMR36015 pin 3 is a no-connect that the datasheet ties to SW
   in copper; BAT54W (SC-70) and 1N4148W pin 1 are opposite polarities.
2. **The netlist is the single source of truth** — `EXPECTED_NETS` in
   gen_phase1.py is asserted against `kicad-cli sch export netlist` output.
3. **Placement claims are asserted too** — pads that must land in a power
   pour, courtyard overlaps, and board-edge escapes are all checked in code.

## Scripts

| Script | Role |
|---|---|
| `kicad_gen.py` | KiCad 7 s-expression schematic writer: symbol extraction (extends-flattening, SnapMagic fallback), pin-position transform, label-at-pin connectivity, synthesized power ports |
| `gen_phase1.py` | Draws all 7 sheets + `EXPECTED_NETS` (~90 nets). Run from tools/: `python3 gen_phase1.py` |
| `check_netlist.py` | Asserts exact/superset (`~` prefix) net membership, pin leaks, duplicate refs, global/local split nets |
| `check_footprints.py` | Every component has a resolvable footprint; every netted pin has a matching pad |
| `merge_vendor.py` | Merges only datasheet-VETTED vendor symbols into `lib/labbench.kicad_sym` |
| `build_fplib.py` | Same for footprints -> `lib/labbench.pretty/`; also generates `PowerFET_SON5x6_GDS` from the TI Q5A land pattern (pads renumbered 1=G/2=D/3=S for the generic symbol) |
| `gen_board.py` | Netlist -> placed 120x80 4-layer board: PLACEMENT table, split In1 ground plane (PGND/AGND star at NT1 + AGND pocket under the LTC7004), In2 5V0/3V3 zones, 10 F.Cu power pours, pour/courtyard/edge checks |
| `route_board.py` | Deterministic copper: In2 heat patches, thermal/stitching/pad vias (seam-aware), critical routes (Kelvin pair, LM5145 gate fan-out, BST/ILIM/VIN, NT1 tie) |
| `autoroute.py` | **WIP** grid A* signal router — see status note in its header |
| `run_drc.py` | DRC via pcbnew `WriteDRCReport` (KiCad 7 CLI has no drc command) |
| `dump helpers` | see scratch usage inside scripts; renders via `kicad-cli pcb export svg` |

## Full rebuild

```bash
cd hardware/phase1-module/tools
python3 gen_phase1.py                                  # 7 .kicad_sch sheets
kicad-cli sch export netlist -o /tmp/p1.net ../phase1-module.kicad_sch
python3 check_netlist.py /tmp/p1.net                   # must be: all nets OK
python3 check_footprints.py /tmp/p1.net                # must be: all OK
python3 gen_board.py /tmp/p1.net                       # placement + pours
python3 route_board.py                                 # vias + critical routes
python3 run_drc.py                                     # expect 0 copper errors
# python3 autoroute.py                                 # WIP — signal nets
```

Any schematic change: rerun the whole chain. Any placement change: rerun from
gen_board. `EXPECTED_NETS` must be updated in the same commit as connectivity
changes.

## pcbnew API notes (KiCad 7.0.11, hard-won)

- `pcbnew.BOARD()` without a project **segfaults ZONE_FILLER** — use
  `pcbnew.NewBoard(path)` + `board.BuildConnectivity()` before filling.
- Footprint children use `FP_SHAPE`/`SetPos0`+`SetDrawCoord` (relative
  coords), not `PCB_SHAPE`/`SetPosition`.
- Rotation semantics (measured, do not guess): 2-pad passives rot 90 puts
  pad 1 **down**, rot 270 up; pin headers/fuse/Phoenix have pin 1 at the
  footprint origin; rot 90 runs a header +x.
- `pad.GetParentFootprint()` returns a container — cast with
  `pcbnew.Cast_to_FOOTPRINT`.
- DRC: `kicad-cli pcb drc` does not exist in v7; `pcbnew.WriteDRCReport` does.

## Audit integration

The kicad-happy plugin analyzers (schematic/PCB/cross/EMC/thermal + ngspice
via the spice skill) run against this project; outputs land in `analysis/`
(run folders gitignored, manifest tracked). Last full audit: 2026-07-15/16 —
findings triaged in commit messages `848f836`, `c1f97c5`. ngspice: 38/40
subcircuits pass (crystal = generic-model warn, bridge = model limitation).
