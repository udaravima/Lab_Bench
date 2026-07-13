# 01 — System Architecture

## 1. Topology

```
                      DC INPUT BUS 24–30 V (kW-class)
   ┌──────────────────────┬─────────────┬─────────────┬─────────────┐
   │                      │             │             │             │
 ┌─┴──────────┐    ┌──────┴─────┐ ┌─────┴──────┐   … up to 8   ┌────┴───────┐
 │  CENTRAL   │    │  MODULE 1  │ │  MODULE 2  │               │  MODULE 8  │
 │  MANAGER   │    │ 600W buck  │ │ 600W buck  │               │ 600W buck  │
 │ ESP32-S3   │    │ CV/CC loop │ │ CV/CC loop │               │ CV/CC loop │
 │ UI+USB+WiFi│    │ V/I sense  │ │ V/I sense  │               │ V/I sense  │
 └─────┬──────┘    └──────┬─────┘ └─────┬──────┘               └────┬───────┘
       │                  │             │                           │
       ├───────────── CAN 2.0B @ 500 kbit/s (multi-drop) ───────────┤
       ├───────────── /HW_ENABLE (wired E-stop, open-drain) ────────┤
       │                  │             │                           │
                       OUT 1         OUT 2                       OUT 8
```

Design principle: **each module is a complete, self-protecting CV/CC supply.**
The manager only sends setpoints and reads telemetry. No control loop is ever
closed over the bus, so a manager failure or module hot-unplug never
destabilizes the remaining channels.

## 2. Input bus and power budget

- Nominal input: **24–30 V DC** from a server PSU, battery bank, or lab rectifier.
  12 V operation is allowed but each channel's output ceiling is V_in − 2 V.
- Theoretical maximum load is 8 × 600 W = 4.8 kW → **200 A at 24 V**. The input
  source will almost always be the real limit, so:
  - The manager holds a configured **global power budget** (e.g. 1.5 kW).
  - Modules report measured input-side power estimate (V_bus × I_out × V_out/V_bus/η)
    and output power in telemetry.
  - The manager arbitrates: new enable requests or setpoint increases that would
    exceed the budget are refused (or other channels are derated per policy).
  - A bus-level V/I monitor (INA228 + shunt at the bus entry) belongs on the
    backplane as the ground truth for total draw.
- Backplane power distribution: copper bus bars or ≥4 oz copper PCB with bolted
  lugs. Each slot presents a blade/power connector rated ≥ 30 A continuous
  (input current at 600 W / 24 V ≈ 27 A worst case).

## 3. Backplane — per-slot connector

| Signal | Type | Purpose |
|---|---|---|
| VBUS+ / VBUS− | Power blades, ≥30 A | Input power (VBUS− is system ground) |
| CAN_H, CAN_L | Twisted pair | Control/telemetry bus, 120 Ω terminated at both physical ends |
| SLOT_ID[2:0] | Hardwired straps | Slot address 0–7, read by module at boot |
| /HW_ENABLE | Open-drain, pulled up on backplane | Global hardware kill (E-stop). Manager (and front-panel E-stop switch) can pull low; **modules only listen** — low forces all outputs off in hardware, independent of firmware |
| PRESENT | Short-to-GND pin on module | Lets manager detect occupied slots even before CAN hello |

Mate-order requirement: power blades make first / break last (standard staggered
pin lengths), so hot-plug never runs logic before ground is connected.

## 4. Grounding and output configuration

- All modules are **non-isolated bucks from a common bus** → every OUT− is the
  same node as system ground (through the shunt return; see module doc for
  sense topology).
- Consequences (accepted design decision):
  - Channels **can be paralleled** for more current.
  - Channels **cannot be series-stacked**, cannot float, no ±rails.
  - A load connected between two channel outputs sees the *difference* of two
    grounded supplies — allowed but the manager UI should warn.

## 5. Scaling: droop-share parallel groups

To gang N channels onto one output bus for > 600 W / > 30 A:

1. Manager assigns channels to a **group** and enables each module's hardware
   droop (an analog switch sums a scaled current-sense signal into the CV error
   amp input, giving a fixed droop of ~20 mV/A — see module doc §5).
2. Manager programs identical V_set/I_set on all group members. Droop guarantees
   stable static sharing without inter-module wiring.
3. Manager trims individual V_set values slowly (≤ 1 Hz) using telemetry to
   equalize currents and to correct the droop-induced voltage sag at the load.
4. Group current limit = sum of member I_set; a member entering CC or faulting
   triggers a group-level derate/shutdown policy in the manager.

Droop sharing is deliberately analog-static + firmware-slow-trim: no fast
digital current-share loop exists to oscillate.

## 6. Central manager

- **MCU:** ESP32-S3 (TWAI CAN controller + external transceiver, e.g. TCAN1042HGV).
- **Local UI:** display + rotary encoder + per-channel enable keys.
- **Remote:** USB-CDC and WiFi, SCPI-style command set
  (`SOUR3:VOLT 12.5`, `MEAS2:CURR?`, `OUTP4 ON`, `SYST:BUDG 1500`).
- **Responsibilities:**
  - Slot discovery (PRESENT pins + CAN hello/heartbeat).
  - Setpoint dispatch, telemetry aggregation/logging.
  - Global power-budget arbitration (§2).
  - Parallel-group management (§5).
  - **Battery-charge sequencer:** CC → CV → cutoff profiles (chemistry presets,
    time/temperature/minimum-current cutoffs). The sequencer only *schedules
    setpoints*; the module's analog CC/CV does the actual regulation, so a
    manager hang can never overcharge — the module keeps the last safe CV/CC
    limits and the module-side watchdogs still apply (see protocol doc §6).
  - /HW_ENABLE control and front-panel E-stop pass-through.

## 7. Numbering & terminology

- **Slot** = physical position 0–7 (SLOT_ID straps). **Channel n** = module in slot n.
- Module firmware is slot-agnostic; identity comes entirely from the straps.
- "600 W envelope": output limited by whichever binds first of
  V_max = V_in − 2 V, I_max = 30 A, P_max = 600 W. The module enforces the power
  envelope locally (firmware derates I_set); V/I limits are analog.
