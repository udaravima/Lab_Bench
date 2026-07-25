# Session Handover — Lab_Bench modular PSU

Written 2026-07-16, updated 2026-07-25 for the next agent (or future session)
continuing this project. Read this + README.md before touching anything.
**Start with the "Phase-2 PCB layout — resume point" section below** — that is
the live work front.

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
| PCB — Phase 1 | Committed board = clean pass-1 (placement + pours + planes + critical routes, 0 copper DRC); `autoroute.py` is WIP (33 unconnected, notes in its header) |
| PCB — Phase 2 | **IN PROGRESS (2026-07-25, committed 27fb2d1).** `gen_board.py` placement green (173 comps, all pour/courtyard/edge assertions pass, 130×90 4-layer); `route_board.py` pass-1 done (power pours, In2 heat patches, both phases' gate fan-outs, Kelvin pairs, disconnect trunk). DRC: **copper down to ~19 clearance + ~11 dangling/mask/hole in 3 known clusters** (see resume section); 243 unconnected = signal nets, autoroute not yet run. Found & fixed a real LM5143 land-pattern bug in the process (see load-bearing decisions) |
| PCB — Phase 3 backplane | **COMPLETE pass-1 (2026-07-25)**: `phase3-backplane/tools/gen_board.py` (single-script: placement + 2oz bus pours + stitching + ALL signal routing) — **0 copper DRC, 0 unconnected**; only lib-bookkeeping (39) + 1 silk nick remain. 8 slots @30mm (XT60PW-F rot-90 mates the module pad-for-pad, socket y60..77.8 = module J5 1:1), M6 lugs -> RS1‖RS2 0.5mΩ Kelvin-sensed by INA228, nested PRESENT L-bus, CAN terminated past both end slots, E-stop chain threaded per docs. Netlist from `tools/wip/bp.net` (regenerate via kicad-cli) |
| PCB — Phase 3 manager | not started (100×80 2L, 80 comps) |
| Module firmware | v0.1 builds clean (6.3 KB): full peripheral binding + CAN dispatch around the host-tested `module_core`. Untested on silicon (no board yet) |
| Host tests | `cd firmware/tests && make test` — must stay green |
| Manager firmware | not started |
| Phase-2 circuit design | **complete (docs/08, 2026-07-16)**: all values worked + datasheet-verified; LM5143/LM5069/CSD18540Q5B/CSD19536KTT/XAL1510/TMUX1101/TL431 PDFs now in docs/datasheets/ |
| Phase-2 schematic | **complete, v1, audited (2026-07-17)**: 8 sheets, 171 components, 116 nets machine-verified; kicad-happy audit triaged (all errors = known false-positive classes or the deferred MPN pass — same baseline as Phase-1); ngspice **45/47 pass** (crystal warn + bridge skip = same model limitations as Phase-1's 38/40) |
| Phase-3 schematics | **complete, v1, audited (2026-07-17)**: backplane (29 comps, EXACT net assertions) + manager (80 comps) — audit caught a real omission (manager I²C pull-ups specified in docs/09 but not drawn; fixed, PR-001 clear). SPICE: manager 16/16, backplane 3/3. Backplane "missing I²C pull-up" findings = by design (manager owns them) |
| Manager firmware | **core v0.1 host-tested (2026-07-18)**: manager_core (discovery, #15 supervision, docs/03 §3 ack/retry, #17 budget arbiter, §7 charge sequencer) green in firmware/tests; ESP-IDF shell committed as an UNBUILT skeleton (no IDF toolchain here — UI/SCPI are TODO stubs) |
| Ordering/BOM | **China-first sourcing pass done (hardware/SOURCING.md, 2026-07-18)**: LCSC prices/stock verified for all phases (~$135 parts for the Phase-3 build, ~$300–380 all-in); inductor + slot-connector decisions taken (Sunlord + 3.75 mΩ shunts APPLIED to gen_phase2; XT60PW slots queued); order-early list: LTC7004 (5 pcs), CSD19536KTT (12 pcs). MPN-properties pass into symbols still pending |

## Phase-2 PCB layout — resume point (LIVE, 2026-07-25)

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
unconnected = the signal nets.** `tools/autoroute.py` is WRITTEN (phase-1's
router with its header fix-list applied: net-independent via hole spacing,
plane targets from the in1/in2 maps, 0.125mm grid after a quantization
failure at 0.25 — the U3/C28 escape lane is only 0.185mm wide). First 0.25mm
run: 262 routed / 70 failed (fine-pitch escapes). The 0.125 run is SLOW
(~30+ min: the per-net plane-map scans in main() want optimizing — invert
in1/in2 maps to net->cells ONCE instead of scanning 750k cells per net).
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

1. **Finish Phase-2 board** — clear the 3 copper clusters above, then
   autoroute the signal nets, then silk cleanup + PGND-island recheck
   (PS-002) + gerbers + analyzer. Then repeat the pipeline for the phase-3
   backplane (330×100 2L 2oz bus bars) and manager (100×80 2L), and the
   MPN-properties pass → BOM CSVs → order files.
   **Gates before gerber submission**: XT60 polarity continuity check
   (MECHANICAL.md — verify J1 male vs backplane J-female in the *mated*
   orientation; the footprint descr still says pads 1/2 are ASSUMED +/−),
   re-verify LCSC stock of the order-early parts (LTC7004, CSD19536KTT).
   Phase-2 audit notes (2026-07-17): VM-001 on CAN_*/DROOP_EN/PS_FPWM/
   PS_PGOOD/I_MEAS/V_MEAS all false positives (VIO-variant / verified
   V_IH / R31-mitigated / divider-bounded); FS-001 "FB divider too low-Z"
   is the injection scheme working as designed; RS-001 set identical to
   the audited Phase-1 baseline.
2. **Phase-3 backplane + ESP32-S3 manager schematics** (bus bars, slot IDs,
   CAN termination, E-stop; manager board with display/encoder/USB).
3. **ESP32-S3 manager firmware** (discovery, UI, SCPI, budget arbiter,
   charge sequencer) — reuses `firmware/common/labbench_can.h` verbatim.
4. Then the batch PCB pass: finish `autoroute.py` (fix list in its header),
   silk cleanup, PGND-island recheck (audit PS-002 expects resolution after
   routing), gerbers + gerber analyzer, MPN pass → BOM CSVs → order files.

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

- `autoroute.py`: 33 unconnected, router-via self-spacing bug, congested
  U3/U10 escapes — its header has the fix list. Deferred with the PCB work.
- DRC noise on the committed board: `lib_footprint_issues` (board-vs-library
  bookkeeping, harmless) and ~75 silk overlaps (cosmetic, clean up in the
  PCB batch).
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
