/* manager_core.c — see manager_core.h. C99, no HAL, no floats. */
#include "manager_core.h"

const lb_mgr_cfg LB_MGR_CFG_DEFAULT = {
    .budget_mw       = 1500000,   /* 1.5 kW (docs/01 §2 example)          */
    .hb_period_ms    = 1000,
    .chan_timeout_ms = 1000,
    .retry_ms        = 50,
    .retry_max       = 3,
};

/* ---- TX ring ------------------------------------------------------------- */
static void txq_push(lb_mgr *m, const lb_can_frame *f)
{
    uint8_t next = (uint8_t)((m->tx_head + 1) % LB_MGR_TXQ);
    if (next == m->tx_tail) {           /* full: drop + count (diagnostic) */
        if (m->tx_dropped < 255) m->tx_dropped++;
        return;
    }
    m->txq[m->tx_head] = *f;
    m->tx_head = next;
}

bool lb_mgr_tx_pop(lb_mgr *m, lb_can_frame *out)
{
    if (m->tx_tail == m->tx_head) return false;
    *out = m->txq[m->tx_tail];
    m->tx_tail = (uint8_t)((m->tx_tail + 1) % LB_MGR_TXQ);
    return true;
}

/* ---- init ----------------------------------------------------------------- */
void lb_mgr_init(lb_mgr *m, const lb_mgr_cfg *cfg)
{
    memset(m, 0, sizeof(*m));
    m->cfg = cfg ? *cfg : LB_MGR_CFG_DEFAULT;
    for (int s = 0; s < LB_NUM_SLOTS; s++)
        m->chan[s].ms_since_status = m->cfg.chan_timeout_ms;  /* born lost */
}

/* ---- helpers -------------------------------------------------------------- */
static bool chan_usable(const lb_mgr_chan *c)
{
    return c->known && !c->lost;
}

/* mW from uV * uA without overflow: (v/1000 mV) * (i/1000 mA) / 1000 */
static uint32_t p_mw(int32_t v_uv, int32_t i_ua)
{
    if (v_uv < 0 || i_ua < 0) return 0;
    int64_t p = ((int64_t)(v_uv / 1000) * (i_ua / 1000)) / 1000;
    return (p > 0xFFFFFFFFll) ? 0xFFFFFFFFu : (uint32_t)p;
}

/* A channel's contribution to the committed budget: the larger of what it
 * measures and what it was told to run (docs/01 §2: refuse enables or
 * raises that would exceed the budget). Lost channels are excluded (#15). */
static uint32_t chan_committed_mw(const lb_mgr_chan *c)
{
    if (!chan_usable(c)) return 0;
    /* counts if commanded on OR still reporting on (turn-off transient) */
    if (c->out_mode == LB_OUT_OFF && !(c->status.mode & LB_MODE_OUT_ON))
        return 0;
    uint32_t meas = p_mw(c->telem.v_uv, c->telem.i_ua);
    uint32_t cmd  = p_mw(c->vset_uv, c->iset_ua);
    return (meas > cmd) ? meas : cmd;
}

uint32_t lb_mgr_committed_mw(const lb_mgr *m, uint8_t slot,
                             int32_t v_uv, int32_t i_ua)
{
    uint32_t sum = p_mw(v_uv, i_ua);
    for (uint8_t s = 0; s < LB_NUM_SLOTS; s++)
        if (s != slot) sum += chan_committed_mw(&m->chan[s]);
    return sum;
}

static void send_output(lb_mgr *m, uint8_t slot, uint8_t mode)
{
    lb_can_frame f;
    lb_enc_output(&f, slot, mode);
    txq_push(m, &f);
    m->chan[slot].out_mode = mode;
}

static void send_set_vi(lb_mgr *m, uint8_t slot)
{
    lb_mgr_chan *c = &m->chan[slot];
    lb_can_frame f;
    lb_set_vi vi = { c->vset_uv, c->iset_ua };
    lb_enc_set_vi(&f, slot, &vi);
    txq_push(m, &f);
    c->ack_pending = true;
    c->ack_age_ms = 0;
}

/* ---- charge sequencer ----------------------------------------------------- */
static void chg_abort(lb_mgr *m, uint8_t slot, lb_chg_reason_t why)
{
    lb_mgr_chan *c = &m->chan[slot];
    if (c->chg == LB_CHG_IDLE || c->chg == LB_CHG_DONE || c->chg == LB_CHG_ABORT)
        return;
    c->chg = LB_CHG_ABORT;
    c->chg_abort_reason = why;
    send_output(m, slot, LB_OUT_OFF);
}

