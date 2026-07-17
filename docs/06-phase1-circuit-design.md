# 06 — Phase 1 Circuit Design (150 W Prototype)

Worked component values and the reasoning behind them. This is the document the
KiCad schematic gets drawn from. Values marked **(bench)** are starting points
expected to be tuned during bring-up.

## 1. Targets

| Parameter | Value |
|---|---|
| Input | 24 V bench supply (circuit tolerates 12–30 V) |
| Output | 0.5–20 V guaranteed (lower reachable in FPWM), 0–8 A, 150 W envelope |
| Switching frequency | 350 kHz |
| Ripple | < 20 mVpp at terminals |
| Accuracy after cal | ±(0.05 % + 5 mV) V, ±(0.1 % + 10 mA) I |

> **Why 0.5 V minimum?** A buck can't make arbitrarily short switch pulses —
> the LM5145 has a minimum on-time of ~100 ns. At 350 kHz that's ~1.5 % duty →
> ~0.4 V at 24 V in. Below that the controller must skip pulses; regulation gets
> coarse. Honest spec: guarantee 0.5 V, note it goes lower in forced-PWM.

## 2. Power stage

### Inductor
Ripple current target ~30 % of I_max. Worst case is D = 0.5 (V_out = 12 V @ 24 V in):

```
ΔI = V_out·(1−D)/(L·fsw)  →  L = 12·0.5/(350k·2.4) ≈ 7.1 µH  →  pick 10 µH
```

With 10 µH: ΔI = 1.7 A at 12 V out (21 %), 0.95 A at 20 V out.
Peak current 8 + 1.7/2 ≈ **8.9 A → I_sat ≥ 12 A**, low-DCR (< 10 mΩ) flat-wire,
e.g. Würth 744325550 class.

### Capacitors
- **Output:** 2 × 220 µF 25 V polymer (≈ 7.5 mΩ ESR combined) + 4 × 22 µF X7R MLCC.
  Ripple ≈ ESR·ΔI ≈ 7.5 mΩ · 1.7 A ≈ 13 mVpp ✓.
  LC corner: f_LC = 1/(2π√(10 µH · ~480 µF)) ≈ **2.3 kHz**;
  ESR zero ≈ 1/(2π·7.5 mΩ·440 µF) ≈ **48 kHz** — both needed for compensation (§6).
- **Input:** 4 × 22 µF 50 V X7R close to the FETs (input RMS ripple ≈ I_out/2 = 4 A
  at D = 0.5) + 220 µF 50 V electrolytic bulk.
- **Preload:** 2.2 kΩ across the output — gives DEM mode a minimum load so the
  output doesn't drift up at zero load, and discharges the caps when disabled.

### FETs & controller housekeeping
- FETs: 60 V, ≤ 10 mΩ, PowerPAK/SO-8 5×6 pair — e.g. CSD18563Q5A / BSC070N06 class.
  (60 V on a 30 V max bus = headroom for switch-node ringing.)
- LM5145 RT resistor per datasheet equation for 350 kHz.
- LM5145 valley current limit (low-side RDS(on) sensing via ILIM resistor) set
  ≈ 11 A — this is the *hardware* backstop; the precision limit is the CC loop.
