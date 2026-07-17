# 10 — Manager Firmware (ESP32-S3, Phase 3)

Firmware in `firmware/manager/` for the rack controller. Same split as the
module firmware (docs/07): a **hardware-independent core**
(`firmware/manager/core/manager_core.{h,c}`, host-tested in
`firmware/tests`) implements every protocol/policy decision; a thin
ESP-IDF shell binds it to TWAI, I²C, USB and the UI. The core reuses
`firmware/common/labbench_can.h` verbatim.

## Design rule

**The manager is never safety-critical.** Modules self-regulate and
self-protect (docs/01); a manager crash mid-charge leaves the module's
analog CV/CC + local watchdogs in charge (comms-loss policy, docs/03 §6).
The manager's own hard action — E-stop — is a GPIO pulling the hardware
/HW_ENABLE line that works with the core hung.

## Core responsibilities (all in manager_core, host-tested)

| Function | Spec | Mechanism |
|---|---|---|
| Discovery | docs/03 §6 | HELLO ⇒ channel known; PRESENT mask (TCA9535) shows seated-but-silent slots |
| Supervision | matrix #15 | STATUS is the module heartbeat: >1 s silent ⇒ lost, alarmed, dropped from the budget |
| Heartbeat | docs/03 §6 | GLOBAL_STATE at 1 Hz (budget, flags, rolling seq) |
| Setpoint ack/retry | docs/03 §3 | SET_VI pending until a STATUS echoes the new setpoints; retry at 50 ms, 3 attempts, then `unresponsive` |
| Budget arbiter | docs/01 §2, matrix #17 | committed = Σ active channels max(measured, vset×iset) + request; refuse enables/raises that exceed it |
| Charge sequencer | docs/03 §7 | per-channel CC→CV→cutoff profile; only *schedules setpoints* — module analog loops regulate |
| Global off / E-stop | matrix #16 | GLOBAL_OFF broadcast (core) + /HW_ENABLE GPIO (shell, works even if core wedges) |

Charge sequencer states:
`IDLE → RAMP (LIMITS hold + SET_VI + OUTPUT on+DEM) → CC (STATUS.CC-active)
→ CV (CC-active clears near V_float) → TERM_WAIT (I < I_cutoff, hold
timer) → DONE (OUTPUT off)`; any module fault, channel loss, or the t_max
guard ⇒ `ABORT` (OUTPUT off, latched reason). Termination uses TELEM_VI
current, cutoff hold defaults 30 s.

Core I/O contract (no HAL, no floats, no allocation): frames in via
`lb_mgr_rx()`, time via `lb_mgr_tick(dt_ms)`, requests via `lb_mgr_*()`
calls; outgoing frames accumulate in a fixed ring drained by
`lb_mgr_tx_pop()`. Same host-test harness as module_core
(`cd firmware/tests && make test`).

## ESP-IDF shell (firmware/manager/idf/ — requires ESP-IDF ≥5.1 to build)

| Piece | Binding |
|---|---|
| TWAI @ 500 k | IO4 TX / IO5 RX (docs/09 §3), rx task → `lb_mgr_rx`, tx task drains the ring |
| Tick | 10 ms esp_timer → `lb_mgr_tick` |
| I²C | IO8/IO9: TCA9535 (0x20, PRESENT+keys, INT on IO7) + bus INA228 (0x40, entry meter) |
| E-stop | IO21 kill FET (assert), IO38 line sense |
| UI | ILI9341 SPI + EC11 encoder + keys: channel list, setpoint edit, budget display |
| SCPI | USB-CDC (TinyUSB): `SOURn:VOLT`, `MEASn:CURR?`, `OUTPn`, `SYST:BUDG` (docs/01 §6) |
| Wi-Fi | later phase; nothing in the core depends on it |

The shell is committed as a buildable skeleton; it is **not** built in CI
here (no ESP-IDF on this machine) — the core logic is what's verified, by
the host suite, exactly like the module firmware before its silicon.

## Bring-up checklist

1. Host: `cd firmware/tests && make test` — manager suite green.
2. Bench: manager + USB-CAN dongle sniffing: GLOBAL_STATE at 1 Hz, seq
   increments; E-stop key drops /HW_ENABLE (scope, <1 ms — exit criterion).
3. With one module on the bench harness: HELLO seen, channel appears,
   SET_VI/OUTPUT round-trip, STATUS ack clears the retry state.
4. Pull the module's CAN mid-run: lost alarm at 1 s, budget shrinks,
   module's own comms-loss policy fires at 3 s (its exit criterion).
5. Charge-sequence a bench battery through CC→CV→cutoff; reboot the
   manager mid-charge: module holds (policy=hold), sequencer resumes
   supervision from telemetry (docs/05 Phase-3 exit criterion).
