# Vendored CMSIS headers

| File | Source | License |
|---|---|---|
| `stm32g431xx.h`, `stm32g4xx.h`, `system_stm32g4xx.h` | [STMicroelectronics/cmsis-device-g4](https://github.com/STMicroelectronics/cmsis-device-g4) (master, fetched 2026-07-16) | Apache-2.0 |
| `core_cm4.h`, `cmsis_gcc.h`, `cmsis_compiler.h`, `cmsis_version.h`, `mpu_armv7.h` | [ARM-software/CMSIS_5](https://github.com/ARM-software/CMSIS_5) tag 5.9.0 | Apache-2.0 |

Register/bit definitions only — no ST HAL/LL code. The firmware in `../src`
is bare-metal against these headers.
