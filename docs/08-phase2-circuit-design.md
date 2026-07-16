# 08 — Phase 2 Circuit Design (600 W Module)

Worked component values for the full-power module, in the same spirit as
docs/06: every number is derived, every part claim is datasheet-verified
(`docs/datasheets/lm5143.pdf`, `lm5069.pdf`, `csd18540q5b.pdf`,
`csd19536ktt.pdf`, Coilcraft `xal1510.pdf`). Values marked **(bench)** are
starting points to be tuned during bring-up. The control/telemetry core is
the *verified Phase-1 block* — only its scale factors change; deltas are
called out explicitly in §4 and §11.

## 1. Targets

| Parameter | Value |
|---|---|
| Input | 24–30 V bus through hot-swap front end (12 V tolerated, ceiling drops) |
| Output | 0.7–28 V guaranteed (V_in − 2 V binds first), 0–30 A, 600 W envelope |
| Topology | LM5143, two interleaved phases, 180°, peak current mode |
| Switching frequency | 347 kHz/phase (694 kHz effective output ripple) |
| Ripple | < 20 mVpp at terminals |
| Accuracy after cal | ±(0.05 % + 5 mV) V, ±(0.1 % + 10 mA) I |
| Phase balance | within 10 % at full load (exit criterion, docs/05) |

> **Why 0.7 V minimum now (was 0.5 V in Phase 1)?** The LM5143's minimum
> on-time is 65 ns. At 347 kHz and 30 V input that is 30 × 65 n × 347 k ≈
> 0.68 V. Below that it pulse-skips. Same honest-spec logic as docs/06 §1.

## 2. Power stage

### Controller configuration (single-output interleaved)

Verified against LM5143 datasheet §9.3.17.2 + Table 9-2:

| Pin | Strap | Effect |
|---|---|---|
| MODE (34) | → VDDA | interleaved single-output, EA gm = 1200 µS |
| FB2 (3) | → AGND | channel-2 EA disabled (high-Z) |
| COMP2 (2) | → COMP1 (29) | single compensation node |
| SS2 (1) | → SS1 (30) | single soft-start cap (one 21 µA source active) |
| FB1 (28) | base divider + injection | regulation threshold **0.6 V** (§5) |
| DEMB (33) | ← PS_FPWM (MCU) | low = diode emulation, high = FPWM. V_IH = 2 V → 3.3 V GPIO drives it directly |
| RT (37) | 63.4 kΩ → AGND | f_sw = 22/63.4 MHz·kΩ = **347 kHz/phase** (datasheet Eq. 1) |
| RES (32) | 470 nF → AGND **(bench)** | hiccup-mode OC protection enabled |
| DITH (38) | 47 nF fitted + DNP strap to VDDA | ±5 % spread spectrum for EMC; strap disables |
| VCCX (6) | ← 5 V aux rail | see below |
| EN1 (31) + EN2 (40) | tied, gated (§8) | 2 V threshold, must never float |
| PG1 (24) | → PS_PGOOD (pull-up 3V3) | output-in-window flag |
| PG2 (7), SYNCOUT (39) | n.c. | unused in interleaved mode (verify PG2 at capture) |

> **Why feed VCCX from the 5 V aux rail?** VCC powers the gate drivers
> (4 FETs × ~20 nC at 5 V × 347 kHz ≈ 28 mA). From the internal linear
> regulator that is (24…30 V − 5 V) × 28 mA ≈ 0.6–0.8 W dissipated *inside
> the VQFN*. VCCX > 4.3 V disables the internal regulator and takes bias
> from the efficient aux buck instead. VCCX operating max is 5.25 V — the
> 5.0 V rail fits. (E-char: V_VCC-REG = 5.0 V, so gate-drive amplitude is
> unchanged; CSD18540Q5B is R_DS(on)-rated at V_GS = 4.5 V.)

### Inductors — 6.8 µH, not 4.7 µH (docs/02 correction)

Peak-current-mode subharmonic stability requires m_c(1−D) > 0.5 where
m_c = 1 + S_e/S_n, S_e = internal slope compensation, S_n = sensed
inductor up-slope. The LM5143's S_e is fixed by RT — interpolating the
e-char points (557 mV/µs @ 2.2 MHz, 64 mV/µs @ 220 kHz): **S_e ≈ 100 mV/µs
at 347 kHz**. Our duty runs to D = 28/30 = 0.93, so (1−D) is tiny and m_c
must be large:

