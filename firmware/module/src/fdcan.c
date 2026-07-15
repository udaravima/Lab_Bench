/* fdcan.c — FDCAN1 as classic CAN 2.0B at 500 kbit/s.
 * Kernel clock = HSE 8 MHz (crystal-accurate): prescaler 1, 16 tq/bit,
 * seg1 13 / seg2 2, sample point 87.5 % (CiA recommendation).
 * G4 message RAM is the fixed SRAMCAN layout (RM0440 44.3.3):
 *   std filters @0x0000 (28x4B), RX FIFO0 @0x00B0 (3x72B),
 *   RX FIFO1 @0x0188, TX events @0x0260, TX buffers @0x0278 (3x72B). */
#include "drv.h"

#define MRAM ((volatile uint32_t *)SRAMCAN_BASE)
#define FLSSA_W   (0x0000 / 4)
#define RXF0_W    (0x00B0 / 4)
#define TXB_W     (0x0278 / 4)
#define ELEM_W    18                 /* 72-byte RX/TX element, in words */

void fdcan_init(uint8_t slot)
{
    RCC->APB1ENR1 |= RCC_APB1ENR1_FDCANEN;

    CAN_STB_SET(0);                  /* TCAN1042 out of standby */

    FDCAN1->CCCR |= FDCAN_CCCR_INIT;
    while (!(FDCAN1->CCCR & FDCAN_CCCR_INIT)) { }
    FDCAN1->CCCR |= FDCAN_CCCR_CCE;

    /* 500 kbit/s from 8 MHz: NBRP=1x, NTSEG1=13tq, NTSEG2=2tq, NSJW=2tq */
    FDCAN1->NBTP = (1u << FDCAN_NBTP_NSJW_Pos)
                 | (0u << FDCAN_NBTP_NBRP_Pos)
                 | (12u << FDCAN_NBTP_NTSEG1_Pos)
                 | (1u << FDCAN_NBTP_NTSEG2_Pos);

    /* wipe message RAM (undefined at power-up) */
    for (int i = 0; i < 212; i++)
        MRAM[i] = 0;

    /* standard filters: classic filter (SFT=2) with mask, store in FIFO0.
     * [0] GLOBAL_OFF + GLOBAL_STATE (0x020/0x021 -> id 0x020 mask 0x7FE)
     * [1] CMD block for this slot   (0x100+slot*16 +0..15 -> mask 0x7F0) */
    MRAM[FLSSA_W + 0] = (2u << 30) | (1u << 27)
                      | ((uint32_t)LB_ID_GLOBAL_OFF << 16) | 0x7FEu;
    MRAM[FLSSA_W + 1] = (2u << 30) | (1u << 27)
                      | ((uint32_t)lb_id_cmd(slot, (lb_cmd_t)0) << 16) | 0x7F0u;

    /* 2 std filters, reject everything else incl. remote frames */
    FDCAN1->RXGFC = (2u << FDCAN_RXGFC_LSS_Pos)
                  | (2u << FDCAN_RXGFC_ANFS_Pos)
                  | (2u << FDCAN_RXGFC_ANFE_Pos)
                  | FDCAN_RXGFC_RRFS | FDCAN_RXGFC_RRFE;

    FDCAN1->CCCR &= ~FDCAN_CCCR_INIT;                /* go */
    while (FDCAN1->CCCR & FDCAN_CCCR_INIT) { }
}

bool fdcan_rx(lb_can_frame *f)
{
    uint32_t s = FDCAN1->RXF0S;
    if (!(s & FDCAN_RXF0S_F0FL))
        return false;
    uint32_t idx = (s & FDCAN_RXF0S_F0GI) >> FDCAN_RXF0S_F0GI_Pos;
    volatile uint32_t *e = &MRAM[RXF0_W + idx * ELEM_W];
    uint32_t w0 = e[0], w1 = e[1];
    f->id = (uint16_t)((w0 >> 18) & 0x7FFu);
    f->dlc = (uint8_t)((w1 >> 16) & 0xFu);
    if (f->dlc > 8)
        f->dlc = 8;
    uint32_t d0 = e[2], d1 = e[3];
    for (int i = 0; i < 4; i++) {
        f->data[i] = (uint8_t)(d0 >> (8 * i));
        f->data[4 + i] = (uint8_t)(d1 >> (8 * i));
    }
    FDCAN1->RXF0A = idx;
    return true;
}

bool fdcan_tx(const lb_can_frame *f)
{
    uint32_t fqs = FDCAN1->TXFQS;
    if (fqs & FDCAN_TXFQS_TFQF)
        return false;
    uint32_t idx = (fqs & FDCAN_TXFQS_TFQPI) >> FDCAN_TXFQS_TFQPI_Pos;
    volatile uint32_t *e = &MRAM[TXB_W + idx * ELEM_W];
    e[0] = ((uint32_t)f->id << 18);
    e[1] = ((uint32_t)f->dlc << 16);
    uint32_t d0 = 0, d1 = 0;
    for (int i = 0; i < 4; i++) {
        d0 |= (uint32_t)f->data[i] << (8 * i);
        d1 |= (uint32_t)f->data[4 + i] << (8 * i);
    }
    e[2] = d0;
    e[3] = d1;
    FDCAN1->TXBAR = 1u << idx;
    return true;
}