static void chg_tick(lb_mgr *m, uint8_t slot, uint32_t dt_ms)
{
    lb_mgr_chan *c = &m->chan[slot];
    if (c->chg == LB_CHG_IDLE || c->chg == LB_CHG_DONE || c->chg == LB_CHG_ABORT)
        return;

    c->chg_t_ms += dt_ms;
    if (c->chg_prof.t_max_ms && c->chg_t_ms > c->chg_prof.t_max_ms) {
        chg_abort(m, slot, LB_CHG_ABORT_TIMEOUT);
        return;
    }
    if (c->fault_live || c->status.state == LB_STATE_FAULT_LATCHED) {
        chg_abort(m, slot, LB_CHG_ABORT_FAULT);
        return;
    }
    if (c->lost) {
        /* module keeps charging safely on policy=hold; we latch the abort
         * so the operator knows supervision was broken (docs/10) */
        chg_abort(m, slot, LB_CHG_ABORT_LOST);
        return;
    }

    bool cc = (c->status.mode & LB_MODE_CC_ACTIVE) != 0;
    bool on = (c->status.mode & LB_MODE_OUT_ON) != 0;
    switch (c->chg) {
    case LB_CHG_RAMP:
        if (on) c->chg = cc ? LB_CHG_CC : LB_CHG_CV;
        break;
    case LB_CHG_CC:
        if (!cc) c->chg = LB_CHG_CV;          /* the CC->CV knee (docs/03 §7) */
        break;
    case LB_CHG_CV:
    case LB_CHG_TERM_WAIT:
        if (cc) { c->chg = LB_CHG_CC; c->chg_hold_ms = 0; break; }
        if (c->telem.i_ua >= 0 && c->telem.i_ua < c->chg_prof.i_cutoff_ua) {
            c->chg = LB_CHG_TERM_WAIT;
            c->chg_hold_ms += dt_ms;
            if (c->chg_hold_ms >= c->chg_prof.t_hold_ms) {
                c->chg = LB_CHG_DONE;
                send_output(m, slot, LB_OUT_OFF);
            }
        } else {
            c->chg = LB_CHG_CV;
            c->chg_hold_ms = 0;
        }
        break;
    default:
        break;
    }
}

bool lb_mgr_charge_start(lb_mgr *m, uint8_t slot, const lb_chg_profile *p)
{
    if (slot >= LB_NUM_SLOTS || m->global_off) return false;
    lb_mgr_chan *c = &m->chan[slot];
    if (!chan_usable(c)) return false;

    c->chg_prof = *p;
    c->chg_t_ms = c->chg_hold_ms = 0;

    /* docs/03 §7: LIMITS(policy=hold) so a manager reboot never interrupts
     * the charge; then setpoints; then output on in battery-safe DEM mode */
    lb_limits lim = { .p_max_mw = (int32_t)m->cfg.budget_mw,
                      .t_derate_dC = 850, .policy = LB_POLICY_HOLD };
    lb_mgr_set_limits(m, slot, &lim);
    if (!lb_mgr_set_vi(m, slot, p->v_float_uv, p->i_charge_ua)) return false;
    if (!lb_mgr_request_output(m, slot, LB_OUT_ON_DEM)) {
        c->chg_abort_reason = LB_CHG_ABORT_REFUSED;   /* budget said no */
        return false;
    }
    c->chg = LB_CHG_RAMP;
    c->chg_abort_reason = LB_CHG_OK;
    return true;
}

void lb_mgr_charge_abort(lb_mgr *m, uint8_t slot)
{
    if (slot < LB_NUM_SLOTS) chg_abort(m, slot, LB_CHG_ABORT_USER);
}

/* ---- operator requests ---------------------------------------------------- */
bool lb_mgr_set_vi(lb_mgr *m, uint8_t slot, int32_t v_uv, int32_t i_ua)
{
    if (slot >= LB_NUM_SLOTS) return false;
    lb_mgr_chan *c = &m->chan[slot];
    if (!chan_usable(c)) return false;
    /* a raise on a running channel is budget-arbited too (docs/01 §2) */
    if (c->out_mode != LB_OUT_OFF &&
        lb_mgr_committed_mw(m, slot, v_uv, i_ua) > m->cfg.budget_mw)
        return false;
    c->vset_uv = v_uv;
    c->iset_ua = i_ua;
    c->ack_tries = 0;
    c->unresponsive = false;
    send_set_vi(m, slot);
    return true;
}

bool lb_mgr_request_output(lb_mgr *m, uint8_t slot, uint8_t mode)
{
    if (slot >= LB_NUM_SLOTS || mode > LB_OUT_MODE_MAX) return false;
    lb_mgr_chan *c = &m->chan[slot];
    if (!c->known) return false;
    if (mode == LB_OUT_OFF) {               /* off is always granted */
        send_output(m, slot, LB_OUT_OFF);
        return true;
    }
    if (!chan_usable(c) || m->global_off) return false;
    if (lb_mgr_committed_mw(m, slot, c->vset_uv, c->iset_ua) > m->cfg.budget_mw)
        return false;                       /* matrix #17: refuse */
    send_output(m, slot, mode);
    return true;
}

void lb_mgr_set_limits(lb_mgr *m, uint8_t slot, const lb_limits *lim)
{
    if (slot >= LB_NUM_SLOTS) return;
    lb_can_frame f;
    lb_enc_limits(&f, slot, lim);
    txq_push(m, &f);
}

