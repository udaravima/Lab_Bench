#include "module_core.h"

const lb_core_cfg LB_CORE_CFG_PHASE1 = {
    .v_max_uv        = 20000000,
    .i_max_ua        = 8000000,
    .p_max_mw        = 150000,
    .ramp_uv_per_ms  = 1000000,
    .derate_start_dC = 850,
    .derate_stop_dC  = 1000,
    .comms_timeout_ms = 3000,
};

void lb_core_init(lb_core *c, const lb_core_cfg *cfg)
{
    memset(c, 0, sizeof(*c));
    c->cfg = *cfg;
    c->state = LB_STATE_SAFE;
    c->policy = LB_POLICY_OFF;
}

int32_t lb_envelope_i_ua(const lb_core_cfg *cfg, int32_t v_uv, int32_t i_req_ua)
{
    int32_t lim = cfg->i_max_ua;
    if (v_uv > 1000) { /* below 1 mV the power term cannot bind */
        int64_t i_pmax = ((int64_t)cfg->p_max_mw * 1000000000LL) / v_uv;
        if (i_pmax < lim) lim = (int32_t)i_pmax;
    }
    if (i_req_ua < 0) return 0;
    return (i_req_ua > lim) ? lim : i_req_ua;
}

void lb_core_cmd_set_vi(lb_core *c, int32_t v_uv, int32_t i_ua)
{
    int32_t v = v_uv < 0 ? 0 : (v_uv > c->cfg.v_max_uv ? c->cfg.v_max_uv : v_uv);
    int32_t i = lb_envelope_i_ua(&c->cfg, v, i_ua);
    if (v != v_uv || i != i_ua) c->warn_bits |= LB_WARN_ENV_CLAMP;
    else                        c->warn_bits &= (uint8_t)~LB_WARN_ENV_CLAMP;
    c->vset_uv = v;
    c->iset_ua = i;
}

bool lb_core_cmd_output(lb_core *c, uint8_t mode)
{
    if (mode > LB_OUT_MODE_MAX) return false;
    if (mode == LB_OUT_OFF) {
        c->out_mode = LB_OUT_OFF;
        if (c->state == LB_STATE_ACTIVE) c->state = LB_STATE_SAFE;
        c->vref_uv = 0;
        return true;
    }
    if (c->state == LB_STATE_FAULT_LATCHED || !c->hw_enable) return false;
    c->out_mode = mode;
    c->state = LB_STATE_ACTIVE;   /* vref ramps up from 0 in tick() */
    return true;
}

void lb_core_cmd_limits(lb_core *c, const lb_limits *m)
{
    if (m->p_max_mw > 0 && m->p_max_mw < c->cfg.p_max_mw) c->cfg.p_max_mw = m->p_max_mw;
    if (m->t_derate_dC > 0 && m->t_derate_dC < c->cfg.derate_start_dC)
        c->cfg.derate_start_dC = m->t_derate_dC;
    c->policy = m->policy;
    /* re-apply the (possibly tightened) envelope to current setpoints */
    lb_core_cmd_set_vi(c, c->vset_uv, c->iset_ua);
}

void lb_core_cmd_reset(lb_core *c, uint8_t magic)
{
    if (magic == LB_RESET_REBOOT) {
        c->reboot_req = true;
    } else if (magic == LB_RESET_CLEAR_FAULT && c->state == LB_STATE_FAULT_LATCHED) {
        /* Supervisors re-assert immediately if the condition persists */
        c->fault_bits = 0;
        c->state = LB_STATE_SAFE;
    }
}

void lb_core_global_off(lb_core *c)
{
    lb_core_cmd_output(c, LB_OUT_OFF);
}

void lb_core_mgr_seen(lb_core *c)
{
    c->ms_since_mgr = 0;
    c->warn_bits &= (uint8_t)~LB_WARN_COMMS_LOST;
}

void lb_core_set_hw_enable(lb_core *c, bool enabled)
{
    /* /HW_ENABLE gates the hardware directly; here we only track state so a
     * released E-stop does not silently re-energize the output. */
    c->hw_enable = enabled;
    if (!enabled && c->state == LB_STATE_ACTIVE) {
        c->state = LB_STATE_SAFE;
        c->out_mode = LB_OUT_OFF;
        c->vref_uv = 0;
    }
}

void lb_core_set_temp(lb_core *c, int16_t dC)
{
    c->temp_dC = dC;
    if (dC >= c->cfg.derate_start_dC) c->warn_bits |= LB_WARN_DERATE;
    else                              c->warn_bits &= (uint8_t)~LB_WARN_DERATE;
    if (dC >= c->cfg.derate_stop_dC) lb_core_fault(c, LB_FAULT_OTP);
}

void lb_core_fault(lb_core *c, uint8_t fault_bit)
{
    c->fault_bits |= fault_bit;
    c->state = LB_STATE_FAULT_LATCHED;
    c->out_mode = LB_OUT_OFF;
    c->vref_uv = 0;
}

void lb_core_tick(lb_core *c, uint32_t dt_ms)
{
    if (c->ms_since_mgr <= c->cfg.comms_timeout_ms) c->ms_since_mgr += dt_ms;
    if (c->ms_since_mgr > c->cfg.comms_timeout_ms) {
        c->warn_bits |= LB_WARN_COMMS_LOST;
        if (c->policy == LB_POLICY_OFF && c->state == LB_STATE_ACTIVE) {
            c->state = LB_STATE_SAFE;
            c->out_mode = LB_OUT_OFF;
            c->vref_uv = 0;
        }
    }

    if (c->state == LB_STATE_ACTIVE) {
        int64_t step = (int64_t)c->cfg.ramp_uv_per_ms * dt_ms;
        if (c->vref_uv < c->vset_uv) {
            int64_t v = (int64_t)c->vref_uv + step;
            c->vref_uv = (v > c->vset_uv) ? c->vset_uv : (int32_t)v;
        } else if (c->vref_uv > c->vset_uv) {
            int64_t v = (int64_t)c->vref_uv - step;
            c->vref_uv = (v < c->vset_uv) ? c->vset_uv : (int32_t)v;
        }
    } else {
        c->vref_uv = 0;
    }
}

int32_t lb_core_vref_uv(const lb_core *c)
{
    return lb_core_output_closed(c) ? c->vref_uv : 0;
}

int32_t lb_core_iref_ua(const lb_core *c)
{
    if (!lb_core_output_closed(c)) return 0;
    int32_t i = c->iset_ua;
    if (c->temp_dC >= c->cfg.derate_start_dC) {
        int32_t span = c->cfg.derate_stop_dC - c->cfg.derate_start_dC;
        int32_t left = c->cfg.derate_stop_dC - c->temp_dC;
        if (left <= 0) return 0;
        i = (int32_t)(((int64_t)i * left) / span);
    }
    return i;
}
