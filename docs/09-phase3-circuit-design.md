# 09 — Phase 3 Circuit Design (Backplane + Manager)

Worked design for the two Phase-3 boards (docs/01 §3/§6, docs/05 Phase 3):
the **backplane** (8 slots, power distribution, bus-entry metering, E-stop
chain, CAN terminations) and the **manager** (ESP32-S3, display, encoder,
USB, CAN). New-part pin maps verified against local datasheets
(`docs/datasheets/esp32-s3-wroom-1.pdf`, `tca9535.pdf`, `tpd2e001.pdf`).
Values marked **(bench)** are starting points.

## 1. System partitioning

Two boards, one connector between them:

```
 PSU/battery ──lugs──► BACKPLANE ──8× slot connectors──► modules
                        │  bus shunt + INA228 (I²C)
                        │  CAN bus + 120Ω ends, /HW_ENABLE line, slot straps
                        │  E-stop loop connector (front panel, NC switch)
                        └──1×20 header──► MANAGER (ESP32-S3-WROOM-1-N8R2)
                                           display + encoder + keys + USB-C
```

The backplane is deliberately almost passive — the only IC on it is the
bus-entry INA228. Everything that can crash lives on the manager, and a
manager failure leaves the backplane distributing power and the modules
self-regulating (docs/01 design principle).

## 2. Backplane

### Power distribution & entry metering

- Input: bolted lugs (M6) from the bus source; **35 A blade fuse per
  module is on each module** (docs/08) — the backplane itself is
  unfused (bus-source breaker is the upstream protection; document in
  the operator manual).
- SMBJ33A TVS at entry + 470 µF/50 V bulk (damps harness inductance).
- **Bus shunt: 250 µΩ ±1 % ≥ 8 W bar/bolt-in** (WSBS8518-class; exact MPN
  at sourcing), high-side, Kelvin. Math: budget 1.5 kW @ 24 V = 62.5 A →
  15.6 mV, 0.98 W; theoretical ceiling 200 A → 50 mV, well inside the
  INA228's ±163.84 mV range (ADCRANGE = 0) with 3.3× headroom; VBUS pin
  senses the 24–30 V rail directly (rated 85 V ✓).
- **INA228** (same vetted part as the modules), A1 = A0 = GND → addr 0x40
  on the *manager-local* I²C bus — no address conflict possible with the
  modules (theirs live behind CAN, not on this bus).

### /HW_ENABLE chain (E-stop)

```
 3V3 (from manager) ──► J_ESTOP.1 … NC panel switch … J_ESTOP.2 ──► R 1kΩ ──► HW_EN line
                                                                              │ (all 8 slots + manager sense
 manager kill FET (open-drain) ───────────────────────────────────────────────┤  + each module's 100k pulldown)
```

- **Fail-safe by construction**: the pull-up current *flows through* the
  NC E-stop switch. Pressing it — or a broken panel wire, or an unplugged
  manager (the 3V3 source) — drops the line and every module enters SAFE
  in hardware. Modules only listen (docs/04 row 16).
- Levels: 8 modules × 100 k pulldown = 12.5 kΩ load; 1 kΩ pull-up →
  V_line = 3.3 × 12.5/13.5 = **3.06 V** (module PB6 V_IH = 2.31 V ✓;
  2N7002 gate fully on ✓). With 2 modules (Phase-3 build): 3.24 V.
- Bench use without a panel switch: fit the shipped 2-pin jumper on
  J_ESTOP.
- Manager asserts E-stop via its own 2N7002 (§3); it also *senses* the
  line so it can tell a panel E-stop from its own.

### CAN bus

Linear bus across the 8 slots, **120 Ω termination resistors at both
physical ends of the backplane** (docs/03). The manager connects as a
short stub near slot 7's end — no termination on the manager board.

### Slot straps (SLOT_ID)

