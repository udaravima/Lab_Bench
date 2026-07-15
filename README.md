# Lab_Bench — Multi-Channel Modular Power Supply

A modular, rack-style DC power supply: up to **8 hot-pluggable 600 W buck
modules** on a shared DC input bus, coordinated by a central manager over CAN.
Each channel is a self-contained analog CV/CC supply with bench-grade
precision, usable for lab work, bulk DC power, and battery charging.

## Headline specification

| Parameter | Value |
|---|---|
| Input bus | 24–30 V DC nominal (12 V tolerated, output ceiling drops with it) |
| Channels | 1–8, hot-pluggable, slot-addressed |
| Per-channel output | 0 … (V_in − 2 V), 0–30 A, **600 W envelope** (first limit binds) |
| Regulation | Analog CV/CC (diode-OR min-selector), firmware never in the loop |
| Setpoint resolution | ~0.5 mV / ~0.5 mA (16-bit DAC, per-module calibration) |
| Readback | 20-bit INA228, ±0.05 % class |
| Comms | CAN 2.0B @ 500 kbit/s, heartbeat-supervised |
| Scaling | Channels parallel into droop-share groups (firmware feature) |
| Grounding | All outputs share input ground — parallel OK, **no series stacking** |
| Global limits | Manager-enforced total power budget + hardwired E-stop line |

## Documentation index

| Doc | Contents |
|---|---|
| [docs/01-system-architecture.md](docs/01-system-architecture.md) | Topology, backplane, grounding, power budget |
| [docs/02-module-design.md](docs/02-module-design.md) | 600 W module: power stage, CV/CC loop, sensing, MCU |
| [docs/03-can-protocol.md](docs/03-can-protocol.md) | Bus parameters, ID map, payloads, fault semantics |
| [docs/04-protection-matrix.md](docs/04-protection-matrix.md) | Every fault: detection, response, latching, recovery |
| [docs/05-build-plan.md](docs/05-build-plan.md) | Phased build with exit criteria (150 W proto → 8-ch rack) |
| [docs/06-phase1-circuit-design.md](docs/06-phase1-circuit-design.md) | Worked component values for the 150 W prototype |
| [docs/07-module-firmware.md](docs/07-module-firmware.md) | STM32G431 firmware architecture, pin map, bring-up |
| [HANDOVER.md](HANDOVER.md) | Session handover: state, decisions, gotchas, next steps |
| [hardware/phase1-module/tools/README.md](hardware/phase1-module/tools/README.md) | Schematic/PCB generation + verification pipeline |
| [hardware/phase1-module/lib/PARTS-TO-DOWNLOAD.md](hardware/phase1-module/lib/PARTS-TO-DOWNLOAD.md) | Exact orderables, package corrections, verified pricing |

## Repository layout

```
docs/                         Design docs 01..07 (+ datasheets/, gitignored)
hardware/phase1-module/       KiCad 7 project — GENERATED, do not hand-edit
  tools/                      Generators + mechanical checkers (see README)
  lib/                        Vetted symbol + footprint libraries
firmware/
  common/labbench_can.h       CAN codec, shared module <-> manager
  module/core/                Portable control core (host-tested)
  module/                     STM32G431 bare-metal firmware (Makefile+arm-gcc)
  manager/                    ESP32-S3 manager firmware          [not started]
  tests/                      Host unit tests — `cd firmware/tests && make test`
```

## Status (2026-07-16)

- **Phase 0 — design docs: complete** (01–07).
- **Phase-1 schematic: complete (v1) and machine-verified** — 7 generated
  sheets, 137 components; every net asserted against the intended net table,
  every footprint pad-checked; vendor symbols/footprints datasheet-vetted.
  Audited with the kicad-happy analyzers + ngspice (38/40 subcircuits pass);
  the audit's one real electrical find (ADC injection current on PA1) is fixed.
- **Module firmware v0.1: builds** — bare-metal STM32G431, 6.3 KB, binds the
  host-tested control core to SPI DAC, I²C INA228, FDCAN @500k, ADC, fan PWM,
  IWDG, flash calibration. Untested on silicon (no board yet).
- **PCB layout: deferred by design** — all phases' boards get laid out
  together at the end. The committed board file is a clean intermediate
  (full placement, split ground planes, power pours, thermal vias, critical
  routes — zero copper DRC errors); the signal autorouter is committed as WIP.
- **Pricing verified** — complete Phase-1 build ≈ **US$100–125** including
  five 4-layer PCBs (details in PARTS-TO-DOWNLOAD.md §E).
- **Next:** Phase-2 600 W module schematic (LM5143 2-phase + LM5069
  hot-swap), Phase-3 backplane + ESP32-S3 manager schematics, manager
  firmware — then the batch PCB pass, ordering, and the Phase-1 test
  campaign per [docs/05-build-plan.md](docs/05-build-plan.md).

## License

GPL-3.0 (see LICENSE).
