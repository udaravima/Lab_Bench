/*
 * encoder.c — EC11 on IO35/36 via the PCNT peripheral in full quadrature
 * (x4) decode with the glitch filter backing up the board's 10k/100n RC
 * (docs/09 §3 "(bench)"). One detent = 4 counts on a standard EC11 —
 * if the fitted part is 2-counts-per-detent, change DETENT_DIV.
 *
 * Button on IO37: sampled by the UI loop; <700 ms release = PUSH,
 * 700 ms held = HOLD (fires once, the release is then swallowed).
 */
#include "driver/pulse_cnt.h"
#include "driver/gpio.h"

#include "encoder.h"
#include "board_pins.h"

#define DETENT_DIV  4
#define HOLD_MS     700

static pcnt_unit_handle_t s_unit;

void enc_init(void)
{
    pcnt_unit_config_t ucfg = {
        .high_limit = 32767,
        .low_limit  = -32768,
    };
    ESP_ERROR_CHECK(pcnt_new_unit(&ucfg, &s_unit));
    pcnt_glitch_filter_config_t fcfg = { .max_glitch_ns = 1000 };
    ESP_ERROR_CHECK(pcnt_unit_set_glitch_filter(s_unit, &fcfg));

    /* full quadrature: both edges of both signals */
    pcnt_chan_config_t c1 = { .edge_gpio_num = PIN_ENC_A,
                              .level_gpio_num = PIN_ENC_B };
    pcnt_chan_config_t c2 = { .edge_gpio_num = PIN_ENC_B,
                              .level_gpio_num = PIN_ENC_A };
    pcnt_channel_handle_t ch1, ch2;
    ESP_ERROR_CHECK(pcnt_new_channel(s_unit, &c1, &ch1));
    ESP_ERROR_CHECK(pcnt_new_channel(s_unit, &c2, &ch2));
    ESP_ERROR_CHECK(pcnt_channel_set_edge_action(
        ch1, PCNT_CHANNEL_EDGE_ACTION_DECREASE, PCNT_CHANNEL_EDGE_ACTION_INCREASE));
    ESP_ERROR_CHECK(pcnt_channel_set_level_action(
        ch1, PCNT_CHANNEL_LEVEL_ACTION_KEEP, PCNT_CHANNEL_LEVEL_ACTION_INVERSE));
    ESP_ERROR_CHECK(pcnt_channel_set_edge_action(
        ch2, PCNT_CHANNEL_EDGE_ACTION_INCREASE, PCNT_CHANNEL_EDGE_ACTION_DECREASE));
    ESP_ERROR_CHECK(pcnt_channel_set_level_action(
        ch2, PCNT_CHANNEL_LEVEL_ACTION_KEEP, PCNT_CHANNEL_LEVEL_ACTION_INVERSE));

    ESP_ERROR_CHECK(pcnt_unit_enable(s_unit));
    ESP_ERROR_CHECK(pcnt_unit_clear_count(s_unit));
    ESP_ERROR_CHECK(pcnt_unit_start(s_unit));

    gpio_set_direction(PIN_ENC_SW, GPIO_MODE_INPUT);   /* 10k pull-up on board */
}

int enc_detents(void)
{
    /* read-and-clear so the counter never reaches its wrap limits; the
     * sub-detent remainder carries over in software */
    static int rem;
    int now = 0;
    pcnt_unit_get_count(s_unit, &now);
    pcnt_unit_clear_count(s_unit);
    rem += now;
    int det = rem / DETENT_DIV;
    rem -= det * DETENT_DIV;
    return det;
}

enc_btn_t enc_button(uint32_t dt_ms)
{
    static uint32_t held_ms;
    static bool was_down, hold_sent;
    bool down = gpio_get_level(PIN_ENC_SW) == 0;   /* active low           */

    enc_btn_t ev = ENC_BTN_NONE;
    if (down) {
        held_ms += dt_ms;
        if (held_ms >= HOLD_MS && !hold_sent) {
            hold_sent = true;
            ev = ENC_BTN_HOLD;
        }
    } else {
        if (was_down && !hold_sent && held_ms >= 20)   /* debounce         */
            ev = ENC_BTN_PUSH;
        held_ms = 0;
        hold_sent = false;
    }
    was_down = down;
    return ev;
}