Firmware convention (authoritative — `firmware/module/src/board.h`):
`SLOT_ID_IN() = ~(PB11..13) & 0x7` with pull-ups, i.e. **a grounded strap
sets a bit; all-open = slot 0, all-grounded = slot 7**. (docs/06 §7 said
"grounded on the bench = slot 0" — that was backwards; corrected there.)
The backplane hardwires each slot's SLOT_ID0..2 pins to GND for each 1-bit
of the slot number — drawn as fitted/DNP 0 Ω links so the generator emits
the correct pattern per slot and the netlist checker can assert it.

### PRESENT lines

Each slot's PRESENT pin (grounded inside a seated module) routes straight
to the manager connector; the pull-ups live on the manager (§3, TCA9535
port 0). Unseated slot = high, seated = low.

### Manager connector (1×20)

VBUS ×2, PGND ×4, CAN_H, CAN_L, HW_EN, 3V3 (manager-sourced, feeds the
E-stop pull-up), SDA, SCL (bus INA228), PRESENT0–7. Manager power is
tapped from the bus through this connector (~0.25 A at 24 V) — no
separate supply input.

## 3. Manager board

### Power

Same vetted chain as the modules: VBUS → mini-blade fuse 2 A →
SMBJ33A → **LMR36015** → 5V0 (display backlight, CAN VCC, buzzer) →
**NCP1117-3.3** → 3V3 (ESP32-S3, TCA9535, logic, E-stop pull-up).
LDO dissipation: ESP32-S3 Wi-Fi average ≈ 250 mA + logic → ≈ 0.5 W on the
SOT-223 tab pour — warm but in spec; Wi-Fi TX bursts (~350 mA) are short.
**(bench)**: verify LDO temperature during a Wi-Fi soak; escape hatch is
dropping 5V0 to 4.5 V (LMR divider) or a second buck.

### ESP32-S3-WROOM-1-N8R2 (pin map verified, esp32-s3-wroom-1.pdf §3.1)

**Why N8R2**: octal-PSRAM variants (R8/R16V) lose IO35–37 to the PSRAM
bus (datasheet note b) — the quad-PSRAM N8R2 keeps them, and 8 MB flash /
2 MB PSRAM is plenty for UI + logging.

| Function | GPIO (module pin) | Notes |
|---|---|---|
| CAN TX / RX | IO4 (4) / IO5 (5) | TWAI via GPIO matrix → TCAN1042HGV (VCC 5 V, VIO 3V3, STB ← IO6 w/ 10 k pulldown = run) |
| I²C SDA / SCL | IO8 (12) / IO9 (17)* | 4.7 k pull-ups; devices: TCA9535 (0x20), bus INA228 (0x40, on backplane) |
| LCD SPI CS/MOSI/SCK/MISO | IO10 (18) / IO11 (19) / IO12 (20) / IO13 (21) | shared with touch |
| LCD DC / RST | IO14 (22) / IO15 (8) | |
| LCD backlight PWM | IO16 (9) | 2N7002 → P-FET high-side from 3V3 (§ display) |
| Touch CS / IRQ | IO17 (10) / IO18 (11) | XPT2046 on the display module, shares SPI |
| Encoder A / B / SW | IO35 (28) / IO36 (29) / IO37 (30) | 10 k pull-ups + 10 k/100 n RC **(bench)** |
| /HW_ENABLE kill | IO21 (23) | → 2N7002 gate (100 k pulldown), drain on HW_EN: high = E-stop assert |
| /HW_ENABLE sense | IO38 (31) | direct input, line is a 3.3 V domain |
| TCA9535 INT | IO7 (7) | falling edge = key/PRESENT change |
| Status / CAN LEDs | IO39 (32) / IO40 (33) | sink via 1 k like the module LED |
| Buzzer | IO41 (34) | 2N7002 low-side, magnetic buzzer on 5V0 + 1N4148W flyback |
| UART0 header | TXD0 (37) / RXD0 (36) | bring-up console, same 3-pin header as modules |
| USB D− / D+ | IO19 (13) / IO20 (14) | native USB → TPD2E001 → USB-C |
| Boot / Reset buttons | IO0 (27) / EN (3) | IO0: 10 k pull-up + button to GND; EN: 10 k pull-up + 1 µF + button (Espressif guideline) |
| Straps left alone | IO3, IO45, IO46 | floating / weak-pulled per Table 4-1 — no connection, no repurposing in v1 |

