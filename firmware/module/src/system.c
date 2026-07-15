/* system.c — clock tree: HSE 8 MHz -> PLL -> 96 MHz core (range 1, 3 WS).
 * 96 MHz keeps us out of boost mode while leaving 10x headroom over the
 * 1 kHz control loop. FDCAN runs from raw HSE for crystal-accurate timing;
 * I2C2 runs from HSI16 so its TIMINGR is a standard 16 MHz value. */
#include "board.h"

uint32_t SystemCoreClock = SYSCLK_HZ;
volatile uint32_t g_ms;

void SystemInit(void)
{
    /* FPU on (compiled hard-float) */
    SCB->CPACR |= (0xFu << 20);

    /* flash: 3 wait states + caches + prefetch (96 MHz, range 1) */
    FLASH->ACR = FLASH_ACR_DCEN | FLASH_ACR_ICEN | FLASH_ACR_PRFTEN
               | FLASH_ACR_LATENCY_3WS;

    /* HSE on (crystal) */
    RCC->CR |= RCC_CR_HSEON;
    while (!(RCC->CR & RCC_CR_HSERDY)) { }

    /* HSI16 stays on for I2C kernel clock. LSI for the IWDG. */
    RCC->CSR |= RCC_CSR_LSION;
    while (!(RCC->CSR & RCC_CSR_LSIRDY)) { }

    /* PLL: 8 MHz /M=1 *N=24 /R=2 = 96 MHz (VCO 192 MHz, in 96..344) */
    RCC->PLLCFGR = RCC_PLLCFGR_PLLSRC_HSE
                 | (0u << RCC_PLLCFGR_PLLM_Pos)      /* /1  */
                 | (24u << RCC_PLLCFGR_PLLN_Pos)     /* x24 */
                 | (0u << RCC_PLLCFGR_PLLR_Pos)      /* /2  */
                 | RCC_PLLCFGR_PLLREN;
    RCC->CR |= RCC_CR_PLLON;
    while (!(RCC->CR & RCC_CR_PLLRDY)) { }

    RCC->CFGR = RCC_CFGR_SW_PLL;                     /* AHB/APB1/APB2 = /1 */
    while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_PLL) { }

    /* kernel clocks: FDCAN <- HSE, I2C2 <- HSI16, ADC12 <- SYSCLK */
    RCC->CCIPR = (2u << RCC_CCIPR_ADC12SEL_Pos)      /* sysclk */
               | (2u << RCC_CCIPR_I2C2SEL_Pos)       /* HSI16  */
               | (0u << RCC_CCIPR_FDCANSEL_Pos);     /* HSE    */

    /* SysTick 1 kHz */
    SysTick_Config(SYSCLK_HZ / 1000u);
}

void SysTick_Handler(void)
{
    g_ms++;
}
