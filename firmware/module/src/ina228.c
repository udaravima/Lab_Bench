/* ina228.c — INA228 on I2C2 (PA8 SDA / PA9 SCL, AF4), address 0x40.
 * Kernel clock HSI16, TIMINGR = ST's reference 100 kHz value for 16 MHz.
 * Shunt 2 mOhm, ADCRANGE=1 (+-40.96 mV; 10 A -> 20 mV), CURRENT_LSB 20 uA:
 * SHUNT_CAL = 13107.2e6 * 20e-6 * 0.002 * 4 = 2097  (ds 8.1.2). */
#include "drv.h"

#define INA_ADDR   0x40u
#define R_CONFIG     0x00
#define R_ADCCFG     0x01
#define R_SHUNTCAL   0x02
#define R_VBUS       0x05
#define R_CURRENT    0x07
#define R_ENERGY     0x09
#define R_CHARGE     0x0A
#define R_DIAGALRT   0x0B
#define R_DEVID      0x3F

#define CURRENT_LSB_nA  20000        /* 20 uA in nA for integer math */

static bool wait_flag(volatile uint32_t *reg, uint32_t mask, bool set)
{
    for (uint32_t t0 = g_ms; (g_ms - t0) < 5; ) {
        uint32_t v = *reg;
        if (set ? (v & mask) : !(v & mask))
            return true;
        if (I2C2->ISR & (I2C_ISR_NACKF | I2C_ISR_BERR | I2C_ISR_ARLO)) {
            I2C2->ICR = I2C_ICR_NACKCF | I2C_ICR_BERRCF | I2C_ICR_ARLOCF
                      | I2C_ICR_STOPCF;
            return false;
        }
    }
    return false;
}

static bool wr(uint8_t reg, const uint8_t *data, unsigned n)
{
    I2C2->CR2 = (INA_ADDR << 1) | ((n + 1u) << I2C_CR2_NBYTES_Pos)
              | I2C_CR2_AUTOEND | I2C_CR2_START;
    if (!wait_flag(&I2C2->ISR, I2C_ISR_TXIS, true)) return false;
    I2C2->TXDR = reg;
    for (unsigned i = 0; i < n; i++) {
        if (!wait_flag(&I2C2->ISR, I2C_ISR_TXIS, true)) return false;
        I2C2->TXDR = data[i];
    }
    if (!wait_flag(&I2C2->ISR, I2C_ISR_STOPF, true)) return false;
    I2C2->ICR = I2C_ICR_STOPCF;
    return true;
}

static bool rd(uint8_t reg, uint8_t *data, unsigned n)
{
    I2C2->CR2 = (INA_ADDR << 1) | (1u << I2C_CR2_NBYTES_Pos) | I2C_CR2_START;
    if (!wait_flag(&I2C2->ISR, I2C_ISR_TXIS, true)) return false;
    I2C2->TXDR = reg;
    if (!wait_flag(&I2C2->ISR, I2C_ISR_TC, true)) return false;
    I2C2->CR2 = (INA_ADDR << 1) | I2C_CR2_RD_WRN
              | (n << I2C_CR2_NBYTES_Pos) | I2C_CR2_AUTOEND | I2C_CR2_START;
    for (unsigned i = 0; i < n; i++) {
        if (!wait_flag(&I2C2->ISR, I2C_ISR_RXNE, true)) return false;
        data[i] = (uint8_t)I2C2->RXDR;
    }
    if (!wait_flag(&I2C2->ISR, I2C_ISR_STOPF, true)) return false;
    I2C2->ICR = I2C_ICR_STOPCF;
    return true;
}

static bool wr16(uint8_t reg, uint16_t v)
{
    uint8_t b[2] = { (uint8_t)(v >> 8), (uint8_t)v };
    return wr(reg, b, 2);
}

bool ina228_init(void)
{
    RCC->APB1ENR1 |= RCC_APB1ENR1_I2C2EN;
    I2C2->TIMINGR = 0x30420F13;      /* 100 kHz @ 16 MHz kernel clock */
    I2C2->CR1 = I2C_CR1_PE;

    uint8_t id[2];
    if (!rd(R_DEVID, id, 2) || (id[0] >> 4) != 0x2)   /* 0x228x */
        return false;
    /* ADCRANGE=1; continuous bus+shunt+temp, 1052 us conversions, avg 16 */
    if (!wr16(R_CONFIG, 1u << 4)) return false;
    if (!wr16(R_ADCCFG, (0xFu << 12) | (5u << 9) | (5u << 6) | (5u << 3) | 2u))
        return false;
    return wr16(R_SHUNTCAL, 2097);
}

bool ina228_read(int32_t *vbus_uv, int32_t *cur_ua)
{
    uint8_t b[3];
    if (!rd(R_VBUS, b, 3)) return false;
    /* 24-bit, LSB 195.3125 uV, bottom 4 bits reserved */
    uint32_t raw = ((uint32_t)b[0] << 16 | (uint32_t)b[1] << 8 | b[2]) >> 4;
    *vbus_uv = (int32_t)(((int64_t)raw * 1953125) / 10000);
    if (!rd(R_CURRENT, b, 3)) return false;
    int32_t c = (int32_t)((uint32_t)b[0] << 16 | (uint32_t)b[1] << 8 | b[2]);
    c = (c << 8) >> 12;              /* sign-extend 24 bit, drop 4 reserved */
    *cur_ua = (int32_t)(((int64_t)c * CURRENT_LSB_nA) / 1000);
    return true;
}

bool ina228_read_energy(int64_t *charge_nAh, int64_t *energy_nWh)
{
    uint8_t b[5];
    if (!rd(R_ENERGY, b, 5)) return false;
    uint64_t e = 0;
    for (int i = 0; i < 5; i++)
        e = (e << 8) | b[i];
    /* ENERGY_LSB = 3.2 * 20 uA * 195.3125 uV... ds: 16 * 3.2 * CURRENT_LSB */
    *energy_nWh = (int64_t)((e * 512 * CURRENT_LSB_nA) / 3600 / 1000);
    if (!rd(R_CHARGE, b, 5)) return false;
    int64_t q = 0;
    for (int i = 0; i < 5; i++)
        q = (q << 8) | b[i];
    q = (q << 24) >> 24;             /* sign-extend 40 bit */
    *charge_nAh = q * CURRENT_LSB_nA / 3600;
    return true;
}
