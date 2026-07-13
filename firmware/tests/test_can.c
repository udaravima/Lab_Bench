#include <stdio.h>
#include "labbench_can.h"

static int fails = 0;
#define CHECK(x) do { if (!(x)) { printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #x); fails++; } } while (0)

int main(void)
{
    lb_can_frame f;
    uint8_t slot = 0, sub = 0;

    /* identifier build + parse for every kind */
    CHECK(lb_id_cmd(3, LB_CMD_SET_VI) == 0x130);
    CHECK(lb_id_status(7, LB_TYP_ENERGY) == 0x373);
    CHECK(lb_id_fault(5) == 0x015);
    CHECK(lb_id_hello(2) == 0x7E2);

    CHECK(lb_id_parse(0x130, &slot, &sub) == LB_KIND_CMD && slot == 3 && sub == LB_CMD_SET_VI);
    CHECK(lb_id_parse(0x373, &slot, &sub) == LB_KIND_STATUS && slot == 7 && sub == LB_TYP_ENERGY);
    CHECK(lb_id_parse(0x015, &slot, &sub) == LB_KIND_FAULT && slot == 5);
    CHECK(lb_id_parse(0x7E2, &slot, &sub) == LB_KIND_HELLO && slot == 2);
    CHECK(lb_id_parse(LB_ID_GLOBAL_OFF, &slot, &sub) == LB_KIND_GLOBAL_OFF);
    CHECK(lb_id_parse(LB_ID_GLOBAL_STATE, &slot, &sub) == LB_KIND_GLOBAL_STATE);
    CHECK(lb_id_parse(0x136, &slot, &sub) == LB_KIND_UNKNOWN);  /* cmd 6 undefined */
    CHECK(lb_id_parse(0x374, &slot, &sub) == LB_KIND_UNKNOWN);  /* typ 4 undefined */
    CHECK(lb_id_parse(0x000, &slot, &sub) == LB_KIND_UNKNOWN);

    /* SET_VI roundtrip incl. negative value and sign preservation */
    lb_set_vi vi = { .v_uv = 12345678, .i_ua = -5 }, vi2;
    lb_enc_set_vi(&f, 4, &vi);
    CHECK(f.id == lb_id_cmd(4, LB_CMD_SET_VI) && f.dlc == 8);
    CHECK(lb_dec_set_vi(&f, &vi2) && vi2.v_uv == 12345678 && vi2.i_ua == -5);
    f.dlc = 7;
    CHECK(!lb_dec_set_vi(&f, &vi2));  /* wrong DLC rejected */

    /* OUTPUT: valid + out-of-range mode */
    uint8_t mode;
    lb_enc_output(&f, 0, LB_OUT_ON_DEM);
    CHECK(lb_dec_output(&f, &mode) && mode == LB_OUT_ON_DEM);
    f.data[0] = 9;
    CHECK(!lb_dec_output(&f, &mode));

    /* LIMITS roundtrip incl. negative temperature */
    lb_limits lm = { .p_max_mw = 600000, .t_derate_dC = -100, .policy = LB_POLICY_HOLD }, lm2;
    lb_enc_limits(&f, 6, &lm);
    CHECK(lb_dec_limits(&f, &lm2));
    CHECK(lm2.p_max_mw == 600000 && lm2.t_derate_dC == -100 && lm2.policy == LB_POLICY_HOLD);
    f.data[6] = 2;
    CHECK(!lb_dec_limits(&f, &lm2));  /* undefined policy rejected */

    /* CAL_WRITE roundtrip + range check */
    lb_cal_write cw = { .item = LB_CAL_IMEAS, .point = LB_CAL_GAIN, .value = -32768 }, cw2;
    lb_enc_cal_write(&f, 1, &cw);
    CHECK(lb_dec_cal_write(&f, &cw2));
    CHECK(cw2.item == LB_CAL_IMEAS && cw2.point == LB_CAL_GAIN && cw2.value == -32768);
    f.data[0] = 4;
    CHECK(!lb_dec_cal_write(&f, &cw2));

    /* RESET, IDENT, GLOBAL_OFF shapes */
    uint8_t magic;
    lb_enc_reset(&f, 2, LB_RESET_CLEAR_FAULT);
    CHECK(lb_dec_reset(&f, &magic) && magic == LB_RESET_CLEAR_FAULT);
    lb_enc_ident(&f, 2);
    CHECK(f.dlc == 0 && f.id == lb_id_cmd(2, LB_CMD_IDENT));
    lb_enc_global_off(&f);
    CHECK(f.id == LB_ID_GLOBAL_OFF && f.dlc == 0);

    /* GLOBAL_STATE roundtrip */
    lb_global_state gs = { .budget_w = 1500, .flags = 0xA5, .seq = 42 }, gs2;
    lb_enc_global_state(&f, &gs);
    CHECK(lb_dec_global_state(&f, &gs2));
    CHECK(gs2.budget_w == 1500 && gs2.flags == 0xA5 && gs2.seq == 42);

    /* STATUS roundtrip with negative echo */
    lb_status st = { .state = LB_STATE_ACTIVE, .fault = 0, .warn = LB_WARN_DERATE,
                     .mode = LB_MODE_OUT_ON | LB_MODE_CC_ACTIVE,
                     .vset_echo_10mV = 2000, .iset_echo_10mA = -1 }, st2;
    lb_enc_status(&f, 5, &st);
    CHECK(lb_dec_status(&f, &st2));
    CHECK(st2.state == LB_STATE_ACTIVE && st2.warn == LB_WARN_DERATE);
    CHECK(st2.mode == (LB_MODE_OUT_ON | LB_MODE_CC_ACTIVE));
    CHECK(st2.vset_echo_10mV == 2000 && st2.iset_echo_10mA == -1);

    /* TELEM_AUX roundtrip with sub-zero temperature */
    lb_telem_aux ta = { .t_fet_dC = -125, .t_ind_dC = 855, .vbus_10mV = 2400, .pout_100mW = 1500 }, ta2;
    lb_enc_telem_aux(&f, 3, &ta);
    CHECK(lb_dec_telem_aux(&f, &ta2));
    CHECK(ta2.t_fet_dC == -125 && ta2.t_ind_dC == 855 && ta2.vbus_10mV == 2400 && ta2.pout_100mW == 1500);

    /* ENERGY, FAULT, HELLO roundtrips */
    lb_energy en = { .charge_10uAh = 123456, .energy_10uWh = -654321 }, en2;
    lb_enc_energy(&f, 0, &en);
    CHECK(lb_dec_energy(&f, &en2) && en2.charge_10uAh == 123456 && en2.energy_10uWh == -654321);

    lb_fault_msg fm = { .fault = LB_FAULT_OVP_HW, .warn = 0, .state = LB_STATE_FAULT_LATCHED }, fm2;
    lb_enc_fault(&f, 7, &fm);
    CHECK(f.id == 0x017);
    CHECK(lb_dec_fault(&f, &fm2) && fm2.fault == LB_FAULT_OVP_HW && fm2.state == LB_STATE_FAULT_LATCHED);

    lb_hello he = { .proto_ver = LB_PROTO_VERSION, .fw_major = 0, .fw_minor = 1, .uid = 0xDEADBEEF }, he2;
    lb_enc_hello(&f, 6, &he);
    CHECK(lb_dec_hello(&f, &he2) && he2.proto_ver == 1 && he2.uid == 0xDEADBEEF);

    /* priority ordering: FAULT id must beat everything slot-scoped */
    CHECK(lb_id_fault(7) < LB_ID_GLOBAL_OFF);
    CHECK(LB_ID_GLOBAL_OFF < lb_id_cmd(0, LB_CMD_SET_VI));
    CHECK(lb_id_cmd(7, LB_CMD_RESET) < lb_id_status(0, LB_TYP_TELEM_VI));

    if (fails == 0) printf("test_can: all checks passed\n");
    return fails ? 1 : 0;
}
