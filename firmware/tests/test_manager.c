/* Host tests for manager_core: discovery, supervision, ack/retry, budget
 * arbitration, charge sequencer (docs/10, docs/03 §3/§6/§7, matrix #15/#17). */
#include <stdio.h>
#include "manager_core.h"

static int fails = 0;
#define CHECK(x) do { if (!(x)) { printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #x); fails++; } } while (0)

/* drain the TX ring, counting frames per CAN id; returns total */
static int drain(lb_mgr *m, uint16_t count_id, int *matched)
{
    lb_can_frame f;
    int total = 0, hit = 0;
    while (lb_mgr_tx_pop(m, &f)) {
        total++;
        if (f.id == count_id) hit++;
    }
    if (matched) *matched = hit;
    return total;
}

static void say_hello(lb_mgr *m, uint8_t slot)
{
    lb_can_frame f;
    lb_hello h = { LB_PROTO_VERSION, 0, 1, 0xDEADBEEF };
    lb_enc_hello(&f, slot, &h);
    lb_mgr_rx(m, &f);
}

/* STATUS with mode bits + setpoint echo derived from the channel's ask */
static void say_status(lb_mgr *m, uint8_t slot, uint8_t mode_bits,
                       int32_t echo_v_uv, int32_t echo_i_ua)
{
    lb_can_frame f;
    lb_status st = {
        .state = (mode_bits & LB_MODE_OUT_ON) ? LB_STATE_ACTIVE : LB_STATE_SAFE,
        .fault = 0, .warn = 0, .mode = mode_bits,
        .vset_echo_10mV = (int16_t)(echo_v_uv / 10000),
        .iset_echo_10mA = (int16_t)(echo_i_ua / 10000),
    };
    lb_enc_status(&f, slot, &st);
    lb_mgr_rx(m, &f);
}

static void say_telem(lb_mgr *m, uint8_t slot, int32_t v_uv, int32_t i_ua)
{
    lb_can_frame f;
    lb_set_vi vi = { v_uv, i_ua };
    lb_enc_telem_vi(&f, slot, &vi);
    lb_mgr_rx(m, &f);
}