- DEM/FPWM pin driven by MCU GPIO (battery mode = DEM, see protection matrix #7).

## 3. Sense & setpoint scaling

One diagram to keep all the scale factors straight:

```
                          0–20 V                       0–8 A
 V_out ──[69.8k]──┬── V_meas = V_out/8 (0–2.5 V)   shunt 2 mΩ ──► INA240A3 (×100)
                [10.0k]      │        │                              │
                  ─┴─        ▼        ▼                        I_meas = 0.2 V/A
                        EA_V (+in)  MCU ADC                       (0–1.6 V)
                                                                  │        │
 DAC80502 (16-bit, 2.5 V FS)                                      ▼        ▼
   ch A: V_ref 0–2.5 V  ≡ 0–20 V   (0.305 mV/LSB)            EA_I (−in)  MCU ADC
   ch B: I_ref 0–2.5 V  ≡ 0–12.5 A (0.19 mA/LSB, fw-clamped to 1.6 V = 8 A)
```

- **Measurement divider:** 69.8 kΩ / 10.0 kΩ, **0.1 % thin-film** — this divider
  (not the controller's) defines voltage accuracy; calibration absorbs the
  residual ratio error. Kelvin-routed from the output terminals.
- **Shunt:** 2 mΩ, 1 W, 2512 wide-terminal metal element, Kelvin pads.
  16 mV drop at 8 A → 128 mW dissipation. INA240A3 (gain 100) → 0.2 V/A.
  INA240 is unidirectional here (REF pins to GND) — the stage is source-only.
- **INA228** across the same shunt + V_out sense for telemetry (ADCRANGE = ±40.96 mV).
- **DAC80502** (dual 16-bit, SPI, internal 2.5 V ref, gain ×1): powers up at
  zero-scale → both references demand 0 V / 0 A at boot. Safe by construction.
  Runs on the **3V3 rail** (logic thresholds scale with VDD; the STM32 talks
  3.3 V — at VDD 5 V its V_IH would exceed the MCU's swing). The 2.5 V internal
  reference keeps enough headroom at 3.3 V. Straps: RSTSEL→AGND (POR to
  zero-scale), SPI2C strap level for SPI mode **verify against datasheet**;
  REFIO decoupled with 150 nF.

## 4. Control core — base divider + FB injection

The LM5145 always regulates its FB pin to 0.8 V. We give it a fixed divider that
would produce **maximum** output, then the outer error amps *inject current into
the FB node through a diode-OR* to pull the output down to the setpoint:

```
 V_out ──[R_top 25.5k]──┬────────── FB (LM5145, wants 0.8 V)
                        │
                 [R_bot 1.00k]          EA_V ──▶|──[R_inj 3.9k]──┐
                        │                                        ├── same FB node
                       GND              EA_I ──▶|──[R_inj 3.9k]──┘
```

**Base divider:** V_max_hw = 0.8 · (1 + 25.5k/1.0k) = **21.2 V** — the absolute
hardware ceiling regardless of firmware.

**Injection math** (FB node current balance, FB held at 0.8 V):

```
V_out = 0.8 + R_top·[ 0.8/R_bot − I_inj ]
```

- No injection (both diodes off): V_out = 21.2 V.
- To force V_out → 0: I_inj = 0.8/R_bot + 0.8/R_top ≈ 0.83 mA.
  With EA swinging to ~4.5 V minus a Schottky drop (~0.4 V):
  R_inj = (4.1 − 0.8)/0.83 mA ≈ 3.97 kΩ → **3.9 kΩ** (slight extra authority).
- Sanity: holding 20 V needs I_inj ≈ 47 µA (EA at ~1.4 V); holding 0.5 V needs
  ≈ 0.81 mA (EA at ~4.4 V) — both inside a 5 V rail-to-rail amp's swing. ✓

> **Why the diode drop and the controller's ±1 % reference don't hurt accuracy:**
> both are *inside* the outer integrator's loop. The EA keeps injecting until
> V_meas exactly equals V_ref — diode drop, controller reference error, and
> R_inj tolerance only change *how much* the EA outputs, not where the output
> settles. Accuracy is owned entirely by the 0.1 % divider, the DAC, and the
> EA's µV-class input offset. This is the whole reason for outer loops.

**Min-selector behaviour:** whichever amp demands the lower output sources more
injection current and forward-biases its diode; the loser's diode reverse-biases
and it rails low. CV↔CC crossover is automatic and analog.

## 5. Error amplifiers

**Op-amp:** OPA2333 (zero-drift, true rail-to-rail I/O, 350 kHz GBW, 10 µV max
offset, 5.5 V max supply) on the 5 V rail — one dual package.
*Why not OPA2189 (the original pick):* the OPAx189 input common-mode range
stops ~2.5 V below V+ — on a 5 V rail that collides exactly with our 2.5 V
full-scale V_MEAS/V_REF signals (and violates outright when the rail sags).
350 kHz GBW still leaves >40 dB of loop gain at the 1–3 kHz outer crossover.

**Topology (both loops):** integrator with a zero, polarity chosen so the output
*rises* when the measured value exceeds its reference:

```
 EA_V:  +in = V_meas          EA_I:  +in = I_meas
        −in = V_ref via R_a 10k        −in = I_ref via R_a 10k
        feedback −in→out: R_z + C_fb (Type-II)
```

Starting values **(bench)**:

| | R_a | C_fb | R_z | Integrator f₀ | Zero |
|---|---|---|---|---|---|
| EA_V | 10 kΩ | 10 nF | 33 kΩ | 1.6 kHz | 480 Hz |
| EA_I | 10 kΩ | 22 nF | 15 kΩ | 720 Hz | 480 Hz |

- Small RC (100 Ω + 1 nF) on the INA240 output before EA_I and the MCU ADC.
- Diodes: BAT54W Schottky, SC-70/SOT-323 3-pin (pin 1 anode, pin 2 NC,
  pin 3 cathode — low drop preserves EA swing authority).
- **Anti-windup (bench):** the inactive amp rails low (harmless — diode blocks),
  but on crossover it must climb back up; RRIO amps recover from a low rail
  quickly. If Phase-1 crossover tests show overshoot, add a Schottky clamp
  holding the inactive output ~0.3 V below its diode's conduction point.

## 6. Compensation strategy

Two nested loops, deliberately decoupled by frequency:

| Loop | Crossover target | Compensated by |
|---|---|---|
| Inner: LM5145 voltage loop (regulates FB) | 25–40 kHz (~fsw/10) | Type-III network around the LM5145 internal EA |
| Outer: CV / CC precision loops | 1–3 kHz | The Type-II EA networks above |

- **Inner (Type-III recipe):** two zeros at/near f_LC (2.3 kHz) to cancel the LC
  double pole, one pole at the ESR zero (~48 kHz), one pole at fsw/2 (175 kHz),
  gain set for the crossover target. The LM5145's input-voltage feedforward
  keeps modulator gain roughly constant over 12–30 V in, so one compensation
  works across the input range. Exact RC values computed at schematic capture
  from the chosen parts, then **verified by FRA/Bode on the board** — this is a
  Phase-1 exit criterion, not a paper exercise.
- **Outer:** with the inner loop closed, the plant seen by each EA is ≈ flat
  from DC to ~25 kHz, so an integrator + zero crossing at 1–3 kHz has a decade
  of separation and ≥ 55° phase margin comes naturally.
- AC subtlety worth knowing **(bench)**: when a diode conducts, R_inj to the
  EA's low-impedance output appears in parallel with R_bot, slightly raising
  inner-loop divider gain. It's a small, benign shift — absorbed when the Bode
  measurement tunes the Type-III values.

## 7. Aux rails, disconnect, housekeeping

- **Aux:** V_bus → LMR36015 buck (4.2–60 V in, 1.5 A) → 5 V @ ≤0.5 A (op-amps,
  INA240, CAN VCC, gate-driver charge pump) → 3.3 V LDO (MCU, DAC80502, INA228,
  TCAN1042 VIO). *Why not TPS54202 (original pick):* its 28 V input maximum
  sits inside our 24–30 V bus spec; the 60 V part adds real margin.
- **Output disconnect:** back-to-back 60 V NFETs, common source, after the shunt.
  Gate drive options (decide at schematic): LTC7004 high-side driver (fast,
  µs-class fault opening) vs. VOM1271 photovoltaic driver (trivially simple,
  ~ms opening). Phase 1 carries footprints for the LTC7004 path; hardware OVP
  comparator (TLV7011 at 105 % of 21.2 V ≈ 22.3 V threshold) and /HW_ENABLE
  gate it directly, MCU only requests.
- **MCU:** STM32G431CBT6 (LQFP48). SPI → DAC80502; I²C → INA228; FDCAN →
  TCAN1042HGV; ADC → V_meas buffer, I_meas, V_bus/12 divider, 2 × NTC (10 k
  B3950: FET area, inductor); GPIO → LM5145 EN, DEM/FPWM, disconnect request,
  droop enable (fitted but unused in Phase 1), status LED; UART debug header;
  SWD header.
- **Slot straps:** 3 GPIO with pull-ups read at boot. Firmware inverts the
  raw pins (`SLOT_ID_IN() = ~PB[13:11]`): a grounded strap sets a bit, so
  **all-open = slot 0** — the bare bench harness needs no strap wiring.
  (Earlier revision said "grounded = slot 0"; that was backwards vs the
  host-tested firmware, caught at Phase-3 backplane design.)

## 8. Test points (bring-up is the point of this board)

TP on: SW node (with RC snubber footprint), FB node, EA_V out, EA_I out, V_meas,
I_meas, V_ref, I_ref, 5 V, 3.3 V, VCC(LM5145), /HW_ENABLE, CAN_H/L, plus
**loop-injection break points**: a 10 Ω resistor in series with the measurement
divider top and with R_top — either can host the FRA injection transformer.

## 9. Ordering shortlist (Phase-1 specific)

| Ref | Part | Qty |
|---|---|---|
| Buck controller | LM5145RGYR | 1 (+1 spare) |
| FET pair | CSD18563Q5A (or equiv 60 V ≤10 mΩ) | 2 (+2) |
| Inductor | 10 µH ≥12 A flat-wire | 1 (+1) |
| Op-amp | OPA2333AIDGKR | 1 (+1) |
| DAC | DAC80502 (SPI) | 1 |
| Sense amp | INA240A3 | 1 (+1) |
| Telemetry | INA228 | 1 |
| Shunt | 2 mΩ 1 W 2512 Kelvin | 2 |
| MCU | STM32G431CBT6 | 1 (+1) |
| CAN xcvr | TCAN1042HGV | 1 |
| Aux buck | LMR36015 | 1 |
| Disconnect | 60 V NFETs + LTC7004 | 2 + 1 |
| OVP comp | TLV7011 | 1 |
| Polymer out caps | 220 µF 25 V | 2 (+2) |
| Precision divider | 69.8 k + 10.0 k 0.1 % | 2 sets |
| USB-CAN adapter | CANable/candleLight class | 1 (bench tool) |

## 10. Open items → resolve at schematic capture

1. Exact LM5145 Type-III values (needs final cap/inductor datasheets) — method in §6.
2. Disconnect gate-driver choice (LTC7004 vs VOM1271) — footprint both if cheap.
3. Confirm LM5145 SS/TRK pin behaviour with our FB-injection scheme (SS cap
   still wanted for controller-level start; our real soft-start is the V_ref ramp).
4. Snubber values for SW node — bench-derived (ring frequency measurement).
5. Whether EA anti-windup clamps are needed — decided by the crossover test.
