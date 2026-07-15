/* flash_cal.c — calibration block in the last 2K flash page (0x0801F800).
 * STM32G431CB: 64 pages x 2K, 64-bit programming granularity. */
#include "drv.h"
#include <stddef.h>

#define CAL_PAGE_ADDR  0x0801F800u
#define CAL_PAGE_INDEX 63u
#define CAL_MAGIC      0x4C424331u   /* "LBC1" */
#define CRC_LEN        offsetof(cal_block, crc)

static uint32_t crc32sw(const uint8_t *p, unsigned n)
{
    uint32_t c = 0xFFFFFFFFu;
    while (n--) {
        c ^= *p++;
        for (int k = 0; k < 8; k++)
            c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
    }
    return ~c;
}

void cal_load(cal_block *cb)
{
    const cal_block *f = (const cal_block *)CAL_PAGE_ADDR;
    if (f->magic == CAL_MAGIC &&
        f->crc == crc32sw((const uint8_t *)f, CRC_LEN)) {
        *cb = *f;
        return;
    }
    cb->magic = CAL_MAGIC;
    for (int i = 0; i < 4; i++) {
        cb->cal[i].gain = 65536;     /* identity */
        cb->cal[i].offset = 0;
    }
    cb->crc = crc32sw((const uint8_t *)cb, CRC_LEN);
}

static void flash_unlock(void)
{
    if (FLASH->CR & FLASH_CR_LOCK) {
        FLASH->KEYR = 0x45670123u;
        FLASH->KEYR = 0xCDEF89ABu;
    }
}

bool cal_store(const cal_block *cb_in)
{
    /* pad to a whole number of 64-bit words for programming */
    union {
        cal_block cb;
        uint32_t w[(sizeof(cal_block) + 7) / 8 * 2];
    } u;
    for (unsigned i = 0; i < sizeof u.w / 4; i++)
        u.w[i] = 0xFFFFFFFFu;
    u.cb = *cb_in;
    u.cb.magic = CAL_MAGIC;
    u.cb.crc = crc32sw((const uint8_t *)&u.cb, CRC_LEN);

    __disable_irq();
    flash_unlock();
    FLASH->SR = FLASH->SR;           /* clear stale error flags */
    FLASH->CR = FLASH_CR_PER | (CAL_PAGE_INDEX << FLASH_CR_PNB_Pos);
    FLASH->CR |= FLASH_CR_STRT;
    while (FLASH->SR & FLASH_SR_BSY) { }
    FLASH->CR = 0;
    FLASH->CR = FLASH_CR_PG;
    volatile uint32_t *dst = (volatile uint32_t *)CAL_PAGE_ADDR;
    for (unsigned i = 0; i < sizeof u.w / 4; i += 2) {
        dst[i] = u.w[i];
        dst[i + 1] = u.w[i + 1];
        while (FLASH->SR & FLASH_SR_BSY) { }
    }
    FLASH->CR = FLASH_CR_LOCK;
    __enable_irq();

    const cal_block *f = (const cal_block *)CAL_PAGE_ADDR;
    return f->magic == CAL_MAGIC && f->crc == u.cb.crc;
}
