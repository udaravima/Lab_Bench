# 03 — CAN Protocol

## 1. Physical / data-link

| Parameter | Value |
|---|---|
| Standard | CAN 2.0B, 11-bit identifiers, 500 kbit/s |
| Transceivers | TCAN1042HGV (3.3 V logic, bus-fault tolerant) |
| Termination | 120 Ω at both physical bus ends (backplane) |
| Compatibility | ESP32-S3 TWAI (manager) and STM32G431 FDCAN in classic mode (modules) |

Bus load estimate: 8 modules × (2 telemetry frames @ 20 Hz + heartbeat @ 4 Hz)
≈ 350 frames/s ≈ 9 % utilization — ample headroom.

## 2. Identifier map

`slot` = 0–7. Lower ID = higher priority.

| ID (hex) | Direction | Name |
|---|---|---|
| `0x010 + slot` | module → mgr | **FAULT** (immediate, also repeated at 1 Hz while latched) |
| `0x020` | mgr → all | **GLOBAL_OFF** broadcast (all outputs off, not latched) |
| `0x021` | mgr → all | GLOBAL_STATE (budget remaining, system flags) — 1 Hz |
| `0x100 + slot·0x10 + cmd` | mgr → module | Commands (see §3) |
| `0x300 + slot·0x10 + typ` | module → mgr | Status/telemetry (see §4) |
| `0x7E0 + slot` | module → mgr | BOOT/HELLO (sent once on power-up/reset) |

## 3. Commands (manager → module), `cmd` offsets

| cmd | Name | Payload (little-endian) |
|---|---|---|
| 0 | `SET_VI` | int32 V_set [µV], int32 I_set [µA] — atomically applied pair |
| 1 | `OUTPUT` | u8: 0=off, 1=on, 2=on+DEM(battery mode), 3=on+droop(group mode), 4=on+DEM+droop |
| 2 | `LIMITS` | int32 P_max [mW], int16 T_derate [0.1 °C], u8 comms-loss policy (0=off, 1=hold), u8 rsvd |
| 3 | `CAL_WRITE` | u8 item {Vset,Iset,Vmeas,Imeas}, u8 point {offset,gain}, int32 value — flash-committed on last item |
| 4 | `IDENT` | none — module blinks LED, replies STATUS (find-my-module) |
| 5 | `RESET` | u8 magic 0xA5 — MCU reset; 0x5A = clear latched faults (if condition gone) |

Every command is acknowledged with a STATUS frame (§4 typ 2) echoing a rolling
sequence number carried in the two MSBs of `cmd`… no — sequence tracking is
kept simple: **manager treats the next STATUS frame containing the new
setpoints as the ack**, and retries after 50 ms timeout, 3 attempts, then
flags the channel unresponsive.

## 4. Status/telemetry (module → manager), `typ` offsets

| typ | Name | Rate | Payload |
|---|---|---|---|
| 0 | `TELEM_VI` | 20 Hz | int32 V_meas [µV], int32 I_meas [µA] (INA228) |
| 1 | `TELEM_AUX` | 5 Hz | int16 T_fet, int16 T_ind [0.1 °C], u16 V_bus [10 mV], u16 P_out [100 mW] |
| 2 | `STATUS` | 4 Hz + on change | u8 state (§5), u8 fault bits, u8 warn bits, u8 mode(out/DEM/droop/CC-active), int16 V_set-echo [10 mV], int16 I_set-echo [10 mA] |
| 3 | `ENERGY` | 1 Hz | int32 charge [mAh·10⁻²], int32 energy [mWh·10⁻²] (INA228 accumulators; battery charging) |

`STATUS.CC-active` (live CV/CC flag, read from the CC amp comparator) is what
the manager's charge sequencer watches for the CC→CV transition.

## 5. Module state machine

```
BOOT → SAFE (output off, setpoints zero)
SAFE → ACTIVE        on OUTPUT on  (precharge → EN → FETs → ramp V_ref)
ACTIVE → SAFE        on OUTPUT off / GLOBAL_OFF / comms-loss(policy=off)
any  → FAULT_LATCHED on latching fault (protection matrix doc)
FAULT_LATCHED → SAFE on RESET(0x5A) with fault condition cleared
any  → SAFE (hardware) on /HW_ENABLE low — overrides everything, incl. FAULT handling
```

## 6. Heartbeats & comms-loss policy

- **Module → manager:** STATUS at 4 Hz is the module heartbeat. Manager marks a
  channel lost after 1 s silence, alarms, and excludes it from the power budget.
- **Manager → module:** GLOBAL_STATE at 1 Hz is the manager heartbeat. On 3 s
  silence a module applies its comms-loss policy (`LIMITS`):
  - default **0 = output off** (bench-safe);
  - **1 = hold last setpoints** (deliberate choice for long unattended
    battery-charge runs — module-local protections and the analog CV/CC
    remain fully active).
- **Hot-plug:** module sends HELLO on boot; manager replies with LIMITS +
  calibration check, then the channel becomes available in the UI.

## 7. Manager-side sequences (not on the wire)

Battery-charge profiles, parallel-group trimming, and budget arbitration are
manager firmware that only *emits the frames above*. Example CC→CV charge:

1. `LIMITS` (policy=hold, P_max), `SET_VI(V_float, I_charge)`, `OUTPUT(on+DEM)`.
2. Watch STATUS.CC-active: while asserted → CC phase; deasserts near V_float → CV phase.
3. Terminate when TELEM_VI current < I_cutoff for t_hold, or on any
   time/temperature guard → `OUTPUT(off)`.
