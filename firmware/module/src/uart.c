/* uart.c — USART2 on PA2/PA3 (AF7), 115200 8N1, blocking TX. */
#include "drv.h"

void uart_init(void)
{
    RCC->APB1ENR1 |= RCC_APB1ENR1_USART2EN;
    USART2->BRR = APB_HZ / 115200u;
    USART2->CR1 = USART_CR1_TE | USART_CR1_RE | USART_CR1_UE;
}

static void tx(char c)
{
    while (!(USART2->ISR & USART_ISR_TXE)) { }
    USART2->TDR = (uint8_t)c;
}

void uart_puts(const char *s)
{
    while (*s) {
        if (*s == '\n')
            tx('\r');
        tx(*s++);
    }
}

void uart_dec(int32_t v)
{
    char buf[12];
    int i = 11;
    uint32_t u = (v < 0) ? (uint32_t)-v : (uint32_t)v;
    buf[i] = 0;
    do {
        buf[--i] = (char)('0' + u % 10);
        u /= 10;
    } while (u);
    if (v < 0)
        buf[--i] = '-';
    uart_puts(&buf[i]);
}

void uart_hex(uint32_t v)
{
    static const char d[] = "0123456789ABCDEF";
    char buf[9];
    for (int i = 0; i < 8; i++)
        buf[i] = d[(v >> (28 - 4 * i)) & 0xF];
    buf[8] = 0;
    uart_puts(buf);
}
