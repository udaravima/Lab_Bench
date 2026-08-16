# Session Handover — Lab_Bench modular PSU

Written 2026-07-16, updated 2026-07-26 for the next agent (or future session)
continuing this project. Read this + README.md before touching anything.
**Start with "Phase-2 PCB — resume point" below** — that is the live work
front: 83 connections to finish by hand in KiCad. Manager firmware is done.

## The user & working agreement

- Hobbyist building a **multi-channel modular bench PSU**, learning along the
  way — explain the *why* of engineering decisions, not just the what.
- **Git: ask per-commit, NEVER `git push`.** The user's global CLAUDE.md rule
  (per-action commit approval) OVERRIDES the older "standing permission" line
  that used to be here — do the work, then stop and ask before each
  `git commit`. The user has been committing the PCB work themselves.
- **The KiCad schematics are hand-owned now (since 2026-07-19).** The user
  hand-rearranged every `.kicad_sch` for readability (commits 7485036 /
  f9c5ff6 / b6402a7). **Never rerun the schematic generators** (gen_phase2.py
  etc.) — they would clobber that work. Fix schematics by surgical hand-edit;
  the netlist/footprint checkers remain the gate. The *board* generators
  (gen_board.py / route_board.py) ARE still the workflow — they consume the
  netlist, not the .kicad_sch.
- Cost-sensitive: verify prices before recommending purchases; user buys from
  Mouser normally, LCSC acceptable.
- "Confirm everything without hallucinating": every part number, pinout,
  rating and register claim gets verified against a local datasheet, the
  vendor's own PDF (web fetch OK), or measured behaviour. This discipline has
  caught real bugs every single session — including my own wrong Isat claim.

## What the project is

Up to 8 hot-pluggable 600 W buck modules on a 24–30 V bus, each an analog
CV/CC supply (diode-OR'd error amps injecting into an LM5145/LM5143 FB node —
firmware is never in the regulation loop), STM32G431 per module, ESP32-S3
manager, CAN 2.0B @500k. Docs 01–07 are the spec; read 05 (build plan) first
— it has phase exit criteria. Phase 1 = single 150 W LM5145 prototype.

## State at handover (git log tells the story; never rebase published history)

