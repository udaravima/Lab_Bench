# 02 — 600 W Power Module Design

## 1. Module block diagram

```
 VBUS 24–30V
    │
 fuse (35A) ── LM5069 hot-swap/inrush ──┬────────────────────────────────┐
                                        │                                │
                                 ┌──────┴──────────┐              aux buck 5V
                                 │ LM5143 2-phase  │              (LMR36015)
                                 │ current-mode    │                 │ 3.3V LDO
                                 │ sync buck ctrl  │                 │
                                 └──┬──────────┬───┘            STM32G431
                     phase A ───────┘          └─────── phase B   │  │  │
                  Q1/Q2 + L1 (6.8µH)          Q3/Q4 + L2 (6.8µH)  │  │  └─ CAN (TCAN1042) ── backplane
                        └───────────┬──────────────┘              │  └─ I²C: DAC80502, INA228
                                    │                             └─ GPIOs: EN, droop, OVP-FET,
                              output cap bank                            fan, NTC ADC, /HW_ENABLE
                                    │
                              shunt 0.5 mΩ ──┬── INA240A4 (gain 200) → CC error amp + MCU ADC
                                    │        └── INA228 (telemetry, I²C)
                          back-to-back NFET output disconnect
                                    │
                                  OUT+          OUT− = power ground (Kelvin at shunt)
```

## 2. Power stage

| Item | Choice | Rationale |
|---|---|---|
| Controller | **LM5143** (dual-channel/dual-phase, 3.5–65 V, current-mode) | Interleaved 2-phase single output; peak-current-mode = easy compensation + inherent per-phase current balance; DEMB pin for diode emulation |
| Switching freq | ~350 kHz/phase (700 kHz effective ripple) | Inductor size vs. FET switching loss balance at 30 V |
| FETs | 60 V NexFET/OptiMOS class, e.g. CSD18540Q5B or BSC050N06 | 2× headroom over 30 V bus + switch-node ringing |
| Inductors | 2 × **6.8 µH**, I_sat ≥ 25 A, low-DCR | 15 A avg/phase, ripple ≈ 20 %. 6.8 µH (not 4.7) because the LM5143's fixed internal slope compensation needs it for subharmonic stability at our D → 0.93 — see docs/08 §2 |
| Input caps | Ceramic X6S/X7R bank + polymer bulk | HF ripple current shared per phase |
| Output caps | Polymer (e.g. 4–6 × 330 µF/2.5–35 V as V range dictates) + MLCC | ESR sets droop under load steps; bench-grade ripple target < 20 mVpp |
| Diode emulation | **DEM enabled whenever output is enabled into a battery** or at light load | A sync buck in forced-PWM will *sink* current — from a connected battery this back-feeds the bus. DEM makes the stage source-only |

Per-phase budget at 600 W / 24 V in: ~15 A average per phase, conservative
thermal design with top-side cooled FETs on ≥2 oz copper + heatsink/fan header.

## 3. CV/CC control — analog outer loops, controller as servant

The LM5143 regulates its FB node to an internal 0.6 V reference and handles all
inner-loop (current-mode) stability itself. Precision CV/CC comes from two
**outer error amplifiers** that inject into the FB summing node through a
**diode-OR (minimum selector)** — whichever loop demands the *lower* output wins:

```
V_ref (DAC A) ──┬─► EA_V (OPA2333) ──►|── ┐
 output divider ┘                          ├──► FB summing node of LM5143
I_ref (DAC B) ──┬─► EA_I (OPA2333) ──►|── ┘
 INA240 (shunt) ┘
```

- **CV amp:** compares scaled output voltage against V_ref. 
- **CC amp:** compares INA240A3 output (0.5 mΩ × 100 = 0.05 V/A → 1.5 V at 30 A)
  against I_ref. (A3, not the earlier A4 pick: gain 200 would put 30 A at
  3.0 V, beyond the DAC's 2.5 V reference ceiling — the CC loop could never
  command full current. Caught at Phase-2 design, docs/08 §4.)
- CV↔CC crossover is automatic, analog, and fast (µs class). Firmware is never
  in the regulation or current-limit path — a firmware crash leaves a perfectly
  regulating, current-limited supply.
- Compensation strategy: inner current-mode loop crosses over ~30–50 kHz;
  outer amps are rolled off to ~1–3 kHz crossover so the loops are decoupled.
  Type-II around each outer amp; verified by load-step + Bode measurement in
  Phase 1 (see build plan).

### Setpoint DAC

