/* startup.c — vector table + reset for STM32G431 (bare-metal, no assembly). */
#include <stdint.h>

extern uint32_t _estack, _sidata, _sdata, _edata, _sbss, _ebss;
extern int main(void);
void SystemInit(void);

void Reset_Handler(void)
{
    const uint32_t *src = &_sidata;
    for (uint32_t *dst = &_sdata; dst < &_edata; )
        *dst++ = *src++;
    for (uint32_t *dst = &_sbss; dst < &_ebss; )
        *dst++ = 0;
    SystemInit();
    main();
    for (;;) { }
}

void Default_Handler(void)
{
    for (;;) { }
}

void SysTick_Handler(void);
void NMI_Handler(void)        __attribute__((weak, alias("Default_Handler")));
void HardFault_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void MemManage_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void BusFault_Handler(void)   __attribute__((weak, alias("Default_Handler")));
void UsageFault_Handler(void) __attribute__((weak, alias("Default_Handler")));

/* Cortex-M4 core vectors + enough IRQ slots for the peripherals in use.
 * Everything routes to Default_Handler; the firmware polls (only SysTick
 * interrupts are enabled). Slots must simply exist so any spurious enable
 * lands in a defined loop instead of random code. */
__attribute__((section(".isr_vector"), used))
static void (* const vectors[16 + 102])(void) = {
    (void (*)(void))((uintptr_t)&_estack),
    Reset_Handler,
    NMI_Handler,
    HardFault_Handler,
    MemManage_Handler,
    BusFault_Handler,
    UsageFault_Handler,
    0, 0, 0, 0,
    Default_Handler,            /* SVCall */
    Default_Handler,            /* DebugMon */
    0,
    Default_Handler,            /* PendSV */
    SysTick_Handler,
    /* external IRQs 0..101: Default_Handler via designated range below */
    [16 ... 16 + 101] = Default_Handler,
};
