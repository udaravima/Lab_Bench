/* ui_core.c — see ui_core.h. C99, no HAL, no floats, no allocation. */
#include "ui_core.h"

#include <stdarg.h>
#include <stdio.h>

/* selectable rows per screen */
#define LIST_ITEMS   9          /* 8 channels + System                    */
enum { DET_VSET = 0, DET_ISET, DET_OUT, DET_CLEAR, DET_CHG, DET_BACK,
       DET_ITEMS };
enum { SYS_BUDG = 0, SYS_GLOBAL, SYS_ALLOFF, SYS_BACK, SYS_ITEMS };

static const int64_t STEP[4] = { 10000000, 1000000, 100000, 10000 };
static const int64_t STEP_W[4] = { 100000000000ll, 10000000000ll,
                                   1000000000ll, 100000000ll }; /* uW: 100/10/1/0.1 W */

void lb_ui_init(lb_ui *u, lb_mgr *mgr)
{
    memset(u, 0, sizeof(*u));
    u->mgr = mgr;
}

void lb_ui_set_bus(lb_ui *u, int32_t bus_uv, int32_t bus_ua)
{
    u->bus_uv = bus_uv;
    u->bus_ua = bus_ua;
}

static void say(lb_ui *u, const char *txt)
{
    snprintf(u->msg, sizeof(u->msg), "%s", txt);
    u->msg_ms = 3000;
}

static void refuse(lb_ui *u, const char *txt)
{
    say(u, txt);
    u->beep = true;
}

/* ---- shared actions -------------------------------------------------------- */
static void toggle_output(lb_ui *u, uint8_t slot)
{
    lb_mgr_chan *c = &u->mgr->chan[slot];
    char t[LB_UI_COLS + 1];
    if (!c->known) {
        snprintf(t, sizeof(t), "CH%d not discovered", slot + 1);
        refuse(u, t);
        return;
    }
    if (c->out_mode != LB_OUT_OFF) {
        lb_mgr_request_output(u->mgr, slot, LB_OUT_OFF);
        snprintf(t, sizeof(t), "CH%d off", slot + 1);
        say(u, t);
    } else if (lb_mgr_request_output(u->mgr, slot, LB_OUT_ON)) {
        snprintf(t, sizeof(t), "CH%d on", slot + 1);
        say(u, t);
    } else {
        snprintf(t, sizeof(t), "CH%d refused (budget?)", slot + 1);
        refuse(u, t);
    }
}

static void edit_begin(lb_ui *u, uint8_t item, int64_t val)
{
    u->screen = LB_UI_EDIT;
    u->edit_item = item;
    u->edit_digit = 1;              /* 1-unit digit is the usual knob     */
    u->edit_val = val;
}

static void edit_commit(lb_ui *u)
{
    lb_mgr *m = u->mgr;
    if (u->edit_item == 2) {        /* budget, uW -> mW */
        m->cfg.budget_mw = (uint32_t)(u->edit_val / 1000);
        u->screen = LB_UI_SYSTEM;
        say(u, "budget set");
        return;
    }
    lb_mgr_chan *c = &m->chan[u->chan];
    int32_t v = (u->edit_item == 0) ? (int32_t)u->edit_val : c->vset_uv;
    int32_t i = (u->edit_item == 1) ? (int32_t)u->edit_val : c->iset_ua;
    u->screen = LB_UI_DETAIL;
    if (!lb_mgr_set_vi(m, u->chan, v, i))
        refuse(u, "refused (budget/lost)");
}

