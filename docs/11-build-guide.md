# 11 — How to Build One

A guide for anyone who wants to build a Lab_Bench module from this repository:
what to order, how to assemble it, how to load the firmware, and how to power
it up the first time without letting the smoke out. When the board passes the
first power-up in §7, [docs/12-phase1-bench-tests.md](12-phase1-bench-tests.md)
takes over and checks that it actually meets the spec.

> **Read this first — honest status (2026-10-06).** Nothing in this repository
> has run on real silicon yet. All four boards are routed and DRC-clean, the
> firmware builds and passes its host tests in CI, but the first board has not
> been built. You would be building alongside the project owner, not after a
> proven design. Expect to debug; the bench-test doc is written with that in
> mind.

## 1. What you can build today

| Board | What it is | Can you order it? |
|---|---|---|
| **Phase-1 module** (`hardware/phase1-module/`) | Single 150 W channel: 24 V in, 0–20 V / 0–8 A out, CAN controlled | **Yes, once the parts in §3.3 are settled.** Order the 100 × 80 board on `development`/`master`; the 120 × 80 layout on branch `phase1-120x80` has wrong L1/U7 lands |
| Phase-2 module (`hardware/phase2-module/`) | 600 W channel, 0–28 V / 0–30 A, hot-swap input | Routed and fab-ready (2026-09-27). Wait for Phase-1 to pass its bench tests (docs/05 exit criteria) and settle the U3 `CHECK:` row |
| Phase-3 backplane (`hardware/phase3-backplane/`) | 8-slot bus with CAN, E-stop and bus metering | Fab-ready, but gated on the XT60 polarity check and only useful with Phase-2 modules and a manager |
| Phase-3 manager (`hardware/phase3-manager/`) | ESP32-S3 with display, encoder, USB SCPI | Routed and fab-ready. Confirm the fab quotes 0.2 mm drilling on 2 layers; regenerate the order files if yours predate 2026-10-06 (L2 changed) |

So today this guide is about the **Phase-1 module**. It is the "learning
board": every risky part of the design (analog CV/CC loops, sensing,
disconnect, firmware, CAN) is on it at a quarter of the power, so mistakes are
cheap. §9 says what changes for the later boards.

## 2. Skills and tools

The board is 4-layer, 100 × 80 mm, almost all SMD, and hand-assembled. The
hard parts are small leadless packages:

| Part | Package | Why it is hard |
|---|---|---|
| U3 LM5145 | VQFN-20 (RGY) with exposed pad | Hidden joints, needs paste + reflow or hot air |
| U8 LMR36015 | VQFN-HR-12 (RNX) | Same |
| U1 DAC80502 | WSON-10 (no exposed pad) | Tiny, easy to bridge |
| U6 LTC7004 | MSOP-10 with exposed pad | Exposed pad must be soldered |
| U10 STM32G431 | LQFP-48, 0.5 mm pitch | Bridges; fine with drag soldering and flux |
| Q1–Q4 | 5 × 6 mm power SON | Large thermal pad into inner planes; needs real heat |

If you have never reflowed a QFN, practise on a scrap board first.

**Assembly tools**
- Solder paste stencil (order it with the PCB; the fab zip has `F_Paste`).
- Hot plate or reflow oven, plus a hot-air station for rework.
- Fine-tip iron, flux, solder wick, tweezers, and a loupe or microscope.
- Isopropyl alcohol for flux cleanup.

**Bring-up tools**
- Bench supply, 24 V, with an adjustable current limit. The first power-up
  must be current limited.
- Multimeter.
- ST-Link (V2 or V3) for SWD programming, with `stlink-tools` (`st-flash`).
- USB-to-UART adapter at 3.3 V logic.
- USB-CAN adapter (CANable / candleLight class, runs as `can0` on Linux).

