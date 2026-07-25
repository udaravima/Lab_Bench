/* scpi_core.c — see scpi_core.h. C99, no HAL, no floats, no allocation. */
#include "scpi_core.h"

#include <stdio.h>

/* ---- error queue ---------------------------------------------------------- */
static void err_push(lb_scpi *s, int16_t code)
{
    uint8_t next = (uint8_t)((s->err_head + 1) % LB_SCPI_ERRQ);
    if (next == s->err_tail) { s->err_overflow = true; return; }
    s->errq[s->err_head] = code;
    s->err_head = next;
}

static const char *err_text(int16_t code)
{
    switch (code) {
    case 0:    return "No error";
    case -104: return "Data type error";
    case -109: return "Missing parameter";
    case -113: return "Undefined header";
    case -221: return "Settings conflict";
    case -222: return "Data out of range";
    case -350: return "Queue overflow";
    default:   return "Error";
    }
}

/* ---- text helpers ---------------------------------------------------------- */
static char up(char c) { return (c >= 'a' && c <= 'z') ? (char)(c - 32) : c; }
static bool is_digit(char c) { return c >= '0' && c <= '9'; }
static bool is_alpha(char c) { return up(c) >= 'A' && up(c) <= 'Z'; }

/* SCPI keyword match: pat = "SOURce" (mandatory upper, optional lower).
 * tok may be the short form or any longer prefix of the full form. */
static bool kw(const char *tok, int len, const char *pat)
{
    int mand = 0, full = 0;
    while (pat[full]) {
        if (pat[full] >= 'A' && pat[full] <= 'Z') mand = full + 1;
        full++;
    }
    if (len < mand || len > full) return false;
    for (int i = 0; i < len; i++)
        if (up(tok[i]) != up(pat[i])) return false;
    return true;
}

/* Parse a decimal (optionally signed, optional V/A/W or mV/mA/mW suffix)
 * into micro-units. Returns false on garbage. */
static bool parse_micro(const char *p, int64_t *out)
{
    while (*p == ' ') p++;
    bool neg = false;
    if (*p == '+' || *p == '-') neg = (*p++ == '-');
    if (!is_digit(*p) && *p != '.') return false;
    int64_t ip = 0;
    while (is_digit(*p)) {
        ip = ip * 10 + (*p++ - '0');
        if (ip > 100000000ll) return false;     /* absurd input */
    }
    int64_t frac = 0, scale = 100000;
    if (*p == '.') {
        p++;
        while (is_digit(*p)) {
            if (scale) { frac += (int64_t)(*p - '0') * scale; scale /= 10; }
            p++;
        }
    }
    int64_t v = ip * 1000000 + frac;
    while (*p == ' ') p++;
    if (up(*p) == 'M' && is_alpha(p[1])) { v /= 1000; p += 2; }
    else if (is_alpha(*p)) p += 1;              /* V / A / W */
    while (*p == ' ') p++;
    if (*p) return false;
    *out = neg ? -v : v;
    return true;
}

/* micro-units -> "12.500000" (always 6 dp, sign if negative) */
static int fmt_micro(char *out, int max, int64_t uv)
{
    const char *sign = uv < 0 ? "-" : "";
    if (uv < 0) uv = -uv;
    return snprintf(out, (size_t)max, "%s%ld.%06ld", sign,
                    (long)(uv / 1000000), (long)(uv % 1000000));
}

/* ---- header tokenizer ------------------------------------------------------ */
typedef struct {
    const char *tok[3];
    int  len[3];            /* keyword letters only                       */
    int  num[3];            /* trailing digits, -1 = none                 */
    int  ntok;
    bool query;
    const char *param;      /* rest of line after first space, or ""      */
} scpi_hdr;

