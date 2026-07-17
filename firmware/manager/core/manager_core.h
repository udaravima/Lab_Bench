/*
 * manager_core.h — hardware-independent core of the rack manager.
 * Implements the manager side of docs/03-can-protocol.md (§3 ack/retry,
 * §6 heartbeats, §7 charge sequences) plus the budget arbiter of
 * docs/01 §2 / matrix #17. See docs/10-manager-firmware.md.
 *
 * No HAL, no floats, no allocation: the ESP-IDF shell feeds it received
 * frames, PRESENT-line state and a millisecond tick; it answers with
 * frames in a fixed TX ring and per-channel state for the UI.
 * The same code runs under host unit tests (firmware/tests).
 *
 * The manager is never safety-critical: modules self-protect, and the
 * E-stop path is a GPIO in the shell, not logic here.
 */
#ifndef MANAGER_CORE_H
#define MANAGER_CORE_H

#include "labbench_can.h"

#define LB_MGR_TXQ 32           /* frames; power of two                  */

typedef struct {
    uint32_t budget_mw;         /* global power budget (docs/01 §2)      */
    uint32_t hb_period_ms;      /* GLOBAL_STATE period (1000)            */
    uint32_t chan_timeout_ms;   /* module heartbeat loss (1000, #15)     */
    uint32_t retry_ms;          /* SET_VI ack timeout (50, docs/03 §3)   */
    uint8_t  retry_max;         /* attempts before unresponsive (3)      */
} lb_mgr_cfg;

extern const lb_mgr_cfg LB_MGR_CFG_DEFAULT;   /* 1500 W, 1 Hz, 1 s, 50 ms, 3 */

/* ---- charge sequencer (docs/03 §7) -------------------------------------- */
typedef enum {
    LB_CHG_IDLE = 0,
    LB_CHG_RAMP,        /* cmds sent, waiting for ACTIVE + CC             */
    LB_CHG_CC,          /* STATUS.CC-active asserted                      */
    LB_CHG_CV,          /* CC-active cleared near V_float                 */
    LB_CHG_TERM_WAIT,   /* current below cutoff, hold timer running       */
    LB_CHG_DONE,
    LB_CHG_ABORT,       /* latched; reason in chg_abort_reason            */
} lb_chg_state_t;

typedef enum {
    LB_CHG_OK = 0, LB_CHG_ABORT_FAULT, LB_CHG_ABORT_LOST,
    LB_CHG_ABORT_TIMEOUT, LB_CHG_ABORT_USER, LB_CHG_ABORT_REFUSED,
} lb_chg_reason_t;

typedef struct {
    int32_t  v_float_uv;
    int32_t  i_charge_ua;
    int32_t  i_cutoff_ua;
    uint32_t t_hold_ms;         /* cutoff must hold this long (30000)     */
    uint32_t t_max_ms;          /* total charge time guard (0 = none)     */
} lb_chg_profile;

/* ---- per-channel view ---------------------------------------------------- */
typedef struct {
    bool     known;             /* HELLO seen since manager boot          */
    bool     present;           /* backplane PRESENT line (pre-CAN)       */
    bool     lost;              /* STATUS silent > chan_timeout (#15)     */
    bool     unresponsive;      /* SET_VI retries exhausted (docs/03 §3)  */
    lb_hello hello;
    lb_status status;           /* last STATUS                            */
    lb_set_vi telem;            /* last TELEM_VI (measured, uV/uA)        */
    lb_telem_aux aux;
    lb_energy energy;
    uint8_t  fault_live;        /* last FAULT frame bits                  */
    uint32_t ms_since_status;
    /* accepted (arbited) setpoints — what we asked the module to run     */
    int32_t  vset_uv, iset_ua;
    uint8_t  out_mode;          /* last commanded LB_OUT_*                */
    /* SET_VI ack tracking */
    bool     ack_pending;
    uint8_t  ack_tries;
    uint32_t ack_age_ms;
    /* charge sequencer */
    lb_chg_state_t  chg;
    lb_chg_reason_t chg_abort_reason;
    lb_chg_profile  chg_prof;
    uint32_t chg_t_ms, chg_hold_ms;
} lb_mgr_chan;

typedef struct {
    lb_mgr_cfg  cfg;
    lb_mgr_chan chan[LB_NUM_SLOTS];
    uint8_t     seq;            /* GLOBAL_STATE rolling sequence          */
    uint32_t    hb_ms;
    bool        global_off;     /* latched until lb_mgr_resume()          */
    /* TX ring drained by the shell */
    lb_can_frame txq[LB_MGR_TXQ];
    uint8_t     tx_head, tx_tail;
    uint8_t     tx_dropped;     /* diagnostics: ring-full drops           */
} lb_mgr;

void lb_mgr_init(lb_mgr *m, const lb_mgr_cfg *cfg);

/* -- inputs ---------------------------------------------------------------- */
void lb_mgr_rx(lb_mgr *m, const lb_can_frame *f);   /* any bus frame       */
void lb_mgr_set_present(lb_mgr *m, uint8_t mask);   /* TCA9535 port 0      */
void lb_mgr_tick(lb_mgr *m, uint32_t dt_ms);

/* -- operator requests (UI / SCPI) ---------------------------------------- */
/* Queue SET_VI with ack tracking. false = channel unusable (unknown/lost). */
bool lb_mgr_set_vi(lb_mgr *m, uint8_t slot, int32_t v_uv, int32_t i_ua);
/* Budget-arbited output request. false = refused (budget, matrix #17) or
 * channel unusable; mode LB_OUT_OFF is always granted for a known channel. */
bool lb_mgr_request_output(lb_mgr *m, uint8_t slot, uint8_t mode);
void lb_mgr_set_limits(lb_mgr *m, uint8_t slot, const lb_limits *lim);
void lb_mgr_clear_fault(lb_mgr *m, uint8_t slot);   /* RESET(0x5A)         */
void lb_mgr_global_off(lb_mgr *m);                  /* broadcast + latch   */
void lb_mgr_resume(lb_mgr *m);                      /* clear global_off    */

/* -- charge sequencer ------------------------------------------------------ */
bool lb_mgr_charge_start(lb_mgr *m, uint8_t slot, const lb_chg_profile *p);
void lb_mgr_charge_abort(lb_mgr *m, uint8_t slot);  /* reason = USER       */

/* -- outputs --------------------------------------------------------------- */
bool lb_mgr_tx_pop(lb_mgr *m, lb_can_frame *out);   /* false = ring empty  */

/* Committed power if `slot` ran at v/i (other channels at their committed
 * values); exposed for the UI's budget display and for tests. mW. */
uint32_t lb_mgr_committed_mw(const lb_mgr *m, uint8_t slot,
                             int32_t v_uv, int32_t i_ua);

#endif /* MANAGER_CORE_H */
