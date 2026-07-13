# 05 — Build Plan

Four phases; each has exit criteria that must pass before spending money on the
next. All risky unknowns are front-loaded into the cheap Phase 1 board.

## Phase 1 — 150 W prototype module (the learning board)

Single-phase LM5145 power stage, full control/telemetry chain
(module doc §8). One 4-layer PCB, hand-assembled.

**Scope**
- Power: 24 V bench input, 0–20 V / 0–8 A / 150 W envelope.
- Full analog CV/CC (diode-OR outer loops), DAC80502, INA240/INA228, STM32G431,
  CAN via USB-CAN dongle (no manager yet), output disconnect FETs, DEM mode.
- Firmware: state machine, SET_VI/OUTPUT/STATUS/TELEM frames, calibration
  routine, protections 2/4/5/7/11–13/19.

**Test plan / exit criteria**
| Test | Pass criterion |
|---|---|
| CV accuracy after 2-pt cal, 0.5–20 V, 0–8 A | ±(0.05 % + 5 mV) |
| CC accuracy after cal, 0.1–8 A | ±(0.1 % + 10 mA) |
| Load step 10↔90 % (electronic load) | Recovery to ±1 % < 200 µs, no ringing; overshoot < 2 % |
| CV↔CC crossover (sweep load R through the corner) | Monotonic, no oscillation, corner sharp within 1 % |
| Outer-loop Bode (injection transformer) | Phase margin ≥ 55°, gain margin ≥ 10 dB, both loops |
| Ripple at full load | < 20 mVpp at output terminals |
| DEM battery test (12 V lead-acid + Li pack w/ supervision) | Zero reverse current disabled and enabled-above-battery-V; clean CC→CV charge |
| Thermal soak 1 h @ 150 W | All NTCs < 70 °C with fan |
| Fault injection: short output, pull FB, heat NTC, kill heartbeat | Matrix rows 2, 4, 11–14 behave as specified |
| MCU crash test (halt via debugger under load) | Output continues regulating in CV/CC; IWDG reboots into SAFE |

## Phase 2 — 600 W module

Reuse the validated control block schematic; new power stage
(LM5143 2-phase, 60 V FET pairs, 0.5 mΩ shunt, heatsink + fan).

**Added work:** interleave/current-balance verification, real thermal design,
input hot-swap (LM5069), droop hardware.

**Exit criteria:** Phase-1 test plan re-run at 0–28 V / 0–30 A / 600 W, plus:
- Phase-current balance within 10 % at full load.
- 1 h full-power soak, FET NTC < 85 °C.
- Efficiency curve recorded (expect ≥ 94 % mid-load); no derate below 500 W at 25 °C ambient.
- Hot-swap: repeated live insertions, inrush < LM5069 limit, no bus disturbance > 5 %.

## Phase 3 — Backplane + manager + 2 modules

- Backplane PCB: bus bars/heavy copper, 8 slots (populate 2), slot-ID straps,
  CAN with end terminations, /HW_ENABLE + panel E-stop, bus-entry INA228.
- Manager board: ESP32-S3, TCAN1042, display + encoder, USB.
- Manager firmware: discovery, UI, SCPI (USB first), budget arbiter,
  charge sequencer, logging.

**Exit criteria**
- Hot-plug either module in any slot: discovered < 2 s, correct address, no glitch on the other channel.
- Budget arbiter: request exceeding budget refused; verified against bus-entry meter.
- Parallel group (2×): static share within 10 %, trimmed share within 3 %, load-step stable.
- Battery charge sequence end-to-end on the manager (CC→CV→cutoff) with manager
  deliberately rebooted mid-charge → policy=hold keeps charging safely, resumes supervision.
- E-stop drops all outputs < 1 ms (scope), independent of both MCUs (verified with manager halted).

## Phase 4 — Scale-out & productionize

- Replicate modules to target count (build in pairs, calibrate each on a
  fixture: scripted 2-pt cal against a 6.5-digit DMM).
- Enclosure: 19-inch or custom rack, airflow front-to-back, finger-safe output
  terminals, panel E-stop.
- Manager: WiFi SCPI, telemetry logging/export, UI polish, per-channel presets.
- Documentation: as-built schematics, cal procedure, operator manual.

## Suggested repo workflow

- `hardware/phase1-module/` KiCad project first; control block drawn as a
  hierarchical sheet for reuse in `hardware/phase2-module/`.
- Firmware from day one in `firmware/module/` (STM32CubeIDE or Makefile+arm-gcc)
  with the CAN frame codecs shared as a small header-only lib later reused by
  `firmware/manager/`.
- One git tag per phase exit (`phase1-pass`, …) with test results committed
  under `docs/test-results/`.

## Bench equipment needed (Phase 1)

Electronic load (≥150 W), 24 V source (≥10 A), 6.5-digit DMM for cal, scope
(≥100 MHz) + current probe (or shunt+diff probe), USB-CAN adapter,
sacrificial 12 V battery for DEM tests. Loop Bode: injection transformer +
scope FRA function (or a Bode-capable scope/analyzer).