void lb_mgr_clear_fault(lb_mgr *m, uint8_t slot)
{
    if (slot >= LB_NUM_SLOTS) return;
    lb_can_frame f;
    lb_enc_reset(&f, slot, LB_RESET_CLEAR_FAULT);
    txq_push(m, &f);
}

void lb_mgr_global_off(lb_mgr *m)
{
    lb_can_frame f;
    lb_enc_global_off(&f);
    txq_push(m, &f);
    m->global_off = true;
    for (uint8_t s = 0; s < LB_NUM_SLOTS; s++) {
        m->chan[s].out_mode = LB_OUT_OFF;
        chg_abort(m, s, LB_CHG_ABORT_USER);
    }
}

void lb_mgr_resume(lb_mgr *m) { m->global_off = false; }

/* ---- inputs ---------------------------------------------------------------- */
void lb_mgr_set_present(lb_mgr *m, uint8_t mask)
{
    for (uint8_t s = 0; s < LB_NUM_SLOTS; s++)
        m->chan[s].present = (mask >> s) & 1u;
}

void lb_mgr_rx(lb_mgr *m, const lb_can_frame *f)
{
    uint8_t slot = 0, sub = 0;
    lb_kind_t k = lb_id_parse(f->id, &slot, &sub);
    if (k == LB_KIND_UNKNOWN || slot >= LB_NUM_SLOTS) return;
    lb_mgr_chan *c = &m->chan[slot];

    switch (k) {
    case LB_KIND_HELLO: {
        lb_hello h;
        if (!lb_dec_hello(f, &h)) return;
        c->hello = h;
        c->known = true;
        c->lost = false;
        c->unresponsive = false;
        c->ms_since_status = 0;
        /* module rebooted: it is in SAFE with zero setpoints now */
        c->out_mode = LB_OUT_OFF;
        c->ack_pending = false;
        break;
    }
    case LB_KIND_STATUS:
        c->ms_since_status = 0;
        c->lost = false;
        switch ((lb_typ_t)sub) {
        case LB_TYP_TELEM_VI:  (void)lb_dec_telem_vi(f, &c->telem); break;
        case LB_TYP_TELEM_AUX: (void)lb_dec_telem_aux(f, &c->aux); break;
        case LB_TYP_ENERGY:    (void)lb_dec_energy(f, &c->energy); break;
        case LB_TYP_STATUS: {
            lb_status st;
            if (!lb_dec_status(f, &st)) return;
            c->status = st;
            c->fault_live = st.fault;
            /* ack rule (docs/03 §3): the next STATUS echoing our setpoints
             * is the acknowledgement */
            if (c->ack_pending &&
                st.vset_echo_10mV == (int16_t)(c->vset_uv / 10000) &&
                st.iset_echo_10mA == (int16_t)(c->iset_ua / 10000)) {
                c->ack_pending = false;
                c->ack_tries = 0;
            }
            break;
        }
        }
        break;
    case LB_KIND_FAULT: {
        lb_fault_msg fm;
        if (!lb_dec_fault(f, &fm)) return;
        c->fault_live = fm.fault;
        c->status.state = fm.state;
        c->ms_since_status = 0;
        break;
    }
    default:
        break;      /* CMD/GLOBAL_* are our own frames echoed; ignore */
    }
}

void lb_mgr_tick(lb_mgr *m, uint32_t dt_ms)
{
    /* GLOBAL_STATE heartbeat at 1 Hz (docs/03 §6) */
    m->hb_ms += dt_ms;
    if (m->hb_ms >= m->cfg.hb_period_ms) {
        m->hb_ms = 0;
        lb_can_frame f;
        lb_global_state gs = {
            .budget_w = (uint16_t)(m->cfg.budget_mw / 1000),
            .flags    = m->global_off ? 1u : 0u,
            .seq      = m->seq++,
        };
        lb_enc_global_state(&f, &gs);
        txq_push(m, &f);
    }

    for (uint8_t s = 0; s < LB_NUM_SLOTS; s++) {
        lb_mgr_chan *c = &m->chan[s];
        if (!c->known) continue;

        /* module heartbeat supervision (matrix #15) */
        if (c->ms_since_status < 0xF0000000u) c->ms_since_status += dt_ms;
        if (!c->lost && c->ms_since_status >= m->cfg.chan_timeout_ms)
            c->lost = true;

        /* SET_VI retry (docs/03 §3: 50 ms, 3 attempts) */
        if (c->ack_pending && !c->lost) {
            c->ack_age_ms += dt_ms;
            if (c->ack_age_ms >= m->cfg.retry_ms) {
                if (c->ack_tries + 1u >= m->cfg.retry_max) {
                    c->ack_pending = false;
                    c->unresponsive = true;
                } else {
                    c->ack_tries++;
                    send_set_vi(m, s);
                }
            }
        }

        chg_tick(m, s, dt_ms);
    }
}