```
S_n = (V_in − V_out)/L × R_S × G_CS      (G_CS = 12, R_S = 3.5 mΩ → 42 mV/A)
worst case sweep over V_in 24–30 V, V_out ≤ V_in − 2:
  L = 4.7 µH → min m_c(1−D) = 0.44   ✗ subharmonic oscillation
  L = 6.8 µH → min m_c(1−D) = 0.61   ✓ stable everywhere
```

**Part: Coilcraft XAL1510-682ME** (verified from Coilcraft xal1510.pdf):
6.8 µH ±20 %, I_sat 36 A (30 % drop), I_rms 19 A @ 20 °C rise, DCR
4.17/4.60 mΩ typ/max, 60 V rated. Margins: I_sat 36 A vs worst-tolerance
current-limit peak 23.4 A (§ shunts); I_rms 19 A vs 15 A phase current.
Ripple with 6.8 µH: ΔI = 3.2 A pk-pk worst (V_out 15 V @ 30 V in, 21 %),
0.8 A at V_out 28 V. Loss ≈ 15² × 4.17 mΩ ≈ 0.94 W each.

> This is the same failure class as the XAL1350 I_sat correction in
> HANDOVER.md: a plausible catalog value that fails a second-order
> constraint. The 4.7 µH part is *fine* at D < 0.8 — it fails only in the
> top corner of our operating range.

### Per-phase current-sense shunts — 3.5 mΩ

The LM5143 senses each phase across a shunt between inductor and output
(CS_x = inductor side, VOUT_x = output side, Kelvin). Cycle-by-cycle limit
trips at V_CS = 73 mV (66 min / 82 max), G_CS = 12.

> **Why shunts and not lossless DCR sensing?** Phase balance. Both phases
> peak-limit against one COMP voltage, so per-phase current matching tracks
> sense-element matching. Shunts: ±1 %. Inductor DCR: +13 % part tolerance
> (4.17→4.60 mΩ) plus copper tempco (+0.4 %/°C ≈ +16 % at ΔT 40 °C) — that
> alone can blow the 10 % balance exit criterion. The ~1.6 W total shunt
> loss (0.27 % of 600 W) is the price of a criterion we can pass.

Sizing (datasheet Eq. 11, R_S = V_CS/(I_OC + ΔI/2)) with R_S = **3.5 mΩ**:

| Tolerance case | Peak-current limit | Comment |
|---|---|---|
| V_CS min 66 mV | 18.9 A | vs worst normal peak 15 + 1.6 = 16.6 A → 2.3 A (14 %) no-false-trip margin |
| V_CS typ 73 mV | 20.9 A | DC-equivalent OCP ≈ 19.3 A/phase (129 % of rated) |
| V_CS max 82 mV | 23.4 A | < XAL1510-682 I_sat 36 A ✓ |

Dissipation 15² × 3.5 mΩ = 0.79 W → **2512/2726 wide-terminal ≥ 3 W, ±1 %**,
Kelvin pads (3.0 mΩ is an acceptable substitute if 3.5 mΩ sources poorly:
margins shift to 22.0 A no-trip / 27.3 A max, still < I_sat).

### FETs — CSD18540Q5B ×4 (verified csd18540q5b.pdf)

60 V NexFET, SON 5×6 (existing `PowerFET_SON5x6_GDS` footprint), R_DS(on)
2.6 mΩ typ @ V_GS 4.5 V, Q_g ≈ 20 nC @ 5 V, avalanche rated 320 mJ,
I_D 29 A (PCB-limited). Per phase at 15 A, D = 0.86: high-side conduction
≈ 0.50 W + switching ≈ 1–1.5 W; low-side ≈ 0.1 W. ~2 W/phase in FETs —
2 oz copper + top-side airflow (fan header, docs/02 §6).

> High duty cycle inverts the usual buck intuition: the *high-side* FET
> conducts 83–93 % of the time, so it carries both the conduction and the
> switching loss. Same low-R_DS(on) part in both positions.

### Capacitors

- **Output:** 4 × 220 µF 35 V hybrid polymer (combined ESR ≈ 5 mΩ) +
  6 × 22 µF 50 V X7R. Ripple ≈ ESR × ΔI ≈ 5 mΩ × 3.2 A ≈ 16 mVpp ✓ (and
  interleaving cancels part of that away from D = 0.5).
  *35 V rating vs 28 V output = 25 % headroom; polymer tolerates it,
  verify exact series (e.g. Panasonic ZK/ZKU hybrid) at sourcing.*
