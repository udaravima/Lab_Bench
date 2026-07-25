/*
 * scpi_core.h — hardware-independent SCPI-style remote control for the
 * rack manager (docs/01 §6, docs/10 shell table). Line in, reply out;
 * the transport (USB-CDC via TinyUSB, later Wi-Fi) lives in the shell.
 *
 * Same rules as manager_core: C99, no HAL, no floats, no allocation —
 * decimal values are parsed/printed in micro-units with integer math.
 * Host-tested in firmware/tests/test_scpi.c.
 *
 * Grammar (SCPI short/long forms, case-insensitive, one command per line):
 *   *IDN?                      "LabBench,PSU-Manager,<uid>,0.1"
 *   *RST                       all known channels -> OUTPUT off
 *   SOURce<n>:VOLTage <v>|?    setpoint volts (decimal, optional V/mV)
 *   SOURce<n>:CURRent <i>|?    setpoint amps  (decimal, optional A/mA)
 *   MEASure<n>:VOLTage?        measured volts (TELEM_VI)
 *   MEASure<n>:CURRent?        measured amps
 *   MEASure<n>:POWer?          measured watts (v*i)
 *   OUTPut<n> ON|OFF|1|0|DEM|DROOP|DEMDROOP     OUTPut<n>? -> live 0/1
 *   SYSTem:BUDGet <w>|?        global budget watts (docs/01 §2)
 *   SYSTem:SLOT<n>?            "known,present,lost,state,fault,warn,mode"
 *   SYSTem:ERRor?              FIFO pop, "0,No error" when empty
 * <n> = channel 1..8 = slot n-1. Set commands that the core refuses
 * (unusable channel, budget arbiter) push -221,"Settings conflict".
 */
#ifndef SCPI_CORE_H
#define SCPI_CORE_H

#include "manager_core.h"

#define LB_SCPI_LINE_MAX 96     /* longest accepted command line          */
#define LB_SCPI_ERRQ     4      /* SCPI error FIFO depth                  */

typedef struct {
    lb_mgr  *mgr;
    int16_t  errq[LB_SCPI_ERRQ];    /* SCPI error codes, FIFO             */
    uint8_t  err_head, err_tail;
    bool     err_overflow;          /* -350 queue overflow pending        */
} lb_scpi;

void lb_scpi_init(lb_scpi *s, lb_mgr *mgr);

/* Process one complete line (terminator already stripped). Writes the
 * reply text WITHOUT trailing newline into out (always NUL-terminated,
 * out_max >= 48). Returns reply length, 0 = command had no reply. */
int lb_scpi_line(lb_scpi *s, const char *line, char *out, int out_max);

#endif /* SCPI_CORE_H */
