# 07 — Module Firmware (STM32G431, Phase 1)

Bare-metal firmware in `firmware/module/` binding the host-tested control core
(`firmware/module/core/`) to the Phase-1 board. No vendor HAL — register-level
code against vendored CMSIS headers (`firmware/module/cmsis/`, Apache-2.0).

## Design rule

**The firmware is never in the fast safety path.** The analog CV/CC loops
regulate; hardware OVP (TLV7011) and the LM5145's valley ILIM protect. The
firmware moves *setpoints*, opens/closes the output, watches temperatures and
reports. If the MCU crashes mid-load, the output keeps regulating and the IWDG
reboots into SAFE — that behaviour is a Phase-1 exit criterion (docs/05).

## Layers

```
main.c        1 kHz tick, CAN dispatch, telemetry, LED/fan, IWDG
  |            binds to ->  module_core.{h,c}   (host-tested state machine:
  |                         SAFE/ACTIVE/FAULT, envelope clamp, ramp, derate,
  |                         comms-loss policy — run `make test` in fw/tests)
drv.h         driver interfaces
adc.c         ADC1: V_MEAS/I_MEAS/NTCx2; ADC2: VBUS_SNS (polled, ~27 us ea.)
dac80502.c    SPI1 mode 1, 6 MHz, soft NSYNC; GAIN=REF/2 x2 -> 2.5 V FS
ina228.c      I2C2 @100k (HSI16 kernel); ADCRANGE=1, SHUNT_CAL=2097
fdcan.c       classic CAN 500 kbit; kernel clock = raw HSE (crystal-exact);
              G4 fixed message RAM; 2 filters: GLOBAL_*, CMD(slot)
flash_cal.c   4x lb_cal in the last 2K flash page, CRC32, identity fallback
uart.c        115200 8N1 bring-up log on PA2/PA3
system.c      HSE 8M -> PLL 96 MHz (range 1, 3 WS, no boost); SysTick 1 kHz
startup.c     C vector table + init (no assembly)
board.h       pin map + scaling constants (single source, mirrors schematic)
```

## Pin map

Authoritative copy in `src/board.h` (mirrors the netlist-verified schematic —
if the schematic changes, board.h must follow):

| Pin | Signal | Peripheral | Pin | Signal | Peripheral |
|---|---|---|---|---|---|
| PA0 | V_MEAS | ADC1_IN1 | PB0 | NTC_FET | ADC1_IN15 |
| PA1 | I_MEAS | ADC1_IN2 | PB1 | NTC_IND | ADC1_IN12 |
| PA2/3 | UART | USART2 AF7 | PB2 | LED_SINK | out, low=on |
| PA4 | DAC_NSYNC | GPIO out | PB3 | PS_OFF | out, high=EN killed |
| PA5/7 | DAC SCLK/SDI | SPI1 AF5 | PB5 | AUX_PG | in |
| PA6 | VBUS_SNS | ADC2_IN3 | PB6 | HW_EN | in, high=enabled |
| PA8/9 | I2C SDA/SCL | I2C2 AF4 | PB7 | INA_ALERT | in, **internal pull-up** |
| PA10 | CAN_STB | out, low=run | PB10 | FAN_PWM | TIM2_CH3 AF1 |
| PA11/12 | CAN RX/TX | FDCAN1 AF9 | PB11-13 | SLOT_ID | in, pull-up, inverted |
| PA15 | PS_PGOOD | in | PB14 | OUT_REQ | out, high=close |
| PF0/1 | 8 MHz crystal | HSE | PB15 | PS_FPWM | out, high=FPWM |

PB7 note: the INA228 ALERT is open-drain and the schematic has **no external
pull-up** on that net — the internal pull-up is load-bearing. Add a discrete
pull-up in the next schematic revision.

## Scaling (ideal values; lb_cal trims on top)

