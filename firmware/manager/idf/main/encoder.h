/* encoder.h — EC11 quadrature (PCNT x4 decode) + push button with
 * push/hold discrimination (docs/09 §3: IO35/36/37, RC-filtered). */
#pragma once
#include <stdint.h>

typedef enum { ENC_BTN_NONE = 0, ENC_BTN_PUSH, ENC_BTN_HOLD } enc_btn_t;

void enc_init(void);
int  enc_detents(void);                /* signed detents since last call   */
enc_btn_t enc_button(uint32_t dt_ms);  /* call from the UI loop            */
