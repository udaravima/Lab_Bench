# 12 — Phase-1 Bench Test Procedure

The procedure for proving a built Phase-1 module (150 W, 0–20 V / 0–8 A)
against the exit criteria in [docs/05](05-build-plan.md#phase-1--150-w-prototype-module-the-learning-board).
Start here once the board has passed the first power-up in
[docs/11 §7](11-build-guide.md#7-firmware-and-first-power-up): rails good,
firmware flashed, HELLO seen on CAN.

Work through the sections in order. Each one depends on the last: there is no
point measuring accuracy before calibration, or ripple before the loop is
known to be stable.

**Recording.** Copy [test-results/phase1-results-template.md](test-results/phase1-results-template.md)
to `docs/test-results/phase1-<board serial>-<date>.md` and fill it in as you
go. Save scope captures and CAN logs next to it. When every row passes, tag
the commit `phase1-pass` (docs/05, repo workflow).

> **Protection gaps closed in firmware 0.2 (2026-09-28).** Two exit tests
> (§6.9) used to be expected to fail; both are now fixed and should pass.
> - Row 2 (OCP backup): the firmware now checks the INA240 current on the ADC
>   every 1 ms and also programs the INA228 alert limit (SOVL) to the same
>   8.8 A; either one held for more than 5 ms latches `OCP_BACKUP`.
> - Row 4 (hardware OVP): the TLV7011 output (OVP_TRIP) now also goes to the
>   MCU's PB4. Its rising edge interrupts the MCU, which pulls LM5145 EN low
>   and latches `OVP_HW`. The comparator still opens the disconnect by itself.
>   This needs the board revision that routes OVP_TRIP to U10 pin 41; on an
>   older board PB4 is unconnected and row 4 stays non-latching.

## 1. Equipment

| Item | Used for | Minimum |
|---|---|---|
| Bench supply | Module input | 24 V, ≥ 10 A, adjustable current limit |
| Electronic load | All loaded tests | ≥ 150 W, 20 V / 10 A, CC/CR modes, dynamic (step) mode with adjustable slew |
| 6.5-digit DMM | Calibration and accuracy | Kelvin (4-wire) leads or short twisted leads to J4 |
| Current reference | CC accuracy | A 4-terminal shunt (e.g. 10 mΩ, ≤ 0.02 %) read by the DMM. A DMM's own 10 A range is not accurate enough |
| Oscilloscope | Transients, ripple, fault timing | ≥ 100 MHz, 20 MHz BW limit, 4 channels helps |
| Current probe or shunt + differential probe | Load-step and fault timing | |
| Loop analyser | Bode | Injection transformer + scope FRA, or a Bode-capable analyser |
| USB-CAN adapter | Control | 500 kbit/s, SocketCAN (`can0`) |
| ST-Link + OpenOCD/GDB | MCU crash test | |
| Thermocouple meter | Thermal soak | 2+ channels |
| 12 V lead-acid battery | DEM test | Sacrificial; plus an inline fuse (≤ 10 A) |
| Resistors | Fault injection | 1.2 kΩ, 750 Ω (NTC emulation); 10 Ω 0603/0805 ×2 (Bode injection) |

**Why the current reference matters.** The CC spec is ±(0.1 % + 10 mA). A
measurement is only useful if it is several times better than what it checks
(a 4:1 ratio is the usual rule). A typical 10 A DMM range is ±0.2 % or worse,
which cannot tell a pass from a fail. A calibrated shunt read on the DMM's
100 mV range can.

## 2. Setup

### 2.1 Wiring

- J1: bench supply, 24 V. Current limit 3 A for §4–§5, raise to 10 A from §6.
- J4: electronic load, with the DMM sense leads landing **on the J4
  terminals themselves**, not at the load. The module regulates at J4 (the
  measurement divider R32/R33 taps VOUT there), so that is where accuracy is
  defined.
- J5: CAN harness with termination; HW_EN (J5.3) to 3V3 through 1 kΩ **via a
  switch**. That switch is the bench E-stop: opening it turns the converter and
  the disconnect off in hardware.
- J6: 5 V fan pointed at the power stage (Q1/Q2, L1).
- J3: UART log open at 115200 throughout; it catches resets.

### 2.2 CAN control

All frames are for slot 0 (all J5 slot straps open). The helper
`firmware/tools/lbcan.py` (Python 3, no dependencies) builds the frames and
decodes the traffic, so nothing is hand-encoded:

```bash
sudo ip link set can0 up type can bitrate 500000
alias lb='python3 firmware/tools/lbcan.py'

candump -L can0 | lb dec --only TELEM_VI TELEM_AUX STATUS FAULT   # terminal 1

# terminal 2: the manager heartbeat — REQUIRED, see below
while true; do cansend can0 $(lb enc heartbeat); sleep 1; done
```

**Why the heartbeat is required.** Without a manager, the module sees no
GLOBAL_STATE frames. After 3 s of silence it applies its comms-loss policy,
which defaults to "output off" (docs/03 §6). Keep the heartbeat loop running
for every test except the one that deliberately kills it (§6.9).

Frames used in this procedure (slot 0):

| Action | Command | Frame |
|---|---|---|
| Set 5 V, 1 A | `lb enc setvi 5 1` | `100#404B4C0040420F00` |
| Output on | `lb enc output on` | `101#01` |
| Output on, DEM (battery) | `lb enc output dem` | `101#02` |
| Output off | `lb enc output off` | `101#00` |
| Limits 150 W, derate 85 °C, policy hold | `lb enc limits 150 85 hold` | `102#F049020052030100` |
| Calibration write | `lb enc cal vset gain 65536` | `103#000100000100` |
| Clear latched faults | `lb enc reset clear` | `105#5A` |
| Reboot | `lb enc reset reboot` | `105#A5` |
| Heartbeat | `lb enc heartbeat` | `021#00000000` |

Send with `cansend can0 <frame>`, e.g. `cansend can0 $(lb enc setvi 12 2)`.

What comes back: TELEM_VI (`300`, 10 Hz: V and I from the INA228), TELEM_AUX
(`301`: NTC temperatures, bus voltage, power), STATUS (`302`, 2 Hz: state,
fault, warn and mode bits, setpoint echo), and FAULT (`010`) on any change.

**Envelope.** Firmware clamps the current setpoint to min(8 A, 150 W / V).
Full power is 18.75 V × 8 A. The voltage DAC's full scale corresponds to
about 19.95 V before calibration, so aim at 19.5 V as the top test point.

### 2.3 Probe points

The board has no dedicated test points (docs/06 §8 planned them; they did not
make it into the layout). Probe on component pads:

| Signal | Where | Notes |
|---|---|---|
| SW | L1 switch-side pad, or Q2 drain | Use the probe's ground spring, not the lead |
| FB | R2 pad 1 (R2 pad 2 is AGND) | Sits at 0.8 V when regulating |
| EA_V_OUT / EA_I_OUT | D1 pin 1 / D2 pin 1 (anodes) | The active loop's amp sits higher |
| V_MEAS / I_MEAS | R33 pad 1 / R31 pad 2 | 0.125 V per output V; 0.2 V per A |
| V_REF / I_REF | R3 pad 1 / R6 pad 1 | DAC outputs |
| PS_EN | R21 pad 1 | LM5145 enable |
| PS_PGOOD | R18 pad 2 | |
| OUT_REQ | R43 pad 1 | MCU request to close the disconnect |
| OVP_TRIP | Q9 pin 1 (gate) | Comparator output |
| HW_EN | J5.3 | |
| 5V0 / 3V3 | J6.1 / J2.1 | |

Measure against AGND (J2.5 or R2 pad 2) for the analog signals, PGND (J1.2)
for SW. The disconnect gate (Q3/Q4 pin 1) is referenced to their common
source, not ground: measure it differentially.

## 3. Safety rules for this bench

- The HW_EN switch is within reach for every powered test.
- Before touching a probe on the power stage, output off **and** HW_EN open.
- The input TVS (D5) is 33 V. Never set the bench supply above 30 V; the OVP
  test in §6.9 runs at 24 V only (the output caps are 25 V parts).
- The battery test (§6.7) uses an inline fuse. Batteries do not have a
  current limit.

## 4. First output enable

Current limit 3 A, no load connected, heartbeat running.

1. With HW_EN **open**, send `setvi 5 0.5` then `output on`. The command must
   be refused: STATUS stays SAFE, J4 stays at 0 V. This proves the hardware
   interlock.
2. Close HW_EN. Send `output on` again. Expect:
   - STATUS `state=ACTIVE mode=OUT_ON`, LED solid;
   - PS_EN rises, then PS_PGOOD, then OUT_REQ;
   - V_REF ramps (1 V/ms in output terms, about 5 ms to reach 5 V);
   - J4 ≈ 5 V (±1–2 % before calibration).
3. Scope the output while sending `output on` a few times: record the
   turn-on overshoot. There should be none beyond a few tens of mV.
4. Step the setpoint: 1 V, 5 V, 10 V, 15 V, 19.5 V. Each should settle
   cleanly. Record uncalibrated error at each (useful for the calibration in
   §5).
5. Open HW_EN with the output on. The output must drop at once (the E-stop
   path is hardware: HW_EN → Q6 → D4 → Q5/Q7). Record the time from HW_EN
   falling to VOUT < 10 % on the scope. docs/05 asks for < 1 ms at Phase 3;
   record it now for reference.
6. Close HW_EN again. The module is now SAFE; send `output on` to resume.

If step 2 fails, check each link of that chain in order: PS_EN (R21 pad 1),
PS_PGOOD, OUT_REQ, then the disconnect gate.

## 5. Calibration

The firmware corrects each path with `y = x · gain / 65536 + offset`
(`lb_cal_apply`). Gain 65536 means 1.0; offsets are in µV (voltage items) or
µA (current items). Each `CAL_WRITE` is stored to flash immediately.

**Which items matter.** VSET and ISET trim the DAC setpoints, which is what the
CV/CC accuracy criteria measure. VMEAS and IMEAS trim only the MCU's ADC path,
which the firmware uses as a fallback and as the sense cross-check. Telemetry
(TELEM_VI) reports the INA228 directly and is **not** calibrated in firmware
0.1, so its readback error is recorded in §6.1 as an observation, not trimmed.

### 5.1 Start from identity

```bash
for it in vset iset vmeas imeas; do
  cansend can0 $(lb enc cal $it gain 65536); sleep 0.2
  cansend can0 $(lb enc cal $it offset 0);   sleep 0.2
done
```

### 5.2 Voltage (VSET)

Load: 0.5 A (so the preload and DEM do not matter). Current setpoint 2 A.

1. `setvi 2 2`, measure J4 with the DMM: that is M1 at S1 = 2 V.
2. `setvi 18 2`, measure: M2 at S2 = 18 V.
3. Compute, in volts:
   ```
   a = (M2 − M1) / (S2 − S1)          # actual volts per requested volt
   b = M1 − a · S1                    # actual volts at a request of 0
   gain   = round(65536 / a)
   offset = round(−b / a · 1e6)       # µV
   ```
4. `cal vset gain <gain>`, `cal vset offset <offset>`.
5. Re-measure at 2 V and 18 V. Both should now be within ±(0.05 % + 5 mV).
   If not, repeat once from the new values (a second pass absorbs any
   non-linearity near the ends).

### 5.3 Current (ISET)

Load in CV mode at about 5 V (so the module runs in CC); voltage setpoint
10 V. Measure current with the reference shunt.

1. `setvi 10 0.5`: M1 at S1 = 0.5 A.
2. `setvi 10 7`: M2 at S2 = 7 A.
3. Same formulas, offset in µA. Write `cal iset gain` / `cal iset offset`.
4. Re-measure both points.

### 5.4 Persistence

Power-cycle the module. Re-measure one voltage and one current point: they
must match the calibrated values. If they revert, the flash write failed;
check the UART log.

## 6. Exit tests

Each subsection is one row of the docs/05 table. The pass criterion is quoted
at the top.

### 6.1 CV accuracy — pass: ±(0.05 % + 5 mV), 0.5–20 V, 0–8 A

Current setpoint at the envelope limit for each voltage. Measure at J4 with
the DMM at each point:

| V_set | Loads |
|---|---|
| 0.5, 1, 2, 5 | 0 A, 4 A, 8 A |
| 10, 15 | 0 A, 4 A, 8 A |
| 18.75 | 0 A, 4 A, 8 A (150 W) |
| 19.5 | 0 A, 3.8 A, 7.6 A (envelope) |

Allowed error = 0.0005 · V_set + 0.005 V (e.g. ±7.5 mV at 5 V, ±14.4 mV at
18.75 V). Also record the TELEM_VI voltage and current at each point: that is
the uncalibrated INA228 readback error.

Change in output from 0 A to full load at the same setpoint is the load
regulation; it should be well inside the accuracy band, because the divider
taps J4 after the shunt and disconnect.

### 6.2 CC accuracy — pass: ±(0.1 % + 10 mA), 0.1–8 A

Load in CV mode at 5 V; voltage setpoint 10 V. Current setpoints 0.1, 0.5, 1,
2, 4, 6, 8 A. Measure with the reference shunt. Allowed error =
0.001 · I_set + 0.010 A (±11 mA at 1 A, ±18 mA at 8 A).

Repeat 1 A and 8 A with the load at 15 V (8 A is then clamped to 150/15 =
10 A → stays 8 A; confirm).

### 6.3 Load step — pass: recovery to ±1 % in < 200 µs, overshoot < 2 %, no ringing

Setpoint 12 V / 8 A. Load in dynamic CC mode, 0.8 A ↔ 7.2 A (10 ↔ 90 %),
slew 1 A/µs or the load's fastest, 1 kHz or slower.

Scope: output at J4, AC coupled, 20 MHz BW; load current on a second channel.
Trigger on the current edge. For both edges record: peak deviation (% of
12 V), time to get back within ±120 mV, and whether it rings (more than one
visible overshoot cycle).

Repeat at 5 V and 18 V (the latter 0.8 ↔ 7.2 A still fits the envelope).

### 6.4 CV↔CC crossover — pass: monotonic, no oscillation, corner sharp within 1 %

Setpoint 12 V / 4 A. The corner is at 3 Ω. Load in CR mode, sweep from 6 Ω
down to 1.5 Ω in steps (0.1 Ω steps between 3.5 and 2.5 Ω). At each step
record V (DMM) and I (TELEM_VI or reference shunt), and watch EA_V_OUT and
EA_I_OUT (D1, D2 anodes) on the scope.

Pass when:
- V decreases and I increases monotonically through the sweep;
- neither amp output shows oscillation at any step, especially right at the
  corner where both are close to conducting;
- "sharp": at the step where I first reaches 99 % of 4 A, V is still ≥ 99 %
  of 12 V.

If the handover from one loop to the other overshoots, that is the anti-windup
question in docs/06 §10 item 5. Record the overshoot on the scope.

### 6.5 Loop Bode — pass: phase margin ≥ 55°, gain margin ≥ 10 dB, both outer loops

The board has no injection resistors, so each measurement needs a small
rework: lift one end of a resistor and bridge the gap with a 10 Ω resistor.
Inject across the 10 Ω with the transformer; measure A on the injection
side and B on the far side.

| Loop | Break point | Operating point |
|---|---|---|
| Inner (LM5145) | Between VOUT_INT and R1 pad 1 | 12 V / 8 A set, 4 A load |
| Outer CV | Between VOUT (J4 side) and R32 pad 1 | 12 V / 8 A set, 4 A load (in CV) |
| Outer CC | In series with R31, at the I_MEAS end (pad 2) | 4 A set, load in CV at 6 V (in CC) |

Sweep 100 Hz – 200 kHz with a small injection amplitude (start at a few tens
of mV and check that the reading does not change when you halve it). Record
crossover frequency, phase margin and gain margin for each.

Targets from docs/06 §6: inner crossover 25–40 kHz; outer crossovers
1–3 kHz. The exit criterion applies to both outer loops. The inner-loop
numbers decide the final Type-III values (docs/06 §10 item 1).

Put each resistor back afterwards and repeat one point of §6.1 to confirm the
rework did not shift calibration.

### 6.6 Ripple — pass: < 20 mVpp at the output terminals

Setpoint 18.75 V / 8 A (full power) and 12 V / 8 A (largest inductor ripple,
D = 0.5). Probe at J4 with a tip-and-barrel or a 50 Ω coax pigtail, 20 MHz
bandwidth limit, AC coupled. Record Vpp and a capture for both points.

While here, capture the SW node ringing frequency: it sets the snubber
(C17/R17, docs/06 §10 item 4).

### 6.7 DEM battery test — pass: zero reverse current when disabled and when enabled with battery above V_set; clean CC→CV charge

Connect a 12 V lead-acid battery to J4 through an inline fuse, with the
current measured in series (reference shunt or current probe). Set the
module's policy to hold for the charge run: `limits 150 85 hold`.

1. **Disabled.** Output off, HW_EN open. Measure current from the battery
   into J4. Only the V_MEAS divider (R32 + R33 ≈ 80 kΩ) should draw from the
   output: about 0.16 mA at 12.7 V. Anything more is leakage through the
   disconnect.
2. **Enabled, battery above setpoint.** `setvi 11 1`, `output dem`. The
   stage cannot sink in DEM, so the battery current must stay at the step-1
   value. Record it for 1 minute.
3. **Charge.** `setvi 13.8 1`, `output dem` (if the battery is well charged,
   discharge it a bit first). Log with `candump -L can0 | lb dec --csv`.
   Expect CC at 1 A with STATUS mode `CC` set, then a smooth transition to CV
   at 13.8 V with current tapering. Record the time of the transition and
   confirm no oscillation at the handover.
4. Optional: a Li-ion pack **with its own BMS**, at its CV voltage and a low
   current.

**Watch the moment the output closes.** The disconnect closes once PGOOD is
up, while the reference is still ramping from zero. With a battery already on
J4, the battery then charges the module's output capacitors (about 500 µF)
through the disconnect FETs. That inrush is limited only by battery and FET
resistance. This is predicted from the firmware and schematic, not yet
measured. For the first run, put a 0.5 Ω power resistor in series with the
battery, scope the current at turn-on, and record the peak.

### 6.8 Thermal soak — pass: all NTCs < 70 °C after 1 h at 150 W, with fan

Setpoint 18.75 V / 8 A, load in CC at 8 A, fan on, open bench, record ambient.
Log TELEM_AUX (T_fet, T_ind) throughout:

```bash
candump -L can0 | lb dec --csv --only TELEM_AUX TELEM_VI > soak.csv
```

Add thermocouples on the shunt R30 and the controller U3, which have no NTC.
Record every 5 minutes. Pass if both NTC readings stay below 70 °C at 60 min.
Also record whether the firmware warn bit `DERATE` ever appeared (it should
not; derating starts at 85 °C).

### 6.9 Fault injection — pass: protection matrix rows 2, 4, 11–14 behave as specified

For each row: what to do, what docs/04 says should happen, and what to
record. Clear latched faults with `reset clear` and re-enable between rows.

**Row 2 — OCP backup (loop failure).** Break the CC loop by lifting R8
(EAI_INJ → FB). Setpoint 12 V / 4 A. Load in CC, step from 2 A to 9 A.
- Spec: MCU detects > 110 % I_max (8.8 A) for > 5 ms, opens the output and
  latches OCP_BACKUP.
- Predicted (firmware 0.2): latches `OCP_BACKUP` about 5 ms after the
  current passes 8.8 A, from the ADC check or the INA228 alert, whichever
  sees it first. The LM5145 valley current limit (~11 A) remains the
  backstop behind it.
- Record: whether FAULT `OCP_BACKUP` appears, and the output current and
  voltage. Keep this short; do not leave it at 9 A for long. Refit R8.

**Row 4 — hardware OVP.** Input 24 V only. Setpoint 5 V, load 0.5 A. Short
R2 (FB to AGND) with a switched wire. The controller then sees FB at 0 V and
drives the output towards the input voltage.
- Spec: TLV7011 trips at 105 % of 21.2 V ≈ 22.3 V (R45/R46 from VOUT_INT
  against the 2.5 V reference R47/R48), the disconnect opens, the controller
  is disabled, and the fault latches.
- Predicted (firmware 0.2, OVP_TRIP routed to PB4): the disconnect opens at
  ~22.3 V; within microseconds the MCU kills EN, so VOUT_INT falls; FAULT
  `OVP_HW` latches and stays latched after the short is removed until
  `reset clear`. A `reset clear` while VOUT_INT is still above the threshold
  re-latches at once.
- Record on the scope: VOUT_INT (R1 pad 1), VOUT (J4), OVP_TRIP (Q9 gate),
  PS_EN (U3 pin 1). Trip voltage, time from threshold to disconnect open,
  time from OVP_TRIP to PS_EN low, and state after the short is removed.

**Rows 11 and 12 — overtemperature.** Emulate a hot NTC by clipping a
resistor across RT1 (NTC_FET), rather than heating the board. At ~25 °C the
NTC is 10 kΩ, so (values from the B3950 curve):

| Emulated temperature | Parallel resistor |
|---|---|
| ~85 °C (derate starts) | 1.2 kΩ |
| ~100 °C (shutdown) | 750 Ω |

Setpoint 12 V / 4 A, load at 3 A.
- 1.2 kΩ: T_fet reads about 85 °C, warn `DERATE` appears, the effective
  current limit starts to fall, fan goes to 100 %. Remove it: warn clears.
- 750 Ω: T_fet reads ≥ 100 °C, output off, FAULT `OTP` latched. With the
  resistor still fitted, `reset clear` must not leave the module running (the
  fault re-latches on the next tick). Remove the resistor, then `reset clear`
  clears it. docs/04 says clearing needs < 70 °C; firmware 0.1 only re-latches
  at ≥ 100 °C, so note the actual behaviour.
- Record the reported temperature, the bits, and the output current at each
  step.

**Row 13 — MCU hang.** Covered by §6.10.

**Row 14 — manager silent.** Setpoint 12 V / 1 A, output on.
- Stop the heartbeat loop. Spec: after 3 s, warn `COMMS_LOST`, output off
  (policy off, the default). Record the time from the last heartbeat to the
  output falling.
- Send `limits 150 85 hold`, restart the heartbeat, turn the output on, stop
  the heartbeat again. Spec: `COMMS_LOST` appears but the output stays on.
  Restart the heartbeat: the warn clears.

### 6.10 MCU crash — pass: output keeps regulating while the MCU is halted; IWDG reboots into SAFE

Setpoint 12 V / 4 A, load at 3 A. Connect the ST-Link and attach OpenOCD
(`openocd -f interface/stlink.cfg -f target/stm32g4x.cfg`) and GDB.

1. OpenOCD's STM32 scripts may freeze the watchdog while the core is halted,
   which would hide the IWDG reset. Before halting, make sure bit 12
   (DBG_IWDG_STOP) of DBGMCU_APB1FZR1 at `0xE0042008` is **clear**:
   `monitor mdw 0xE0042008`, and if needed `monitor mww 0xE0042008 <value
   with bit 12 cleared>`. (Register address from RM0440; check it against
   your copy.)
2. `monitor halt`. Scope J4. While halted, the DAC holds its last value and
   the analog loops keep regulating: the output must stay at 12 V and
   respond to a load change.
3. About 500 ms after the halt, the IWDG resets the MCU. At reset the MCU pins
   float: R44 pulls the disconnect request low, so the output opens, and the
   firmware boots into SAFE (LED 2 Hz, HELLO on CAN, UART banner).
4. Record: output during the halt, time from halt to reset, the output at
   reset, and the state after boot.

If the reset never comes, the watchdog is frozen (step 1), not broken.

## 7. After the tests

- Fill in the summary table of the results file, with a pass/fail per row
  and links to captures.
- Every failing row gets a note: measured value, suspected cause, and the
  change proposed (schematic, layout, firmware, or the spec itself).
- If all rows pass: commit the results, tag `phase1-pass`, and Phase 2 can
  spend money.
