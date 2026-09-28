# Lab_Bench — Multi-Channel Modular Power Supply

[![CI](https://github.com/udaravima/Lab_Bench/actions/workflows/ci.yml/badge.svg)](https://github.com/udaravima/Lab_Bench/actions/workflows/ci.yml)

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
| Setpoint resolution | ~0.5 mV / ≤0.8 mA (16-bit DAC, per-module calibration) |
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
| [docs/08-phase2-circuit-design.md](docs/08-phase2-circuit-design.md) | Worked component values for the 600 W module (LM5143 + LM5069) |
| [docs/09-phase3-circuit-design.md](docs/09-phase3-circuit-design.md) | Backplane + ESP32-S3 manager design (slots, E-stop chain, bus metering, UI) |
| [docs/10-manager-firmware.md](docs/10-manager-firmware.md) | Manager firmware architecture (host-tested core + ESP-IDF shell) |
| [docs/11-build-guide.md](docs/11-build-guide.md) | How to build one: ordering, assembly, firmware, first power-up |
| [docs/12-phase1-bench-tests.md](docs/12-phase1-bench-tests.md) | Phase-1 bench test procedure against the exit criteria (+ results template) |
| [hardware/SOURCING.md](hardware/SOURCING.md) | LCSC-first part sourcing, prices, order-early list |
| [HANDOVER.md](HANDOVER.md) | Session handover: state, decisions, gotchas, next steps |
| [hardware/phase1-module/tools/README.md](hardware/phase1-module/tools/README.md) | Schematic/PCB generation + verification pipeline |
| [hardware/phase1-module/lib/PARTS-TO-DOWNLOAD.md](hardware/phase1-module/lib/PARTS-TO-DOWNLOAD.md) | Exact orderables, package corrections, verified pricing |

## Repository layout

```
docs/                         Design docs 01..10, build guide 11, bench tests 12
  test-results/               Bench results (template + one file per board run)
hardware/common/              Shared generators, checkers, bom.py + lcsc_parts.py
hardware/phase1-module/       KiCad 7 project (schematics hand-owned; board generated + routed)
  tools/                      Generators + mechanical checkers (see README)
  lib/                        Vetted symbol + footprint libraries (shared by phase 2)
hardware/phase2-module/       KiCad 7 project — GENERATED (600 W module, docs/08)
hardware/phase3-backplane/    KiCad 7 project — GENERATED (8-slot backplane, docs/09)
hardware/phase3-manager/      KiCad 7 project — GENERATED (ESP32-S3 manager, docs/09)
firmware/
  common/labbench_can.h       CAN codec, shared module <-> manager
  module/core/                Portable control core (host-tested)
  module/                     STM32G431 bare-metal firmware (Makefile+arm-gcc)
  manager/core/               Portable manager core (host-tested)
  manager/idf/                ESP-IDF shell (needs IDF >= 5.1; unproven on silicon)
  tests/                      Host unit tests — `cd firmware/tests && make test`
  tools/lbcan.py              Bench helper: build cansend frames, decode candump
```

## Status (2026-09-27)

Nothing has run on silicon yet; the first board to be built is the Phase-1 module.

| Area | State |
|---|---|
| Design docs | Complete: 01–10, plus the build guide (11) and Phase-1 bench test procedure (12) |
| Phase-1 module (150 W) | Schematic verified and audited; **board routed, 0 unconnected, 0 DRC errors**, fab zip committed. Layout review fixes in PR #5. Next: settle the open BOM items (Q3/Q4 part, R30 shunt, the BOM `CHECK:` rows), then order and run [docs/12](docs/12-phase1-bench-tests.md) |
| Phase-2 module (600 W) | Schematic verified and audited; board placed and pass-1 routed, **83 connections left** to finish by hand in KiCad |
| Phase-3 backplane | Board fab-ready; gated on the XT60 polarity buzz-out ([MECHANICAL.md](hardware/MECHANICAL.md)) |
| Phase-3 manager | Schematic verified; board placed, signal routing not started |
| Module firmware | v0.1 builds (~6 KB, bare-metal STM32G431); control core host-tested |
| Manager firmware | v0.2 builds on ESP-IDF 5.3.2; manager, SCPI and UI cores host-tested |
| BOM / sourcing | LCSC numbers in the schematics and per-board BOM CSVs (`hardware/common/bom.py`); five `CHECK:` part mismatches await a pick; generic R/C parts not yet numbered |
| CI | GitHub Actions: host tests, module and manager firmware builds on every PR |

Complete Phase-1 build (parts, five PCBs, stencil, shipping) ≈ US$100–125.
[HANDOVER.md](HANDOVER.md) has the detailed resume points. Work lands on the
`development` branch through pull requests; `master` receives batched merges.

## License

GPL-3.0 (see LICENSE).
