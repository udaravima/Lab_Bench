# Parts to download — symbols & datasheets

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
| 5 | **LTC7004EMSE#TRPBF** (ADI) | MSOP-8E | Output-disconnect high-side gate driver | Confirm exposed-pad variant while downloading |

## B. Datasheets only (symbol already in KiCad's official library)

| Part | Verify against datasheet |
|---|---|
| **DAC80502** | SPI2C strap level for SPI mode; REFIO cap value; power-on zero-scale |
| **OPA2189** | Standard dual-opamp pinout in DGK (VSSOP-8) matches library symbol |
| **INA240A3** | PW (TSSOP-8) pinout, REF1/REF2 strapping for unidirectional |
| **TPS54202** | SOT-23-6 pin order, FB voltage, EN threshold |
| **STM32G431CB** | (also grab RM0440 reference manual — firmware work) |
| **BAT54W** | Any vendor's SC-70 single Schottky — pin 1 A / pin 3 K |

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
