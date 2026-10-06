# SOURCING — China-market pass (LCSC-first)

Verified 2026-07-18 via the jlcsearch API (LCSC stock + qty-1 USD prices)
and JLCPCB part pages for critical ratings. **Strategy: everything from
LCSC/JLCPCB in one consolidated shipment to Sri Lanka** (LCSC parts +
JLCPCB boards combine into one DHL parcel; modules/AliExpress items noted
separately). Prices move — re-check stock the week of ordering. Individual
rows were re-checked and changed later (dated in their notes, latest
2026-10-05); the per-board BOM CSVs are the current source of truth.

The LCSC numbers below are applied to the schematic symbols and the per-board
BOMs by `common/bom.py` (table: `common/lcsc_parts.py`) — change a part there,
then rerun it.

Decisions taken this pass (user-approved 2026-07-18):
- **Inductors:** Sunlord MWSA1707S-6R8MT ($1.72) with the phase shunts
  moved to 3.75 mΩ (2×7.5 mΩ 1206) so the worst-corner current-limit peak
  (21.9 A) fits its 22 A I_sat; two XAL1510-682 spares bought for an A/B
  thermal test at bring-up (docs/08 §2 note). Bourns SRP1265A-6R8M
  **rejected** (I_sat 18 A / Irms 11.5 A — verified, the XAL1350 lesson
  again).
- **Slot connector:** Amass XT60PW pairs (power, 60 A rated) + 2.54 mm
  header/socket row (signals); power-first mating from connector height
  stagger. ~$1.25/slot.

## A. Semiconductors (all phases) — LCSC verified

| Part | LCSC | $ qty-1 | Stock | Note |
|---|---|---|---|---|
| LM5143QRHARQ1 | C5219258 | 2.93 | 52 | automotive variant CHEAPER than LM5143RHAR ($4.62/C5219297); same VQFN-40 6×6 — confirm RHA0040P land vs Q1 addendum at order |
| LM5069MM-2/NOPB | C111822 | 1.17 | 6.6k | |
| CSD18540Q5B (TI) | C86513 | 1.43 | 953 | ×8/module. TOKMAS/“ES” clones at $0.45–0.57 exist — **do not substitute** power-stage FETs |
| CSD19536KTT | C2687963 | 4.94 | **12** | hot-swap pass FET — SOA-critical, no clone. **Order early** |
| STM32G431CBT6 | C529355 | 2.85 | 67k | |
| DAC80502DRXR | C1880990 | 4.19 | 189 | |
| INA228AQDGSRQ1 | C5214669 | 17.16 | 142 | ×1/module + 1 backplane. The AIDGSR (C2887910, $3.83) was out of stock on 2026-09-28; the Q1 grade is pin- and register-identical. Swap back if it returns |
| INA240A3DR | C2060584 | 1.87 | 1.7k | |
| OPA2333AIDGKR | C19608 | 1.14 | 1.3k | |
| TCAN1042VDRQ1 | C485806 | 0.57 | 2.6k | V = VIO variant ✓ (Phase-1 finding) |
| LMR36015ARNXR | C1850345 | 1.91 | 1.2k | |
| NCP1117ST33T3G | C26537 | 0.21 | 14k | |
| LTC7004EMSE#PBF | C690105 | 5.77 | **5** | thinnest stock in the BOM; 3 needed + spares. **Order early** (IMSE $6.98/30 as fallback) |
| TLV7011DCKR | C193688 | 0.27 | 838 | **SC-70-5** instead of DBVR (SOT-23-5, $0.52, only 42 left); the boards carry the SC-70-5 land |
| TL431BIDBZR | C41283 | 0.054 | 7.9k | |
| TS5A3166DBVR | C353035 | 0.28 | 7.6k | replaces TMUX1101 (not stocked on LCSC). Verified + applied 2026-07-18 (§F) |
| TCA9535PWR | C130204 | 0.44 | 11k | UMW clone $0.33 acceptable here (non-critical) |
| ESP32-S3-WROOM-1-N8R2 | C2913204 | 5.01 | 18k | |
| TPD2E001DRLR | C150526 | 0.16 | 14k | |
| LM5145RGYR (P1) | C485912 | 1.55 | 5.2k | |
| CSD18563Q5A (P1) | C77239 | 0.85 | 794 | out of stock 2026-09-27: the P1 BOM orders onsemi NTMFS5C670NLT1G (C179626, $0.49) for Q1–Q4 instead, same S-S-S-G / tab pinout. Still a `CHECK:` row: confirm the pad overlay in the JLCPCB preview |
| 2N7002 / BAT54W / 1N4148WS / SMBJ33A / AO3401A | — | 0.01–0.05 | ≫10k | jellybeans, any reputable line |

## B. Magnetics & power passives

