# Schematic / PCB generation pipeline

> **Phase 2:** `hardware/phase2-module/tools/` follows this same pipeline
> (gen_phase2.py + its own check wrappers); it shares this project's
> `lib/` and everything in `hardware/common/`. merge_vendor.py also emits
> the synthesized LM5143/LM5069 symbols (hardware/common/synth_symbols.py,
> pin maps transcribed from local datasheets); build_fplib.py generates the
> LM5143_RHA0040P land pattern (EP 3.3×3.3 — no stock RHA variant matches).

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
| `../../common/kicad_gen.py` | KiCad 7 s-expression schematic writer: symbol extraction (extends-flattening, SnapMagic fallback), pin-position transform, label-at-pin connectivity, synthesized power ports. **Shared with phase2-module** |
| `../../common/sheets_common.py` | The five sheets both phases share (control-core, sensing, disconnect, aux-rails, mcu-can) as parameterized builders — extracted verbatim from the netlist-verified Phase-1 generator (netlist-equivalence-checked at extraction) |
| `gen_phase1.py` | Draws all 7 sheets + `EXPECTED_NETS` (~90 nets). Run from tools/: `python3 gen_phase1.py` |
| `check_netlist.py` | Asserts exact/superset (`~` prefix) net membership, pin leaks, duplicate refs, global/local split nets |
| `check_footprints.py` | Every component has a resolvable footprint; every netted pin has a matching pad |
| `merge_vendor.py` | Merges only datasheet-VETTED vendor symbols into `lib/labbench.kicad_sym` |
| `build_fplib.py` | Same for footprints -> `lib/labbench.pretty/`; also generates `PowerFET_SON5x6_GDS` from the TI Q5A land pattern (pads renumbered 1=G/2=D/3=S for the generic symbol) |
| `gen_board.py` | Netlist -> placed 100x80 4-layer board: PLACEMENT table, split In1 ground plane (PGND/AGND star at NT1; the LTC7004 now sits on the AGND side, so no pocket), In2 5V0/3V3 zones, 10 F.Cu power pours, pour/courtyard (real polygons)/edge checks. The 120x80 layout is on branch `phase1-120x80` |
| `route_board.py` | Deterministic copper: In2 heat patches, thermal/stitching/pad vias (seam-aware), critical routes (Kelvin pair, LM5145 gate fan-out, BST/ILIM/VIN, NT1 tie) |
| `autoroute.py` | Superseded grid A* signal router (kept for reference) |
| `fanout.py` | Routing pass 1b: placement nudges (NUDGES, empty now), solid-joined pads (SOLID_PADS), hand escapes for U3's boxed-in pins, then a via drop for every plane-net pad (PGND/AGND to In1, 3V3/5V0 to In2) and an escape for signal pads inside a foreign F.Cu pour |
| `export_dsn.py` | Specctra export for Freerouting: In1/In2 as power layers, real filled plane outlines, F.Cu pours as planes + keepouts, existing copper locked |
| `import_ses.py` | Imports a Freerouting session (own SES parser; KiCad 7's ImportSpecctraSES cannot run headless), refuses to save if unconnected went up |
| `eco_move.py` | Moves parts on the routed board and peels their old routes back to the nearest junction, so `finish_routes.py` only reconnects them; `--find` lists legal spots near a point |
| `finish_routes.py` | Routing pass 3: exact-geometry (Shapely) A* router that closes whatever Freerouting left open, with rip-up of non-base copper and a final tidy of dangling stubs |
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
```

## Signal routing (how the committed board was routed, 2026-09-27)

`gen_board.py` + `route_board.py` give pass 1. The committed board adds:

```bash
python3 fanout.py                                  # escapes + plane via drops
cp ../phase1-module.kicad_pcb /tmp/base.kicad_pcb  # base for rip-up
python3 export_dsn.py wip/p1.dsn
xvfb-run -a java -Xss64m -jar freerouting-1.9.0.jar \
    -de wip/p1.dsn -do wip/p1.ses -mp 20 -mt 1     # 2.x CLI never finishes
python3 import_ses.py wip/p1.ses                   # 145 -> ~18 unconnected
python3 finish_routes.py ../phase1-module.kicad_pcb --base=/tmp/base.kicad_pcb  # -> 0 (board path first)
python3 fb_reroute.py                              # FB run >= 5.5 mm from SW copper
python3 ../../common/fix_fpids.py ../phase1-module.kicad_pcb
python3 ../../common/finish_board.py ../phase1-module.kicad_pcb --silk --planes
python3 run_drc.py                                 # 0 unconnected, 0 errors
python3 ../../common/finish_board.py ../phase1-module.kicad_pcb --fab
(cd ../.. && python3 common/cpl.py phase1-module/phase1-module.kicad_pcb)  # JLCPCB CPL
```

Freerouting is not deterministic, so a rerun gives a different (equally
DRC-clean) result.

### Changing placement on the routed board

Rerouting from scratch is not needed to move a few parts. The 2026-09-27
review fixes were made this way:

```bash
cp ../phase1-module.kicad_pcb /tmp/b.kicad_pcb
python3 eco_move.py /tmp/b.kicad_pcb --find R60 86.75 93 5   # legal spots
python3 eco_move.py /tmp/b.kicad_pcb C28=67.75,52.2,90       # move + peel
python3 eco_move.py /tmp/b.kicad_pcb R60=83.5,93,0 C62=86.5,93,0 \
    R61=85,94.75,0 --keep=U10.14 --drop=86,93.5
cp /tmp/b.kicad_pcb /tmp/base.kicad_pcb
python3 finish_routes.py /tmp/b.kicad_pcb --base=/tmp/base.kicad_pcb
```

Then copy the result over the board, run the finishing steps above (if
DRC flags a kept escape via as dangling because the router joined the
pin another way, delete that via and its stub), and
put the new positions in `gen_board.py` PLACEMENT (page mm minus the
20,20 origin; eco_move takes page mm). PLACEMENT matches the committed
board for every footprint. `gen_board.py` still fails its own L1/C23
courtyard check, as before.

### Swapping a land on the routed board

A footprint change (not just a move) is done with
`../../common/eco_swap_fp.py`, which replaces the footprint in place and
carries the reference, value, fields and pad nets over. The 2026-10-06 L2
change (1210 -> 5 x 5 mm FNR5040S, same as the manager's in PR #16):

```bash
python3 ../../common/eco_swap_fp.py ../phase1-module.kicad_pcb L2 \
    Inductor_SMD:L_Changjiang_FNR5040S 32.6 61.25 0
```

then the SW_AUX diagonal was re-ended on the new pad 1 at (30.75, 60.15),
a 0.4 mm F.Cu 5V0 link was added from L2's via (35.5, 61) to C54's
(36.425, 61), and `finish_board --silk --planes`, `run_drc.py`, `--fab` and
`common/cpl.py` were rerun. The spot came from `eco_move.py --find L2`.
PLACEMENT in `gen_board.py` carries the new position.

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
