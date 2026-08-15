# Phase-2 manual routing work order — for interactive KiCad sessions

Board state: **81 unconnected, 0 copper-clearance DRC** (commit 5974056).
Route these by hand in KiCad's push-and-shove; every wall below was
proven at 0.2 mm clearance (pads carrying 0.25 overrides are noted).

Track 0.25 / via 0.6-0.3 works everywhere EXCEPT the sealed strips
called out below. KiCad's shove will do in seconds what the scripted
router couldn't: it moves copper out of the way instead of routing
around frozen junk.

## Pocket items (~10) — the hard core

The AGND pocket (x69-98, y31-41) is dense with autorouter junk. Known
walls — don't fight them, shove them:

1. **PS_RT tail**: connect the (86.12,23.88) via cluster (north run,
   still intact) to R26.1 (83.4,36.5). The y35.6/y37.4 walls are
   DELETED (this session); R26.1's north is walled by PS_SS's
   y37.4/y38.0 escape — approach R26.1 from the south or west.
2. **PS_VDDA**: U3 pads 34+36 (top row, y32.1) to C21.1 (86.5,36.5) to
   R39.2 (91.2,36.5). Top row is sealed north by the RT staircase +
   the cap at (76.0,30.5) — easiest: shove the RT staircase north
   0.3 mm to open the y31.4 lane (RT is a timing resistor, length
   doesn't matter), then run VDDA over the top.
3. **PS_RES**: U3.32 (77.8,32.1) → C19.1 (89.6,34.5). Same top-row
   seal; same shove helps.
4. **PS_FPWM**: U3.33 (77.3,32.1) → trunk stub (84.2,75.2). Escape
   north is sealed; consider B.Cu via just west of the PH_CS_B stub.
5. **PS_VIN**: U3.25 (78.9,35.2) → stub (77.2,29.9). The G_HS_A dive
   (79.5-80.3, y35.5+) blocks the corner; a small shove of that dive
   opens it.
6. **PS_PGOOD**: U3.24 (78.9,35.8) → trunk (77.9,72.0). Same corner.
7. **FB**: U3.28 (78.9,33.8) → FB spine (83.4-87.3, y33.5). The via
   at (81.05,34.05) + R1 pads wall the direct lane; shove R1 north or
   drop to B.Cu north of the SS stub (y32.7 lane is legal).
8. **VOUT_INT pin 5** (73.1,34.8) → zone edge x79: PS_SS's y32.75
   stub seals the under-body band; shove it 0.3 south, or via down
   beside the pad.
9. **PS_VCC**: C23.1 (77.9,39.8) → C22.1 (72.9,39.8). BST_B stub +
   pin-11 keepout overlap blocks every horizontal lane y36.9-40.7 —
   shove the BST_B stub (73.75, 37.9-39.6) west/south 0.5 mm and the
   straight row run opens.
10. **PS_COMP**: pin 29 stub (78.0-78.6, y33.25) + pin 2 stub (74,34.5)
    → C25.1 (83.4,34.6) + R24.1 (86.5,34.6). FB spine y33.5 + COMP_Z
    y33.6 wall east-west — go south of C25 row (y35.6 lane is legal)
    or shove the spine.

## U10 cluster (~20) — mechanical, not hard

Escapes MUST run straight out along each pad's long axis and turn
OUTSIDE the pad-shadow strips: west of x77.2 / east of x79.1 (right
row, pins 25-36 face east), west of x69.8 (left row 1-12), north of
y73.0 (top 37-48), south of y82.9 (bottom 13-24). Between-pad gaps
(0.20 mm) admit nothing. Suggested trunks: y74.0 north, y82.5-83.6
south, then the B.Cu analog corridors y68.5-69.3 / y71.25-71.9 for the
long hauls west (CAN, DAC, SLOT_ID, V_MEAS).

## What I'll script AFTER your manual pass (copper must freeze first)

Long-haul trunks (EAV/EAI injections, DISC_INP, I_MEAS, INA_ALERT
east side), 5V0 ties, then plane stitching LAST, then silk pass +
zone priorities + gerbers. Each scripted batch: validate → apply →
DRC → commit, per the working agreement.