| Part | LCSC | $ | Stock | Verified rating |
|---|---|---|---|---|
| MWSA1707S-6R8MT ×2 (P2) | C6238332 | 1.72 | 67 | **17 A Irms / 22 A Isat / 7.5 mΩ** (JLCPCB page) |
| XAL1510-682MED ×2 spares | C3911560 | 6.13 | 5 | 36 A Isat (Coilcraft pdf) — A/B test pair |
| MWSA1707S-100MT (P1 10 µH) | C5240401 | 1.68 | 51 | **verified: 16.5 A Isat / 10.5 A Irms / 9.9 mΩ ✓** (1265S-100MT REJECTED: 12 A/7.5 A) |
| 7.5 mΩ 1206 1 W 1 % ×4 | C49837985 | 0.025 | 5k | phase-shunt pairs (docs/08 §2) |
| 1.0 mΩ 2512 3 W 1 % ×2 | C46634444 | 0.058 | 27k | output shunt pair; alloy-strip series — check TCR ≤ ±75 ppm on ds; Vishay WSLP upgrade path if cal drifts at bench |
| 1.5 mΩ 2512 3 W 1 % | C49837991 | 0.044 | 4k | LM5069 R_SNS |
| 2 mΩ 2512 3 W 1 % (P1) | C2994640 | 0.060 | 167k | same TCR caveat |
| Bus shunt 0.5 mΩ 3920 ×2 ∥ | C466580 | 0.60 | 2.9k | BVS-M-R0005: 2 in parallel = 0.25 mΩ (0.5 W each @62 A); verify power rating on ds. Alt: ARCS8518 100 µΩ bar $3.64/49 |
| 220 µF 35 V hybrid ×4 | C454349 | 1.42 | **1** | Panasonic EEHZA1V221P D10×10.2, 20 mΩ / 2.5 A — fits the CP_Elec_10x10.5 land. Stocked alternative on the same land: SUNCON 35HVH220M+P (C179812, D10×12.5, 8 in stock 2026-09-28). The earlier D8 SVZ pick (C2923769) did not fit the land and is out of stock |
| 470 µF 50 V bulk | C106666 | 0.10 | 73k | **THT radial D10×20** — cheaper + stronger than SMD; phase-2 C14 carries the CP_Radial_D10 land |
| 470 µF 50 V SMD (backplane C2) | C462700 | 1.63 | 633 (JLCPCB) | Nichicon UCX1H471MNS1MS, 16×16.5, 70 mΩ, 1.0 A @100 kHz, 135 °C. The board has an SMD CP_Elec_16x17.5 land (17×17 platform), not the THT D10 above; 16×16.5 cans fit it. Fallback: Panasonic EEEFK1H471AM (C178551, 131). Picked 2026-10-05 |
| 33 µH aux-buck inductor (manager L2) | C167973 | 0.06 | 51k (JLCPCB) | cjiang FNR5040S330MT, 5×5×4 mm: **Isat 1.30 A min / Irms 1.20 A min / DCR 0.244 Ω max** (cjiang FNR datasheet). No 1210 33 µH is stocked above 0.5 A, so the manager land grew to L_Changjiang_FNR5040S (2026-10-05). Phase-1/2 L2 are still 1210: see the next row |
| 33 µH 1210 (phase-1 L2) | C223226 | 0.25 | — | Taiyo Yuden CBC3225T330KR, 0.5 A: the strongest stocked 1210 33 µH, against a 1.2 A value. A BOM `CHECK:` row (fine only if 5V0 stays well under ~0.4 A). Phase-2 L2 has no number yet. Moving both to the manager's 5×5 land is offered and waits on the owner |
| 10 µF 50 V X7S 1210 ×8+6 | C126612 | 0.144 | 43k | GCM32EC71H106KA03L; also replaces the 22 µF/50 V output MLCCs (that value barely exists) |
| 8 MHz 3225 crystal | C400090 | 0.105 | 200k | cheap parts are CL=12 pF → C66/C67 = 18 p (APPLIED, both phases) |

## C. Connectors & electromechanical