/* ---- input ----------------------------------------------------------------- */
void lb_ui_input(lb_ui *u, lb_ui_ev_t ev, uint8_t arg)
{
    lb_mgr *m = u->mgr;

    if (ev == LB_UI_EV_KEY) {       /* channel keys work from any screen  */
        if (arg < LB_NUM_SLOTS) toggle_output(u, arg);
        return;
    }

    switch (u->screen) {
    case LB_UI_LIST:
        if (ev == LB_UI_EV_ENC_CW)  u->sel = (uint8_t)((u->sel + arg) % LIST_ITEMS);
        if (ev == LB_UI_EV_ENC_CCW) u->sel = (uint8_t)((u->sel + LIST_ITEMS -
                                                        arg % LIST_ITEMS) % LIST_ITEMS);
        if (ev == LB_UI_EV_ENC_PUSH) {
            if (u->sel < LB_NUM_SLOTS) {
                u->chan = u->sel;
                u->screen = LB_UI_DETAIL;
                u->sel = DET_VSET;
            } else {
                u->screen = LB_UI_SYSTEM;
                u->sel = SYS_BUDG;
            }
        }
        break;

    case LB_UI_DETAIL: {
        lb_mgr_chan *c = &m->chan[u->chan];
        if (ev == LB_UI_EV_ENC_CW)  u->sel = (uint8_t)((u->sel + arg) % DET_ITEMS);
        if (ev == LB_UI_EV_ENC_CCW) u->sel = (uint8_t)((u->sel + DET_ITEMS -
                                                        arg % DET_ITEMS) % DET_ITEMS);
        if (ev == LB_UI_EV_ENC_HOLD) { u->screen = LB_UI_LIST; u->sel = u->chan; break; }
        if (ev != LB_UI_EV_ENC_PUSH) break;
        switch (u->sel) {
        case DET_VSET: edit_begin(u, 0, c->vset_uv); break;
        case DET_ISET: edit_begin(u, 1, c->iset_ua); break;
        case DET_OUT:  toggle_output(u, u->chan); break;
        case DET_CLEAR:
            lb_mgr_clear_fault(m, u->chan);
            say(u, "fault clear sent");
            break;
        case DET_CHG:
            if (c->chg != LB_CHG_IDLE && c->chg != LB_CHG_DONE &&
                c->chg != LB_CHG_ABORT) {
                lb_mgr_charge_abort(m, u->chan);
                say(u, "charge aborted");
            } else {
                say(u, "no charge running");
            }
            break;
        case DET_BACK: u->screen = LB_UI_LIST; u->sel = u->chan; break;
        }
        break;
    }

    case LB_UI_EDIT: {
        const int64_t *step = (u->edit_item == 2) ? STEP_W : STEP;
        int64_t max = (u->edit_item == 2) ? 20000000000000ll : 32000000ll;
        if (ev == LB_UI_EV_ENC_CW)  u->edit_val += step[u->edit_digit] * arg;
        if (ev == LB_UI_EV_ENC_CCW) u->edit_val -= step[u->edit_digit] * arg;
        if (u->edit_val < 0)   u->edit_val = 0;
        if (u->edit_val > max) u->edit_val = max;
        if (ev == LB_UI_EV_ENC_PUSH) u->edit_digit = (uint8_t)((u->edit_digit + 1) % 4);
        if (ev == LB_UI_EV_ENC_HOLD) edit_commit(u);
        break;
    }

    case LB_UI_SYSTEM:
        if (ev == LB_UI_EV_ENC_CW)  u->sel = (uint8_t)((u->sel + arg) % SYS_ITEMS);
        if (ev == LB_UI_EV_ENC_CCW) u->sel = (uint8_t)((u->sel + SYS_ITEMS -
                                                        arg % SYS_ITEMS) % SYS_ITEMS);
        if (ev == LB_UI_EV_ENC_HOLD) { u->screen = LB_UI_LIST; u->sel = LB_NUM_SLOTS; break; }
        if (ev != LB_UI_EV_ENC_PUSH) break;
        switch (u->sel) {
        case SYS_BUDG:
            edit_begin(u, 2, (int64_t)m->cfg.budget_mw * 1000);
            break;
        case SYS_GLOBAL:
            if (m->global_off) {
                lb_mgr_resume(m);
                say(u, "resumed");
            } else {
                lb_mgr_global_off(m);
                refuse(u, "GLOBAL OFF latched");
            }
            break;
        case SYS_ALLOFF:
            for (uint8_t s = 0; s < LB_NUM_SLOTS; s++)
                if (m->chan[s].known)
                    lb_mgr_request_output(m, s, LB_OUT_OFF);
            say(u, "all outputs off");
            break;
        case SYS_BACK: u->screen = LB_UI_LIST; u->sel = LB_NUM_SLOTS; break;
        }
        break;
    }
}

void lb_ui_tick(lb_ui *u, uint32_t dt_ms)
{
    if (u->msg_ms) u->msg_ms = (u->msg_ms > dt_ms) ? u->msg_ms - dt_ms : 0;
    for (uint8_t s = 0; s < LB_NUM_SLOTS; s++) {
        uint8_t f = u->mgr->chan[s].fault_live;
        if (f & (uint8_t)~u->fault_seen[s]) {   /* new fault bit -> alert  */
            char t[LB_UI_COLS + 1];
            snprintf(t, sizeof(t), "CH%d FAULT 0x%02X", s + 1, f);
            refuse(u, t);
        }
        u->fault_seen[s] = f;
    }
}