- **Input (post hot-swap):** 8 × 10 µF 50 V X7S 1210 close to the FETs
  (2-phase interleaved worst RMS ripple ≈ 0.25 × I_out ≈ 7.5 A) +
  470 µF 50 V electrolytic bulk. Keep total ≈ 550 µF — it is the C_OUT in
  the LM5069 SOA/timer math (§3); more bulk means recomputing §3.
- **Preload:** 4.7 kΩ 0.5 W across the output (DEM minimum load + cap
  discharge; 0.17 W at 28 V).

## 3. Hot-swap front end — LM5069-2 (verified lm5069.pdf)

Blade fuse 35 A → R_SNS → CSD19536KTT → module. **LM5069MM-2** (auto-retry,
0.5 % duty): a transient bus event recovers without reseating the module,
consistent with protection-matrix rows 8/9 auto-recovery semantics. DGS
(VSSOP-10) package.

| Item | Value | Derivation |
|---|---|---|
| R_SNS | **1.5 mΩ ≥ 3 W** Kelvin | I_CL = 55 mV/1.5 mΩ = 36.7 A typ, 32.3 A min (V_CL 48.5/55/61.5 mV) vs 26.6 A max input current (600 W/0.94/24 V). P = 1.06 W at full load |
| Pass FET | **CSD19536KTT** (100 V, 2 mΩ, D²PAK) | The exact part TI's LM5069 design example SOA-verifies: 30 V/9 A/10 ms, 30 V/20 A/1 ms. Steady loss 26.6² × 2 mΩ ≈ 1.4 W → ≥ 6 cm² 2 oz drain copper (drain ≠ GND plane, it's the protected rail) |
| R_PWR | **15.0 kΩ** → P_LIM ≈ 100 W | Eq. 9/10: R_PWR = 1.3e5 × R_SNS × (P_LIM − 1.18 mV × V_DS/R_SNS). 100 W is the *minimum accurate* limit for R_SNS = 1.5 mΩ (V_SNS ≥ 5 mV floor, Eq. 8) |
| C_TIMER | **100 nF** | t_start (Eq. 12, C_OUT 550 µF) = 2.5 ms; ×1.5 margin → 3.7 ms; C_T = t·85 µA/4 V → 79 nF → 100 nF ⇒ t_flt = 4.7 ms, insertion delay = 73 ms |
| SOA check | pass, 34 % margin | Hot-short: 30 V, P_LIM/30 V = 3.35 A for 4.7 ms. FET SOA at 4.7 ms (power-law interp, Eq. 15–18) = 11.7 A; derated to T_C 100 °C → 5.85 A ≥ 1.3 × 3.35 = 4.36 A ✓ |
| UVLO divider | R1 = 47.5 k, R2 = 12.1 k, R3 = 4.87 k (Eq. 21–23) | UV on 10.50 V / off 9.50 V; OV off 33.1 V / re-arm 31.8 V (21 µA hysteresis sources; thresholds 2.5 V) — matches docs/02 §6 (UVLO 10.5 V, OVP 33 V) |
| PGD | open-drain → LMR36015 EN (pull-up to protected rail) + MCU input **PC13** | releases when FET V_DS < 1.25 V |

> **Why the aux buck waits for PGD:** during inrush the pass FET is a
> resistor in its linear region, budgeted by P_LIM for *capacitor charging
> only*. Any load that starts early (the aux buck booting the MCU) eats
> that budget and stretches t_start toward the fault timeout — TI's "load
> off until PG asserted" rule. Gating LMR36015-EN with PGD makes the whole
> logic domain sequence correctly for free; the MCU boots ~75 ms after
> insertion, long after the bus transient has settled. PGD also wire-ANDs
> into the LM5143 EN net (§8) as a hardware backstop.

## 4. Sense & setpoint scaling (control-core deltas)

```
                        0–30 V FS                          0–30 A
 V_out ──[110k]──┬── V_meas = V_out/12 (0–2.5 V)   shunt 0.5 mΩ ──► INA240A3 (×100)
               [10.0k]     │        │                                  │
                 ─┴─       ▼        ▼                          I_meas = 0.05 V/A
                      EA_V (+in)  MCU ADC                        (0–1.5 V at 30 A)
 DAC80502 (16-bit, 2.5 V FS):                                      │        │
   ch A: V_ref 0–2.5 V ≡ 0–30 V   (0.458 mV/LSB)                   ▼        ▼
   ch B: I_ref 0–2.5 V ≡ 0–50 A   (0.763 mA/LSB, fw-clamped   EA_I (−in)  MCU ADC
                                    to 1.5 V = 30 A)
```