**DAC80502** (dual 16-bit, internal 2.5 V reference, I²C).
- V path: 16 bit over 0–30 V span → 0.46 mV/LSB.
- I path: 16 bit over 0–50 A span at 0.05 V/A → 0.76 mA/LSB
  (firmware-clamped to 1.5 V = 30 A; see docs/08 §4).
- Power-on-reset outputs 0 → both references demand zero volts / zero amps
  until the MCU deliberately programs them. Output stays off anyway until the
  enable sequence completes.

## 4. Measurement

| Path | Device | Role |
|---|---|---|
| Fast current (control) | INA240A3 on 0.5 mΩ shunt | CC loop + MCU fast OCP backup via internal comparator/ADC watchdog |
| Precision telemetry | **INA228** (20-bit, ±0.05 %, I²C) across same shunt + V_out sense | Reported V/I/P/energy/charge; basis for calibration and manager display |
| Housekeeping | STM32G431 ADCs | NTC temps (FETs, inductor, shunt), V_bus, aux rails, INA240 mirror |

Shunt: 0.5 mΩ, ≥3 W wide-terminal metal element, Kelvin-routed. Dissipation at
30 A = 0.45 W. OUT− carries the shunt so remote-sense is Kelvin at the output
terminals; a 4-wire remote sense terminal option is provisioned (jumper) for
bench use.

Calibration: two-point gain/offset for each of {V_set, I_set, V_meas, I_meas},
stored in MCU flash, applied in firmware. Target after cal:
**±(0.05 % + 5 mV)** voltage, **±(0.1 % + 10 mA)** current.

## 5. Droop for parallel groups

An analog switch (MCU GPIO) sums an attenuated copy of the INA240 signal into
the CV error amp's reference divider, creating a fixed ~20 mV/A droop. Enabled
only when the manager assigns the module to a parallel group
(architecture doc §5). Static sharing is analog; the manager trims setpoints
slowly to balance and to compensate sag.

## 6. Protection hardware (detail in protection matrix doc)

- **Input:** blade fuse 35 A → **LM5069** hot-swap controller (inrush limit,
  UVLO 10.5 V, OVP 33 V, circuit-breaker function).
- **Output:** back-to-back NFET disconnect — blocks both directions, so a
  connected battery cannot back-feed a disabled module; driven by a dedicated
  gate driver, opened by MCU or by hardware OVP comparator (TLV7011 against a
  fixed 105 %-of-max threshold) — not firmware-dependent.
- **Thermal:** NTCs on FET area, inductors, shunt; firmware derate at 85 °C,
  hardware-latched shutdown at 100 °C; fan header PWM-controlled.
- **/HW_ENABLE (backplane):** gates the LM5143 EN pin and the output disconnect
  driver directly in hardware.
- **Watchdogs:** MCU IWDG; CAN heartbeat supervision (protocol doc §6).

## 7. Module MCU — STM32G431

Cheap, 170 MHz, FDCAN (runs classic CAN 2.0B at 500 k), plenty of ADC channels,
5 V-tolerant-enough peripherals for the sense chain. Responsibilities:

- Read SLOT_ID straps, join bus, heartbeat.
- Program DAC setpoints (with calibration + power-envelope clamp:
  I_set ≤ min(30 A, 600 W / V_set)).
- Poll INA228 (~100 Hz internally), stream telemetry at 20 Hz.
- Enable sequencing: precharge → LM5143 EN → close output FETs → ramp V_ref
  (soft-start in the reference domain, so soft-start is calibrated and monotonic).
- Supervisors: OTP derate/shutdown, digital OCP/OVP backup, comms-loss policy.
- Local console UART (debug header) for bring-up without the manager.

## 8. Phase-1 prototype variant (150 W)

Identical architecture, cheaper iron — validates every risky part of the design
(outer-loop stability, CV/CC crossover, DEM behavior with batteries, telemetry
accuracy) before committing to 600 W layout:

| Item | 600 W module | 150 W prototype |
|---|---|---|
| Controller | LM5143, 2-phase | **LM5145**, single phase |
| Envelope | 0–28 V, 30 A, 600 W | 0–20 V, 8 A, 150 W |
| Shunt / amp | 0.5 mΩ / INA240A3 (gain 100 → 0.05 V/A, 1.5 V FS) | 2 mΩ / INA240A3 (gain 100 → 0.2 V/A, 1.6 V FS) |
| FETs | 60 V power pair ×4 | 60 V SO-8 pair ×2 |
| Everything else | — | **identical** (MCU, DACs, INA228, CAN, protections) |

The control/telemetry section is laid out as a reusable schematic block so the
Phase-2 board changes only the power stage.
