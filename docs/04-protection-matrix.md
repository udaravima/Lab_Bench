# 04 — Protection Matrix

Layering rule: **anything that can destroy hardware or a battery is handled in
hardware; firmware only adds slower backup and reporting.** The analog CV/CC
loops are themselves the first protection layer.

| # | Fault | Detected by | Response | Latching | Recovery |
|---|---|---|---|---|---|
| 1 | Output overcurrent (normal) | Analog CC loop (INA240 → EA_I) | Seamless CV→CC transition at I_set | No | Automatic (it's regulation, not a fault) |
| 2 | Output overcurrent (loop failure backup) | MCU ADC watchdog on INA240, >110 % I_max for >5 ms | Output FETs open, LM5143 disabled | Yes | `RESET(0x5A)` after cause cleared |
| 3 | Per-phase overcurrent (shoot-through, saturation) | LM5143 cycle-by-cycle current limit + hiccup | Cycle truncation → hiccup restart | No (hiccup) | Automatic; MCU reports if persistent >100 ms |
| 4 | Output overvoltage | Hardware comparator (TLV7011, fixed 105 % V_max) — independent of MCU | Output disconnect FETs open + controller EN low | Yes | `RESET(0x5A)`; requires V_out below threshold |
| 5 | Output overvoltage (setpoint sanity) | Module firmware clamp | I_set/V_set clamped to envelope: I ≤ min(30 A, 600 W/V) | No | n/a — clamp, report in STATUS warn bits |
| 6 | Battery back-feed into disabled output | Back-to-back output FETs (blocking both directions) | Inherently blocked | n/a | n/a |
| 7 | Reverse current while enabled (battery > V_set) | DEM mode (LM5143 DEMB) — stage cannot sink | Inherently blocked in battery mode; firmware warns if I_meas < −200 mA in non-DEM mode and opens FETs | Yes (non-DEM case) | `RESET(0x5A)` |
| 8 | Input overvoltage (>33 V) | LM5069 OVP pin | Module input disconnected | No (follows condition) | Automatic when bus back in range |
| 9 | Input undervoltage (<10.5 V) | LM5069 UVLO | Module input disconnected / no start | No | Automatic |
| 10 | Inrush / input short / input overcurrent | LM5069 current limit + circuit-breaker timer; upstream 35 A blade fuse | Power-limited inrush; breaker trip on fault; fuse as last resort | LM5069: retry per config; fuse: replace | Per condition |
| 11 | Overtemperature — derate | NTCs (FET, inductor, shunt) ≥ 85 °C | Firmware progressively lowers effective I_set; fan to 100 % | No | Automatic below hysteresis |
| 12 | Overtemperature — shutdown | Any NTC ≥ 100 °C | Output off, controller disabled | Yes | `RESET(0x5A)` below 70 °C |
| 13 | MCU hang | IWDG watchdog | MCU reset → boots into SAFE (output off, DAC reset to 0) | Effectively | Automatic reboot; manager sees HELLO |
| 14 | Manager silent | Missing GLOBAL_STATE > 3 s | Comms-loss policy: default output off; optional hold (battery runs) | No | Automatic on manager return |
| 15 | Module silent | Missing STATUS > 1 s (manager side) | Alarm, channel marked lost, removed from budget; optional group shutdown if in parallel group | Manager-side | Automatic on module return |
| 16 | E-stop / system kill | /HW_ENABLE pulled low (manager, panel switch) | All outputs off **in hardware** (gates EN + disconnect driver on every module) | While low | Release line; modules re-enter SAFE, wait for commands |
| 17 | Budget exceeded | Manager arbiter (module telemetry + bus INA228) | Refuse new enables/raises; per-policy derate or shed lowest-priority channel | No | Automatic |
| 18 | Sense chain implausible (INA228 vs INA240 disagree > 5 %, or NTC open/short) | Module firmware cross-check | Output off, fault report | Yes | `RESET(0x5A)`; likely hardware service |
| 19 | Setpoints on power-up | DAC80502 power-on-reset = 0 V/0 A; state machine boots into SAFE | Output cannot enable until manager configures | n/a | n/a |

## Design notes

- Faults 2, 4, 7, 12, 18 latch because they indicate something *broken*, not
  something *operating at a limit*. Latched faults repeat on CAN at 1 Hz
  (protocol doc §2) and require an explicit operator clear.
- The hardware OVP (fault 4) threshold is fixed by resistors at 105 % of the
  module's absolute V_max, not the current setpoint — it is a catastrophic-
  failure backstop (e.g. CV loop open), not a user-range protection. Tight
  user-level OVP is a firmware warn/trip configured via LIMITS if desired.
- Battery work always uses `OUTPUT(on+DEM)` mode: source-only power stage
  (fault 7) plus blocking disconnect when off (fault 6) means no path ever
  drains or back-feeds the pack.
- The E-stop line is deliberately **listen-only for modules**: a single failed
  module cannot kill the whole rack; only the manager/panel can.
