# Parts to download — symbols & datasheets

> **Status 2026-07-14 (evening):** everything downloaded and verified.
> Section-A symbols merged; section-B datasheets checked — DAC80502 straps
> verified (SPI2C low = SPI, RSTSEL low = zero-code), LMR36015AQRNXRQ1 symbol
> vetted and merged (needed for aux-rails). Two package corrections landed:
> DAC80502 = WSON-10 only, LMR36015 = VQFN-HR-12. No open verification items.

## How to fetch (Mouser)

On each Mouser part page: **ECAD Model → Download → format "KiCad"** (served via
Ultra Librarian / SnapMagic). Drop the downloaded ZIPs (or extracted
`.kicad_sym` / `.kicad_mod` files) into `hardware/phase1-module/lib/vendor/` —
no need to unpack or rename carefully, Claude will extract, review each pin map
against the datasheet, and merge the good symbols into `lib/labbench.kicad_sym`
(the project library is already registered in `sym-lib-table`).

Datasheet PDFs go into `docs/datasheets/` (gitignored — copyrighted, so they
stay local and off GitHub).

## A. Symbols + datasheets needed (not in KiCad's official library)

| # | Orderable part | Package | Role | Notes |
|---|---|---|---|---|
| 1 | **LM5145RGYR** (TI) | VQFN-20 3.5×4.5 | Phase-1 buck controller | The critical one. Datasheet also needed for RT/ILIM equations, SS/TRK behaviour, min on-time |
| 2 | **TCAN1042HGVDR** (TI) | SOIC-8 | CAN transceiver, 5 V bus drive + 3.3 V VIO | "H G V" suffixes matter (VIO variant). DRB (VSON-8) also fine if stock is better |
| 3 | **INA228AIDGSR** (TI) | VSSOP-10 | Precision V/I telemetry | Datasheet also for ADCRANGE + SHUNT_CAL math (firmware) |
| 4 | **TLV7011DBVR** (TI) | SOT-23-5 | Hardware OVP comparator | Tiny, easy — symbol optional (5 pins), datasheet is the point |
| 5 | **LTC7004EMSE#TRPBF** (ADI) | MSOP-10 (MSE, exposed pad = pin 11, GND) | Output-disconnect high-side gate driver | Earlier revision of this file said MSOP-8 — wrong; datasheet confirms 10-lead |

## B. Datasheets only (symbol already in KiCad's official library)

Exact orderable variants — suffixes matter. Datasheets are per-family; search
by the family name shown in the datasheet column.