The characterisation equipment (electronic load, 6.5-digit DMM, scope) is
listed in [docs/12 §1](12-phase1-bench-tests.md#1-equipment).

## 3. Order the parts and boards

### 3.1 PCB

The fabrication files are in `hardware/phase1-module/phase1-module-fab.zip`:
Gerbers for four copper layers, mask, paste, silk, edge cuts, and the drill
file. Upload the zip as is.

| Setting | Value |
|---|---|
| Layers | 4 |
| Size | 100 × 80 mm |
| Thickness | 1.6 mm |
| Copper | 1 oz outer (JLCPCB standard stackup `JLC04161H-7628` is what the design assumes) |
| Stencil | Yes, top side |

To regenerate the zip after changing the board (needs KiCad 7 with its Python
module):

```bash
cd hardware/phase1-module/tools
python3 ../../common/finish_board.py ../phase1-module.kicad_pcb --fab
```

`--fab` refuses to run while anything is unconnected, and fills zones before
plotting.

### 3.2 Parts

Two files describe the parts:

- `hardware/phase1-module/bom/phase1-module-bom.csv`: every reference, value,
  footprint, and (where chosen) LCSC number, MPN, manufacturer and price.
- `hardware/phase1-module/bom/phase1-module-jlcpcb.csv`: the same in JLCPCB's
  assembly upload format.

Both are generated from `hardware/common/lcsc_parts.py`. To change a part,
edit that table and rerun the generator (from `hardware/`):

```bash
python3 common/bom.py          # writes schematic properties + both CSVs
python3 common/bom.py --check  # fails if anything is stale
```

The reasoning behind each choice, prices and stock are in
[hardware/SOURCING.md](../hardware/SOURCING.md). The short version: one
consolidated LCSC order plus the JLCPCB boards is the cheapest route, about
**US$45 of parts per module** and **US$100–125** for a complete first build
including five PCBs, a stencil and shipping (2026-07 prices; re-check stock the
week you order).

The generic resistors, capacitors, headers and jellybean semiconductors
(2N7002, BAT54W, 1N4148W, SMBJ33A) have **no LCSC number yet**. Pick any
reputable part matching the value, footprint and tolerance in the BOM. The
tolerance matters in a few places:

| Refs | Why it matters |
|---|---|
| R1, R2, R3, R6, R32, R33 (0.1 %) | They set the voltage accuracy and the analog references. Do not substitute 1 % |
| R20/R21, R45/R46, R47/R48, R50/R51, R60/R61, R67/R68 (1 %) | Undervoltage lockout, OVP threshold, rails and sensing dividers |
| C66, C67 = 18 pF | Matches the CL = 12 pF crystal in the BOM. If you use a CL = 8 pF crystal, fit 10 pF |

### 3.3 Decide these before ordering

| Item | What to decide |
|---|---|
| **Q1–Q4 (power and disconnect FETs)** | The CSD18563Q5A was out of stock on 2026-09-27; the BOM orders onsemi NTMFS5C670NLT1G (60 V, 6.1 mΩ, Qg 20 nC) with the same S-S-S-G / tab pinout. Confirm the pad overlay in the JLCPCB preview, or buy CSD18563Q5A if it is back |
| **C20, C75–C77 (input ceramics)** | No 22 µF 50 V 1210 is stocked; the BOM orders 10 µF 50 V, which drops the input ceramic from 88 to 40 µF (C21 is the bulk). Accept it or source 22 µF elsewhere |
| **L2 (5V0 aux buck inductor)** | The 1210 land only takes 33 µH parts rated about 0.5 A; the value asks for 1.2 A. Fine if the 5V0 load (fan included) stays well under ~0.4 A. A bigger 5 × 5 mm land, as on the manager, is an open option |
| **R30 (2 mΩ shunt)** | The LCSC part (C2994640) is cheap but its TCR is unverified. The CC accuracy depends on it. A Vishay WSLP-class part (~US$1.50) is the safe choice |
| **U8, U11 variants** | The LCSC variants (LMR36015ARNXR, TCAN1042VDRQ1) differ from the symbol values. Both are the right function (adjustable buck, VIO-capable CAN transceiver) in the same package |
| **J1, J4 terminal blocks** | The footprint is a 5.0 mm Phoenix PT; SOURCING.md lists 5.08 mm 2EDG plugs. Buy a header that matches the 5.0 mm footprint |
| **Order-early parts** | LTC7004EMSE had only 5 in stock at LCSC. Put it in the cart first |

## 4. Assemble

1. **Inspect the bare board.** Check the fab didn't swap layers: the In1/In2
   ground and power planes should not be visible, and the silkscreen should
   match the KiCad 3D view.
2. **Paste and place the top side.** Use the KiCad board file as the
   placement map (highlight a reference to find it). Watch the orientation of:
   - diodes: **BAT54W (D1–D4) is pin 1 = anode; 1N4148W (D6) is pin 1 =
     cathode.** They are opposite. Follow the silk, not habit;
   - the LED D7, the TVS D5, and every IC's pin-1 mark;
   - the polymer caps C22/C78 and bulk cap C21 (polarised).
3. **Reflow.** Leave the thermal pads of Q1–Q4, U3 and U8 a little longer on
   the hot plate; the inner planes pull heat away.
4. **Hand-solder** the through-hole and large parts: J1–J6 headers and
   terminals, and the F1 fuse holder (fit a **10 A mini blade** fuse).
5. **Leave C17 and R17 empty.** They are the switch-node snubber, sized on the
   bench from the ringing frequency (docs/06 §10).
6. **Inspect under magnification.** The usual failures are bridges on U10 and
   U1, and dry joints on the QFN thermal pads (hard to see; the power-up
   checks below catch them).
7. **Clean off the flux.** Flux residue near the 69.8 kΩ divider (R32) and the
   error-amp network leaks enough current to shift the calibration.

## 5. Cold checks (no power)

Measure resistance with the multimeter before applying any power. A short here
is cheap; a short at 24 V is not.

| Between | Expect |
|---|---|
| VBUS (J1.1) and PGND (J1.2) | Not a short. It will charge up slowly on the input caps |
| VOUT (J4.1) and PGND (J4.2) | High resistance (disconnect FETs are open) |
| 5V0 (J6.1) and PGND | Not a short |
| 3V3 (J2.1) and AGND (J2.5) | Not a short |
| AGND (J2.5) and PGND (J1.2) | Near 0 Ω. They are joined at one point, the net-tie NT1 |

## 6. Connectors and the bench harness

| Conn | Pins | Notes |
|---|---|---|
| J1 VBUS IN | 1 = VBUS, 2 = PGND | 24 V nominal. Never exceed 30 V: D5 is a 33 V TVS |
| J4 OUTPUT | 1 = VOUT, 2 = PGND | The regulated output |
| J2 SWD | 1 = 3V3, 2 = SWDIO, 3 = SWCLK, 4 = NRST, 5 = GND | See the note on pin 1 below |
| J3 UART | 1 = GND, 2 = TX (from MCU), 3 = RX (to MCU) | 115200 8N1, 3.3 V |
| J5 BACKPLANE | 1 = CAN_H, 2 = CAN_L, 3 = HW_EN, 4–6 = SLOT_ID0–2, 7–8 = PGND | The bench harness plugs in here |
| J6 FAN | 1 = +5 V, 2 = fan return (switched low side) | Small 5 V fan; keep it under ~200 mA. The 5 V rail is sized for 0.5 A total, and the 1210 L2 the BOM fits is rated about 0.5 A, so keep the whole 5V0 load under ~0.4 A (§3.3) |

**J2 pin 1:** a genuine ST-Link only senses target voltage on this pin. Many
clone ST-Link V2 dongles *drive* 3.3 V onto it, which then fights the board's
own regulator. With a clone, leave pin 1 unconnected when the board is powered
from J1.

**The J5 bench harness.** Without the backplane, three things must be wired
by hand:

1. **CAN:** J5.1/J5.2 to the USB-CAN adapter's CAN_H/CAN_L, and J5.7 to the
   adapter's ground. The module has no termination resistor. Turn on the
   adapter's 120 Ω terminator and put a second 120 Ω across J5.1–J5.2.
2. **HW_EN (J5.3) is the hardware enable, and it is pulled low on the board
   (R19, 100 kΩ).** Left open, the converter and the output disconnect are
   held off in hardware, whatever the firmware says. That is the safe state for
   first power-up. To run the output, tie J5.3 to 3V3 (J2.1) through a
   1 kΩ resistor, ideally through a switch: that switch is your bench E-stop.
3. **SLOT_ID0–2 (J5.4–6):** leave open. All-open reads as slot 0, and every
   CAN example in the docs assumes slot 0.

## 7. Firmware and first power-up

### 7.1 Build and flash

The same commands CI runs (Debian/Ubuntu package names):

```bash
sudo apt install gcc-arm-none-eabi libnewlib-arm-none-eabi make stlink-tools
make -C firmware/tests test     # host tests of the control logic, must pass
make -C firmware/module         # builds firmware/module/*.bin (~6 KB)
make -C firmware/module flash   # st-flash to 0x08000000 over J2
```

The last 2 KB page of flash (0x0801F800) holds the calibration block. Flashing
the image does not erase it.

### 7.2 First power-up, step by step

Keep **HW_EN open** for this whole section.

1. Set the bench supply to **24 V with a 100 mA current limit**. Connect J1.
2. The supply should stay well below the limit. If it sits at the limit, power
   off and look for a short or a reversed part.
3. Measure the aux rails: **5V0 ≈ 5.0 V** at J6.1, **3V3 ≈ 3.3 V** at J2.1.
4. Flash the firmware (§7.1) if you have not already.
5. Open the UART at 115200. After a reset you should see:
   ```
   labbench module fw 0.1
   slot 0 up
   ```
   If you also see `INA228 missing`, the I²C bus or U5 has a problem
   (solder joints, or the pull-ups R62/R63).
6. The status LED blinks at 2 Hz. That is the SAFE state (8 Hz means a
   latched fault, solid means the output is on).
7. Bring up CAN on the PC and watch the bus:
   ```bash
   sudo ip link set can0 up type can bitrate 500000
   candump -td can0
   ```
   Reset the board (NRST on J2, or power-cycle). A **HELLO frame on ID
   `7E0`** appears, followed by STATUS frames on `302` twice a second and
   telemetry on `300`/`301` ten times a second.

If all seven steps pass, the logic side of the board is alive. Raise the
current limit to 1 A and carry on with
[docs/12-phase1-bench-tests.md](12-phase1-bench-tests.md), which enables the
output for the first time under controlled conditions and then measures the
board against the Phase-1 exit criteria.

## 8. When something is wrong

| Symptom | Look at first |
|---|---|
| Supply hits the current limit at power-on | Shorts on VBUS or 5V0; D5 fitted backwards; U8 bridges |
| 5V0 fine, 3V3 missing | U9 orientation (SOT-223 tab is pin 2, the output) |
| No UART text | TX/RX swapped; BOOT0 (R65 must pull it low); crystal Y1 and C66/C67 |
| `INA228 missing` | U5 joints; R62/R63; the I²C runs on PA8/PA9, not PB8 |
| No CAN frames | Termination; CAN_H/L swapped; U11 must be a VIO variant (TCAN1042**V** or **HGV**); CAN_STB (R64 pulls it low = run) |
| Output never turns on | HW_EN not tied high; the OUTPUT command is refused while HW_EN is low |

The debugging order in [docs/07 §Known-untested surface](07-module-firmware.md#known-untested-surface)
is the most likely order of firmware trouble: I²C, then the CAN filters, then
ADC sampling on the high-impedance V_MEAS divider, then the DAC80502 gain.

## 9. Later phases

- **Phase-2 module (600 W)** reuses the Phase-1 control, sensing, disconnect,
  aux and MCU blocks, with a 2-phase LM5143 power stage and LM5069 hot-swap
  input. Its assembly is the same as above plus heavier soldering on the power
  stage. The board is routed and the 220 µF caps are settled (EEHZA1V221P);
  the one open BOM item is the LM5143 Q1-variant land check (U3), plus the
  1210 L2 question that Phase-1 has too.
- **Phase-3 backplane and manager** turn modules into a rack. Before ordering
  the backplane, mate one XT60PW-M/F pair and buzz out which pad connects to
  which, and which cavity is marked "+" ([hardware/MECHANICAL.md](../hardware/MECHANICAL.md)).
  Pads 1 = + on both sides is still an assumption. The manager board is
  routed; its order files changed on 2026-10-06 (L2 on a 5 × 5 mm land), so
  use ones generated from `development` or later. The manager firmware builds
  in CI (`firmware/manager/idf`, ESP-IDF 5.3.2); its bring-up knobs are in
  [docs/10](10-manager-firmware.md).

Each phase has exit criteria in [docs/05](05-build-plan.md) that must pass
before money is spent on the next one. Please share your results: commit them
under `docs/test-results/` or open an issue.
