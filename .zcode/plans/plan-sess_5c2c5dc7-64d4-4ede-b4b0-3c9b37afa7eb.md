Route the 83 remaining phase-2 connections deliberately — every net hand-planned as explicit waypoints, nothing blind.

## Where we are (verified)
- Board = HEAD (fcf72bb), byte-identical. Fresh facts: 1512 tracks, 359 vias, 44 zones; 0 copper DRC, 11 silk warnings, 83 unconnected. Layer plan: F.Cu components+power pours, In1 PGND/AGND planes split at PCB y=87.3 (SEAM) with two AGND pockets, In2 logic-power patches, B.Cu ground mirror + signal.
- Exact split of the 83: **U3 control cluster 19** (pocket-local hops + long control runs), **U10 STM32 cluster 15** (escapes + digital fan-out), **scattered 14** (AUX_BOOT, DISC_INP, VBUS_P, V_REF, V_MEAS 3rd, SW1 zone), **plane stitching 35** (AGND 16, 5V0 9, PGND 7 zone-islands, 3V3 3).
- `route_board.py` is the declarative pattern to extend: `(net, layer, width, waypoints)` TRACKS + `(net,x,y)` VIAS with `too_close()`/`stub_hits_pad()` clearance gates. `autoroute.py` exposes importable `build_grid`/`route_net` (pocket costs + entry-stub fixes already in) for the agreed per-net fallback. `run_drc.py` always exits 0 — parse stdout.

## Steps

**0. Baseline + structure map.** Re-run `run_drc.py` for a fresh report; parse all 83 `[unconnected_items]` into a table and join with `wip/p2.net` pinlists so each net's full connectivity goal is known (an item between two track-ends may still leave a third pad dangling). Classify into the four groups above. This map drives everything.

**1. Write `tools/finish_routes.py`** — new additive-only script in route_board's style (imports ORG/P/point_in_poly from gen_board; carries its own copies of too_close/stub_hits_pad/add_via/add_track since route_board's are nested in main()). Groups as CLI-selectable batches: `--group u3_local|u3_long|u10|long_haul|scattered|stitch`. It loads the committed board, applies only the selected group's copper, refills zones, saves. Never re-run gen_board/route_board/autoroute on this board — they re-add copper non-idempotently.

**2. Route in batches, hardest-constrained first, each batch DRC-verified then committed by the user:**
   1. Fine-pitch escapes (position-constrained): U3 top/left pin rows (PS_VDDA/VCC/COMP/RES/DITH, FB, PS_VIN, VOUT_INT ties) and U10 QFP escapes (I2C, CAN, DAC, NTC, SWCLK, SLOT_ID, V_MEAS, I_MEAS, HW_EN, AUX_PG, INA_ALERT). A* per-net fallback allowed here for stuck escapes, result reviewed.
   2. Long-haul lanes (freedom to plan): PS_EN/FPWM/PGOOD U3→MCU; EAV_INJ/EAI_INJ D1/D2 (x≈69,y≈92/101) → R5/R8 (x≈106/109,y≈52) crossing the seam region on planned vertical lanes; CAN_RX/TX/STB U11 (x≈35)↔U10; SLOT_ID0-2 J5↔U10; DISC_INP U6→trunk; V_MEAS 3-node trunk; I_MEAS. Lane map documented in the script header (B.Cu/In2 vertical x-lanes in the analog region), crossings avoided by construction like route_board's corridor plan.
   3. Scattered locals: AUX_BOOT, VBUS_P on U8, V_REF, 5V0 local ties (U13/U7/R47/R22/R20/C43/C33).
   4. Plane stitching LAST (island geometry moves with every copper change — PS-002): AGND fragment ties, 3V3, 5V0 trunks, the 6 PGND zone-island stitches; every stitch via verified on the correct side of SEAM y=87.3 (wrong side = AGND/PGND short), then re-check with `check_planes.py`.

**3. Verification protocol per batch:** backup board to `tools/wip/`, run the batch, `run_drc.py` — unconnected must drop by exactly the batch's count and copper violations stay 0; render the touched region (`kicad-cli export svg`) and review geometry against LAYOUT.md rules (FB shortest copper, gate drives via-free, Kelvin pairs intact). Roll back via `git checkout` if a run misbehaves. After all copper: `silk_refs.py` → `check_planes.py` → final `run_drc.py`; independent check via `layout_qa.unconnected() == 0`; then `finish_board.py --silk --planes --fab` (its unconnected>0 refusal is the done gate). Ordering the fab stays gated on the user's XT60 polarity buzz-out — out of scope here.

**4. Commits:** stop and summarize after each verified batch for your per-commit approval, per the working agreement. No push, ever.