- **INA240A3, not A4 — docs/02 §4 had a latent bug.** A4 (gain 200) on
  0.5 mΩ gives 0.1 V/A → 3.0 V at 30 A, but I_ref tops out at the DAC's
  2.5 V full scale (3V3 rail, docs/06 §3) → the CC loop could never
  command above 25 A. A3 (gain 100) → 1.5 V at 30 A with the same 2.5 V
  reference headroom the Phase-1 board has (1.6 V of 2.5 V). Cost: I-set
  LSB coarsens from the headline ~0.5 mA to **0.76 mA** (docs/01 amended).
- **Measurement divider 110 k / 10.0 k, 0.1 % thin film** (exactly /12;
  FS 30.0 V), Kelvin from the output terminals as in Phase 1.
- **Output shunt: 0.5 mΩ ≥ 3 W** wide-terminal (3920 class), Kelvin;
  0.45 W at 30 A. INA228 across the same shunt: 15 mV at 30 A, stays on
  ADCRANGE = 1 (±40.96 mV); firmware SHUNT_CAL recomputed for 0.5 mΩ.
- MCU ADC scale constants (board.h): V_MEAS 9668 µV/count (3.3/4096 × 12),
  I_MEAS 8057 µA/count (3.3/4096 / 0.1 V/A… = /(100 × 0.5 mΩ)),
  DAC V counts = µV·2¹⁶/30.0e6, DAC I counts = µA·2¹⁶/50.0e6.
- NTCs: 2 external as Phase 1 (FET area between phases, inductor pair).
  The shunt-region sensor is the **INA228 die temperature** (±1 °C,
  register DIETEMP) — the part already sits beside the shunt; no third
  ADC pin needed.

## 5. Control core — base divider + FB injection at 0.6 V

Same architecture as docs/06 §4, rescaled for the LM5143's **0.6 V** FB
threshold (Phase-1 LM5145 was 0.8 V — do not copy values across):

```
 V_out ──[R_top 46.4k]──┬────────── FB1 (LM5143, wants 0.6 V)
                        │
                 [R_bot 1.00k]          EA_V ──▶|──[R_inj 5.6k]──┐
                        │                                        ├── same FB node
                       GND              EA_I ──▶|──[R_inj 5.6k]──┘
```

- **Hardware ceiling:** V_max_hw = 0.6 × (1 + 46.4k/1.0k) = **28.4 V**.
- **Injection authority:** forcing V_out → 0 needs
  I_inj = 0.6/R_bot + 0.6/R_top ≈ 0.613 mA. OPA2333 swings to ~4.55 V on
  the 5 V rail minus a BAT54W drop ~0.35 V → available authority
  (4.55 − 0.6)/5.6 k = 0.705 mA → 15 % margin.
- Sanity: holding 28 V needs 9.5 µA (EA at ≈ 1.0 V); holding 0.5 V needs
  0.602 mA (EA at ≈ 4.3 V) — both inside the rail-to-rail swing. ✓
- The accuracy argument of docs/06 §4 (diode drop, ±1 % controller
  reference and R_inj tolerance all live *inside* the outer integrator's
  loop) carries over unchanged.

## 6. Error amplifiers

Identical to Phase 1: OPA2333 dual, BAT54W diode-OR, Type-II networks.
Starting values **(bench)** carry over (EA_V 10 k/10 nF/33 kΩ, EA_I
10 k/22 nF/15 kΩ, 100 Ω + 1 nF RC on the INA240 output) — the plant the
outer amps see is again ≈ flat below the inner-loop crossover, so the
1–3 kHz outer crossover targets and the anti-windup notes in docs/06 §5
apply as written. Verify by Bode; retune C_fb if the higher-gain plant
(30 V FS vs 20 V) moves the crossover.

## 7. Droop hardware (new in Phase 2)

Target ~20 mV/A output droop (docs/01 §5). Sum an attenuated copy of
I_meas into the **V_meas node** (EA_V +input): raising the +input makes
the loop believe the output is high, so it regulates the real output
*down* — droop with the correct sign using only a resistor.

