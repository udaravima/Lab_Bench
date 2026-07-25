/* Host tests for ui_core: navigation, digit edit + commit, key toggles,
 * refusal messages, fault beep (docs/10 UI row of the shell table). */
#include <stdio.h>
#include <string.h>
#include "ui_core.h"

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

/* drain, remembering the last SET_VI / OUTPUT payload for a slot */
static int drain_cmds(lb_mgr *m, uint8_t slot, lb_set_vi *vi, int *out_mode)
{
    lb_can_frame f;
    int n = 0;
    while (lb_mgr_tx_pop(m, &f)) {
        n++;
        if (f.id == lb_id_cmd(slot, LB_CMD_SET_VI) && vi) lb_dec_set_vi(&f, vi);
        if (f.id == lb_id_cmd(slot, LB_CMD_OUTPUT) && out_mode) *out_mode = f.data[0];
    }
    return n;
}

static bool screen_has(lb_ui *u, const char *needle)
{
    for (int r = 0; r < LB_UI_ROWS; r++)
        if (strstr(u->text[r], needle)) return true;
    return false;
}

int main(void)
{
    lb_mgr m;
    lb_ui u;
    lb_mgr_init(&m, NULL);
    lb_ui_init(&u, &m);

    /* --- boot: list screen, nothing discovered --- */
    lb_ui_render(&u);
    CHECK(screen_has(&u, "LabBench"));
    CHECK(strstr(u.text[1], "---") != NULL);
    CHECK(u.attr[1] == LB_UI_A_SEL);             /* row for CH1 selected */

    /* --- discover CH3 (slot 2), navigate to it --- */
    say_hello(&m, 2);
    lb_ui_input(&u, LB_UI_EV_ENC_CW, 2);
    lb_ui_input(&u, LB_UI_EV_ENC_PUSH, 0);
    CHECK(u.screen == LB_UI_DETAIL && u.chan == 2);
    lb_ui_render(&u);
    CHECK(strstr(u.text[0], "CH3") != NULL);
    CHECK(strstr(u.text[0], "OFF") != NULL);

    /* --- edit Vset: 12 clicks on the 1 V digit, 5 on the 0.1 V digit --- */
    lb_ui_input(&u, LB_UI_EV_ENC_PUSH, 0);       /* Vset -> EDIT */
    CHECK(u.screen == LB_UI_EDIT && u.edit_digit == 1);
    lb_ui_input(&u, LB_UI_EV_ENC_CW, 12);
    lb_ui_input(&u, LB_UI_EV_ENC_PUSH, 0);       /* -> 0.1 digit */
    lb_ui_input(&u, LB_UI_EV_ENC_CW, 5);
    CHECK(u.edit_val == 12500000);
    lb_ui_render(&u);
    CHECK(strstr(u.text[2], "12.500") != NULL);
    CHECK(strchr(u.text[3], '^') != NULL);       /* caret row under Vset */
    lb_ui_input(&u, LB_UI_EV_ENC_HOLD, 0);       /* commit */
    CHECK(u.screen == LB_UI_DETAIL);
    lb_set_vi vi = { 0, 0 };
    CHECK(drain_cmds(&m, 2, &vi, NULL) > 0 && vi.v_uv == 12500000);
    CHECK(m.chan[2].vset_uv == 12500000);

    /* --- clamp at zero --- */
    lb_ui_input(&u, LB_UI_EV_ENC_CW, 1);         /* sel = Iset */
    lb_ui_input(&u, LB_UI_EV_ENC_PUSH, 0);
    lb_ui_input(&u, LB_UI_EV_ENC_CCW, 10);
    CHECK(u.edit_val == 0);
    lb_ui_input(&u, LB_UI_EV_ENC_CW, 3);         /* 3 A */
    lb_ui_input(&u, LB_UI_EV_ENC_HOLD, 0);
    CHECK(m.chan[2].iset_ua == 3000000);
    drain_cmds(&m, 2, NULL, NULL);

    /* --- front-panel key toggles the output from any screen --- */
    int mode = -1;
    lb_ui_input(&u, LB_UI_EV_KEY, 2);
    drain_cmds(&m, 2, NULL, &mode);
    CHECK(mode == LB_OUT_ON && m.chan[2].out_mode == LB_OUT_ON);
    lb_ui_input(&u, LB_UI_EV_KEY, 2);
    drain_cmds(&m, 2, NULL, &mode);
    CHECK(mode == LB_OUT_OFF && m.chan[2].out_mode == LB_OUT_OFF);

    /* --- key on an undiscovered slot: message + beep, no frame --- */
    u.beep = false;
    lb_ui_input(&u, LB_UI_EV_KEY, 5);
    CHECK(u.beep);
    CHECK(drain_cmds(&m, 5, NULL, NULL) == 0);
    lb_ui_render(&u);
    CHECK(screen_has(&u, "CH6 not discovered"));

    /* --- budget refusal message on commit --- */
    m.cfg.budget_mw = 30000;                     /* 30 W */
    say_status(&m, 2, LB_MODE_OUT_ON, 12500000, 3000000);
    m.chan[2].out_mode = LB_OUT_ON;
    u.beep = false;
    lb_ui_input(&u, LB_UI_EV_ENC_CCW, 1);        /* back to Vset */
    lb_ui_input(&u, LB_UI_EV_ENC_PUSH, 0);
    lb_ui_input(&u, LB_UI_EV_ENC_CW, 8);         /* 12.5 -> 20.5 V = 61 W */
    lb_ui_input(&u, LB_UI_EV_ENC_HOLD, 0);
    CHECK(u.beep);
    lb_ui_render(&u);
    CHECK(screen_has(&u, "refused"));
    CHECK(m.chan[2].vset_uv == 12500000);        /* unchanged */
    drain_cmds(&m, 2, NULL, NULL);

    /* --- message decays with tick --- */
    lb_ui_tick(&u, 3000);
    lb_ui_render(&u);
    CHECK(!screen_has(&u, "refused"));

    /* --- fault edge -> alert + beep exactly once --- */
    u.beep = false;
    lb_can_frame f;
    lb_fault_msg fm = { LB_FAULT_OVP_HW, 0, LB_STATE_FAULT_LATCHED };
    lb_enc_fault(&f, 2, &fm);
    lb_mgr_rx(&m, &f);
    lb_ui_tick(&u, 10);
    CHECK(u.beep);
    u.beep = false;
    lb_ui_tick(&u, 10);
    CHECK(!u.beep);                              /* edge, not level */
    lb_ui_render(&u);
    CHECK(screen_has(&u, "FAULT 0x02"));

    /* --- system screen: global off + resume --- */
    lb_ui_input(&u, LB_UI_EV_ENC_HOLD, 0);       /* leave DETAIL */
    CHECK(u.screen == LB_UI_LIST);
    while (u.sel != LB_NUM_SLOTS) lb_ui_input(&u, LB_UI_EV_ENC_CW, 1);
    lb_ui_input(&u, LB_UI_EV_ENC_PUSH, 0);
    CHECK(u.screen == LB_UI_SYSTEM);
    lb_ui_input(&u, LB_UI_EV_ENC_CW, 1);         /* Global OFF */
    lb_ui_input(&u, LB_UI_EV_ENC_PUSH, 0);
    CHECK(m.global_off);
    lb_ui_render(&u);
    CHECK(screen_has(&u, "RESUME"));
    lb_ui_input(&u, LB_UI_EV_ENC_PUSH, 0);       /* resume */
    CHECK(!m.global_off);

    if (fails) { printf("test_ui: %d FAILED\n", fails); return 1; }
    printf("test_ui: all passed\n");
    return 0;
}
