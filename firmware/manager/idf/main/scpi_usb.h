/* scpi_usb.h — SCPI over native USB-CDC (TinyUSB, docs/10 shell table).
 * Lines in, replies out; parsing/policy is scpi_core (host-tested). */
#pragma once
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "scpi_core.h"

/* mtx guards the shared lb_mgr (and this lb_scpi) across tasks. */
void scpi_usb_init(lb_scpi *scpi, SemaphoreHandle_t mtx);
