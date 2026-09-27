# Phase-1 results — board <serial>, <date>

Procedure: [docs/12-phase1-bench-tests.md](../12-phase1-bench-tests.md).
Copy this file to `phase1-<serial>-<date>.md` and fill it in.

| Item | Value |
|---|---|
| Board serial / build notes | |
| Firmware commit | |
| Q3/Q4 part fitted, R30 part fitted | |
| Ambient temperature | |
| DMM / load / scope / current reference (model, cal date) | |

## Summary

| docs/05 row | Criterion | Result | Pass? |
|---|---|---|---|
| CV accuracy | ±(0.05 % + 5 mV), 0.5–20 V, 0–8 A | worst: | |
| CC accuracy | ±(0.1 % + 10 mA), 0.1–8 A | worst: | |
| Load step | ±1 % in < 200 µs, overshoot < 2 %, no ringing | | |
| CV↔CC crossover | monotonic, no oscillation, corner within 1 % | | |
| Bode, outer CV | PM ≥ 55°, GM ≥ 10 dB | fc / PM / GM: | |
| Bode, outer CC | PM ≥ 55°, GM ≥ 10 dB | fc / PM / GM: | |
| Ripple | < 20 mVpp | 18.75 V: / 12 V: | |
| DEM battery | zero reverse current; clean CC→CV | | |
| Thermal soak | NTCs < 70 °C after 1 h at 150 W | T_fet / T_ind: | |
| Fault injection | rows 2, 4, 11–14 as docs/04 | see §6.9 | |
| MCU crash | regulates while halted; IWDG → SAFE | | |

## §4 First output enable

| Check | Result |
|---|---|
| OUTPUT refused with HW_EN open | |
| PS_EN → PGOOD → OUT_REQ sequence seen | |
| Turn-on overshoot at 5 V | |
| HW_EN open → VOUT < 10 % (time) | |

Uncalibrated setpoint error:

| V_set | J4 measured | Error |
|---|---|---|
| 1 | | |
| 5 | | |
| 10 | | |
| 15 | | |
| 19.5 | | |

## §5 Calibration

| Item | S1 | M1 | S2 | M2 | gain | offset | After: err @ S1 / S2 |
|---|---|---|---|---|---|---|---|
| VSET | 2 V | | 18 V | | | µV | |
| ISET | 0.5 A | | 7 A | | | µA | |

Survives power cycle: yes / no

## §6.1 CV accuracy

Allowed = 0.0005·V + 5 mV.

| V_set | Load | J4 (DMM) | Error | Allowed | TELEM V | TELEM I | Pass |
|---|---|---|---|---|---|---|---|
| 0.5 | 0 A | | | 5.25 mV | | | |
| 0.5 | 4 A | | | 5.25 mV | | | |
| 0.5 | 8 A | | | 5.25 mV | | | |
| 1 | 0 A | | | 5.5 mV | | | |
| 1 | 4 A | | | 5.5 mV | | | |
| 1 | 8 A | | | 5.5 mV | | | |
| 2 | 0 A | | | 6 mV | | | |
| 2 | 4 A | | | 6 mV | | | |
| 2 | 8 A | | | 6 mV | | | |
| 5 | 0 A | | | 7.5 mV | | | |
| 5 | 4 A | | | 7.5 mV | | | |
| 5 | 8 A | | | 7.5 mV | | | |
| 10 | 0 A | | | 10 mV | | | |
| 10 | 4 A | | | 10 mV | | | |
| 10 | 8 A | | | 10 mV | | | |
| 15 | 0 A | | | 12.5 mV | | | |
| 15 | 4 A | | | 12.5 mV | | | |
| 15 | 8 A | | | 12.5 mV | | | |
| 18.75 | 0 A | | | 14.4 mV | | | |
| 18.75 | 4 A | | | 14.4 mV | | | |
| 18.75 | 8 A | | | 14.4 mV | | | |
| 19.5 | 0 A | | | 14.75 mV | | | |
| 19.5 | 3.8 A | | | 14.75 mV | | | |
| 19.5 | 7.6 A | | | 14.75 mV | | | |