int main(void)
{
    lb_mgr m;

    /* --- boot: nothing known, requests refused, heartbeat runs --- */
    lb_mgr_init(&m, NULL);
    CHECK(!m.chan[0].known && !m.chan[3].known);
    CHECK(!lb_mgr_set_vi(&m, 0, 12000000, 1000000));
    CHECK(!lb_mgr_request_output(&m, 0, LB_OUT_ON));
    int hb = 0;
    lb_mgr_tick(&m, 1000);
    drain(&m, LB_ID_GLOBAL_STATE, &hb);
    CHECK(hb == 1);
    lb_mgr_tick(&m, 999);
    CHECK(drain(&m, 0, NULL) == 0);          /* not due yet */
    lb_mgr_tick(&m, 1);
    drain(&m, LB_ID_GLOBAL_STATE, &hb);
    CHECK(hb == 1 && m.seq == 2);

    /* --- discovery + supervision (matrix #15) --- */
    lb_mgr_init(&m, NULL);
    say_hello(&m, 2);
    CHECK(m.chan[2].known && !m.chan[2].lost);
    lb_mgr_tick(&m, 999);
    CHECK(!m.chan[2].lost);
    lb_mgr_tick(&m, 1);
    CHECK(m.chan[2].lost);                   /* silent 1 s -> lost */
    say_status(&m, 2, 0, 0, 0);
    CHECK(!m.chan[2].lost);                  /* recovered on any STATUS */
    CHECK(!lb_mgr_set_vi(&m, 5, 1, 1));      /* slot never seen: refused */

    /* --- SET_VI ack via STATUS echo (docs/03 §3) --- */
    lb_mgr_init(&m, NULL);
    say_hello(&m, 0);
    say_status(&m, 0, 0, 0, 0);
    CHECK(lb_mgr_set_vi(&m, 0, 12000000, 2000000));
    CHECK(m.chan[0].ack_pending);
    int setvi = 0;
    drain(&m, lb_id_cmd(0, LB_CMD_SET_VI), &setvi);
    CHECK(setvi == 1);
    say_status(&m, 0, 0, 11990000, 2000000); /* wrong echo: still pending */
    CHECK(m.chan[0].ack_pending);
    say_status(&m, 0, 0, 12000000, 2000000); /* correct echo: acked */
    CHECK(!m.chan[0].ack_pending && !m.chan[0].unresponsive);

    /* --- retry x3 then unresponsive --- */
    CHECK(lb_mgr_set_vi(&m, 0, 15000000, 2000000));
    drain(&m, 0, NULL);
    lb_mgr_tick(&m, 50);                     /* retry 1 */
    drain(&m, lb_id_cmd(0, LB_CMD_SET_VI), &setvi);
    CHECK(setvi == 1 && m.chan[0].ack_pending);
    lb_mgr_tick(&m, 50);                     /* retry 2 */
    drain(&m, lb_id_cmd(0, LB_CMD_SET_VI), &setvi);
    CHECK(setvi == 1);
    lb_mgr_tick(&m, 50);                     /* attempts exhausted */
    CHECK(!m.chan[0].ack_pending && m.chan[0].unresponsive);
    say_status(&m, 0, 0, 15000000, 2000000); /* late echo doesn't resurrect */
    CHECK(m.chan[0].unresponsive == false || !m.chan[0].ack_pending);

    /* --- budget arbiter (docs/01 §2, matrix #17): 1.5 kW default --- */
    lb_mgr_init(&m, NULL);
    say_hello(&m, 0);
    say_status(&m, 0, 0, 0, 0);
    say_hello(&m, 1);
    say_status(&m, 1, 0, 0, 0);
    CHECK(lb_mgr_set_vi(&m, 0, 24000000, 30000000));   /* 720 W ask */
    CHECK(lb_mgr_request_output(&m, 0, LB_OUT_ON));
    say_status(&m, 0, LB_MODE_OUT_ON, 24000000, 30000000);
    CHECK(lb_mgr_set_vi(&m, 1, 24000000, 30000000));   /* chan off: allowed */
    CHECK(lb_mgr_committed_mw(&m, 1, 24000000, 30000000) == 1440000);
    CHECK(lb_mgr_request_output(&m, 1, LB_OUT_ON));    /* 1440 W total: ok */
    say_status(&m, 1, LB_MODE_OUT_ON, 24000000, 30000000);
    /* raising chan 1 to 28 V x 30 A = 840 W -> 1560 W total: refused */
    CHECK(!lb_mgr_set_vi(&m, 1, 28000000, 30000000));
    CHECK(m.chan[1].vset_uv == 24000000);              /* ask unchanged */
    /* chan 0 lost: excluded from the budget, the raise now fits */
    lb_mgr_tick(&m, 1000);                             /* both lose heartbeat */
    CHECK(m.chan[0].lost && m.chan[1].lost);
    say_status(&m, 1, LB_MODE_OUT_ON, 24000000, 30000000);  /* 1 recovers */
    CHECK(lb_mgr_set_vi(&m, 1, 28000000, 30000000));
    /* measured > commanded dominates the committed sum */
    say_status(&m, 0, LB_MODE_OUT_ON, 24000000, 30000000);  /* 0 recovers */
    say_telem(&m, 0, 24000000, 32000000);              /* measures 768 W */
    CHECK(lb_mgr_committed_mw(&m, 1, 0, 0) == 768000);
    /* OFF is always granted */
    CHECK(lb_mgr_request_output(&m, 0, LB_OUT_OFF));

    /* --- global off latches; enables refused until resume --- */
    lb_mgr_global_off(&m);
    int goff = 0;
    drain(&m, LB_ID_GLOBAL_OFF, &goff);
    CHECK(goff == 1 && m.global_off);
    CHECK(!lb_mgr_request_output(&m, 1, LB_OUT_ON));
    lb_mgr_resume(&m);
    CHECK(lb_mgr_set_vi(&m, 1, 12000000, 5000000));
    CHECK(lb_mgr_request_output(&m, 1, LB_OUT_ON));

    /* --- charge sequencer: CC -> CV -> cutoff (docs/03 §7) --- */
    lb_mgr_init(&m, NULL);
    say_hello(&m, 4);
    say_status(&m, 4, 0, 0, 0);
    lb_chg_profile p = {
        .v_float_uv = 14400000, .i_charge_ua = 5000000,
        .i_cutoff_ua = 500000, .t_hold_ms = 30000, .t_max_ms = 0,
    };
    CHECK(lb_mgr_charge_start(&m, 4, &p));
    CHECK(m.chan[4].chg == LB_CHG_RAMP);
    int lim = 0, out = 0;
    lb_can_frame f;
    while (lb_mgr_tx_pop(&m, &f)) {
        if (f.id == lb_id_cmd(4, LB_CMD_LIMITS)) {
            lb_limits l;
            CHECK(lb_dec_limits(&f, &l) && l.policy == LB_POLICY_HOLD);
            lim++;
        }
        if (f.id == lb_id_cmd(4, LB_CMD_OUTPUT)) {
            uint8_t mode;
            CHECK(lb_dec_output(&f, &mode) && mode == LB_OUT_ON_DEM);
            out++;
        }
    }
    CHECK(lim == 1 && out == 1);
    say_status(&m, 4, LB_MODE_OUT_ON | LB_MODE_DEM | LB_MODE_CC_ACTIVE,
               14400000, 5000000);
    lb_mgr_tick(&m, 10);
    CHECK(m.chan[4].chg == LB_CHG_CC);
    say_status(&m, 4, LB_MODE_OUT_ON | LB_MODE_DEM, 14400000, 5000000);
    lb_mgr_tick(&m, 10);
    CHECK(m.chan[4].chg == LB_CHG_CV);                 /* the CC->CV knee */
    say_telem(&m, 4, 14400000, 400000);                /* below cutoff */
    /* 35 x 900 ms = 31.5 s with the heartbeat kept fresh (a 10 s tick would
     * trip supervision first - the core rightly aborts LOST in that case) */
    for (int i = 0; i < 35; i++) {
        say_status(&m, 4, LB_MODE_OUT_ON | LB_MODE_DEM, 14400000, 5000000);
        say_telem(&m, 4, 14400000, 400000);
        lb_mgr_tick(&m, 900);
    }
    CHECK(m.chan[4].chg == LB_CHG_DONE);
    drain(&m, lb_id_cmd(4, LB_CMD_OUTPUT), &out);
    CHECK(out >= 1);                                   /* charger shut off */

    /* --- charge aborts: module fault --- */
    lb_mgr_init(&m, NULL);
    say_hello(&m, 4);
    say_status(&m, 4, 0, 0, 0);
    CHECK(lb_mgr_charge_start(&m, 4, &p));
    say_status(&m, 4, LB_MODE_OUT_ON | LB_MODE_CC_ACTIVE, 14400000, 5000000);
    lb_mgr_tick(&m, 10);
    CHECK(m.chan[4].chg == LB_CHG_CC);
    lb_fault_msg fm = { LB_FAULT_OTP, 0, LB_STATE_FAULT_LATCHED };
    lb_enc_fault(&f, 4, &fm);
    lb_mgr_rx(&m, &f);
    lb_mgr_tick(&m, 10);
    CHECK(m.chan[4].chg == LB_CHG_ABORT);
    CHECK(m.chan[4].chg_abort_reason == LB_CHG_ABORT_FAULT);

    /* --- charge abort: channel lost (supervision broken, latched) --- */
    lb_mgr_init(&m, NULL);
    say_hello(&m, 4);
    say_status(&m, 4, 0, 0, 0);
    CHECK(lb_mgr_charge_start(&m, 4, &p));
    say_status(&m, 4, LB_MODE_OUT_ON | LB_MODE_CC_ACTIVE, 14400000, 5000000);
    lb_mgr_tick(&m, 1000);                             /* heartbeat gone */
    CHECK(m.chan[4].lost && m.chan[4].chg == LB_CHG_ABORT);
    CHECK(m.chan[4].chg_abort_reason == LB_CHG_ABORT_LOST);

    /* --- charge abort: total-time guard --- */
    lb_mgr_init(&m, NULL);
    say_hello(&m, 4);
    say_status(&m, 4, 0, 0, 0);
    p.t_max_ms = 5000;
    CHECK(lb_mgr_charge_start(&m, 4, &p));
    for (int i = 0; i < 6; i++) {
        say_status(&m, 4, LB_MODE_OUT_ON | LB_MODE_CC_ACTIVE, 14400000, 5000000);
        lb_mgr_tick(&m, 900);                          /* 5.4 s total, hb fresh */
    }
    CHECK(m.chan[4].chg == LB_CHG_ABORT);
    CHECK(m.chan[4].chg_abort_reason == LB_CHG_ABORT_TIMEOUT);

    /* --- HELLO after a module reboot resets our view of it --- */
    lb_mgr_init(&m, NULL);
    say_hello(&m, 6);
    say_status(&m, 6, 0, 0, 0);
    CHECK(lb_mgr_set_vi(&m, 6, 12000000, 1000000));
    CHECK(lb_mgr_request_output(&m, 6, LB_OUT_ON));
    CHECK(m.chan[6].out_mode == LB_OUT_ON);
    say_hello(&m, 6);                                  /* it rebooted (IWDG) */
    CHECK(m.chan[6].out_mode == LB_OUT_OFF && !m.chan[6].ack_pending);

    printf("test_manager: %s\n", fails ? "FAILURES" : "all OK");
    return fails ? 1 : 0;
}
