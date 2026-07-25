/*
 * ui_core.h — hardware-independent front-panel UI for the rack manager
 * (docs/10 shell table: ILI9341 + EC11 encoder + 8 channel keys).
 *
 * Same rules as manager_core: C99, no HAL, no floats, no allocation.
 * The core consumes input events and renders a text screen model
 * (LB_UI_ROWS x LB_UI_COLS + per-row attribute); the shell paints that
 * with its font/driver (8x16 VGA glyphs fill 320x240 exactly) and pulses
 * the buzzer when `beep` is set. Host-tested in firmware/tests/test_ui.c.
 *
 * Screens:
 *   LIST    8 channel rows + system row; encoder selects, push enters.
 *           Channel keys toggle their output from any screen (docs/09 §3).
 *   DETAIL  one channel: setpoints (editable), telemetry, output toggle,
 *           fault clear, charge state/abort, back.
 *   EDIT    digit-wise setpoint edit: rotate = +/- at the cursor digit,
 *           push = next digit, hold = commit (SET_VI through the budget
 *           arbiter — refusals show a message and beep).
 *   SYSTEM  budget (editable), global off/resume, all-off, bus meter
 *           (INA228 entry meter fed by the shell via lb_ui_set_bus).
 */
#ifndef UI_CORE_H
#define UI_CORE_H

#include "manager_core.h"

#define LB_UI_COLS 40
#define LB_UI_ROWS 15

/* row attributes for the shell's painter */
#define LB_UI_A_NORM   0u
#define LB_UI_A_SEL    1u      /* selection bar                          */
#define LB_UI_A_ALERT  2u      /* fault/lost highlight                   */
#define LB_UI_A_EDIT   3u      /* row being edited (caret row follows)   */

typedef enum {
    LB_UI_EV_ENC_CW = 0,    /* arg = detents                            */
    LB_UI_EV_ENC_CCW,       /* arg = detents                            */
    LB_UI_EV_ENC_PUSH,
    LB_UI_EV_ENC_HOLD,
    LB_UI_EV_KEY,           /* arg = slot 0..7 (front-panel enable key) */
} lb_ui_ev_t;

typedef enum { LB_UI_LIST = 0, LB_UI_DETAIL, LB_UI_EDIT, LB_UI_SYSTEM } lb_ui_screen_t;

typedef struct {
    lb_mgr  *mgr;
    lb_ui_screen_t screen;
    uint8_t  sel;               /* selected row index per screen         */
    uint8_t  chan;              /* channel shown by DETAIL/EDIT          */
    /* EDIT state */
    uint8_t  edit_item;         /* 0 = Vset, 1 = Iset, 2 = budget        */
    uint8_t  edit_digit;        /* 0..3 = 10/1/0.1/0.01 units            */
    int64_t  edit_val;          /* micro-units (uW for budget)           */
    /* transient message line + beep */
    char     msg[LB_UI_COLS + 1];
    uint32_t msg_ms;
    /* bus entry meter (INA228 on the backplane, shell-fed) */
    int32_t  bus_uv, bus_ua;
    /* fault edge detection for the alert beep */
    uint8_t  fault_seen[LB_NUM_SLOTS];
    /* ---- output model ---- */
    char     text[LB_UI_ROWS][LB_UI_COLS + 1];
    uint8_t  attr[LB_UI_ROWS];
    bool     beep;              /* shell pulses buzzer, then clears      */
} lb_ui;

void lb_ui_init(lb_ui *u, lb_mgr *mgr);
void lb_ui_input(lb_ui *u, lb_ui_ev_t ev, uint8_t arg);
void lb_ui_tick(lb_ui *u, uint32_t dt_ms);     /* msg timeout, fault edges */
void lb_ui_set_bus(lb_ui *u, int32_t bus_uv, int32_t bus_ua);
void lb_ui_render(lb_ui *u);                   /* fills text/attr          */

#endif /* UI_CORE_H */
