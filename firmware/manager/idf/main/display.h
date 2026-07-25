/* display.h — ILI9341 painter for the ui_core screen model (docs/10).
 * esp_lcd + espressif/esp_lcd_ili9341 managed component; 8x16 VGA font
 * (font8x16.h, machine-extracted) fills 320x240 with the 40x15 model. */
#pragma once
#include "ui_core.h"

void display_init(void);
void display_paint(lb_ui *u);          /* repaints rows that changed       */
void display_backlight(uint8_t percent);
