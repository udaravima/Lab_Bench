/*
 * main.c — Phase-1 module firmware: binds the host-tested module_core to the
 * STM32G431 peripherals. Architecture per docs/02 s.8: the analog CV/CC loops
 * regulate; this firmware only moves setpoints, opens/closes the output and
 * reports. The fast OVP action is hardware (TLV7011 opens the disconnect);
 * firmware adds the converter kill and the latch (EXTI4), and the OCP backup.
 *
 * Loop layout: main loop polls CAN + kicks the watchdog continuously;
 * a 1 ms tick samples ADCs, runs lb_core_tick, drives DAC/GPIO;
 * 100 ms telemetry, 500 ms status, FAULT frames on change.
 */
#include "drv.h"

static lb_core core;
static cal_block cal;
static uint8_t slot;
static adc_raw raw;
static int32_t ina_v_uv, ina_i_ua;        /* precise telemetry (INA228) */
static bool ina_ok;
static volatile bool ovp_tripped;          /* set by EXTI4, latched below */

/* ---- GPIO ------------------------------------------------------------- */
static void gpio_init(void)
{
    RCC->AHB2ENR |= RCC_AHB2ENR_GPIOAEN | RCC_AHB2ENR_GPIOBEN
                  | RCC_AHB2ENR_GPIOFEN;

    /* safe defaults before switching pins to outputs */
    PS_OFF_SET(1);
    OUT_REQ_SET(0);
    FPWM_SET(0);
    CAN_STB_SET(1);
    DAC_NSYNC(1);
    LED_OFF();

    /* PA: 0,1,6 analog; 2,3 AF7; 4,10 out; 5,7 AF5; 8,9 AF4 OD; 11,12 AF9;
     * 13,14 SWD (default); 15 input */
    GPIOA->MODER =
        (3u << 0) | (3u << 2) | (2u << 4) | (2u << 6) | (1u << 8) |
        (2u << 10) | (3u << 12) | (2u << 14) | (2u << 16) | (2u << 18) |
        (1u << 20) | (2u << 22) | (2u << 24) | (2u << 26) | (2u << 28) |
        (0u << 30);
    GPIOA->OTYPER = (1u << 8) | (1u << 9);            /* I2C open-drain */
    GPIOA->OSPEEDR |= (3u << 10) | (3u << 14) | (2u << 22) | (2u << 24);
    GPIOA->AFR[0] = (7u << 8) | (7u << 12) | (5u << 20) | (5u << 28);
    GPIOA->AFR[1] = (4u << 0) | (4u << 4) | (9u << 12) | (9u << 16);
    /* keep SWD: PA13/14 AF0 is default in AFR, MODER=AF already set above */

    /* PB: 0,1 analog; 2,3,14,15 out; 4,5,6,7 in; 10 AF1; 11,12,13 in pull-up
     * (PB4 leaves reset as NJTRST AF with a pull-up; this makes it a plain
     * input with a pull-down, so an unfitted U7 reads "no trip"). */
    GPIOB->MODER =
        (3u << 0) | (3u << 2) | (1u << 4) | (1u << 6) | (0u << 8) |
        (0u << 10) | (0u << 12) | (0u << 14) |
        (2u << 20) |
        (0u << 22) | (0u << 24) | (0u << 26) |
        (1u << 28) | (1u << 30);
    /* SLOT_ID pull-ups + PB7: INA228 ALERT is open-drain and the board has
     * no external pull-up on that net — the internal one is required. */
    GPIOB->PUPDR = (2u << 8) | (1u << 14) | (1u << 22) | (1u << 24) | (1u << 26);
    GPIOB->AFR[1] = (1u << 8);                             /* PB10 TIM2_CH3 */
}

/* ---- hardware OVP trip (matrix #4) -------------------------------------- */
/* The TLV7011 opens the disconnect by itself (Q9 on DISC_INP) but cannot
 * stop the converter or hold anything off: it is a plain comparator. Its
 * output also reaches PB4, so the rising edge kills LM5145 EN (PS_OFF ->
 * EN_KILL, which also holds DISC_INP low through Q7) within microseconds, and
 * the 1 ms tick latches OVP_HW until RESET(0x5A) with VOUT_INT back below
 * the threshold. */