| Path | Constant | Derivation (docs/06) |
|---|---|---|
| V_MEAS | 6429 uV/count | 3.3 V/4096 x (69.8k+10k)/10k |
| I_MEAS | 4028 uA/count | 3.3 V/4096 / (INA240A3 100 V/V x 2 mOhm) |
| VBUS_SNS | 16919 uV/count | 3.3 V/4096 x 21 |
| DAC V | counts = uv·2^16/19.95e6 | 2.5 V FS ↔ V_MEAS 2.5 V ↔ 19.95 V out |
| DAC I | counts = ua·2^16/12.5e6 | 2.5 V FS ↔ 0.2 V/A ↔ 12.5 A |

Calibration model `y = x·gain/65536 + offset` applied at the DAC/ADC boundary
(`lb_cal_apply`). Items: VSET/ISET/VMEAS/IMEAS, written over CAN
(`LB_CMD_CAL_WRITE`), persisted to flash immediately.

## Control flow

Main loop: poll CAN RX FIFO -> dispatch, kick IWDG (500 ms), catch up 1 ms
ticks (max 20 after a blocking flash write), 100 ms telemetry, 500 ms STATUS,
FAULT frame on any state/fault-bit change.

Per 1 ms tick:
1. ADC scan; hottest NTC -> `lb_core_set_temp` (derate #11 / OTP #12).
2. `lb_core_tick` (ramp, envelope, comms timeout).
3. Backup latches: V_MEAS > 112 % of v_max -> OVP fault #4 (reporting only —
   the comparator already tripped the disconnect); INA_ALERT low in ACTIVE ->
   OCP backup #2.
4. DAC references written with calibration applied.
5. Outputs: `PS_OFF = !(state ok && mode!=OFF && hw_enable)`;
   `OUT_REQ = output_closed && PS_PGOOD`; `PS_FPWM = !DEM`.
6. Fan: 0 % below 45 degC, 40->100 % linear 45..75 degC.

Telemetry (100 ms): INA228 VBUS/CURRENT preferred; ADC path is the fallback
and the cross-check — 5 consecutive disagreements >5 % and >0.5 V latch
SENSE fault #18.

## Build / flash

```
cd firmware/module
make            # arm-none-eabi-gcc from PATH or ~/tools/xpack-arm-none-eabi-gcc-*
make flash      # st-flash (ST-Link on J2 SWD header)
```

6.3 KB flash, 120 B static RAM. The image region ends at 126 K — the last 2 K
page (0x0801F800) belongs to the calibration block.

## Bring-up checklist (no manager needed — USB-CAN dongle at 500 k)

1. Power the logic only (24 V in, converter held off: no OUTPUT command).
   UART shows `labbench module fw 0.1`, `slot N up`; LED blinks 2 Hz (SAFE).
   `INA228 missing` on the log means the I2C chain / address is wrong.
2. Confirm HELLO frame (`0x7E0+slot`) on the bus at power-up.
3. `LB_CMD_SET_VI` + `LB_CMD_OUTPUT(ON)` -> LED solid, PS_OFF drops, OUT_REQ
   rises after PGOOD. Scope the DAC outputs ramp (1 V/ms reference-domain).
4. Two-point calibration per item: set two known points, measure with the
   6.5-digit DMM, compute gain/offset, `LB_CMD_CAL_WRITE`, verify persistence
   across a power cycle.
5. Kill the manager heartbeat -> comms-loss policy fires after 3 s
   (default OFF). Halt the MCU under load with the debugger -> output keeps
   regulating, IWDG reboot lands in SAFE (exit criterion, docs/05).

## Known-untested surface

Every register write is per RM0440/datasheet but has never met silicon:
expect bring-up friction in (likelihood order) I2C timing/NACK handling,
FDCAN filter behaviour, ADC sampling-time vs source impedance on V_MEAS
(69.8k divider is high-Z: watch for droop; increase sampling or buffer),
DAC80502 GAIN readback. The logic layer is host-tested and is not the risk.