| Part | LCSC | $ | Stock | Use |
|---|---|---|---|---|
| XT60PW-M (Amass) | C98732 | 0.54 | 29k | module power edge + P2 output |
| XT60PW-F (Amass) | C428722 | 0.56 | 8.4k | backplane, ×8 slots |
| 2.54 header/socket strips | — | ~0.05 | ≫100k | slot signal rows, UART/SWD |
| GCT USB4105-GF-A | C3020560 | 1.30 | 1.1k at JLCPCB | manager USB (J3). 2026-09-28: matches the routed land. LCSC retail shows 0, JLCPCB assembly stock holds it; backup USB4105-GF-A-120 C5184243 (4.7k). The cheaper TYPE-C-31-M-12 C165948 has longer pads and would need the J3 breakout re-routed |
| EC11E encoder with switch (Alps EC11E18244A5) | C255515 | 2.40 | 766 | 2026-09-27: the old "generic EC11" C2831776 was really a 100 µF/50 V electrolytic; no generic EC11 with switch is listed |
| YX-SMD8530P SMD buzzer (Yuexin) | C781886 | 0.39 | 368 | 2026-09-27: replaces MLT-8530 C94599, which is rated 2.5–4.5 V but runs from 5V0; same vendor land, pad 1 (+) in the same corner |
| ATO fuse holder | C3207132 | 0.42 | 997 | module 35 A |
| 2 A MINI blade fuse (Littelfuse 0297002.WXNV) | C151091 | 0.11 | 5.9k | manager F1, soldered directly into the Fuse_Blade_Mini_directSolder land. 2026-09-27: replaces C3207114, which is a 6.35 mm cylindrical clip, not a mini-blade holder |
| 2EDG 5.08 plugs (P1 bench IO) | C3697 | 0.04 | 103k | |
| ILI9341+XPT2046 2.8" module | — | ~5 | — | AliExpress/Taobao (not LCSC); confirm 3V3-VCC jumper before soldering |
| E-stop NC mushroom, M6 lugs, standoffs | — | ~3 | — | AliExpress/hardware store |

## D. Per-board part totals (qty-1 prices, ex-PCB, USD)

| Board | Semis | Passives/EM | Total parts |
|---|---|---|---|
| Phase-1 module | ~29 | ~16 | **~45** |
| Phase-2 module | ~39 | ~13 | **~52** |
| Backplane (2 slots populated) | ~4 | ~6 | **~10** |
| Manager (incl. display) | ~9 | ~10 | **~19** |
| Phase-3 build (2× P2 + BP + MGR) | | | **~135** |

PCBs (JLCPCB, ×5 each): P1 4-layer ~$35; P2 4-layer + 2 oz outer ~$50–70
(the 2 oz/stackup call is still open — docs pre-PCB checklist); backplane
2-layer 2 oz ~$30–50 (size TBD by slot pitch); manager 2-layer ~$10.
Shipping LCSC+JLCPCB consolidated to Sri Lanka ≈ $25–40 DHL; customs on
the LKR side is the user's local knowledge. **Realistic Phase-3 all-in:
US$300–380** including boards, spares and the Coilcraft A/B pair.

## E. Order-early / risk list

1. **LTC7004EMSE — 5 in stock.** 3 boards need 3 + spares. First thing in
   the cart, or accept IMSE ($6.98, 30 pcs).
2. **CSD19536KTT — 12 in stock.** SOA-verified hot-swap FET, no substitute
   without redoing the SOA math.
3. LM5143QRHARQ1 (52) and MWSA1707S-6R8MT (67) — fine for this build,
   thin for a rebuy; recheck at order time.
4. Clones: FET clones rejected for the power path; UMW TCA9535 and generic
   EC11/2N7002/diodes accepted.
5. Ratings still to verify from datasheets **at order time** (flagged
   above): BVS power rating,
   alloy-shunt TCR, TS5A3166 pin map. (MLT-8530 drive voltage: resolved
   2026-09-27 by the 5 V-rated YX-SMD8530P.)

## F. Engineering changes from this pass — APPLIED 2026-07-18

All schematic-level changes are in the generators, all four checker chains
green (137/173/30/80 components):
- phase shunts → 2×7m5 1206 parallel (gen_phase2 + docs/08)
- TMUX1101 → **TS5A3166DBVR** (ts5a3166.pdf verified: 1=NO 2=COM 3=GND
  4=IN 5=V+ — pin POSITIONS identical to TMUX1101, symbol-only swap;
  VIH 2.4 V ≤ 3.3 V GPIO ✓)
- TLV7011 DBVR → **DCKR** (tlv7022.pdf: DBV and DCK share one pinout —
  footprint-only, SOT-353_SC-70-5; applies to Phase 1 AND 2)
- crystal load caps 10 p → **18 p** for CL=12 pF China crystals (both phases)
- Phase-1 inductor → **MWSA1707S-100MT** (JLCPCB-verified 16.5 A Isat /
  10.5 A Irms / 9.9 mΩ ✓ vs 12 A/8 A required; MWSA1265S-100MT REJECTED)
- 470 µF bulk → THT radial D10; output MLCCs 22 µF→10 µF/50 V X7S
- module slot power + P2 output → XT60PW-M (2-pin); backplane slots →
  XT60PW-F; bus shunt → 2× BVS-M-R0005 parallel
- buzzer value → MLT-8530 (since replaced by the 5 V-rated YX-SMD8530P, §C)

The placeholder footprints for XT60PW, MWSA1707S (17.2×17.2), BVS 3920 and
MLT-8530 were replaced by vendor-drawing land patterns in the footprint pass
(commit d281f94; `labbench.pretty`).