- At the V_meas node the target is 20 mV/A ÷ 12 = 1.667 mV/A. Divider
  Thévenin resistance ≈ 110k∥10k = 9.17 k; I_meas is 0.05 V/A from the
  INA240's low-Z output:
  0.05 × 9.17k/(9.17k + R_droop) = 1.667 mV → **R_droop = 267 kΩ**.
- Switch: **TMUX1101** class analog switch (5 V supply, logic-level
  control from 3.3 V GPIO — verify V_IH at capture) in series with
  R_droop; MCU pin **PB4** = DROOP_EN (safe: NJTRST pull-up at boot only
  closes the switch while the module is in SAFE with output off).
- **Known, deterministic side effect:** with the switch closed and 0 A
  flowing, R_droop loads the divider (10k → 10k∥267k) and the output
  rises 3.4 %. Firmware applies a fixed ×0.9668 correction to V_ref
  whenever droop mode is commanded (OUTPUT modes 3/4), so the manager
  still sees volts-are-volts. Document in module firmware notes.

## 8. Enable chain, OVP, disconnect

- **EN1+EN2** (tied): pulled up 100 k to 5 V aux; wire-AND pulldowns:
  PS_OFF driver (MCU, PB3 logic unchanged), /HW_ENABLE gate, LM5069 PGD.
  Any of firmware, backplane E-stop, or an unhealthy hot-swap holds the
  converter off in hardware.
- **Hardware OVP (TLV7011): threshold 29.4 V** = 105 % of the 28 V
  envelope. It must sit *below* the 30 V bus so a shorted high-side FET
  (output dragged to V_bus) trips it, and *above* the 28.4 V divider
  ceiling so a CV-loop-open fault (output regulates at the ceiling —
  still a controlled state) does not nuisance-trip. Note the squeeze:
  28.4 < 29.4 < 30 — tell the layout/tolerance pass this comparator
  divider wants 0.1 % parts.
- **Output disconnect: 4 × CSD18540Q5B** (two parallel per direction,
  common source), LTC7004 driver as Phase 1. At 30 A: ≈ 1.3 mΩ/direction
  → ≈ 2.3 W total spread over four packages — pour + airflow. LTC7004
  only switches it statically, so gate charge ×4 is irrelevant; check
  its V_GS drive level against ltc7004.pdf at capture.

## 9. Compensation strategy

| Loop | Crossover target | Compensated by |
|---|---|---|
| Inner: LM5143 current-mode voltage loop | 25 kHz (~f_sw/14) | Type-II R_COMP/C_COMP on COMP1 (gm EA, 1200 µS) |
| Outer: CV/CC precision loops | 1–3 kHz | Phase-1 Type-II networks (§6) |

Peak current mode makes the inner plant ≈ single-pole: power-stage
transconductance g_m,ps = 2/(G_CS × R_S) = 47.6 A/V (two phases, shared
COMP), output pole f_p = 1/(2π R_load C_out) ≈ 120 Hz at full load,
ESR zero ≈ 36 kHz. Starting values **(bench)**:

```
|T(f_c)| = 1 :  R_COMP = 1/(gm_EA · g_m,ps · Z_out(25 kHz)) ≈ 2.2 kΩ
zero at f_c/10:  C_COMP = 1/(2π · 2.2 k · 2.5 kHz) ≈ 27 nF
HF pole at ESR zero:  C_HF ≈ 2.2 nF
```

Soft-start C_SS = 47 nF (21 µA → ~1.4 ms controller ramp; the *real*
soft-start remains the firmware V_ref ramp, as in Phase 1). Exact values
finalized by FRA/Bode on the board — Phase-2 exit criterion, docs/05.

## 10. Protection matrix mapping (deltas vs Phase 1)

| Matrix row | Phase-2 implementation |
|---|---|
| 3 per-phase OC | LM5143 73 mV cycle-by-cycle + RES hiccup (§2 shunts) |
| 8 input OV | LM5069 OVLO 33.1 V, auto-recover at 31.8 V |
| 9 input UV | LM5069 UVLO 10.5/9.5 V |
| 10 inrush/short | LM5069 P_LIM 100 W + breaker (36.7 A typ), t_flt 4.7 ms, -2 auto-retry at 0.5 % duty; 35 A blade fuse upstream |
| 4 output OV | TLV7011 at 29.4 V (§8) |
| 7 reverse current | DEMB low = diode emulation (source-only stage) |

## 11. MCU pin-map deltas (board.h must follow)