## §6.2 CC accuracy

Allowed = 0.001·I + 10 mA. Load in CV at 5 V unless noted.

| I_set | Measured (ref shunt) | Error | Allowed | TELEM I | Pass |
|---|---|---|---|---|---|
| 0.1 | | | 10.1 mA | | |
| 0.5 | | | 10.5 mA | | |
| 1 | | | 11 mA | | |
| 2 | | | 12 mA | | |
| 4 | | | 14 mA | | |
| 6 | | | 16 mA | | |
| 8 | | | 18 mA | | |
| 1 (load 15 V) | | | 11 mA | | |
| 8 (load 15 V) | | | 18 mA | | |

## §6.3 Load step (0.8 ↔ 7.2 A)

| V_set | Edge | Peak deviation (%) | Recovery to ±1 % (µs) | Ringing? | Capture |
|---|---|---|---|---|---|
| 12 | up | | | | |
| 12 | down | | | | |
| 5 | up | | | | |
| 5 | down | | | | |
| 18 | up | | | | |
| 18 | down | | | | |

## §6.4 Crossover (12 V / 4 A, corner 3 Ω)

| R (Ω) | V | I | EA_V / EA_I oscillation? |
|---|---|---|---|
| 6 | | | |
| 4 | | | |
| 3.5 | | | |
| 3.2 | | | |
| 3.1 | | | |
| 3.0 | | | |
| 2.9 | | | |
| 2.8 | | | |
| 2.5 | | | |
| 2 | | | |
| 1.5 | | | |

Corner: at I = 3.96 A, V = ______ (≥ 11.88 V to pass)

## §6.5 Bode

| Loop | Crossover | Phase margin | Gain margin | Capture |
|---|---|---|---|---|
| Inner (target 25–40 kHz) | | | | |
| Outer CV (target 1–3 kHz) | | | | |
| Outer CC (target 1–3 kHz) | | | | |

Calibration re-check after rework: ______

## §6.6 Ripple

| Point | Vpp | Capture |
|---|---|---|
| 18.75 V / 8 A | | |
| 12 V / 8 A | | |
| SW ringing frequency | | |

## §6.7 DEM battery

| Step | Result |
|---|---|
| Disabled: battery → J4 current | |
| Enabled, V_set 11 V: current over 1 min | |
| Inrush peak at output close (with 0.5 Ω) | |
| Charge: CC current, CC→CV time, CV voltage, oscillation? | |

## §6.8 Thermal soak (18.75 V / 8 A)

| Minute | T_fet | T_ind | R30 (TC) | U3 (TC) | Warn bits |
|---|---|---|---|---|---|
| 0 | | | | | |
| 5 | | | | | |
| 10 | | | | | |
| 15 | | | | | |
| 20 | | | | | |
| 30 | | | | | |
| 40 | | | | | |
| 50 | | | | | |
| 60 | | | | | |

## §6.9 Fault injection

| Row | Injection | Specified (docs/04) | Observed | Match? |
|---|---|---|---|---|
| 2 | R8 lifted, load 2 → 9 A | latch OCP_BACKUP, output open | | |
| 4 | R2 shorted | disconnect open at ~22.3 V, EN low, latched | trip V: / time: / after: | |
| 11 | 1.2 kΩ across RT1 | DERATE warn, I limit falls, fan 100 % | T reported: | |
| 12 | 750 Ω across RT1 | output off, OTP latched | T reported: | |
| 14 | heartbeat stopped, policy off | COMMS_LOST, output off after 3 s | time: | |
| 14 | heartbeat stopped, policy hold | COMMS_LOST, output stays on | | |

## §6.10 MCU crash

| Check | Result |
|---|---|
| DBGMCU_APB1FZR1 bit 12 clear | |
| Output during halt (and load-change response) | |
| Halt → IWDG reset time | |
| Output at reset | |
| State after boot | |

## Failures and proposed changes

| Row | Measured | Suspected cause | Proposed change |
|---|---|---|---|
| | | | |