static void ovp_trip_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_SYSCFGEN;
    SYSCFG->EXTICR[1] = (SYSCFG->EXTICR[1] & ~SYSCFG_EXTICR2_EXTI4)
                      | SYSCFG_EXTICR2_EXTI4_PB;
    EXTI->RTSR1 |= EXTI_RTSR1_RT4;
    EXTI->PR1 = EXTI_PR1_PIF4;
    EXTI->IMR1 |= EXTI_IMR1_IM4;
    NVIC_SetPriority(EXTI4_IRQn, 0);
    NVIC_EnableIRQ(EXTI4_IRQn);
}

void EXTI4_IRQHandler(void)
{
    EXTI->PR1 = EXTI_PR1_PIF4;
    /* a real trip holds the comparator high for as long as VOUT_INT is over
     * the threshold; an edge already gone at ISR entry (~0.2 us) is coupled
     * noise on the 40 mm OVP_TRIP run, not an overvoltage */
    if (!OVP_TRIP_IN())
        return;
    PS_OFF_SET(1);
    OUT_REQ_SET(0);
    ovp_tripped = true;
}

/* ---- fan PWM: TIM2_CH3, 25 kHz ---------------------------------------- */
static void fan_init(void)
{
    RCC->APB1ENR1 |= RCC_APB1ENR1_TIM2EN;
    TIM2->PSC = 0;
    TIM2->ARR = APB_HZ / 25000u - 1u;
    TIM2->CCMR2 = (6u << TIM_CCMR2_OC3M_Pos) | TIM_CCMR2_OC3PE;
    TIM2->CCER = TIM_CCER_CC3E;
    TIM2->CCR3 = 0;
    TIM2->CR1 = TIM_CR1_ARPE | TIM_CR1_CEN;
}
static void fan_set_pct(uint32_t pct)
{
    TIM2->CCR3 = (TIM2->ARR + 1u) * pct / 100u;
}

/* ---- CAN dispatch (doc 03) --------------------------------------------- */
static void send_fault_frame(void)
{
    lb_can_frame f;
    lb_fault_msg m = { core.fault_bits, core.warn_bits, (uint8_t)core.state };
    lb_enc_fault(&f, slot, &m);
    fdcan_tx(&f);
}

static void handle_cmd(uint8_t cmd, const lb_can_frame *f)
{
    switch ((lb_cmd_t)cmd) {
    case LB_CMD_SET_VI: {
        lb_set_vi m;
        if (lb_dec_set_vi(f, &m))
            lb_core_cmd_set_vi(&core, m.v_uv, m.i_ua);
        break;
    }
    case LB_CMD_OUTPUT: {
        uint8_t mode;
        if (lb_dec_output(f, &mode))
            lb_core_cmd_output(&core, mode);
        break;
    }
    case LB_CMD_LIMITS: {
        lb_limits m;
        if (lb_dec_limits(f, &m))
            lb_core_cmd_limits(&core, &m);
        break;
    }
    case LB_CMD_CAL_WRITE: {
        lb_cal_write m;
        if (lb_dec_cal_write(f, &m)) {
            if (m.point == LB_CAL_GAIN)
                cal.cal[m.item].gain = (uint32_t)m.value;
            else
                cal.cal[m.item].offset = m.value;
            cal_store(&cal);
        }
        break;
    }
    case LB_CMD_IDENT: {
        lb_can_frame tx;
        lb_hello h = { LB_PROTO_VERSION, FW_MAJOR, FW_MINOR,
                       *(volatile uint32_t *)UID_BASE };
        lb_enc_hello(&tx, slot, &h);
        fdcan_tx(&tx);
        break;
    }
    case LB_CMD_RESET: {
        uint8_t magic;
        if (lb_dec_reset(f, &magic)) {
            lb_core_cmd_reset(&core, magic);
            if (core.reboot_req)
                NVIC_SystemReset();
            if (magic == LB_RESET_CLEAR_FAULT)
                send_fault_frame();          /* report the cleared state */
        }
        break;
    }
    }
}

static void can_poll(void)
{
    lb_can_frame f;
    uint8_t s = 0, sub = 0;
    while (fdcan_rx(&f)) {
        switch (lb_id_parse(f.id, &s, &sub)) {
        case LB_KIND_GLOBAL_OFF:
            lb_core_global_off(&core);
            lb_core_mgr_seen(&core);
            break;
        case LB_KIND_GLOBAL_STATE:
            lb_core_mgr_seen(&core);
            break;
        case LB_KIND_CMD:
            if (s == slot) {
                handle_cmd(sub, &f);
                lb_core_mgr_seen(&core);
            }
            break;
        default:
            break;
        }
    }
}