| Pin | Phase-1 | Phase-2 |
|---|---|---|
| PB4 | free | DROOP_EN (out, high = droop switch closed) |
| PC13 | free | HOTSWAP_PGD (in, pull-up, low = FET not enhanced) |
| PB15 | PS_FPWM → LM5145 SYNCIN | PS_FPWM → LM5143 DEMB (same polarity: high = FPWM) |
| PA15 | PS_PGOOD ← LM5145 PGOOD | PS_PGOOD ← LM5143 PG1 |
| everything else | — | unchanged (I²C stays on PA8/PA9, OUT_REQ on PB14, PB8/BOOT0 untouched — HANDOVER.md traps) |

Firmware constant deltas: V/I scale factors (§4), INA228 SHUNT_CAL for
0.5 mΩ, droop-mode V_ref correction 0.9668 (§7), envelope clamp
I_set ≤ min(30 A, 600 W/V_set).

## 12. Slot connector (schematic-level)

Generic hierarchical connector symbol carrying docs/01 §3 exactly:
VBUS+ / VBUS− power blades (≥30 A, first-mate/last-break), CAN_H/L,
SLOT_ID[2:0] (module side: straps to GND read by pull-up inputs),
/HW_ENABLE, PRESENT (tied to GND on module). Physical family (power
blade vs card edge) is chosen at the batch PCB pass with the backplane —
the netlist doesn't care.

## 13. Test points

Everything from docs/06 §8 (per-phase SW nodes now: SW1, SW2 with snubber
footprints), plus: CS1/CS2 (phase-balance measurement), COMP, LM5069
GATE/TIMER (inrush profiling), PGD, droop node, and the two loop-injection
break resistors (10 Ω) in the measurement divider and R_top as before.

## 14. Ordering shortlist (Phase-2 specific)

Verified parts (datasheet in docs/datasheets/):

| Ref | Part | Qty | Note |
|---|---|---|---|
| Controller | LM5143RHAR (VQFN-40) | 1 (+1) | |
| Hot-swap | LM5069MM-2/NOPB (VSSOP-10) | 1 (+1) | -2 = auto-retry |
| Power FETs | CSD18540Q5B | 4 (+2) | SON 5×6, existing footprint |
| Disconnect FETs | CSD18540Q5B | 4 | shared reel with above |
| Hot-swap FET | CSD19536KTT | 1 (+1) | D²PAK, SOA-verified in LM5069 example |
| Inductors | XAL1510-682ME | 2 (+1) | I_sat 36 A verified |

Requirements to close at the sourcing/BOM pass (candidates, prices, LCSC
stock — jlcsearch first, then Mouser):

| Item | Requirement |
|---|---|
| Phase shunts | 3.5 mΩ (alt 3.0 mΩ) ±1 % ≥3 W 2512/2726 Kelvin ×2 |
| Output shunt | 0.5 mΩ ±1 % ≥3 W 3920-class wide terminal |
| Hot-swap R_SNS | 1.5 mΩ ±1 % ≥3 W Kelvin |
| Output caps | 220 µF 35 V hybrid polymer ×4 (ESR ≤ 25 mΩ each) |
| Input bulk | 470 µF 50 V electrolytic + 8 × 10 µF 50 V X7S 1210 |
| Droop switch | TMUX1101-class SPST analog switch, 5 V supply, 3.3 V logic |
| Fuse + holder | 35 A blade | 
| Control core | Phase-1 BOM carries over (PARTS-TO-DOWNLOAD.md) |

## 15. Open items → resolve at schematic capture

1. PG2 behavior with FB2 = AGND in interleaved mode (float it, but confirm
   no spurious pull needed) — LM5143 datasheet re-read at capture.
2. TMUX1101 exact variant + logic V_IH verification (or SN74LVC1G66-class
   alternative if TMUX prices badly).
3. LTC7004 gate-drive amplitude for the 4-FET disconnect stack (local PDF).
4. OVP comparator divider values for 29.4 V ± tolerance stack (0.1 %).
5. RES/hiccup cap value vs restart cadence (bench preference).
6. DITH: populate 47 nF or strap to VDDA — decide after first EMC scan.
7. Snubber values for SW1/SW2 — bench-derived, footprints only.
8. gen_phase2.py: factor the Phase-1 control-core sheet generation into a
   shared module (docs/05 calls for the control core as a reusable
   hierarchical sheet) — next session's work.
