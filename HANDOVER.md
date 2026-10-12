# Session Handover — Lab_Bench modular PSU

Written 2026-07-16, last refreshed 2026-10-06 for the next agent (or future
session) continuing this project. Read this + README.md before touching anything.
**All four boards are routed with 0 unconnected and 0 DRC errors**, v0.1.0
was released from `master` on 2026-09-29, and the manager L2 / backplane C2
part change (PR #16) landed on `development` on 2026-10-06. On 2026-10-06
the phase-1/phase-2 L2 moved to the manager's 5 × 5 mm land and the last
BOM `CHECK:` rows were closed, so no `CHECK:` row is left in any BOM. What
stands between the project and the first order is the gates under
"Immediate next steps".

## The user & working agreement

- Hobbyist building a **multi-channel modular bench PSU**, learning along the
  way — explain the *why* of engineering decisions, not just the what.
- **Git: ask before committing, never push to `master`.** The user's global
  CLAUDE.md rule (per-action commit approval) OVERRIDES the older "standing
  permission" line that used to be here. Since 2026-09-27 all work goes to
  the `development` branch through a feature branch and a pull request;
  `master` only receives batched merges from `development` (it stays the
  GitHub default branch). A major board redesign goes on its own branch,
  and the prior design is saved as a branch first (e.g. `phase1-120x80`).
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
| PCB — Phase 1 | **100 × 80 mm, routed, 0 unconnected, 0 DRC errors** (2026-09-27, PR #9, merged; the 120 × 80 layout it replaces is kept on branch `phase1-120x80`). Re-placed from the netlist, so L1 now has the 17 mm MWSA1707S/XAL1510 superset land and U7 the SC-70-5 land the BOM orders (the 120 × 80 board still carried XAL1350 and SOT-23-5 lands: do not order it). Output bank tightened round the bigger L1; R30 Kelvin shunt, U4/U5 and their sense traces moved as one block with the same geometry; Q3/Q4, J4 and the LTC7004 stack down the right edge. Pipeline: pass-1 + `fanout.py` + Freerouting 1.9 + `finish_routes.py`; 1303 tracks / 353 vias. DRC = 11 silk *warnings*. Fab zip + CPL regenerated. 2026-09-28 (PR #13): OVP_TRIP routed to U10 PB4 for the firmware 0.2 OVP latch. **ECO 2026-10-06:** L2 1210 → 5×5 mm FNR5040S at (32.6, 61.25), SW_AUX stub re-ended on the new pad, a 0.4 mm F.Cu 5V0 link added from L2's via to C54's; C20/C75–C77 value now 10u/50V. DRC unchanged (10 silk warnings) |
| PCB — Phase 3 backplane | **FAB-READY (2026-07-26, d9e1a7b)**: 0 DRC, 0 unconnected, silk 39/39 clean, no plane islands. Gerbers+drills in `fab/` (gitignored) via `python3 ../common/finish_board.py phase3-backplane.kicad_pcb`. Cross-checked: Edge_Cuts exactly 330.00×100.00 mm; drills 2×6.4 (M6 lugs), 16×2.8 (8 slots × 2 XT60 pins), 6×3.2 (M3), 86×1.0, 61×0.4. **Still gated on the XT60 polarity buzz-out before ordering** |
| PCB — Phase 2 | **130 × 90 mm, routed, 0 unconnected, 0 DRC errors (2026-09-27, PR #11, merged 2026-09-28)**; fab zip + CPL committed; pre-order review closed (see the resume section). **ECO 2026-10-06:** L2 1210 → 5×5 mm FNR5040S at (68.4, 57.45) r270; its SW_AUX and 5V0 vias now sit in its pads, a 5V0 stub ties C55's via to L2. DRC unchanged (19 warnings, 0 errors). The 83-unconnected history is kept below for its tooling notes |
| PCB — Phase 3 manager | **Routed, 0 unconnected, 0 DRC errors (2026-09-27, merged into `development`)**: placement reworked (15+ passives had been placed by stale refdes, far from their pins; U8 buck re-laid tight round its pinout; U11 turned so CAN faces J1; U12 in the USB path), PGND now poured on both layers (was F.Cu 3V3 / B.Cu PGND), USB + CAN pairs and buck power copper hand-drawn and locked (`route_critical.py`), rest Freerouting 1.9 + `finish_routes.py`, 283 PGND stitch vias. DRC = 5 warnings (4 silk, 1 U8 courtyard-override lib mismatch). Antenna keep-out copper-free. Pipeline: `phase3-manager/tools/README.md`. **ECO 2026-10-05:** L2 moved from the 1210 land (no stocked 33 µH above 0.5 A) to a 5×5 mm FNR5040S (FNR5040S330MT, Isat 1.3 A); C54/C55 turned 180° so 5V0 runs straight from L2; PRESENT1/4–7 re-routed round the bigger part with `finish_routes.py`. Still 0 unconnected, 0 DRC errors, 4 warnings (PR #16, merged 2026-10-06; fab zip, BOM and CPL regenerated) |
| Module firmware | v0.2 builds clean (7.1 KB): full peripheral binding + CAN dispatch around the host-tested `module_core`. 0.2 (2026-09-28) closes the two protection gaps from the bench-test review: OCP backup #2 (`lb_core_ocp_sample`: INA240 ADC or INA228 SOVL alert >110 % i_max for >5 ms) and OVP latch #4 (OVP_TRIP routed to PB4 on the 100 × 80 board; EXTI4 kills EN, tick latches). Untested on silicon (no board yet) |
| Host tests | `cd firmware/tests && make test` — must stay green. **5 suites now**: can, core, manager, scpi, ui |
| Manager firmware | **v0.2 COMPLETE (2026-07-25, commit 174595e)**: `scpi_core` + `ui_core` join `manager_core` as host-tested cores; ESP-IDF shell fully written (display/encoder/USB-SCPI/app_main). **First compile 2026-09-27: builds clean on IDF v5.3.2** (355 KB image, two build fixes). Untested on silicon. See docs/10 |
| Phase-2 circuit design | **complete (docs/08, 2026-07-16)**: all values worked + datasheet-verified; LM5143/LM5069/CSD18540Q5B/CSD19536KTT/XAL1510/TMUX1101/TL431 PDFs now in docs/datasheets/ |
| Phase-2 schematic | **complete, v1, audited (2026-07-17)**: 8 sheets, 171 components, 116 nets machine-verified; kicad-happy audit triaged (all errors = known false-positive classes or the deferred MPN pass — same baseline as Phase-1); ngspice **45/47 pass** (crystal warn + bridge skip = same model limitations as Phase-1's 38/40) |
| Phase-3 schematics | **complete, v1, audited (2026-07-17)**: backplane (29 comps, EXACT net assertions) + manager (80 comps) — audit caught a real omission (manager I²C pull-ups specified in docs/09 but not drawn; fixed, PR-001 clear). SPICE: manager 16/16, backplane 3/3. Backplane "missing I²C pull-up" findings = by design (manager owns them) |
| Manager firmware — detail | manager_core v0.1 (2026-07-18) + **scpi_core & ui_core v0.2 (2026-07-25)**, all host-tested. Shell modules: `display.c` (esp_lcd ILI9341, 8×16 VGA font generated by `idf/tools/gen_font.py` from the system PSF — never hand-typed), `encoder.c` (PCNT ×4 quadrature, push/hold), `scpi_usb.c` (TinyUSB CDC), `app_main.c` (one mutex over the three cores; TCA9535 keys; backplane INA228 meter). Managed components in `main/idf_component.yml`. **Bring-up knobs (expect wrong on first light-up): display rotation + RGB565 byte order, then encoder direction** — docs/10 §Bring-up 6–7 |
| Ordering/BOM | **China-first sourcing pass done (hardware/SOURCING.md, 2026-07-18)**: LCSC prices/stock verified for all phases (~$135 parts for the Phase-3 build, ~$300–380 all-in); inductor + slot-connector decisions taken (Sunlord + 3.75 mΩ shunts APPLIED to gen_phase2; XT60PW slots queued); order-early list: LTC7004 (5 pcs), CSD19536KTT (12 pcs). MPN/LCSC pass done (`common/bom.py`, see next steps). Picks since: ENC1/F1/BZ1 (PR #10), phase-2 C15/16/36/37 EEHZA1V221P and U5 INA228AQDGSRQ1 (PR #11), manager J3 USB4105-GF-A (C3020560, PR #12), manager L2 FNR5040S330MT (C167973) and backplane C2 Nichicon UCX1H471MNS1MS (C462700, fallback EEEFK1H471AM C178551) (PR #16) |

## Phase-2 PCB — resume point (routed, 2026-09-27)

**State: routed. 0 unconnected, 0 DRC errors, 19 warnings (silk and
four one-layer vias), PS-002 clear, fab zip + CPL generated.** The routing
recipe is in `tools/README.md`. The pre-order review (2026-09-28) closed
every point: FB2 -> AGND is what LM5143 §8.3.17.2 asks for in interleaved
mode; C15/16/36/37 are now EEHZA1V221P (fits the 10x10.5 land); U5 is the
stocked INA228AQDGSRQ1 (same pinout and registers). Layout points kept on
purpose: G_LS_A's B.Cu detour is 26 mm vs G_LS_B's 20 mm (a few nH);
VOUT2/COMP2 under U3 are mask-covered, DC-quiet tie nets; B.Cu signal
crossings leave the In1 AGND pocket (the reference plane) unbroken.
**Bring-up item:** RT1 sits between the phases as docs/08 intends, but on
the AGND pocket, which is thermally isolated from the PGND copper the FETs
heat. Expect NTC_FET to lag and read low: log it against a thermocouple
on Q2 at full load and set the derate/OTP thresholds from that offset.

Everything below in this section is the 2026-07-26 history (83 open
connections, since finished), kept for its Freerouting and PS-002 notes.
The old recipe:

```bash
cd hardware/phase2-module/tools
python3 gen_board.py wip/p2.net   # placement + pours
python3 route_board.py            # pass-1 hand copper
python3 autoroute.py              # ~41 min, 240 -> 83 unconnected
python3 silk_refs.py              # refdes reflow, silk 154 -> 11
python3 check_planes.py           # PS-002 island advisory
python3 run_drc.py                # -> ../drc-report.txt
```

### History: the 83 connections left on 2026-07-26 (all routed since)

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

### Freerouting: the 2026-07 failure notes

Superseded: Freerouting 1.9 with a zone-free DSN and `-oit` finished the
board on 2026-09-27 (`tools/README.md`). The notes below explain why the
plugin route and 2.x still fail.

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

## Immediate next steps (agreed order)

1. **BOM `CHECK:` rows: all closed 2026-10-06** (stock checked that day):
   - Phase-1 C20/C75–C77: no 22 µF 50 V 1210 is stocked anywhere, so the
     design value is now 10 µF 50 V X7R (GRM32ER71H106KA12L). About 0.3 Vpp
     input ripple at 8 A, D = 0.5, 350 kHz; ~1 A RMS per cap; C21 is the bulk.
   - Phase-1 and phase-2 L2: moved to the manager's 5 × 5 mm FNR5040S land
     (FNR5040S330MT, C167973, Isat 1.3 A) as an ECO on both routed boards.
   - Phase-1 Q1–Q4: CSD18563Q5A is still out of stock; NTMFS5C670NLT1G
     stays. Its case 488AA terminals sit within 0.14 mm of the TI part's on
     the TI Q5A land, with more clearance to the drain land (0.35 vs 0.24 mm).
   - Phase-2 U3: LM5143QRHARQ1 is the LM5143A-Q1. Same pin map, and its
     RHA0040N land equals RHA0040P (EP 3.3, 0.5 pitch, 5.8 span); only
     wettable flanks differ. It now costs $6.29 (243 at LCSC).
2. **Thin stock (2026-10-06):** INA228AQDGSRQ1 has **5** at LCSC/JLCPCB
   (the AIDGSR has 0): one per module plus the backplane, so buy them
   first or from Mouser/DigiKey. LTC7004EMSE has 25 (now $11.62).
3. **Order files**: `python3 common/bom.py` (from `hardware/`) writes hidden
   LCSC/MPN/Manufacturer properties into the schematics (surgical, additive
   only) and emits `<board>/bom/*-bom.csv` + `*-jlcpcb.csv`;
   `common/cpl.py` writes the placement files. The part table is
   `common/lcsc_parts.py`; `--check` fails if anything is stale. Still
   open: generic R/C/jellybean/header numbers. The v0.1.0 release order
   files are superseded; use the v0.2.0 set.
4. Review notes that still hold at order time: manager J3 is the GCT
   USB4105-GF-A (C3020560; JLCPCB assembly stock, backup -120 C5184243);
   13 manager nets cross under the USB pair on B.Cu (fine at full speed).
   Phase-1: C28 sits on U3.20, the VBUS divider (R60/R61/C62) by U10.14,
   every part offset is in `gen_board.py` PLACEMENT, and the VOUT_INT FB
   sense run keeps 5.5 mm or more from SW copper (`tools/fb_reroute.py`).
   Phase-2 bring-up: calibrate NTC_FET against a thermocouple (resume
   section).

**Gates before ordering ANY board — including the fab-ready backplane:**

- **XT60 polarity continuity check** (MECHANICAL.md — verify J1 male vs
  backplane J-female in the *mated* orientation; the footprint descr still
  says pads 1/2 are ASSUMED +/−).
- **Re-verify LCSC stock** of the order-early parts (INA228AQDGSRQ1,
  LTC7004, CSD19536KTT).
- **Manager board only: confirm the fab quotes 0.2 mm drilling** on a 2-layer
  stackup — the board rule was relaxed from 0.3 to 0.2 for the stock ESP32
  footprint's thermal-pad stitching, and that is above some cheapest-process
  quotes.
- Phase-2 audit notes (2026-07-17), all triaged, none blocking: VM-001 on
  CAN_*/DROOP_EN/PS_FPWM/PS_PGOOD/I_MEAS/V_MEAS are false positives
  (VIO-variant / verified V_IH / R31-mitigated / divider-bounded); FS-001
  "FB divider too low-Z" is the injection scheme working as designed; RS-001
  set identical to the audited Phase-1 baseline.

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
  sense amps). Phase-1 (100 × 80) has no AGND pocket: the LTC7004 cluster
  sits below the seam. Never add a via that shorts the domains — the seam
  geometry lives in gen_board.py (`SEAM`, `AUXW`).
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

- **`route_board.py` is not deterministic** (67/68/66 pad-vias on identical
  input). Harmless today, but it breaks the reproducibility contract.
- **Freerouting on the phase-2 board works since 2026-09-27** (1.9.0,
  zone-free DSN, `-oit` bounds the optimizer; see tools/README.md). The
  older failure notes: the KiCad plugin hits the same StackOverflowError. On phase-1 it
  works headless as **1.9.0** under `xvfb-run` with `-Xss64m` (2.x's CLI
  never finished); see phase1-module/tools/README.md. both
  boards' `import_ses.py` now use their own SES parser (KiCad 7's
  `ImportSpecctraSES` takes no board, so it cannot run headless).
- Phase-1 `autoroute.py` is superseded by fanout.py + Freerouting +
  finish_routes.py (the board is routed); kept for reference.
- Phase-1/2 DRC noise is now **silk only** (9 and 11 warnings, cosmetic). The
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
