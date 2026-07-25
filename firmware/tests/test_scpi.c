/* Host tests for scpi_core: grammar, numbers, refusals, error queue
 * (docs/01 §6, docs/10). Reuses the fake-module helpers of test_manager. */
#include <stdio.h>
#include <string.h>
#include "scpi_core.h"

static int fails = 0;
#define CHECK(x) do { if (!(x)) { printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #x); fails++; } } while (0)

static void say_hello(lb_mgr *m, uint8_t slot)
{
    lb_can_frame f;
    lb_hello h = { LB_PROTO_VERSION, 0, 1, 0xDEADBEEF };
    lb_enc_hello(&f, slot, &h);
    lb_mgr_rx(m, &f);
}

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

static void drain(lb_mgr *m) { lb_can_frame f; while (lb_mgr_tx_pop(m, &f)) {} }

static char rsp[64];
static int go(lb_scpi *s, const char *line)
{
    return lb_scpi_line(s, line, rsp, sizeof(rsp));
}

int main(void)
{
    lb_mgr m;
    lb_scpi s;
    lb_mgr_init(&m, NULL);
    lb_scpi_init(&s, &m);

    /* --- *IDN? and case/short-form insensitivity --- */
    CHECK(go(&s, "*IDN?") > 0 && strncmp(rsp, "LabBench,", 9) == 0);
    CHECK(go(&s, "syst:err?") > 0 && strcmp(rsp, "0,\"No error\"") == 0);

    /* --- setpoints on a discovered channel (n is 1-based) --- */
    say_hello(&m, 2);                            /* channel 3 */
    CHECK(go(&s, "SOUR3:VOLT 12.5") == 0);
    CHECK(go(&s, "sour3:volt?") > 0 && strcmp(rsp, "12.500000") == 0);
    CHECK(go(&s, "SOURCE3:CURRENT 850mA") == 0);
    CHECK(go(&s, "SOUR3:CURR?") > 0 && strcmp(rsp, "0.850000") == 0);
    CHECK(m.chan[2].vset_uv == 12500000 && m.chan[2].iset_ua == 850000);
    CHECK(go(&s, "SYST:ERR?") > 0 && strcmp(rsp, "0,\"No error\"") == 0);
    drain(&m);

    /* --- undiscovered channel refused, error queued --- */
    CHECK(go(&s, "SOUR1:VOLT 5") == 0);
    CHECK(go(&s, "SYST:ERR?") > 0 && strncmp(rsp, "-221,", 5) == 0);

    /* --- measurements come from TELEM_VI --- */
    say_telem(&m, 2, 12487000, 2998000);
    CHECK(go(&s, "MEAS3:VOLT?") > 0 && strcmp(rsp, "12.487000") == 0);
    CHECK(go(&s, "MEAS3:CURR?") > 0 && strcmp(rsp, "2.998000") == 0);
    CHECK(go(&s, "MEAS3:POW?") > 0 && strncmp(rsp, "37.4", 4) == 0);

    /* --- output on/off + live query --- */
    CHECK(go(&s, "OUTP3 ON") == 0);
    CHECK(go(&s, "SYST:ERR?") > 0 && strcmp(rsp, "0,\"No error\"") == 0);
    CHECK(m.chan[2].out_mode == LB_OUT_ON);
    CHECK(go(&s, "OUTP3?") > 0 && strcmp(rsp, "0") == 0);   /* not live yet */
    say_status(&m, 2, LB_MODE_OUT_ON, 12500000, 850000);
    CHECK(go(&s, "OUTP3?") > 0 && strcmp(rsp, "1") == 0);
    CHECK(go(&s, "OUTP3 OFF") == 0 && m.chan[2].out_mode == LB_OUT_OFF);
    drain(&m);

    /* --- budget --- */
    CHECK(go(&s, "SYST:BUDG?") > 0 && strcmp(rsp, "1500") == 0);
    CHECK(go(&s, "SYST:BUDG 600") == 0);
    CHECK(m.cfg.budget_mw == 600000);
    /* channel 3 asks 12.5 V x 30 A = 375 W: fine; then x2 via raise: no */
    say_status(&m, 2, 0, 12500000, 850000);
    CHECK(go(&s, "SOUR3:CURR 30") == 0);
    CHECK(go(&s, "SYST:ERR?") > 0 && strcmp(rsp, "0,\"No error\"") == 0);
    CHECK(go(&s, "OUTP3 ON") == 0);
    say_status(&m, 2, LB_MODE_OUT_ON, 12500000, 30000000);
    CHECK(go(&s, "SOUR3:VOLT 25") == 0);         /* 750 W > 600 W budget */
    CHECK(go(&s, "SYST:ERR?") > 0 && strncmp(rsp, "-221,", 5) == 0);
    CHECK(m.chan[2].vset_uv == 12500000);        /* unchanged */
    drain(&m);

    /* --- SLOT status CSV --- */
    CHECK(go(&s, "SYST:SLOT3?") > 0);
    CHECK(strncmp(rsp, "1,0,0,1,0x00,0x00,", 18) == 0);

    /* --- number & header errors --- */
    CHECK(go(&s, "SOUR3:VOLT 40") == 0);         /* out of range */
    CHECK(go(&s, "SYST:ERR?") > 0 && strncmp(rsp, "-222,", 5) == 0);
    CHECK(go(&s, "SOUR3:VOLT bogus") == 0);
    CHECK(go(&s, "SYST:ERR?") > 0 && strncmp(rsp, "-104,", 5) == 0);
    CHECK(go(&s, "SOUR3:VOLT") == 0);
    CHECK(go(&s, "SYST:ERR?") > 0 && strncmp(rsp, "-109,", 5) == 0);
    CHECK(go(&s, "NOPE:NOPE?") == 0);
    CHECK(go(&s, "SYST:ERR?") > 0 && strncmp(rsp, "-113,", 5) == 0);
    CHECK(go(&s, "SOUR9:VOLT 1") == 0);          /* bad channel */
    CHECK(go(&s, "SYST:ERR?") > 0 && strncmp(rsp, "-222,", 5) == 0);
    CHECK(go(&s, "SYST:ERR?") > 0 && strcmp(rsp, "0,\"No error\"") == 0);

    /* --- error queue overflow -> -350 after the queued ones --- */
    for (int k = 0; k < 6; k++) go(&s, "NOPE");
    int seen = 0;
    for (int k = 0; k < 6; k++) {
        go(&s, "SYST:ERR?");
        if (strncmp(rsp, "-113,", 5) == 0 || strncmp(rsp, "-350,", 5) == 0) seen++;
    }
    CHECK(seen == 4);                            /* 3 queued + overflow mark */

    /* --- *RST turns every known output off --- */
    say_hello(&m, 0);
    drain(&m);
    go(&s, "OUTP1 ON");
    go(&s, "OUTP3 ON");
    CHECK(go(&s, "*RST") == 0);
    CHECK(m.chan[0].out_mode == LB_OUT_OFF && m.chan[2].out_mode == LB_OUT_OFF);

    if (fails) { printf("test_scpi: %d FAILED\n", fails); return 1; }
    printf("test_scpi: all passed\n");
    return 0;
}