/* ---- rendering ------------------------------------------------------------- */
/* "%2d.%03d" of a micro value, 6 chars wide ("12.500"), clamped 0..99.999 */
static void fmt_m(char *out, int max, int64_t uv)
{
    if (uv < 0) uv = 0;
    if (uv > 99999000) uv = 99999000;
    snprintf(out, (size_t)max, "%2d.%03d",
             (int)(uv / 1000000), (int)((uv % 1000000) / 1000));
}

static void row(lb_ui *u, int r, uint8_t attr, const char *fmt, ...)
    __attribute__((format(printf, 4, 5)));
static void row(lb_ui *u, int r, uint8_t attr, const char *fmt, ...)
{
    if (r < 0 || r >= LB_UI_ROWS) return;
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(u->text[r], sizeof(u->text[r]), fmt, ap);
    va_end(ap);
    u->attr[r] = attr;
}

static const char *chan_tag(const lb_mgr_chan *c)
{
    if (!c->known)                 return c->present ? "SEATED" : "---";
    if (c->lost)                   return "LOST";
    if (c->status.state == LB_STATE_FAULT_LATCHED) return "FAULT";
    if (c->status.mode & LB_MODE_OUT_ON)
        return (c->status.mode & LB_MODE_CC_ACTIVE) ? "ON CC" : "ON CV";
    return "OFF";
}

static const char *chg_name(lb_chg_state_t s)
{
    switch (s) {
    case LB_CHG_RAMP: return "RAMP";
    case LB_CHG_CC:   return "CC";
    case LB_CHG_CV:   return "CV";
    case LB_CHG_TERM_WAIT: return "TERM";
    case LB_CHG_DONE: return "DONE";
    case LB_CHG_ABORT: return "ABORT";
    default: return "idle";
    }
}