/* ---- 1 ms control tick -------------------------------------------------- */
static void tick_1ms(void)
{
    adc_read(&raw);

    /* thermal: hottest NTC into the core (derate + OTP latch, matrix #11/12) */
    int16_t t_fet = ntc_dC(raw.ntc_fet);
    int16_t t_ind = ntc_dC(raw.ntc_ind);
    lb_core_set_temp(&core, t_fet > t_ind ? t_fet : t_ind);

    lb_core_set_hw_enable(&core, HW_EN_IN());
    lb_core_tick(&core, 1);

    /* OVP (matrix #4): the comparator output latches here. The level check
     * also re-asserts the fault after RESET while VOUT_INT is still high. */
    if (ovp_tripped || OVP_TRIP_IN()) {
        ovp_tripped = false;
        lb_core_fault(&core, LB_FAULT_OVP_HW);
    }
    /* backup OVP check on the terminals (V_MEAS is after the disconnect) */
    int32_t v_uv = lb_cal_apply(&cal.cal[LB_CAL_VMEAS],
                                (int32_t)raw.v_meas * V_MEAS_UV_PER_COUNT);
    if (v_uv > core.cfg.v_max_uv + core.cfg.v_max_uv / 8)
        lb_core_fault(&core, LB_FAULT_OVP_HW);
    /* OCP backup (matrix #2): INA240 via the ADC, and the INA228 ALERT
     * (SOVL programmed to the same 110 % limit), >5 ms -> latch */
    lb_core_ocp_sample(&core,
                       lb_cal_apply(&cal.cal[LB_CAL_IMEAS],
                                    (int32_t)raw.i_meas * I_MEAS_UA_PER_COUNT),
                       !INA_ALERT_IN(), 1);

    /* references out (calibration at the DAC boundary) */
    dac_write_v(dac_counts_v(
        lb_cal_apply(&cal.cal[LB_CAL_VSET], lb_core_vref_uv(&core))));
    dac_write_i(dac_counts_i(
        lb_cal_apply(&cal.cal[LB_CAL_ISET], lb_core_iref_ua(&core))));

    /* output controls: converter EN, disconnect, DEM/FPWM */
    bool run = core.state != LB_STATE_FAULT_LATCHED && core.hw_enable
             && core.out_mode != LB_OUT_OFF;
    /* an OVP edge landing after the latch check above must not be undone
     * here: with IRQs masked it either shows in the flag or runs after */
    __disable_irq();
    bool trip = ovp_tripped;
    PS_OFF_SET(!run || trip);
    OUT_REQ_SET(!trip && lb_core_output_closed(&core) && PS_PGOOD_IN());
    __enable_irq();
    FPWM_SET(!lb_core_dem(&core));

    /* fan: proportional 40..100 % between 45 and 75 degC */
    int16_t t = core.temp_dC;
    fan_set_pct(t <= 450 ? 0 : t >= 750 ? 100 : 40 + (t - 450) * 60 / 300);
}

/* ---- telemetry ---------------------------------------------------------- */
static void telem_100ms(void)
{
    lb_can_frame f;
    ina_ok = ina228_read(&ina_v_uv, &ina_i_ua);
    lb_set_vi vi;
    if (ina_ok) {
        vi.v_uv = ina_v_uv;
        vi.i_ua = ina_i_ua;
    } else {                       /* fall back to the ADC path */
        vi.v_uv = lb_cal_apply(&cal.cal[LB_CAL_VMEAS],
                               (int32_t)raw.v_meas * V_MEAS_UV_PER_COUNT);
        vi.i_ua = lb_cal_apply(&cal.cal[LB_CAL_IMEAS],
                               (int32_t)raw.i_meas * I_MEAS_UA_PER_COUNT);
    }
    lb_enc_telem_vi(&f, slot, &vi);
    fdcan_tx(&f);

    lb_telem_aux aux;
    aux.t_fet_dC = ntc_dC(raw.ntc_fet);
    aux.t_ind_dC = ntc_dC(raw.ntc_ind);
    aux.vbus_10mV = (uint16_t)((int64_t)raw.vbus * VBUS_UV_PER_COUNT / 10000);
    int64_t p_mw = (int64_t)vi.v_uv * vi.i_ua / 1000000000;
    aux.pout_100mW = (uint16_t)(p_mw / 100);
    lb_enc_telem_aux(&f, slot, &aux);
    fdcan_tx(&f);

    /* sense cross-check (matrix #18): ADC path vs INA228, >5 % + 500 mV */
    if (ina_ok) {
        int32_t adc_uv = lb_cal_apply(&cal.cal[LB_CAL_VMEAS],
                                      (int32_t)raw.v_meas * V_MEAS_UV_PER_COUNT);
        int32_t diff = adc_uv - ina_v_uv;
        if (diff < 0)
            diff = -diff;
        static uint8_t bad;
        if (diff > 500000 && diff > ina_v_uv / 20)
            bad++;
        else
            bad = 0;
        if (bad >= 5) {
            lb_core_fault(&core, LB_FAULT_SENSE);
            bad = 0;
        }
    }
}