*Module pin numbers in parentheses; IO9 is module pin 17 — the module pin
numbering is not GPIO-ordered, the generator maps by the verified table.

### USB (data only — deliberate)

USB-C receptacle wired USB 2.0: D+/D− through **TPD2E001DRL** (pin map
verified: 1=VCC, 3/5=IO, 4=GND), CC1/CC2 → 5.1 k pulldowns (UFP
advertise). **VBUS is not used as a power source**: OR-ing USB 5 V into
the 5V0 rail costs a schottky drop on the CAN transceiver's supply and
adds a back-feed path; this is a PSU lab — bus power is always available
when flashing. VBUS lands on a test point only.

### Display

Header for the ubiquitous 2.8"/3.2" ILI9341 + XPT2046 SPI module
(14-pin: VCC GND CS RESET DC MOSI SCK LED MISO T_CLK T_CS T_DIN T_DO
T_IRQ). VCC pin fed 3V3 (module's own regulator jumpered out), backlight
LED pin switched high-side: IO16 → 2N7002 → SOT-23 P-FET from 3V3
(backlight draws 50–120 mA — far beyond a GPIO). Exact P-FET MPN at
sourcing (AO3401A-class).

### Front panel keys

8 per-channel enable keys + PRESENT lines both land on the **TCA9535**
(pin map verified, tca9535.pdf Table 5-1): port 0 = PRESENT0–7, port 1 =
KEY0–7, all 16 with 10 k pull-ups to 3V3 (the part has push-pull drivers
but **no internal pull-ups**), INT → IO7, A0=A1=A2=GND → 0x20.

## 4. What Phase 3 explicitly reuses

LMR36015 + NCP1117 aux chain, TCAN1042HGV, INA228, SMBJ33A, 2N7002,
1N4148W, blade-fuse footprints, UART/SWD-style headers — all vetted in
Phases 1–2; the generators pull the same symbols from the shared library.
New symbols to synthesize from the verified tables: ESP32-S3-WROOM-1
(41 pads incl. thermal pad), TCA9535 (TSSOP-24), TPD2E001 (DRL),
USB-C receptacle (16-pin USB 2.0 type), EC11 encoder, ILI9341 module
header (generic 1×14).

## 5. Ordering shortlist (Phase-3 specific, sourcing pass later)

| Item | Part | Note |
|---|---|---|
| MCU module | ESP32-S3-WROOM-1-N8R2 | quad PSRAM keeps IO35–37 (§3) |
| I/O expander | TCA9535PWR (TSSOP-24) | 16 ch: PRESENT + keys |
| USB ESD | TPD2E001DRLR | SOT-5X3 |
| USB-C | 16-pin USB2.0 receptacle (GCT USB4105-class) | verify at sourcing |
| Bus shunt | 250 µΩ ±1 % ≥8 W bolt/bar | WSBS8518-class, verify at sourcing |
| Display | 2.8" ILI9341+XPT2046 SPI module | off-the-shelf, header-mounted |
| Encoder | EC11 w/ switch | panel part |
| E-stop | NC mushroom switch (panel) | + shipped bench jumper |
| P-FET | SOT-23 PMOS (AO3401A-class) | backlight switch, verify at sourcing |
| Everything else | Phase-1/2 BOM carries over | |

## 6. Open items → resolve at capture / bring-up

1. Backplane slot connector family — decided at the batch PCB pass
   together with the module edge (docs/08 §12); schematic uses the same
   generic 1×04 + 1×08 pair per slot.
2. Encoder RC values + TCA9535 key debounce (firmware) **(bench)**.
3. NCP1117 thermal under Wi-Fi soak **(bench)**, escape hatches in §3.
4. Display module VCC jumper convention varies by vendor — confirm the
   purchased module runs on 3V3 VCC before soldering the header.
5. Manager firmware architecture doc (docs/10) — discovery, UI, SCPI,
   budget arbiter, charge sequencer (reuses firmware/common/labbench_can.h).
