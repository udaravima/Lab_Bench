/* dac80502.c — DAC80502 on SPI1 (PA5 SCK / PA7 MOSI, AF5), NSYNC = PA4 GPIO.
 * 24-bit frames, SPI mode 1 (CPOL=0, data latched on SCLK falling edge),
 * 6 MHz. Registers per DACx0502 ds: GAIN=0x04, DAC-A=0x08, DAC-B=0x09.
 * Config: REF-DIV=/2 + gain=2 -> 2.5 V full scale from the 2.5 V internal
 * reference with clean headroom on the 3V3 supply (ds 8.4.1 / doc 06 s.4). */
#include "drv.h"

#define REG_SYNC  0x02
#define REG_GAIN  0x04
#define REG_DACA  0x08
#define REG_DACB  0x09

static void xfer24(uint8_t reg, uint16_t val)
{
    DAC_NSYNC(0);
    uint8_t bytes[3] = { reg, (uint8_t)(val >> 8), (uint8_t)val };
    for (int i = 0; i < 3; i++) {
        while (!(SPI1->SR & SPI_SR_TXE)) { }
        *(volatile uint8_t *)&SPI1->DR = bytes[i];
    }
    while (SPI1->SR & SPI_SR_BSY) { }
    DAC_NSYNC(1);                     /* rising edge updates the register */
}

void dac_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_SPI1EN;
    /* master, CPOL=0 CPHA=1, /16 = 6 MHz, software NSS, 8-bit frames */
    SPI1->CR2 = (7u << SPI_CR2_DS_Pos);
    SPI1->CR1 = SPI_CR1_MSTR | SPI_CR1_CPHA | (3u << SPI_CR1_BR_Pos)
              | SPI_CR1_SSM | SPI_CR1_SSI | SPI_CR1_SPE;
    DAC_NSYNC(1);
    for (volatile int i = 0; i < 5000; i++) { }      /* DAC POR settle */
    xfer24(REG_GAIN, 0x0103);        /* REF-DIV=1(/2), BUFA/B gain=2 */
    xfer24(REG_DACA, 0);             /* both references at zero */
    xfer24(REG_DACB, 0);
}

void dac_write_v(uint16_t counts) { xfer24(REG_DACA, counts); }
void dac_write_i(uint16_t counts) { xfer24(REG_DACB, counts); }
