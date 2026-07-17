# SOURCING — China-market pass (LCSC-first)

Verified 2026-07-18 via the jlcsearch API (LCSC stock + qty-1 USD prices)
and JLCPCB part pages for critical ratings. **Strategy: everything from
LCSC/JLCPCB in one consolidated shipment to Sri Lanka** (LCSC parts +
JLCPCB boards combine into one DHL parcel; modules/AliExpress items noted
separately). Prices move — re-check stock the week of ordering.

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
| INA228AIDGSR | C2887910 | 3.83 | 236 | ×1/module + 1 backplane |
| INA240A3DR | C2060584 | 1.87 | 1.7k | |
| OPA2333AIDGKR | C19608 | 1.14 | 1.3k | |
| TCAN1042VDRQ1 | C485806 | 0.57 | 2.6k | V = VIO variant ✓ (Phase-1 finding) |
| LMR36015ARNXR | C1850345 | 1.91 | 1.2k | |
| NCP1117ST33T3G | C26537 | 0.21 | 14k | |
| LTC7004EMSE#PBF | C690105 | 5.77 | **5** | thinnest stock in the BOM; 3 needed + spares. **Order early** (IMSE $6.98/30 as fallback) |
| TLV7011DCKR | C193688 | 0.27 | 838 | **SC-70-5** — footprint changes from DBVR (SOT-23-5, $0.52, only 42 left) at the PCB pass |
| TL431BIDBZR | C41283 | 0.054 | 7.9k | |
| TS5A3166DBVR | C353035 | 0.28 | 7.6k | replaces TMUX1101 (not stocked on LCSC). **Pin map differs — verify vs TI ds + update gen_phase2 at swap** |
| TCA9535PWR | C130204 | 0.44 | 11k | UMW clone $0.33 acceptable here (non-critical) |
| ESP32-S3-WROOM-1-N8R2 | C2913204 | 5.01 | 18k | |
| TPD2E001DRLR | C150526 | 0.16 | 14k | |
| LM5145RGYR (P1) | C485912 | 1.55 | 5.2k | |
| CSD18563Q5A (P1) | C77239 | 0.85 | 794 | |
| 2N7002 / BAT54W / 1N4148WS / SMBJ33A / AO3401A | — | 0.01–0.05 | ≫10k | jellybeans, any reputable line |

## B. Magnetics & power passives

| Part | LCSC | $ | Stock | Verified rating |
|---|---|---|---|---|
| MWSA1707S-6R8MT ×2 (P2) | C6238332 | 1.72 | 67 | **17 A Irms / 22 A Isat / 7.5 mΩ** (JLCPCB page) |
| XAL1510-682MED ×2 spares | C3911560 | 6.13 | 5 | 36 A Isat (Coilcraft pdf) — A/B test pair |
| MWSA1707S-100MT (P1 10 µH) | C5240401 | 1.68 | 51 | **verify Isat/Irms at order** (needs ≥12 A sat, ≥8 A rms; the 1265S-100MT is REJECTED: 12 A/7.5 A) |
| 7.5 mΩ 1206 1 W 1 % ×4 | C49837985 | 0.025 | 5k | phase-shunt pairs (docs/08 §2) |
| 1.0 mΩ 2512 3 W 1 % ×2 | C46634444 | 0.058 | 27k | output shunt pair; alloy-strip series — check TCR ≤ ±75 ppm on ds; Vishay WSLP upgrade path if cal drifts at bench |
| 1.5 mΩ 2512 3 W 1 % | C49837991 | 0.044 | 4k | LM5069 R_SNS |
| 2 mΩ 2512 3 W 1 % (P1) | C2994640 | 0.060 | 167k | same TCR caveat |
| Bus shunt 0.5 mΩ 3920 ×2 ∥ | C466580 | 0.60 | 2.9k | BVS-M-R0005: 2 in parallel = 0.25 mΩ (0.5 W each @62 A); verify power rating on ds. Alt: ARCS8518 100 µΩ bar $3.64/49 |
| 220 µF 35 V polymer ×4 | C2923769 | 0.28 | 3.1k | Lelon SVZ SMD D8×11.5 — verify ESR ≤ 25 mΩ on ds; Panasonic EEHZK1V221UP hybrid $0.64/1.8k as upgrade |
| 470 µF 50 V bulk | C106666 | 0.10 | 73k | **THT radial D10×20** — cheaper + stronger than SMD; footprint changes at PCB pass |
| 10 µF 50 V X7S 1210 ×8+6 | C126612 | 0.144 | 43k | GCM32EC71H106KA03L; also replaces the 22 µF/50 V output MLCCs (that value barely exists) |
| 8 MHz 3225 crystal | C400090 | 0.105 | 200k | cheap parts are CL=12 pF → **C66/C67 change 10 p→18 p** (HANDOVER-blessed path) — fold into gen at PCB pass |

## C. Connectors & electromechanical

| Part | LCSC | $ | Stock | Use |
|---|---|---|---|---|
| XT60PW-M (Amass) | C98732 | 0.54 | 29k | module power edge + P2 output |
| XT60PW-F (Amass) | C428722 | 0.56 | 8.4k | backplane, ×8 slots |
| 2.54 header/socket strips | — | ~0.05 | ≫100k | slot signal rows, UART/SWD |
| TYPE-C-31-M-12 | C165948 | 0.16 | 336k | manager USB |
| EC11 encoder (generic) | C2831776 | 0.036 | 4.6k | vs Alps $1.99 — generic fine |
| MLT-8530 SMD buzzer | C94599 | 0.18 | 46k | replaces CUI CST-931RP (footprint change at PCB pass; verify 5 V drive on ds) |
| ATO fuse holder | C3207132 | 0.42 | 997 | module 35 A |
| Mini blade holder | C3207114 | 0.64 | 450 | manager 2 A |
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
   above): MWSA1707S-100MT Isat/Irms, BVS power rating, Lelon SVZ ESR,
   alloy-shunt TCR, MLT-8530 drive voltage, TS5A3166 pin map.

## F. Engineering changes queued by this pass (fold in at the batch PCB pass)

Already applied: phase shunts → 2×7m5 1206 (gen_phase2 + docs/08, checkers
green). Queued for the PCB pass: TLV7011 DBVR→DCKR footprint,
TMUX1101→TS5A3166 (pin-map re-verify + gen edit), crystal load caps
10 p→18 p, buzzer CST-931RP→MLT-8530 footprint, 470 µF SMD→THT radial,
22 µF/50 V→10 µF/50 V output MLCCs, XT60PW + 2.54 slot connector footprints
(module io + backplane), bus shunt 2×BVS-M-R0005.
