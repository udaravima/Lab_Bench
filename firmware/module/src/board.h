/*
 * board.h — Phase-1 module pin map and scaling constants.
 * Single source of truth on the firmware side; mirrors the netlist-verified
 * schematic (hardware/phase1-module, gen_phase1.py pin assignments) and the
 * worked values of docs/06-phase1-circuit-design.md.
 */
#ifndef BOARD_H
#define BOARD_H

#include "stm32g431xx.h"
#include <stdbool.h>
#include <stdint.h>

/* ---- clocks -------------------------------------------------------------- */
#define HSE_HZ        8000000u      /* Y1, CL=8pF */
#define SYSCLK_HZ     96000000u     /* HSE/1 *24 /2 (range-1, no boost, 3WS) */
#define APB_HZ        SYSCLK_HZ     /* both APB prescalers = 1 */

/* ---- GPIO map (port, pin) ------------------------------------------------ */
/* PA0  V_MEAS    ADC1_IN1        PA10 CAN_STB   out (low = transceiver on)  */
/* PA1  I_MEAS    ADC1_IN2        PA11 CAN_RX    FDCAN1 AF9                  */
/* PA2  UART_TX   USART2 AF7      PA12 CAN_TX    FDCAN1 AF9                  */
/* PA3  UART_RX   USART2 AF7      PA15 PS_PGOOD  in (high = in regulation)   */
/* PA4  DAC_NSYNC out (soft CS)   PB0  NTC_FET   ADC1_IN15                   */
/* PA5  DAC_SCLK  SPI1 AF5        PB1  NTC_IND   ADC1_IN12                   */
/* PA6  VBUS_SNS  ADC2_IN3        PB2  LED_SINK  out (low = LED on)          */
/* PA7  DAC_SDI   SPI1 AF5        PB3  PS_OFF    out (high = kill LM5145 EN) */
/* PA8  I2C_SDA   I2C2 AF4        PB5  AUX_PG    in                          */
/* PA9  I2C_SCL   I2C2 AF4        PB6  HW_EN     in (high = enabled)         */
/*                                PB7  INA_ALERT in (low = alert)            */
/*                                PB10 FAN_PWM   TIM2_CH3 AF1                */
/*                                PB11..13 SLOT_ID0..2 in, pull-up,          */
/*                                         strap-to-GND encoded, inverted    */
/*                                PB14 OUT_REQ   out (high = close disconnect)*/
/*                                PB15 PS_FPWM   out (high = FPWM, low = DEM)*/

#define LED_ON()      (GPIOB->BSRR = GPIO_BSRR_BR2)
#define LED_OFF()     (GPIOB->BSRR = GPIO_BSRR_BS2)
#define PS_OFF_SET(x)  (GPIOB->BSRR = (x) ? GPIO_BSRR_BS3  : GPIO_BSRR_BR3)
#define OUT_REQ_SET(x) (GPIOB->BSRR = (x) ? GPIO_BSRR_BS14 : GPIO_BSRR_BR14)
#define FPWM_SET(x)    (GPIOB->BSRR = (x) ? GPIO_BSRR_BS15 : GPIO_BSRR_BR15)
#define CAN_STB_SET(x) (GPIOA->BSRR = (x) ? GPIO_BSRR_BS10 : GPIO_BSRR_BR10)
#define DAC_NSYNC(x)   (GPIOA->BSRR = (x) ? GPIO_BSRR_BS4  : GPIO_BSRR_BR4)

#define PS_PGOOD_IN()   ((GPIOA->IDR >> 15) & 1u)
#define AUX_PG_IN()     ((GPIOB->IDR >> 5) & 1u)
#define HW_EN_IN()      ((GPIOB->IDR >> 6) & 1u)
#define INA_ALERT_IN()  ((GPIOB->IDR >> 7) & 1u)      /* open-drain, 0 = alert */
#define SLOT_ID_IN()    ((uint8_t)(~(GPIOB->IDR >> 11) & 0x7u))

/* ---- analog scaling (doc 06; ideal values, trimmed by lb_cal) ------------ */
/* ADC: 12 bit, VDDA = 3.3 V -> 805.66 uV/count                               */
/* V_MEAS divider 69.8k/10k (x7.98)  -> 6429 uV(out)/count                    */
/* I_MEAS INA240A3 (100 V/V) x 2 mOhm = 0.2 V/A -> 4028 uA/count             */
/* VBUS_SNS divider 200k/10k (x21)   -> 16919 uV(bus)/count                   */
#define V_MEAS_UV_PER_COUNT   6429
#define I_MEAS_UA_PER_COUNT   4028
#define VBUS_UV_PER_COUNT     16919

/* DAC80502, internal ref 2.5 V, REF-DIV=/2, gain=2 -> 2.5 V full scale.
 * V loop servos V_MEAS(=Vout/7.98) to VREF_A: counts = uv * 65536 / 19.95e6
 * I loop servos I_MEAS(=0.2 V/A)   to VREF_B: counts = ua * 65536 / 12.5e6  */
static inline uint16_t dac_counts_v(int32_t v_uv)
{
    int64_t c = ((int64_t)v_uv << 16) / 19950000;
    return (c < 0) ? 0 : (c > 65535 ? 65535 : (uint16_t)c);
}
static inline uint16_t dac_counts_i(int32_t i_ua)
{
    int64_t c = ((int64_t)i_ua << 16) / 12500000;
    return (c < 0) ? 0 : (c > 65535 ? 65535 : (uint16_t)c);
}

/* NTC: 10k B3950 to AGND, 10k pull-up to 3V3 (ratiometric).
 * ADC counts -> deci-degC lookup, linear interpolation between entries. */
typedef struct { uint16_t counts; int16_t dC; } ntc_pt;
static const ntc_pt NTC_LUT[] = {
    {3742, -200}, {3157, 0}, {2738, 100}, {2278, 200}, {2048, 250},
    {1419, 400}, {816, 600}, {462, 800}, {268, 1000}, {160, 1200},
};
static inline int16_t ntc_dC(uint16_t counts)
{
    const unsigned n = sizeof NTC_LUT / sizeof NTC_LUT[0];
    if (counts >= NTC_LUT[0].counts) return NTC_LUT[0].dC;
    if (counts <= NTC_LUT[n - 1].counts) return NTC_LUT[n - 1].dC;
    for (unsigned i = 1; i < n; i++) {
        if (counts > NTC_LUT[i].counts) {
            int32_t span_c = NTC_LUT[i - 1].counts - NTC_LUT[i].counts;
            int32_t span_t = NTC_LUT[i].dC - NTC_LUT[i - 1].dC;
            return (int16_t)(NTC_LUT[i - 1].dC +
                             span_t * (NTC_LUT[i - 1].counts - counts) / span_c);
        }
    }
    return NTC_LUT[n - 1].dC;
}

/* ---- firmware identity ---------------------------------------------------- */
#define FW_MAJOR 0
#define FW_MINOR 1

/* millisecond tick from SysTick */
extern volatile uint32_t g_ms;

#endif /* BOARD_H */
