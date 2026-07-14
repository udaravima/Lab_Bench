# Parts to download — symbols & datasheets

> **Status 2026-07-14:** all five section-A symbols downloaded, pin maps
> diffed against datasheets (zero errors), and merged into
> `lib/labbench.kicad_sym` by `tools/merge_vendor.py`. Section-B datasheets
> still wanted — most importantly **DAC80502** (SPI2C strap must be verified
> before ordering).

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
| **DAC80502MDGSR** (TI) | VSSOP-10 (DGS) | "DAC80501/DAC80502" | SPI2C strap level for SPI mode; REFIO cap; power-on zero-scale; VDD 3.3 V logic thresholds |
| **OPA2333AIDGKR** (TI) | VSSOP-8 (DGK) | "OPAx333" | Standard dual-opamp pinout; CM range includes both rails; 5.5 V abs-max supply — **replaces OPA2189**, whose input CM stops 2.5 V below V+ (broken on our 5 V rail at 2.5 V full-scale) |
| **INA240A3DR** (TI) | SOIC-8 (D) | "INA240" (covers A1–A4 gains) | A3 = gain 100; REF1/REF2 → GND for unidirectional; −4…80 V CM |
| **LMR36015ADDAR** (TI) | HSOIC-8 (DDA) | "LMR36015" | 4.2–60 V in, 1.5 A sync buck — **replaces TPS54202**, whose 28 V V_IN(max) is inside our 24–30 V bus spec. Confirm exact suffix on the order page (adjustable-output, non-Q1 is fine) |
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

LM5143 (2-phase controller), LM5069 (hot-swap), power FETs (CSD18563Q5A or
equivalent — final selection happens after Phase-1 thermals).

## Quality warning

Vendor ECAD symbols are frequently sloppy (odd pin ordering, wrong units,
ugly graphics). That's fine here: the generator connects by pin number/name
read from the symbol file, and `check_netlist.py` verifies every net after
generation — but each symbol's pin map still gets a manual check against its
datasheet before first use. Do not trust a vendor symbol that hasn't been
diffed against the datasheet pinout table.
