# MECHANICAL — pre-layout frame (proposed 2026-07-18)

Proposed defaults so the batch layout can start; veto/adjust before board
outlines are drawn. Everything follows from the XT60PW slot decision
(hardware/SOURCING.md).

## Slot pitch: 30 mm

**Server-PSU style insertion** (follows from the right-angle XT60PW):
the backplane stands vertically at the rear, modules are vertical cards
sliding in horizontally from the front; XT60PW-M on each module's rear
edge mates XT60PW-F on the backplane face, signal header rows beside
them (shorter, so power mates first). Pitch is set by the tallest module
component + airflow:

- XAL1510 inductor (the A/B spare) is 11.3 mm tall — the Sunlord 1707 is
  ~8 mm, but the pitch must fit BOTH;
- + 1.6 mm PCB + ~1 mm bottom-side parts + ≥8 mm air channel for
  front-to-back flow + XT60PW-F shroud clearance on the backplane
  → 22 mm minimum, **30 mm chosen** (margin for the Phase-2 heatsink
  clips and hand access).

## Board outlines

| Board | Size | Layers/copper | Notes |
|---|---|---|---|
| phase2-module | **130 × 90 mm** | 4-layer (stackup below) | grows from P1's 120×80 for hot-swap + 4 FETs; XT60PW-M + signal row on the bottom edge (power connector proud by ~2 mm for power-first mating) |
| phase1-module | 120 × 80 mm | 4-layer | unchanged; gets the same bottom-edge connector pair so it can plug the backplane too |
| phase3-backplane | **~330 × 100 mm** | 2-layer 2 oz | 8 × 30 mm slots + end margins + manager header zone; M6 lug bolts at entry; bus rails solder-reinforced |
| phase3-manager | **100 × 80 mm** | 2-layer 1 oz | display module on standoffs above (or panel-mounted via ribbon); encoder/keys wired to panel |

## Stackup / copper (cost-first)

- **Phase-2 module: JLCPCB 4-layer, standard 1 oz outer** (JLC04161H-7628)
  with the 30 A paths carried as both-side pours + via stitching +
  **solder-reinforced bus strips** (mask-opened copper). 2 oz outer adds
  ~$25–45 per lot — decide AFTER the Phase-2 thermal soak, not before;
  the generators keep pour widths parameterized so the swap is cheap.
- **Backplane: 2-layer 2 oz** (modest upcharge on a big simple board) +
  solder-reinforced rails; the 62 A budget current mostly flows lug →
  nearest slots.
- Manager: plain 2-layer 1 oz.

## Land patterns — DONE 2026-07-18 (build_fplib.py `sourcing_footprints`)

All generated into labbench.pretty from vetted LCSC/EasyEDA library pulls:
`XT60PW-M`, `XT60PW-F` (power pads RENUMBERED to 1,2 — the library pull
had the retention legs as 1,2 on the F!), `L_1707_XAL1510` (**superset**
pad 5.39×13.2 @ ±6.405 covering Sunlord MWSA1707S AND Coilcraft XAL1510,
so the A/B thermal pair — and the P1 10 µH — are pure part swaps; stencil
note: paste only the fitted part's terminal zone), `R3920_BVS`, `MLT-8530`.

## ⚠ HARD GATE before submitting gerbers

**XT60 polarity: pads 1=+ on both M and F, and 1↔1 mating, are ASSUMED**
(no Amass drawing was fetchable). When the connector order arrives, mate
an M+F pair and buzz out which M pad connects to which F pad, and which
cavity the shell marks "+". Fix the two footprints/netlists if wrong —
a $1 check that prevents a reversed-bus rack.
