/*
 * module_core.h — hardware-independent control core of a PSU module.
 * Implements the state machine of docs/03-can-protocol.md §5 and the
 * firmware-side rows of docs/04-protection-matrix.md.
 *
 * No HAL, no interrupts, no floats: the STM32 wrapper feeds it commands,
 * temperatures and a millisecond tick; it answers with reference values and
 * output-control flags. The same code runs under host unit tests.
 *
 * The analog CV/CC loops regulate; this core only decides *setpoints* and
 * *on/off*, so nothing here is in the fast safety path.
 */
#ifndef MODULE_CORE_H
#define MODULE_CORE_H

#include "labbench_can.h"

typedef struct {
    int32_t  v_max_uv;          /* envelope: absolute voltage limit   */
    int32_t  i_max_ua;          /* envelope: absolute current limit   */
    int32_t  p_max_mw;          /* envelope: power limit              */
    uint32_t ramp_uv_per_ms;    /* reference-domain soft-start rate   */
    int16_t  derate_start_dC;   /* thermal derate begins (0.1 degC)   */
    int16_t  derate_stop_dC;    /* I forced to 0 / OTP latch (0.1 degC) */
    uint32_t comms_timeout_ms;  /* manager-heartbeat loss threshold   */
} lb_core_cfg;

/* Phase-1 prototype defaults (20 V / 8 A / 150 W, 1 V/ms, 85..100 degC, 3 s) */
extern const lb_core_cfg LB_CORE_CFG_PHASE1;

typedef struct {
    lb_core_cfg cfg;
    lb_state_t  state;
    uint8_t     fault_bits;
    uint8_t     warn_bits;
    uint8_t     out_mode;        /* requested LB_OUT_* mode           */
    uint8_t     policy;          /* comms-loss policy                 */
    bool        hw_enable;       /* backplane /HW_ENABLE (true = run) */
    bool        reboot_req;
    int16_t     temp_dC;         /* hottest NTC                       */
    int32_t     vset_uv;         /* accepted setpoints (post-clamp)   */
    int32_t     iset_ua;
    int32_t     vref_uv;         /* live, ramped V reference          */
    uint32_t    ms_since_mgr;
} lb_core;

void lb_core_init(lb_core *c, const lb_core_cfg *cfg);

/* -- inputs from the CAN dispatcher -------------------------------------- */
void lb_core_cmd_set_vi(lb_core *c, int32_t v_uv, int32_t i_ua);
bool lb_core_cmd_output(lb_core *c, uint8_t mode);   /* false = refused */
void lb_core_cmd_limits(lb_core *c, const lb_limits *m);
void lb_core_cmd_reset(lb_core *c, uint8_t magic);
void lb_core_global_off(lb_core *c);
void lb_core_mgr_seen(lb_core *c);                   /* any manager frame */

/* -- inputs from supervisors / hardware ----------------------------------- */
void lb_core_set_hw_enable(lb_core *c, bool enabled);
void lb_core_set_temp(lb_core *c, int16_t dC);
void lb_core_fault(lb_core *c, uint8_t fault_bit);   /* latching, matrix rows */

/* -- periodic -------------------------------------------------------------- */
void lb_core_tick(lb_core *c, uint32_t dt_ms);

/* -- outputs to the hardware layer ----------------------------------------- */
static inline bool lb_core_output_closed(const lb_core *c) { return c->state == LB_STATE_ACTIVE && c->hw_enable; }
static inline bool lb_core_dem(const lb_core *c)   { return c->out_mode == LB_OUT_ON_DEM   || c->out_mode == LB_OUT_ON_DEM_DRP; }
static inline bool lb_core_droop(const lb_core *c) { return c->out_mode == LB_OUT_ON_DROOP || c->out_mode == LB_OUT_ON_DEM_DRP; }
int32_t lb_core_vref_uv(const lb_core *c);           /* ramped V reference  */
int32_t lb_core_iref_ua(const lb_core *c);           /* derated I reference */

/* Envelope clamp used for both accepted setpoints and status reporting:
 * i limited to min(i_max, p_max/v). Exposed for tests and the manager UI. */
int32_t lb_envelope_i_ua(const lb_core_cfg *cfg, int32_t v_uv, int32_t i_req_ua);

/* Two-point calibration: y = x * gain / 65536 + offset (gain 65536 = 1.0).
 * Applied by the HAL at the DAC/ADC boundary. */
typedef struct { uint32_t gain; int32_t offset; } lb_cal;
static inline int32_t lb_cal_apply(const lb_cal *k, int32_t x)
{
    return (int32_t)(((int64_t)x * k->gain) / 65536) + k->offset;
}

#endif /* MODULE_CORE_H */