static bool hdr_split(const char *line, scpi_hdr *h)
{
    memset(h, 0, sizeof(*h));
    while (*line == ' ') line++;
    const char *p = line;
    while (*p && *p != ' ') p++;
    const char *hdr_end = p;
    while (*p == ' ') p++;
    h->param = p;

    const char *t = line;
    while (t < hdr_end) {
        if (h->ntok == 3) return false;
        const char *e = t;
        while (e < hdr_end && *e != ':') e++;
        int len = (int)(e - t);
        h->num[h->ntok] = -1;
        /* trailing '?' only on the last token */
        if (len && t[len - 1] == '?') {
            if (e != hdr_end) return false;
            h->query = true;
            len--;
        }
        int d = len;
        while (d > 0 && is_digit(t[d - 1])) d--;
        if (d < len) {
            int n = 0;
            for (int i = d; i < len; i++) n = n * 10 + (t[i] - '0');
            h->num[h->ntok] = n;
            len = d;
        }
        h->tok[h->ntok] = t;
        h->len[h->ntok] = len;
        h->ntok++;
        t = (e < hdr_end) ? e + 1 : e;
    }
    return h->ntok > 0;
}

/* ---- command execution ----------------------------------------------------- */
void lb_scpi_init(lb_scpi *s, lb_mgr *mgr)
{
    memset(s, 0, sizeof(*s));
    s->mgr = mgr;
}

/* channel suffix -> slot, SCPI channels are 1-based, absent = channel 1 */
static int chan_slot(int num) { return (num == -1) ? 0 : num - 1; }

