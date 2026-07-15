/* adc.c — ADC1: V_MEAS(IN1) I_MEAS(IN2) NTC_FET(IN15) NTC_IND(IN12);
 * ADC2: VBUS_SNS(IN3). Single conversions, polled, 640.5-cycle sampling
 * (ADC clock = SYSCLK/4 = 24 MHz -> ~27 us per conversion; the 1 kHz loop
 * spends ~140 us total, fine). */
#include "drv.h"

static void adc_enable(ADC_TypeDef *adc)
{
    adc->CR &= ~ADC_CR_DEEPPWD;
    adc->CR |= ADC_CR_ADVREGEN;
    for (volatile int i = 0; i < 2000; i++) { }      /* > 20 us */
    adc->CR |= ADC_CR_ADCAL;
    while (adc->CR & ADC_CR_ADCAL) { }
    adc->ISR = ADC_ISR_ADRDY;
    adc->CR |= ADC_CR_ADEN;
    while (!(adc->ISR & ADC_ISR_ADRDY)) { }
}

void adc_init(void)
{
    RCC->AHB2ENR |= RCC_AHB2ENR_ADC12EN;
    /* common clock: HCLK/4 synchronous */
    ADC12_COMMON->CCR = (3u << ADC_CCR_CKMODE_Pos);
    adc_enable(ADC1);
    adc_enable(ADC2);
    /* max sampling time on every used channel (high-ish source impedance) */
    ADC1->SMPR1 = (7u << ADC_SMPR1_SMP1_Pos) | (7u << ADC_SMPR1_SMP2_Pos);
    ADC1->SMPR2 = (7u << ADC_SMPR2_SMP12_Pos) | (7u << ADC_SMPR2_SMP15_Pos);
    ADC2->SMPR1 = (7u << ADC_SMPR1_SMP3_Pos);
}

static uint16_t convert(ADC_TypeDef *adc, uint32_t ch)
{
    adc->SQR1 = (ch << ADC_SQR1_SQ1_Pos);            /* length 1 */
    adc->CR |= ADC_CR_ADSTART;
    while (!(adc->ISR & ADC_ISR_EOC)) { }
    return (uint16_t)adc->DR;
}

void adc_read(adc_raw *r)
{
    r->v_meas  = convert(ADC1, 1);
    r->i_meas  = convert(ADC1, 2);
    r->ntc_ind = convert(ADC1, 12);
    r->ntc_fet = convert(ADC1, 15);
    r->vbus    = convert(ADC2, 3);
}
