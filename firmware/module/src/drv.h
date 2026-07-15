/* drv.h — driver interfaces for the Phase-1 module firmware. */
#ifndef DRV_H
#define DRV_H

#include "board.h"
#include "labbench_can.h"
#include "module_core.h"

/* uart.c — 115200 8N1 on USART2, blocking TX (bring-up log only) */
void uart_init(void);
void uart_puts(const char *s);
void uart_dec(int32_t v);
void uart_hex(uint32_t v);

/* adc.c — ADC1 (V_MEAS/I_MEAS/NTCs) + ADC2 (VBUS_SNS), polled */
void adc_init(void);
typedef struct {
    uint16_t v_meas, i_meas, vbus, ntc_fet, ntc_ind;   /* raw 12-bit */
} adc_raw;
void adc_read(adc_raw *r);

/* dac80502.c — SPI1 + soft NSYNC */
void dac_init(void);                 /* config: REF/2, gain 2 -> 2.5 V FS */
void dac_write_v(uint16_t counts);   /* DAC-A = V_REF */
void dac_write_i(uint16_t counts);   /* DAC-B = I_REF */

/* ina228.c — I2C2, addr 0x40 (A1=A0=GND) */
bool ina228_init(void);              /* false: not responding (fault #18) */
bool ina228_read(int32_t *vbus_uv, int32_t *cur_ua);
bool ina228_read_energy(int64_t *charge_nAh, int64_t *energy_nWh);

/* fdcan.c — classic CAN 2.0B, 500 kbit/s, kernel clock = HSE 8 MHz */
void fdcan_init(uint8_t slot);       /* filters: GLOBAL_* + CMD(slot) */
bool fdcan_rx(lb_can_frame *f);
bool fdcan_tx(const lb_can_frame *f);   /* false: all TX buffers busy */

/* flash_cal.c — calibration block in the last flash page */
typedef struct {
    uint32_t magic;
    lb_cal cal[4];                   /* lb_cal_item_t order */
    uint32_t crc;
} cal_block;
void cal_load(cal_block *cb);        /* falls back to identity */
bool cal_store(const cal_block *cb);

/* iwdg: LSI/32 -> 1 ms ticks */
static inline void iwdg_init(uint16_t timeout_ms)
{
    IWDG->KR = 0x5555;               /* unlock  */
    IWDG->PR = 3;                    /* /32     */
    IWDG->RLR = timeout_ms;
    while (IWDG->SR) { }
    IWDG->KR = 0xCCCC;               /* start   */
}
static inline void iwdg_kick(void) { IWDG->KR = 0xAAAA; }

#endif /* DRV_H */