| Exact orderable | Package | Datasheet (family) | Verify from it |
|---|---|---|---|
| **DAC80502DRXT/R** (TI) | **WSON-10 (DRX)** — dual comes in WSON only; the earlier VSSOP/DGS claim here applied to the single-channel DAC80501 | "DACx0502" | ✅ verified: SPI2C **low = SPI** (§8.5.1); RSTSEL **low = zero-code POR**; keep DAC IOVDD ≤ VDD (both 3V3 here) |
| **OPA2333AIDGKR** (TI) | VSSOP-8 (DGK) | "OPAx333" | Standard dual-opamp pinout; CM range includes both rails; 5.5 V abs-max supply — **replaces OPA2189**, whose input CM stops 2.5 V below V+ (broken on our 5 V rail at 2.5 V full-scale) |
| **INA240A3DR** (TI) | SOIC-8 (D) | "INA240" (covers A1–A4 gains) | A3 = gain 100; REF1/REF2 → GND for unidirectional; −4…80 V CM |
| **LMR36015AQRNXRQ1** (TI) | **VQFN-HR-12 (RNX)** — the HSOIC-8/DDA claim here was wrong (that's the LMR33630) | "LMR36015-Q1" | ✅ verified: pin map matches vendor symbol; A**Q**…Q1 = adjustable, 400 kHz, non-FPWM — the right variant for 24 V→5 V aux. Replaces TPS54202 (28 V V_IN max) |
| **STM32G431CBT6** (ST) | LQFP-48 | STM32G431x6/x8/xB datasheet | C=48 pins, B=128 KB flash, T=LQFP, 6=−40…85 °C; has FDCAN ✓. Also grab **RM0440** (STM32G4 reference manual) and the STM32G431 errata sheet |
| **BAT54W** (any: Nexperia BAT54W,115 / onsemi BAT54WT1G / Diodes BAT54W-7-F) | SC-70 / SOT-323 | vendor BAT54W | 30 V, 200 mA Schottky; pin 1 = A, pin 2 = NC, pin 3 = K (already verified against the KiCad symbol) |

Substitution warnings: **BAT54** (no W) is SOT-23 with a different footprint;
**BAT54A/C/S** are duals in various topologies — only plain **-W** fits our
footprint and single-diode role. **STM32G431CBU6** (UFQFPN-48) is an acceptable
substitute for the T6 if stock demands, footprint changes. For the DAC, any
**DAC80502…DGS** variant works (the letter between 80502 and DGS is a grade
code); WSON-package variants do NOT match our footprint — stick to VSSOP-10
(DGS).

## C. Phase 2 — defer (don't download yet)

LM5143 (2-phase controller), LM5069 (hot-swap). (Phase-1 power FETs moved to
section D — they are needed now.)

## D. Footprint pass — parts finalized 2026-07-15

Footprints live in `lib/labbench.pretty/` (built by `tools/build_fplib.py`
from the vetted vendor drops + one generated pattern). New/changed orderables:

| Qty | Orderable part | Package / footprint | Role |
|---|---|---|---|
| 4 | **CSD18563Q5A** (TI) | SON 5×6 → `labbench:PowerFET_SON5x6_GDS` (generated from SLPS444C §7.2; pads renumbered 1=G 2=D 3=S for the generic symbol) | Q1/Q2 half-bridge, Q3/Q4 output disconnect |
| 1 | **XAL1350-103ME_** (Coilcraft; suffix B/C/D = packaging) | 13×13 flat-wire → official `L_Coilcraft_XAL1350-XXX` | L1 main inductor, 10 µH / Isat ≈ 18 A @ 30 % drop, DCR ≈ 8.7 mΩ (Coilcraft Doc373 selector — earlier "28 A" here was wrong; 18 A still clears the ~14 A peak at valley ILIM) |
| 4 | 22 µF 50 V X7R 1210 (e.g. Murata GRM32EC72A226KE05) | C_1210 | input bank C20/C75–C77 |
| 1 | 220 µF 50 V SMD electrolytic (e.g. Panasonic EEE-FK1H221AM, Ø10×10.2) | CP_Elec_10x10.5 | input bulk C21 |
| 2 | 220 µF 25 V polymer (e.g. Panasonic 25SVPF220M OS-CON, Ø8×11.9) | CP_Elec_8x11.9 | output bulk C22/C78 |
| 4 | 22 µF 25 V X7R 1210 | C_1210 | output bank C23/C79–C81 |
| 1 | 2.2 kΩ 1 W 2512 | R_2512 | R27 preload (was on a 0402 — fixed) |

Crystal note (from ngspice run 2026-07-15): C66/C67 = 10 pF target **CL ≈ 8 pF**
— order the 8 MHz crystal as a CL = 8 pF part (e.g. Abracon ABM8 series -8-…),
or change C66/C67 to 18 pF for a CL = 12 pF crystal.

Notes from the pass: default passives moved 0402 → **0603** (hand assembly);
DAC80502 now uses the vendor WSON-10 footprint (DRX has **no** exposed pad —
the official `WSON-10-1EP` was wrong for it); crystal symbol switched to
`Crystal_GND24` so the 3225's shield pads are grounded; bulk-cap banks are now
one schematic component per physical capacitor. `tools/check_footprints.py`
verifies every component's footprint resolves and every netted pin has a pad.

## E. Pricing snapshot — verified 2026-07-16 (LCSC via jlcsearch, qty 1–10 USD)

| Part | Unit $ | Stock | Note |
|---|---|---|---|
| LTC7004EMSE#PBF | 5.77 | **5** | priciest IC, thin stock — order early or Mouser (~1.5×) |
| DAC80502DRXR/T | 4.19/4.68 | 189/53 | |
| INA228AIDGSR | 3.83 | 236 | |
| STM32G431CBT6 | 2.85 | 67k | |
| LMR36015ARNXR | 1.91 | 1.2k | non-Q1 "A" variant OK (adjustable) |
| INA240A3DR | 1.87 | 1.7k | |
| LM5145RGYR | 1.55 | 5.2k | |
| OPA2333AIDGKR | 1.14 | 1.3k | |
| CSD18563Q5A ×4 | 0.85 | 794 | |
| TLV7011DBVR | 0.52 | **42** | |
| TCAN1042VDRQ1 | 0.57 | 2.5k | V-suffix = VIO variant, OK at 500k (HGV from Mouser also fine) |
| NCP1117ST33T3G | 0.21 | 14k | |
| 220 µF/25 V polymer | 0.13–0.17 | 10k | |
| 2 mΩ 2512 shunt | — | — | buy the Vishay WSLP (~$1.50, Mouser): TCR owns the CC spec |
| XAL1350-103 | ~5–6 (Mouser) | — | not on LCSC; Sunlord MWSA1265S-100MT $0.69 is a budget candidate **only after** verifying Isat ≥ 15 A from its datasheet |

Totals: semiconductors ≈ **$29**; all components for one module ≈ **$45–50**
(LCSC-heavy) or ~$75 all-Mouser; JLCPCB 4-layer 120×80 ×5 ≈ $30–45; with
stencil + shipping the complete Phase-1 build lands ≈ **US$100–125**.

## Quality warning

Vendor ECAD symbols are frequently sloppy (odd pin ordering, wrong units,
ugly graphics). That's fine here: the generator connects by pin number/name
read from the symbol file, and `check_netlist.py` verifies every net after
generation — but each symbol's pin map still gets a manual check against its
datasheet before first use. Do not trust a vendor symbol that hasn't been
diffed against the datasheet pinout table.