| Area | State |
|---|---|
| Design docs 01–07 | complete (07 = module firmware, new) |
| Phase-1 schematic | **complete, v1**: 7 generated sheets, 137 components, ~90 nets machine-verified; audited (kicad-happy + ngspice 38/40 pass) |
| Footprints | all vetted; custom lib `labbench.pretty` (LM5145 RGY, LMR36015 RNX, DAC80502 no-EP WSON, PowerFET_SON5x6_GDS) |
| PCB — Phase 1 | Committed board = clean pass-1 (placement + pours + planes + critical routes, 0 copper DRC), **187 unconnected**, 75 silk. The old "33 unconnected" was from an autoroute run that was never committed (its drc-report.txt is gitignored, so the stale number persisted) — verified 2026-07-26 against the committed board |
| PCB — Phase 3 backplane | **FAB-READY (2026-07-26, d9e1a7b)**: 0 DRC, 0 unconnected, silk 39/39 clean, no plane islands. Gerbers+drills in `fab/` (gitignored) via `python3 ../common/finish_board.py phase3-backplane.kicad_pcb`. Cross-checked: Edge_Cuts exactly 330.00×100.00 mm; drills 2×6.4 (M6 lugs), 16×2.8 (8 slots × 2 XT60 pins), 6×3.2 (M3), 86×1.0, 61×0.4. **Still gated on the XT60 polarity buzz-out before ordering** |
| PCB — Phase 2 | **83 unconnected, 0 copper DRC, silk clean (2026-07-26, c1a86eb)** — see the resume section; finish by hand in KiCad. Older detail below: |
| PCB — Phase 2 (history) | **(2026-07-25, 27fb2d1).** `gen_board.py` placement green (173 comps, all pour/courtyard/edge assertions pass, 130×90 4-layer); `route_board.py` pass-1 done (power pours, In2 heat patches, both phases' gate fan-outs, Kelvin pairs, disconnect trunk). DRC: **copper down to ~19 clearance + ~11 dangling/mask/hole in 3 known clusters** (see resume section); 243 unconnected = signal nets, autoroute not yet run. Found & fixed a real LM5143 land-pattern bug in the process (see load-bearing decisions) |
| PCB — Phase 3 backplane | **COMPLETE pass-1 (2026-07-25)**: `phase3-backplane/tools/gen_board.py` (single-script: placement + 2oz bus pours + stitching + ALL signal routing) — **0 copper DRC, 0 unconnected**; only lib-bookkeeping (39) + 1 silk nick remain. 8 slots @30mm (XT60PW-F rot-90 mates the module pad-for-pad, socket y60..77.8 = module J5 1:1), M6 lugs -> RS1‖RS2 0.5mΩ Kelvin-sensed by INA228, nested PRESENT L-bus, CAN terminated past both end slots, E-stop chain threaded per docs. Netlist from `tools/wip/bp.net` (regenerate via kicad-cli) |
| PCB — Phase 3 manager | **placement pass complete, 0 DRC (2026-07-26)**: 100×80 2L, 87 footprints (80 comps + 4 M3 + 3 fiducials), 86 nets, F.Cu 3V3 / B.Cu PGND planes, antenna keep-out verified copper-free. **173 unconnected = the signal nets; routing is the next pass.** Reproduce: `cd tools && python3 gen_board.py wip/mgr.net` → `python3 ../../common/fix_fpids.py ../phase3-manager.kicad_pcb` → `python3 ../../common/finish_board.py ../phase3-manager.kicad_pcb --silk --planes` → `python3 run_drc.py` |
| Module firmware | v0.1 builds clean (6.3 KB): full peripheral binding + CAN dispatch around the host-tested `module_core`. Untested on silicon (no board yet) |
| Host tests | `cd firmware/tests && make test` — must stay green. **5 suites now**: can, core, manager, scpi, ui |
| Manager firmware | **v0.2 COMPLETE (2026-07-25, commit 174595e)**: `scpi_core` + `ui_core` join `manager_core` as host-tested cores; ESP-IDF shell fully written (display/encoder/USB-SCPI/app_main). Still **UNBUILT** — no IDF toolchain here. See docs/10 |
| Phase-2 circuit design | **complete (docs/08, 2026-07-16)**: all values worked + datasheet-verified; LM5143/LM5069/CSD18540Q5B/CSD19536KTT/XAL1510/TMUX1101/TL431 PDFs now in docs/datasheets/ |
| Phase-2 schematic | **complete, v1, audited (2026-07-17)**: 8 sheets, 171 components, 116 nets machine-verified; kicad-happy audit triaged (all errors = known false-positive classes or the deferred MPN pass — same baseline as Phase-1); ngspice **45/47 pass** (crystal warn + bridge skip = same model limitations as Phase-1's 38/40) |
| Phase-3 schematics | **complete, v1, audited (2026-07-17)**: backplane (29 comps, EXACT net assertions) + manager (80 comps) — audit caught a real omission (manager I²C pull-ups specified in docs/09 but not drawn; fixed, PR-001 clear). SPICE: manager 16/16, backplane 3/3. Backplane "missing I²C pull-up" findings = by design (manager owns them) |
| Manager firmware — detail | manager_core v0.1 (2026-07-18) + **scpi_core & ui_core v0.2 (2026-07-25)**, all host-tested. Shell modules: `display.c` (esp_lcd ILI9341, 8×16 VGA font generated by `idf/tools/gen_font.py` from the system PSF — never hand-typed), `encoder.c` (PCNT ×4 quadrature, push/hold), `scpi_usb.c` (TinyUSB CDC), `app_main.c` (one mutex over the three cores; TCA9535 keys; backplane INA228 meter). Managed components in `main/idf_component.yml`. **Bring-up knobs (expect wrong on first light-up): display rotation + RGB565 byte order, then encoder direction** — docs/10 §Bring-up 6–7 |
| Ordering/BOM | **China-first sourcing pass done (hardware/SOURCING.md, 2026-07-18)**: LCSC prices/stock verified for all phases (~$135 parts for the Phase-3 build, ~$300–380 all-in); inductor + slot-connector decisions taken (Sunlord + 3.75 mΩ shunts APPLIED to gen_phase2; XT60PW slots queued); order-early list: LTC7004 (5 pcs), CSD19536KTT (12 pcs). MPN-properties pass into symbols still pending |

## Phase-2 PCB — resume point (LIVE, rewritten 2026-08-16)

**State: 82 unconnected, 0 copper clearance DRC, board migrated to KiCad
10 format.** KiCad on this machine is now 10.0.5 (7 is gone); run_drc.py
works again via kicad-cli (commits ab57e42, 02a9e73, 0f2b361).

### Division of labour (user decision, 2026-08-16 session 3)

The user hand-routes the dense-field/hard parts of each board in KiCad
(see phase2-module/MANUAL-ROUTES.md — per-item work order with the wall
map and shove suggestions). Scripting handles: lane surveys, junk DELs,
open-field/long-haul routes, validation, DRC gates, stitching. Phase-3
manager routing and the BOM/MPN pass proceed in parallel with the user's
manual phase-2 pass. LESSON LEARNED: never iterate scripted waypoints
against sealed fine-pitch mazes — tried at length on the u3 pocket; the
analysis produced the wall map (valuable) but the routing itself is a
shove job.

### The routing method (working, keep using it)

1. `tools/finish_routes.py` — declarative waypoint router with an EXACT
   analytic clearance validator (`--check grp` / `--apply grp`). Groups:
   u3 (applied), u10, haul, aux, rail, stitch (tables written, unvalidated).
   Never rasterize occupancy: cell quantization false-blocks the
   exactly-legal 0.2/0.25mm geometry that covers this QFN field.
2. `autoroute.py NET1 NET2...` — per-net A* fallback (net filter added
   2026-08-16). Works for open-field nets; CANNOT escape sealed pins.
3. Pocket nets that failed BOTH are sealed by real geometry — the fix
   is deleting junk copper that walls lanes (two wins already: PS_RT's
   pocket "walls" y35.62/y37.38 + its 60mm-round-trip tail; PS_COMP
   pin2's dangling y37.0 wander). More of that surgery is the
   highest-value next move.

### Sealed-pin facts (proven at 0.2 clearance, don't re-derive)

- U3 top row: RT staircase (y31.0/31.38) + the C-pad at (76.0,30.5) +
  DITH vertical (x74.75) own every lane. VDDA 34/36, RES 32, FPWM 33
  have NO north escape; PS_EN pin40 got the only west via (73.15,31.65).
- U3 right col: 0.5mm pitch, 0.25-wide pads = 0.25 gaps; pins 24/25/28
  sealed east. G_HS_A's dive (79.54-80.3, y35.45+) + PH_CS_A (y34.25) +
  via (81.05,34.05) wall the corner.
- U3 bottom row: sealed; PS_VCC's corridor blocked by the BST_B
  stub/pin11 kp overlap at every height y36.9-40.7.
- Pocket east-west: FB spine (y33.5, x83.4-87.3) + COMP_Z (y33.6,
  x88.8-92.8) wall y33.4-33.8; B.Cu crossings blocked by SW1 (x82.55,
  y24.8-37.6, w0.4), G_HS_A (x80.3, y7.6-33.4, w0.64), BST_A (x83.55,
  y27.6-38.5) columns. Cross B.Cu only north of y24 or south of y39.
- PS_SS owns the under-body north band (y32.75) + escape tracks y37.38/
  y38.0; R26.1 is walled on its north by them.
- Via-in-pad does NOT fit at 0.5mm pitch (0.6 via + 0.25 clr > gap).

### U10 escape-channel facts (diag_grid-proven, 2026-08-16 session 2)

U10's rows seal between pads exactly like U3's (1.48mm-long pads, 0.5mm
pitch -> 0.20mm edge gaps, adjacent kp overlap). All four sides have
pad-shadow strips inside which NO turn is legal: west x77.22-79.10,
east x68.90-69.85, north y72.95-74.10, south y82.90-83.40 (approx).
Escapes run STRAIGHT OUT along the pad axis, then turn outside the
strip; bundle-lane plan needed per side (the y74.0 north and
y82.5-83.6 south corridors surveyed earlier are still the right
trunks). The u10 tables in finish_routes.py draft wrong-direction
routes (west through the body for right-row pads) - REWRITE before
use; do not iterate them as-is. A* on these nets fails not from
sealed pads (diag shows free srcs + exits everywhere) but from the
congested turn corridor; hand lanes + validator converges faster.

### What remains of the 81 (after 5974056)

- ~10 pocket items (sealed pins + PS_RT tail + PS_VCC + PS_COMP cluster
  + VOUT_INT pin5 + FB pin28): junk-surgery or interactive routing.
- U10 cluster (~15), long-haul lanes (~19: CAN/DAC/SLOT_ID/EAV/EAI),
  aux/5V0 locals, plane stitching (LAST). Lane surveys in
  tools/wip/lane_find.py + finish_routes.py comments: B.Cu analog-region
  trunk corridors y68.5-69.3 and y71.25-71.9 wide open; U10 escape
  lanes y74.0 north / y82.5-83.6 south.
- 3 zones_intersect (same-priority PGND pours) + silk pass at the end.

### Session tooling notes

- kicad-cli needs a scrubbed env (LD_LIBRARY_PATH/XDG_DATA_DIRS point
  into the session AppImage) — run_drc.py does this.
- pcbnew 10 API: Cast_to_FOOTPRINT, via GetWidth(layer), snapshot
  board.GetTracks() before Remove() loops, GetConnectedItems returns
  fresh wrappers (key by m_Uuid), pads stamp as RECTANGLES.
- finish_routes.py --check models DELs; run_drc.py exit code is real.

## Phase-2 PCB — earlier resume notes (2026-07-26, superseded by the section above)

**State: 83 unconnected, 0 copper DRC, silk clean.** Reproduce end to end:

```bash
cd hardware/phase2-module/tools
python3 gen_board.py wip/p2.net   # placement + pours
python3 route_board.py            # pass-1 hand copper
python3 autoroute.py              # ~41 min, 240 -> 83 unconnected
python3 silk_refs.py              # refdes reflow, silk 154 -> 11
python3 check_planes.py           # PS-002 island advisory
python3 run_drc.py                # -> ../drc-report.txt
```

### What is left: finish 83 connections by hand in KiCad

This is the honest recommendation, not a fallback. A grid maze router
cannot finish fine-pitch escapes; KiCad's interactive push-and-shove can,
and 83 items is an evening's work. The split:

| Group | Items | Nets | Note |
|---|---|---|---|
| Plane nets | 35 | AGND 16, 5V0 9, PGND 7, 3V3 3 | pour-fragment stubs — mostly a few stitch vias, not routing |
| U3 control cluster | ~14 | PS_VDDA 3, PS_COMP/PS_EN 2 ea, PS_DITH/FPWM/RES/VIN/VCC/PGOOD/FB 1 ea | LM5143 left+top pins, x 73–90 / y 32–38 |
| U10 (STM32 QFN) | ~15 | I2C_SDA/SCL, CAN_RX/TX/STB, SWCLK, NTC_*, SLOT_ID0-2, HW_EN, INA_ALERT, AUX_PG | x 70–98 / y 69–86 |
| Scattered | ~19 | V_MEAS 3, DAC_SCLK/SDI, V_REF, EAV_INJ/EAI_INJ, I_MEAS, VOUT_INT, VBUS_P, SW1, DISC_INP, AUX_BOOT, HS_PGD | 1–3 items each |

Exact per-item coordinates: `drc-report.txt`, `[unconnected_items]`
blocks (subtract the 20,20 page offset for board-relative).

**After hand-routing:** rerun `silk_refs.py` (new vias may push refdes),
then `check_planes.py`, then `run_drc.py`, then `gen_gerbers.py`.

### PS-002 (plane islands) — do this LAST

`check_planes.py` reports F.Cu pour islands whose pads reach ground only
through a pour arm. **Island geometry depends on the finished copper** —
they move every time routing changes (pre-route 70.5,45.2 / 96.3,43.8;
post-route 96.6,46.1 / 45.3,33.5 / 47.8,30.0 …). So do NOT bake
coordinates into route_board's STITCH: an attempt to do that this session
was silently rejected by `too_close()`. Stitch after routing is frozen,
verify the spot is on the right side of SEAM 67.3 (a via on the wrong
side shorts AGND to PGND), then rerun the checker. Current advisory: 6
islands, all electrically connected — quality, not a break.

### Freerouting: ruled out, with evidence

Do not spend another session on it without reading this.

- **With zones** (what the KiCad Freerouting *plugin* exports):
  `java.lang.StackOverflowError` in `PolylineTrace.combine`. Both v1.9
  and v2.2.4. This is the crash dialog you'll see from the plugin.
- **Zone-free** (`tools/export_dsn.py`): clears that crash — but then
  ran 2 h at 100 % CPU with zero output. A `jstack` dump caught it in
  `PolylineTrace.normalize -> split -> ShapeSearchTree.overlapping_tree_entries`,
  i.e. the same pathological path, no longer overflowing (big `-Xss`)
  just grinding. RSS 491 MB / 3 GB, so not GC thrash.
- v1.9 also needs a display even in batch mode (HeadlessException).
- **Untested hypothesis worth one experiment:** `route_board` emits
  multi-point runs as many short touching segments, and `normalize` is
  exactly the routine that merges collinear/touching segments. Merging
  them before export may be what unblocks it. Board geometry was already
  cleared as a cause (no zero-length, sub-50 µm or duplicate segments, no
  coincident vias).
- Round-trip tooling is ready if revisited: `export_dsn.py` (zone-free,
  all pass-1 copper locked → `(type fix)`) and `import_ses.py` (refuses
  to save if the fixed routes did not return, or unconnected went up).

### Known wart: route_board is not deterministic

Identical inputs gave 67, then 68, then 66 ground pad-vias across runs.
Only affects redundant stitching, but it undercuts the "regenerate
deterministically" discipline everything else here relies on — likely
iteration-order dependence in the pad-via pass. Worth pinning down.

## Phase-2 PCB layout — earlier resume notes (2026-07-25)

The generated-board pipeline is running and committed (27fb2d1). To reproduce
the exact current state:

```bash
cd hardware/phase2-module/tools
python3 gen_board.py wip/p2.net     # placement + pours, all assertions green
python3 route_board.py              # pass-1 copper (loads the board in place)
python3 run_drc.py                  # writes ../drc-report.txt
```

`wip/` (gitignored, reboot-proof) holds `p2.net` (the netlist the generator
runs against — regenerate with the `kicad-cli sch export netlist` line in
`wip/README.md`) and `gen_board_draft.py` (the superseded reasoning record).
Placement rationale: `hardware/LAYOUT.md`. The board generator mirrors phase-1
exactly — same PLACEMENT / PWR_POURS / EXPECT_IN_POUR / check_pours /
check_courtyards structure.

**STATUS 2026-07-25 (later): copper pass-1 COMPLETE — 0 copper DRC.**
The three clusters described in earlier revisions of this section are fixed
(the CS2 chain attached to U3 pin 3 instead of pin 4 — that was the root of
the dangling set; U6's 180-degree stubs redrawn; U5's via-on-pad and the R32
clip resolved; orphan vias and the isolated In2 5V0 fragment cleaned).
Remaining DRC: 180 lib_footprint_issues (benign bookkeeping, phase-1 carries
the same class), ~154 silk (cosmetic — silk-cleanup pass), and **238
unconnected = the signal nets.**

**Autoroute state (2026-07-25 evening):** `tools/autoroute.py` runs at a
0.125mm bytearray grid (the 0.25 grid could not hit the 0.185mm-wide legal
lanes at fine-pitch escapes; hole spacing is net-independent; plane targets
come from the in1/in2 maps). Result of the first full 0.125 run:
**unconnected 238 -> 88**; ~45 'no path' fails still cluster at the U3
pocket / U10 escapes. The run takes ~30 min. The committed board (c9888d7)
is the clean pre-autoroute copper state; the autoroute output is NOT
committed. Known issues for the next session, in order:
1. **False fails**: some failed pads (e.g. G_HS_A/U3) are already hand-
   routed by route_board — the router doesn't recognise the existing copper
   as connected (pad-center cell vs seeded track cells miss at 0.125).
   Fix: seed net_copper with the PAD cells of every pad that board
   connectivity already reports as connected, or check
   `board.GetConnectivity()` per pad before routing.
2. **Entry-stub clipping** (4 clearance): the grid-to-pad-centre entry stub
   clips the adjacent pad at 0.5mm-pitch pins (U6.5 stub vs U6.4, U6.7 stub
   vs U6.8). Fix: constrain the entry stub to the pad's long axis.
3. Two 0.4-0.9mm dangling slivers at (33.1,30.0)/(79.1,34.2).
4. Perf: invert the in1/in2 maps to net->cells ONCE (main() currently scans
   750k cells per net = most of the runtime).
After autoroute converges: silk cleanup, PS-002 recheck, gerbers + analyzer.

Notable route_board facts a future session needs:
- U3 (LM5143) left-col pin rows: 1=SS 32.75 / 2=COMP 33.25 / 3=AGND 33.75 /
  4=CS2 34.25 / 5=VOUT2 34.75 — off-by-one here cost a full DRC round.
- VOUT2 (U3.5) is deliberately left to autoroute: it shares VOUT_INT with
  VOUT1's Kelvin run (same sense node, so sharing is correct).
- The In2 VOUT_INT patch has a notch (105.5-109.5, 31-39) so the 5V0 zone
  reaches U4/C33 under the INA240; U4.6 has an explicit 5V0 via at
  (108.6,34.6) because the auto pad-via pass is pour-blocked in the column.
- C33.1 <-> U4.6 (5V0) and U3.25 <-> C28.1 (PS_VIN) are pad-to-pad joins
  left for autoroute on purpose.

## Phase-3 manager routing — state 2026-08-16 (commits 5aa913a, 942dda1)

**54 unconnected, ZERO DRC violations.** KiCad-10-native, kicad-cli
run_drc, autoroute.py ported + parallel (30 forked workers, re-validating
merge; --jobs=N). Fixes that mattered: keepout zones block the grid
(z.Outline().Outline(0)), per-pad local clearance honored (fiducials 0.5).
Remaining: 25 signal (USB DP/DN @ J3, PRESENT3-7 @ J1, U8 aux cluster,
I2C @ J1, LCD_SCK, KEY0/1/4, ESP_EN/BOOT0/ENC_B/BUZZ_N locals) — hand
waypoints via the ported tools/finish_routes.py or interactive; 29
power spokes (PGND/3V3/5V0/VBUS_F) LAST. Division of labour per the
phase-2 decision applies here too.

## Immediate next steps (agreed order)

1. **Finish Phase-2 board** — hand-route the remaining 83 connections in
   KiCad (table + per-item coords in the resume section), then
   `../common/finish_board.py` (silk + planes + fab) and `run_drc.py`.
2. **Phase-3 manager board — ROUTE it.** Placement is done and DRC-clean
   (see the table); what is left is 173 unconnected signal nets on a 2-layer
   board. Mostly 3-node digital nets, so hand-routing in KiCad is realistic;
   there is no `route_board.py` for this phase yet.
3. **MPN-properties pass → BOM CSVs → order files** — LCSC part numbers
   and prices are already verified in `hardware/SOURCING.md`; what is
   missing is the properties in the symbols and the generated CSVs.
4. **Phase-1 board** — 187 unconnected; port the phase-2 autoroute fixes
   (connectivity seeding, entry-stub snap, pocket costs, net ordering)
   before hand-finishing.

**Gates before ordering ANY board — including the fab-ready backplane:**

- **XT60 polarity continuity check** (MECHANICAL.md — verify J1 male vs
  backplane J-female in the *mated* orientation; the footprint descr still
  says pads 1/2 are ASSUMED +/−).
- **Re-verify LCSC stock** of the order-early parts (LTC7004, CSD19536KTT).
- **Manager board only: confirm the fab quotes 0.2 mm drilling** on a 2-layer
  stackup — the board rule was relaxed from 0.3 to 0.2 for the stock ESP32
  footprint's thermal-pad stitching, and that is above some cheapest-process
  quotes.
- Phase-2 audit notes (2026-07-17), all triaged, none blocking: VM-001 on
  CAN_*/DROOP_EN/PS_FPWM/PS_PGOOD/I_MEAS/V_MEAS are false positives
  (VIO-variant / verified V_IH / R31-mitigated / divider-bounded); FS-001
  "FB divider too low-Z" is the injection scheme working as designed; RS-001
  set identical to the audited Phase-1 baseline.

(This section used to carry three orphaned list items — "backplane + manager
schematics", "manager firmware", "batch PCB pass for phase-1" — left behind
by an earlier edit of the next-steps list above. All three were either
complete or superseded, and one repeated the stale "phase-1 has 33
unconnected" figure. Removed 2026-07-26; the live list is the numbered one
above.)

## Shared layout tooling (hardware/common, 2026-07-26)

Board-agnostic — use these instead of writing per-phase copies:

```bash
python3 ../common/finish_board.py BOARD.kicad_pcb   # silk + planes + fab
python3 ../common/finish_board.py BOARD.kicad_pcb --silk     # refdes reflow
python3 ../common/finish_board.py BOARD.kicad_pcb --planes   # PS-002
python3 ../common/finish_board.py BOARD.kicad_pcb --fab      # gerbers+drills
python3 ../common/fix_fpids.py    BOARD.kicad_pcb   # footprint lib nicknames
```

`--fab` refuses while anything is unconnected (`--force` overrides and
labels the output NOT fab-ready). The layer set is read from the board,
so 2- and 4-layer boards both work. `--fab` fills the zones before
plotting — it did not always, and a board whose stored fill was stale
plotted B.Cu at 8.5 kB instead of 219 kB, i.e. the whole 2 oz plane
missing from a run that reported success.

**Re-running a board generator throws away two post-generation passes.**
`gen_board.py` adds footprints by name only and places refdes naively, so
straight after a regenerate the board reports ~87 `lib_footprint_issues`
and a pile of silk errors that were not there before. That is expected, not
a regression — the fix is to finish the pipeline every time:

```bash
python3 gen_board.py wip/BOARD.net
python3 ../../common/fix_fpids.py ../BOARD.kicad_pcb        # nicknames
python3 ../../common/finish_board.py ../BOARD.kicad_pcb --silk --planes
python3 run_drc.py                                         # then the numbers
```

**The `lib_footprint_issues` pile was NOT benign bookkeeping** — it was
two real defects, both fixed 2026-07-26:
1. Generated footprints had an **empty FPID library nickname**
   (`fix_fpids.py` resolves and writes them back).
2. KiCad's global fp-lib-table expands `${KICAD7_FOOTPRINT_DIR}`, which
   only the GUI sets — so headless DRC resolved **no** library at all.
   Every `run_drc.py` now sets it before importing pcbnew.
Together these hid the fact that KiCad could not diff board footprints
against their libraries, i.e. silent land-pattern drift would have gone
unnoticed — and an LM5143 land-pattern bug was already caught here once
by hand. If a DRC report ever shows this class again, suspect the env.

## Verification workflow (non-negotiable, it works)

- Schematic change → `gen_phase1.py` → export netlist → `check_netlist.py` +
  `check_footprints.py`, all green, EXPECTED_NETS updated in the same commit.
- Board change → `gen_board.py` (pour/courtyard/edge assertions) →
  `route_board.py` → `run_drc.py`.
- Pipeline details + hard-won pcbnew API traps:
  `hardware/phase1-module/tools/README.md`.
- Audit stack available and installed: kicad-happy plugin skills (kicad, emc,
  spice, bom, distributor search) + **ngspice** installed; ARM toolchain at
  `~/tools/xpack-arm-none-eabi-gcc-14.2.1-1.1` (Makefile auto-finds it).
- Datasheets live in `docs/datasheets/` (gitignored). Vendor ECAD ZIPs in
  `hardware/phase1-module/lib/vendor/` (gitignored). If a needed datasheet is
  missing, ask the user (they download from Mouser) or fetch the vendor PDF.

## Load-bearing design decisions (with the trap each one avoids)

- **R31 = 1 kΩ** (INA240→PA1): PA1 is TT_a, 3.6 V max; INA240 on 5 V can rail
  to 4.8 V in an OC transient; 100 Ω would inject 12 mA into the clamp (5 mA
  abs max). Do not "optimise" it back down.
- **I²C on I2C2/PA8+PA9**, never I2C1/PB8: PB8 is BOOT0 — a pull-up there
  boots the ROM loader. **OUT_REQ on PB14**, not PB4 (NJTRST reset pull-up
  would close the disconnect at boot).
- **TCAN1042 must be a VIO variant** (HGV or V-suffix): logic side is 3V3.
- **LM5145 SYNCIN doubles as DEM/FPWM select**; low = diode emulation =
  battery-safe default (R16 pulldown). PS_FPWM drives it.
- **Crystal must be CL = 8 pF** (C66/C67 = 10 pF), or change caps to 18 pF.
- **XAL1350-103: Isat ≈ 18 A @30 % (Coilcraft Doc373), DCR 8.7 mΩ** — an
  earlier claim of 28 A was wrong. ILIM peak is ~14 A; keep margin.
- **INA228 ALERT has no external pull-up** in schematic v1 — firmware enables
  PB7's internal one; add a discrete pull-up in the next schematic rev.
- **Grounding**: PGND/AGND split planes joined ONLY at NT1 (net-tie beside the
  sense amps); In1 has an AGND pocket under the LTC7004 cluster. Never add a
  via that shorts the domains — the seam geometry lives in gen_board.py
  (`SEAM`, `AUXW`, `POCKET`).
- **Kelvin shunt**: pours grab only the outer halves of R30's pads; sense
  traces leave the inner edges. Preserve this in any re-layout.
- Package truths (all datasheet-verified): LM5145 pin 15 = isolated "EP"
  perimeter pin + pad 21 die pad; DAC80502 DRX has NO exposed pad; LMR36015
  pin 3 = NC (datasheet ties to SW in copper only); LTC7004 = MSOP-10, EP=11;
  BAT54W is SC-70 pin1=A, 1N4148W pin1=K (opposite!).
- **LM5143 land-pattern fix (2026-07-20, DO NOT revert):** the RHA0040P
  perimeter-pad centres are at **±2.9 mm, not ±2.6**. The datasheet's (5.8)
  callout is the pad centre-to-centre span; at the ±2.6 misread the
  perpendicular corner pads overlapped 0.075 mm (real DRC clearance error,
  caught only once U3 was on a board). `build_fplib.py` regenerates the
  corrected `labbench:LM5143_RHA0040P` (courtyard grew to ±3.45, silk ticks
  moved out). **Regenerating the footprint lib rewrites every file's tstamps**
  — after `python3 build_fplib.py`, `git checkout` all the other .kicad_mod
  files so only LM5143 changes (that's what commit 27fb2d1 did).
- **Manager C64/C65 are rotated 180° on purpose (2026-07-26, DO NOT revert):**
  at rot 0 these caps face U10 with their *PGND* pad, 0.97 mm from U10's pad
  column — and at 0.3 mm zone clearance per side that channel is too narrow to
  fill, so the F.Cu 3V3 pour was pinched into a **244.6 mm² island carrying
  U10's own 3V3 pad with no tie**. Turned round, the gap is same-net and the
  pour flows; it also shortens the decoupling path (C65 3.73 → 2.68 mm, C64
  6.70 → 4.79 mm from pad 2), so it is strictly better than the placement it
  replaced. Note what this defect looked like: the board still passed DRC at
  **0 violations**, and the break showed up only as one extra unconnected item
  hidden among 173 unrouted signal nets. `check_plane_continuity()` in the
  manager's `gen_board.py` now fails the build on any pour fragment that holds
  pads without a via/PTH tie — it runs after the final fill, because island
  geometry is a property of the finished copper. On a 2-layer board a stitch
  via cannot fix this class at all: the other layer is the other plane.
- **Phase-2 (docs/08) load-bearing findings — do not "optimise" these away:**
  - **6.8 µH, not 4.7 µH**: LM5143 internal slope comp (~100 mV/µs @347 kHz)
    fails Ridley m_c(1−D) > 0.5 with 4.7 µH at D→0.93 (worst 0.44). 6.8 µH
    gives 0.61. Any change to L, R_S(3.5 mΩ) or f_sw reruns this check.
  - **INA240A3, not A4**: gain 200 on 0.5 mΩ puts 30 A at 3.0 V — above the
    DAC80502's 2.5 V full scale → CC loop capped at 25 A. A3 = 1.5 V @30 A.
  - **OVP squeeze**: divider ceiling 28.4 V < TLV7011 trip 29.4 V < bus 30 V.
    Only ~1 V each side — the OVP divider needs 0.1 % parts.
  - **Aux buck EN gated by LM5069 PGD**: load must stay off during inrush or
    it eats the P_LIM budget and can fault the start (TI rule). Don't tie
    LMR36015 EN high.

## Deferred requirement (2026-07-18, user decision)

Sub-0.5 V / millivolt-accurate output for laptop/CPU-rail work is wanted
**later**, as a future dedicated module (linear post-regulator card in a
rack slot — the "Option B" analysis: buck pre-regulator tracking
V_out+1.5 V, D2PAK pass stage with DC SOA, ~$5–12 BOM, remote sense
mandatory). Current modules keep their buck floors: P2 guarantees clean
output from 0.7 V (30 V bus; ~0.55 V at 24 V bus), P1 from 0.5 V — below
that the average is servo'd but ripple is skip-mode coarse.

## Open items / known warts

- **Phase-2: 83 connections to finish by hand** — see the resume section.
- **`route_board.py` is not deterministic** (67/68/66 pad-vias on identical
  input). Harmless today, but it breaks the reproducibility contract.
- **Freerouting does not work on this board** — evidence in the resume
  section; the KiCad plugin hits the same StackOverflowError.
- Phase-1 `autoroute.py`: router-via self-spacing bug, congested U3/U10
  escapes — its header has the fix list. Deferred. (Its old "33 unconnected"
  claim was wrong; the committed board is **187** — see the table.)
- Phase-1/2 DRC noise is now **silk only** (75 and 11, cosmetic). The
  `lib_footprint_issues` pile is gone and was never "harmless bookkeeping" —
  see the shared-tooling section for what it was actually hiding.
- **`run_drc.py` in phase-1, phase-2 and phase-3-backplane still always
  `sys.exit(0)`**, despite the docstring promising exit 1 on error-severity
  violations. Only the phase-3-manager copy has been fixed (it now parses
  per-item severity and fails on errors or unconnected items). Anything that
  gates on the other three exit codes is gating on nothing — read their
  printed output instead until they are ported.
- **The phase-2 tools are not wrappers over `hardware/common/`.**
  `silk_refs.py`, `check_planes.py` and `gen_gerbers.py` each carry their own
  copy of logic that now also lives in `common/layout_qa.py`. Retiring the
  copies changes the silk algorithm the committed phase-2 board was built
  with, so it needs a board diff attached — deliberately not done yet.
- LCSC stock was thin on LTC7004 (5) and TLV7011 (42) at 2026-07-16.
- kicad-happy VM-001 flags CAN_RX/TX/STB as 5V↔3.3V crossings — false
  positives (VIO variant); I_MEAS was the one real hit (fixed via R31).
- `.remember/` memory files and `analysis/` run folders are working artifacts,
  not design data.

## Session/tooling quirks

- The permission classifier occasionally goes down mid-session ("temporarily
  unavailable"): wait and retry the same call; do read-only work meanwhile.
- KiCad 7.0.11: no CLI DRC/ERC — use `tools/run_drc.py`. Renders via
  `kicad-cli * export svg` + ImageMagick `convert` (rsvg-convert flaky).
- Coilcraft/Mouser/DigiKey product pages block scraping; use the jlcsearch
  API (no auth) for LCSC data, `curl` with browser UA for vendor PDFs, and
  the Farnell datasheet CDN as fallback.
- **A VSCode local-history "restore" can silently revert a whole board.** On
  2026-07-26 `phase2-module.kicad_pcb` came back as an old revision — 213
  tracks instead of 1512, 247 vias instead of 359, **unconnected 83 -> 244**,
  i.e. the entire autoroute + pass-1 result gone — with the good file dropped
  into `hardware/phase2-module/_restore_backup_<timestamp>/`. It looks like an
  ordinary dirty file in `git status`; nothing announces it. If a board file
  is unexpectedly modified, **diff the copper before committing**: count
  tracks/vias/unconnected against HEAD rather than eyeballing the diff, which
  is a 100k-line whole-file rewrite either way. Recovery is just
  `git checkout -- <board>` as long as the good state was committed — which is
  the real argument for committing each clean board state promptly.