static void status_500ms(void)
{
    lb_can_frame f;
    lb_status st;
    st.state = (uint8_t)core.state;
    st.fault = core.fault_bits;
    st.warn = core.warn_bits;
    st.mode = 0;
    if (lb_core_output_closed(&core)) st.mode |= LB_MODE_OUT_ON;
    if (lb_core_dem(&core))           st.mode |= LB_MODE_DEM;
    if (lb_core_droop(&core))         st.mode |= LB_MODE_DROOP;
    /* CC active heuristic: measured V more than 2 % below the reference */
    if (ina_ok && core.vref_uv > 0 &&
        ina_v_uv < core.vref_uv - core.vref_uv / 50)
        st.mode |= LB_MODE_CC_ACTIVE;
    st.vset_echo_10mV = (int16_t)(core.vset_uv / 10000);
    st.iset_echo_10mA = (int16_t)(core.iset_ua / 10000);
    lb_enc_status(&f, slot, &st);
    fdcan_tx(&f);
}

int main(void)
{
    gpio_init();
    uart_init();
    uart_puts("\nlabbench module fw " );
    uart_dec(FW_MAJOR); uart_puts("."); uart_dec(FW_MINOR); uart_puts("\n");

    slot = SLOT_ID_IN();
    cal_load(&cal);
    lb_core_init(&core, &LB_CORE_CFG_PHASE1);

    adc_init();
    dac_init();
    fan_init();
    ovp_trip_init();
    ina_ok = ina228_init() &&
             ina228_set_ocp_limit(lb_core_ocp_limit_ua(&core.cfg));
    if (!ina_ok) {
        uart_puts("INA228 missing\n");
        lb_core_fault(&core, LB_FAULT_SENSE);      /* matrix #18 */
    }
    fdcan_init(slot);
    iwdg_init(500);

    lb_can_frame hello;
    lb_hello h = { LB_PROTO_VERSION, FW_MAJOR, FW_MINOR,
                   *(volatile uint32_t *)UID_BASE };
    lb_enc_hello(&hello, slot, &h);
    fdcan_tx(&hello);
    uart_puts("slot "); uart_dec(slot); uart_puts(" up\n");

    uint32_t last_ms = g_ms, last_telem = g_ms, last_status = g_ms;
    uint8_t prev_fault = 0;
    lb_state_t prev_state = core.state;

    for (;;) {
        can_poll();
        iwdg_kick();

        uint32_t now = g_ms;
        if (now != last_ms) {
            /* catch up if a slow op (flash write) blocked more than 1 ms */
            uint32_t behind = now - last_ms;
            if (behind > 20)
                behind = 20;
            for (uint32_t i = 0; i < behind; i++)
                tick_1ms();
            last_ms = now;

            /* LED: solid in ACTIVE, 2 Hz blink in SAFE, 8 Hz in FAULT */
            uint32_t blink = (core.state == LB_STATE_ACTIVE) ? 1
                           : (core.state == LB_STATE_SAFE) ? ((now >> 8) & 1)
                                                           : ((now >> 6) & 1);
            if (blink) LED_ON(); else LED_OFF();
        }
        if (now - last_telem >= 100) {
            last_telem = now;
            telem_100ms();
        }
        if (now - last_status >= 500) {
            last_status = now;
            status_500ms();
        }
        if (core.fault_bits != prev_fault || core.state != prev_state) {
            prev_fault = core.fault_bits;
            prev_state = core.state;
            send_fault_frame();
        }
    }
}
