# MECHANICAL — pre-layout frame (proposed 2026-07-18)

Proposed defaults so the batch layout can start; veto/adjust before board
outlines are drawn. Everything follows from the XT60PW slot decision
(hardware/SOURCING.md).

## Slot pitch: 30 mm

Modules are vertical cards plugging down onto a horizontal backplane.
Pitch is set by the tallest module component + airflow:

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

## Still to fetch before footprints are drawn (land patterns)

XT60PW-M/-F (Amass drawing), MWSA1707S (Sunlord), BVS 3920 bar shunt,
MLT-8530 buzzer. Everything else is stock or already generated.

**Inductor footprint must be a SUPERSET pattern**: pads accepting both the
Sunlord MWSA1707S (17.2×17.2) and Coilcraft XAL1510 (15.2×15.2) land
patterns, so the A/B thermal pair is a pure part swap on the same board
(applies to L1/L3 on phase-2 and L1 on phase-1 — the 10 µH/6.8 µH parts
share the 1707 body; XAL1350 is the P1 alt).
