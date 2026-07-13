#include <stdio.h>
#include "module_core.h"

static int fails = 0;
#define CHECK(x) do { if (!(x)) { printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #x); fails++; } } while (0)

static lb_core fresh_active(void)
{
    lb_core c;
    lb_core_init(&c, &LB_CORE_CFG_PHASE1);
    lb_core_set_hw_enable(&c, true);
    lb_core_mgr_seen(&c);
    return c;
}

int main(void)
{
    /* --- boot state: safe by construction --- */
    lb_core c;
    lb_core_init(&c, &LB_CORE_CFG_PHASE1);
    CHECK(c.state == LB_STATE_SAFE);
    CHECK(!lb_core_output_closed(&c));
    CHECK(lb_core_vref_uv(&c) == 0 && lb_core_iref_ua(&c) == 0);

    /* enable refused while /HW_ENABLE is low */
    CHECK(!lb_core_cmd_output(&c, LB_OUT_ON));
    CHECK(c.state == LB_STATE_SAFE);

    /* --- envelope clamp --- */
    /* 20 V: power binds first: 150 W / 20 V = 7.5 A */
    CHECK(lb_envelope_i_ua(&LB_CORE_CFG_PHASE1, 20000000, 8000000) == 7500000);
    /* 5 V: current limit binds: 8 A */
    CHECK(lb_envelope_i_ua(&LB_CORE_CFG_PHASE1, 5000000, 10000000) == 8000000);
    /* inside the envelope: passes through */
    CHECK(lb_envelope_i_ua(&LB_CORE_CFG_PHASE1, 5000000, 8000000) == 8000000);
    CHECK(lb_envelope_i_ua(&LB_CORE_CFG_PHASE1, 0, 5000000) == 5000000);
    CHECK(lb_envelope_i_ua(&LB_CORE_CFG_PHASE1, 5000000, -1) == 0);

    c = fresh_active();
    lb_core_cmd_set_vi(&c, 20000000, 8000000);          /* clamped: warn set */
    CHECK(c.iset_ua == 7500000 && (c.warn_bits & LB_WARN_ENV_CLAMP));
    lb_core_cmd_set_vi(&c, 12000000, 5000000);          /* clean: warn clears */
    CHECK(c.iset_ua == 5000000 && !(c.warn_bits & LB_WARN_ENV_CLAMP));
    lb_core_cmd_set_vi(&c, 25000000, 1000000);          /* V above envelope */
    CHECK(c.vset_uv == 20000000 && (c.warn_bits & LB_WARN_ENV_CLAMP));

    /* --- enable + reference-domain soft start (1 V/ms) --- */
    c = fresh_active();
    lb_core_cmd_set_vi(&c, 12000000, 5000000);
    CHECK(lb_core_cmd_output(&c, LB_OUT_ON));
    CHECK(c.state == LB_STATE_ACTIVE && lb_core_output_closed(&c));
    CHECK(lb_core_vref_uv(&c) == 0);                    /* ramp starts at 0 */
    lb_core_tick(&c, 5);
    CHECK(lb_core_vref_uv(&c) == 5000000);
    lb_core_tick(&c, 10);
    CHECK(lb_core_vref_uv(&c) == 12000000);             /* capped at setpoint */
    CHECK(lb_core_iref_ua(&c) == 5000000);
    /* setpoint lowered while active: ramps down too */
    lb_core_cmd_set_vi(&c, 10000000, 5000000);
    lb_core_tick(&c, 1);
    CHECK(lb_core_vref_uv(&c) == 11000000);
    lb_core_tick(&c, 5);
    CHECK(lb_core_vref_uv(&c) == 10000000);

    /* --- output off / global off --- */
    lb_core_global_off(&c);
    CHECK(c.state == LB_STATE_SAFE && lb_core_vref_uv(&c) == 0);

    /* --- DEM / droop mode flags --- */
    c = fresh_active();
    CHECK(lb_core_cmd_output(&c, LB_OUT_ON_DEM));
    CHECK(lb_core_dem(&c) && !lb_core_droop(&c));
    CHECK(lb_core_cmd_output(&c, LB_OUT_ON_DEM_DRP));
    CHECK(lb_core_dem(&c) && lb_core_droop(&c));
    CHECK(!lb_core_cmd_output(&c, 9));                  /* undefined mode refused */

    /* --- latched fault blocks enable until explicit clear --- */
    c = fresh_active();
    CHECK(lb_core_cmd_output(&c, LB_OUT_ON));
    lb_core_fault(&c, LB_FAULT_OVP_HW);
    CHECK(c.state == LB_STATE_FAULT_LATCHED && !lb_core_output_closed(&c));
    CHECK(lb_core_vref_uv(&c) == 0 && lb_core_iref_ua(&c) == 0);
    CHECK(!lb_core_cmd_output(&c, LB_OUT_ON));          /* refused while latched */
    lb_core_cmd_reset(&c, 0x00);                        /* wrong magic: no effect */
    CHECK(c.state == LB_STATE_FAULT_LATCHED);
    lb_core_cmd_reset(&c, LB_RESET_CLEAR_FAULT);
    CHECK(c.state == LB_STATE_SAFE && c.fault_bits == 0);
    CHECK(lb_core_cmd_output(&c, LB_OUT_ON));           /* enable works again */

    /* reboot magic only requests, never touches the output state */
    CHECK(!c.reboot_req);
    lb_core_cmd_reset(&c, LB_RESET_REBOOT);
    CHECK(c.reboot_req && c.state == LB_STATE_ACTIVE);

    /* --- comms loss, policy OFF (default) --- */
    c = fresh_active();
    CHECK(lb_core_cmd_output(&c, LB_OUT_ON));
    lb_core_tick(&c, 2999);
    CHECK(c.state == LB_STATE_ACTIVE && !(c.warn_bits & LB_WARN_COMMS_LOST));
    lb_core_tick(&c, 2);
    CHECK(c.state == LB_STATE_SAFE && (c.warn_bits & LB_WARN_COMMS_LOST));
    /* manager returns: warn clears, output stays off until commanded */
    lb_core_mgr_seen(&c);
    CHECK(!(c.warn_bits & LB_WARN_COMMS_LOST) && c.state == LB_STATE_SAFE);

    /* --- comms loss, policy HOLD (battery-charge runs) --- */
    c = fresh_active();
    lb_limits lm = { .p_max_mw = 0, .t_derate_dC = 0, .policy = LB_POLICY_HOLD };
    lb_core_cmd_limits(&c, &lm);
    lb_core_cmd_set_vi(&c, 14400000, 5000000);
    CHECK(lb_core_cmd_output(&c, LB_OUT_ON_DEM));
    lb_core_tick(&c, 10000);
    CHECK(c.state == LB_STATE_ACTIVE);                  /* keeps charging */
    CHECK(c.warn_bits & LB_WARN_COMMS_LOST);            /* but flags it */

    /* --- LIMITS can only tighten the envelope --- */
    c = fresh_active();
    lb_limits tighter = { .p_max_mw = 100000, .t_derate_dC = 0, .policy = LB_POLICY_OFF };
    lb_core_cmd_limits(&c, &tighter);
    CHECK(c.cfg.p_max_mw == 100000);
    lb_limits looser = { .p_max_mw = 900000, .t_derate_dC = 0, .policy = LB_POLICY_OFF };
    lb_core_cmd_limits(&c, &looser);
    CHECK(c.cfg.p_max_mw == 100000);                    /* cannot exceed hardware */
    lb_core_cmd_set_vi(&c, 20000000, 8000000);
    CHECK(c.iset_ua == 5000000);                        /* 100 W / 20 V */

    /* --- thermal derate and OTP latch --- */
    c = fresh_active();
    lb_core_cmd_set_vi(&c, 10000000, 8000000);
    CHECK(lb_core_cmd_output(&c, LB_OUT_ON));
    lb_core_set_temp(&c, 840);
    CHECK(lb_core_iref_ua(&c) == 8000000 && !(c.warn_bits & LB_WARN_DERATE));
    lb_core_set_temp(&c, 925);                          /* halfway 85..100 C */
    CHECK(c.warn_bits & LB_WARN_DERATE);
    CHECK(lb_core_iref_ua(&c) == 4000000);              /* linearly halved */
    lb_core_set_temp(&c, 1000);                         /* OTP latch */
    CHECK(c.state == LB_STATE_FAULT_LATCHED && (c.fault_bits & LB_FAULT_OTP));

    /* --- /HW_ENABLE kill and release --- */
    c = fresh_active();
    CHECK(lb_core_cmd_output(&c, LB_OUT_ON));
    lb_core_set_hw_enable(&c, false);
    CHECK(c.state == LB_STATE_SAFE && !lb_core_output_closed(&c));
    lb_core_set_hw_enable(&c, true);
    CHECK(c.state == LB_STATE_SAFE);                    /* no silent re-energize */

    /* --- calibration helper --- */
    lb_cal k = { .gain = 65536 + 655, .offset = -1200 };   /* +0.99945 % gain, -1.2 mV */
    CHECK(lb_cal_apply(&k, 1000000) == 1008794);           /* 1e6*66191/65536 - 1200 */
    lb_cal unity = { .gain = 65536, .offset = 0 };
    CHECK(lb_cal_apply(&unity, -12345678) == -12345678);

    if (fails == 0) printf("test_core: all checks passed\n");
    return fails ? 1 : 0;
}