void lb_ui_render(lb_ui *u)
{
    lb_mgr *m = u->mgr;
    char v[16], i[16], w[16];

    for (int r = 0; r < LB_UI_ROWS; r++) {
        u->text[r][0] = '\0';
        u->attr[r] = LB_UI_A_NORM;
    }

    switch (u->screen) {
    case LB_UI_LIST: {
        /* slot index out of range = exclude nothing: sum of all channels */
        uint32_t used = lb_mgr_committed_mw(m, LB_NUM_SLOTS, 0, 0);
        row(u, 0, LB_UI_A_NORM, "LabBench %4luW/%4luW%s",
            (unsigned long)(used / 1000),
            (unsigned long)(m->cfg.budget_mw / 1000),
            m->global_off ? " OFF!" : "");
        for (uint8_t s = 0; s < LB_NUM_SLOTS; s++) {
            const lb_mgr_chan *c = &m->chan[s];
            bool on = (c->status.mode & LB_MODE_OUT_ON) != 0;
            fmt_m(v, sizeof(v), on ? c->telem.v_uv : c->vset_uv);
            fmt_m(i, sizeof(i), on ? c->telem.i_ua : c->iset_ua);
            uint8_t a = (u->sel == s) ? LB_UI_A_SEL : LB_UI_A_NORM;
            if (c->known && (c->lost || c->fault_live)) a = LB_UI_A_ALERT;
            row(u, 1 + s, a, "%d %sV %sA %-6s", s + 1, v, i, chan_tag(c));
        }
        row(u, 9, (u->sel == 8) ? LB_UI_A_SEL : LB_UI_A_NORM, "System / budget ...");
        break;
    }

    case LB_UI_DETAIL:
    case LB_UI_EDIT: {
        if (u->screen == LB_UI_EDIT && u->edit_item == 2) {
            /* budget edit (entered from SYSTEM) */
            row(u, 0, LB_UI_A_NORM, "System");
            row(u, 2, LB_UI_A_EDIT, " Budget %5luW",
                (unsigned long)(u->edit_val / 1000000));
            row(u, 3, LB_UI_A_NORM, "  turn=step push=digit");
            row(u, 4, LB_UI_A_NORM, "  hold=save");
            break;
        }
        const lb_mgr_chan *c = &m->chan[u->chan];
        bool edit = (u->screen == LB_UI_EDIT);
        row(u, 0, c->fault_live ? LB_UI_A_ALERT : LB_UI_A_NORM,
            "CH%d  %s  flt 0x%02X", u->chan + 1, chan_tag(c), c->fault_live);
        fmt_m(v, sizeof(v), (edit && u->edit_item == 0) ? u->edit_val : c->vset_uv);
        fmt_m(i, sizeof(i), (edit && u->edit_item == 1) ? u->edit_val : c->iset_ua);
        row(u, 2, (edit && u->edit_item == 0) ? LB_UI_A_EDIT :
            (u->sel == DET_VSET && !edit) ? LB_UI_A_SEL : LB_UI_A_NORM,
            " Vset  %sV", v);
        row(u, 3, (edit && u->edit_item == 1) ? LB_UI_A_EDIT :
            (u->sel == DET_ISET && !edit) ? LB_UI_A_SEL : LB_UI_A_NORM,
            " Iset  %sA", i);
        if (edit) {
            /* caret row: value starts at col 7 ("  Vset  "), digits x.xxx:
             * digit 0/1 before the point, 2/3 after it */
            static const int caret_col[4] = { 7, 8, 10, 11 };
            int r = (u->edit_item == 0) ? 2 : 3;
            char car[LB_UI_COLS + 1] = "                          ";
            car[caret_col[u->edit_digit]] = '^';
            car[caret_col[u->edit_digit] + 1] = '\0';
            row(u, r + 1, LB_UI_A_NORM, "%s", car);
        }
        fmt_m(v, sizeof(v), c->telem.v_uv);
        fmt_m(i, sizeof(i), c->telem.i_ua);
        row(u, 5, LB_UI_A_NORM, " meas  %sV %sA", v, i);
        row(u, 6, LB_UI_A_NORM, " T fet %d.%dC ind %d.%dC",
            c->aux.t_fet_dC / 10, (c->aux.t_fet_dC % 10 + 10) % 10,
            c->aux.t_ind_dC / 10, (c->aux.t_ind_dC % 10 + 10) % 10);
        row(u, 8, (u->sel == DET_OUT && !edit) ? LB_UI_A_SEL : LB_UI_A_NORM,
            " Output %s", (c->out_mode != LB_OUT_OFF) ? "ON" : "OFF");
        row(u, 9, (u->sel == DET_CLEAR && !edit) ? LB_UI_A_SEL : LB_UI_A_NORM,
            " Clear fault");
        row(u, 10, (u->sel == DET_CHG && !edit) ? LB_UI_A_SEL : LB_UI_A_NORM,
            " Charge: %s", chg_name(c->chg));
        row(u, 11, (u->sel == DET_BACK && !edit) ? LB_UI_A_SEL : LB_UI_A_NORM,
            " Back");
        break;
    }

    case LB_UI_SYSTEM: {
        row(u, 0, LB_UI_A_NORM, "System");
        row(u, 2, (u->sel == SYS_BUDG) ? LB_UI_A_SEL : LB_UI_A_NORM,
            " Budget %4luW", (unsigned long)(m->cfg.budget_mw / 1000));
        row(u, 3, (u->sel == SYS_GLOBAL) ?
            (m->global_off ? LB_UI_A_ALERT : LB_UI_A_SEL) :
            (m->global_off ? LB_UI_A_ALERT : LB_UI_A_NORM),
            " %s", m->global_off ? "RESUME (latched off)" : "Global OFF");
        row(u, 4, (u->sel == SYS_ALLOFF) ? LB_UI_A_SEL : LB_UI_A_NORM,
            " All outputs off");
        fmt_m(v, sizeof(v), u->bus_uv);
        fmt_m(i, sizeof(i), u->bus_ua);
        fmt_m(w, sizeof(w), (u->bus_uv / 1000) * (int64_t)(u->bus_ua / 1000));
        row(u, 6, LB_UI_A_NORM, " Bus %sV %sA", v, i);
        row(u, 7, LB_UI_A_NORM, "     %sW  drops %u", w, m->tx_dropped);
        row(u, 9, (u->sel == SYS_BACK) ? LB_UI_A_SEL : LB_UI_A_NORM, " Back");
        break;
    }
    }

    if (u->msg_ms)
        row(u, LB_UI_ROWS - 1, LB_UI_A_ALERT, "%s", u->msg);
}