int lb_scpi_line(lb_scpi *s, const char *line, char *out, int out_max)
{
    lb_mgr *m = s->mgr;
    scpi_hdr h;
    out[0] = '\0';

    if (!hdr_split(line, &h)) return 0;         /* blank line: ignore */

    /* ---- *IDN? / *RST ---- */
    if (h.ntok == 1 && h.tok[0][0] == '*') {
        if (h.query && kw(h.tok[0], h.len[0], "*IDN"))
            return snprintf(out, (size_t)out_max, "LabBench,PSU-Manager,0,0.1");
        if (!h.query && kw(h.tok[0], h.len[0], "*RST")) {
            for (uint8_t sl = 0; sl < LB_NUM_SLOTS; sl++)
                if (m->chan[sl].known)
                    lb_mgr_request_output(m, sl, LB_OUT_OFF);
            return 0;
        }
        err_push(s, -113);
        return 0;
    }

    /* ---- SOURce<n>:VOLTage/CURRent ---- */
    if (h.ntok == 2 && kw(h.tok[0], h.len[0], "SOURce")) {
        int slot = chan_slot(h.num[0]);
        bool volt = kw(h.tok[1], h.len[1], "VOLTage");
        bool curr = kw(h.tok[1], h.len[1], "CURRent");
        if ((!volt && !curr) || slot < 0 || slot >= LB_NUM_SLOTS) {
            err_push(s, slot < 0 || slot >= LB_NUM_SLOTS ? -222 : -113);
            return 0;
        }
        lb_mgr_chan *c = &m->chan[slot];
        if (h.query)
            return fmt_micro(out, out_max, volt ? c->vset_uv : c->iset_ua);
        if (!*h.param) { err_push(s, -109); return 0; }
        int64_t v;
        if (!parse_micro(h.param, &v)) { err_push(s, -104); return 0; }
        if (v < 0 || v > 32000000ll) { err_push(s, -222); return 0; }
        int32_t nv = volt ? (int32_t)v : c->vset_uv;
        int32_t ni = curr ? (int32_t)v : c->iset_ua;
        if (!lb_mgr_set_vi(m, (uint8_t)slot, nv, ni)) err_push(s, -221);
        return 0;
    }

    /* ---- MEASure<n>:VOLTage?/CURRent?/POWer? ---- */
    if (h.ntok == 2 && kw(h.tok[0], h.len[0], "MEASure")) {
        int slot = chan_slot(h.num[0]);
        if (slot < 0 || slot >= LB_NUM_SLOTS) { err_push(s, -222); return 0; }
        if (!h.query) { err_push(s, -113); return 0; }
        lb_mgr_chan *c = &m->chan[slot];
        if (kw(h.tok[1], h.len[1], "VOLTage"))
            return fmt_micro(out, out_max, c->telem.v_uv);
        if (kw(h.tok[1], h.len[1], "CURRent"))
            return fmt_micro(out, out_max, c->telem.i_ua);
        if (kw(h.tok[1], h.len[1], "POWer")) {
            int64_t p_uw = ((int64_t)(c->telem.v_uv / 1000) *
                            (c->telem.i_ua / 1000));
            return fmt_micro(out, out_max, p_uw);
        }
        err_push(s, -113);
        return 0;
    }

    /* ---- OUTPut<n> ---- */
    if (h.ntok == 1 && kw(h.tok[0], h.len[0], "OUTPut")) {
        int slot = chan_slot(h.num[0]);
        if (slot < 0 || slot >= LB_NUM_SLOTS) { err_push(s, -222); return 0; }
        lb_mgr_chan *c = &m->chan[slot];
        if (h.query)
            return snprintf(out, (size_t)out_max, "%d",
                            (c->status.mode & LB_MODE_OUT_ON) ? 1 : 0);
        if (!*h.param) { err_push(s, -109); return 0; }
        const char *p = h.param;
        int plen = 0;
        while (p[plen] && p[plen] != ' ') plen++;
        uint8_t mode;
        if      (kw(p, plen, "ON") || kw(p, plen, "1"))  mode = LB_OUT_ON;
        else if (kw(p, plen, "OFF") || kw(p, plen, "0")) mode = LB_OUT_OFF;
        else if (kw(p, plen, "DEM"))                     mode = LB_OUT_ON_DEM;
        else if (kw(p, plen, "DROOP"))                   mode = LB_OUT_ON_DROOP;
        else if (kw(p, plen, "DEMDROOP"))                mode = LB_OUT_ON_DEM_DRP;
        else { err_push(s, -104); return 0; }
        if (!lb_mgr_request_output(m, (uint8_t)slot, mode)) err_push(s, -221);
        return 0;
    }

    /* ---- SYSTem:... ---- */
    if (h.ntok == 2 && kw(h.tok[0], h.len[0], "SYSTem")) {
        if (kw(h.tok[1], h.len[1], "BUDGet")) {
            if (h.query)
                return snprintf(out, (size_t)out_max, "%lu",
                                (unsigned long)(m->cfg.budget_mw / 1000));
            if (!*h.param) { err_push(s, -109); return 0; }
            int64_t w;
            if (!parse_micro(h.param, &w)) { err_push(s, -104); return 0; }
            if (w < 0 || w > 20000000000ll) { err_push(s, -222); return 0; }
            m->cfg.budget_mw = (uint32_t)(w / 1000);    /* uW -> mW */
            return 0;
        }
        if (kw(h.tok[1], h.len[1], "SLOT")) {
            int slot = chan_slot(h.num[1]);
            if (slot < 0 || slot >= LB_NUM_SLOTS) { err_push(s, -222); return 0; }
            if (!h.query) { err_push(s, -113); return 0; }
            lb_mgr_chan *c = &m->chan[slot];
            return snprintf(out, (size_t)out_max,
                            "%d,%d,%d,%d,0x%02X,0x%02X,0x%02X",
                            c->known ? 1 : 0, c->present ? 1 : 0,
                            c->lost ? 1 : 0, c->status.state,
                            c->fault_live, c->status.warn, c->status.mode);
        }
        if (kw(h.tok[1], h.len[1], "ERRor")) {
            if (!h.query) { err_push(s, -113); return 0; }
            int16_t code = 0;
            if (s->err_tail != s->err_head) {
                code = s->errq[s->err_tail];
                s->err_tail = (uint8_t)((s->err_tail + 1) % LB_SCPI_ERRQ);
            } else if (s->err_overflow) {
                code = -350;
                s->err_overflow = false;
            }
            return snprintf(out, (size_t)out_max, "%d,\"%s\"",
                            code, err_text(code));
        }
    }

    err_push(s, -113);
    return 0;
}
