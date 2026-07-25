/*
 * display.c — ILI9341 over SPI2 via esp_lcd (managed component
 * espressif/esp_lcd_ili9341). Paints the ui_core 40x15 text model one
 * 320x16 row strip at a time, diffing against the last painted state.
 *
 * BRING-UP SUSPICION (docs/10): rotation (swap_xy/mirror for landscape
 * with the header at the left) and the RGB565 byte order on the wire
 * (palette below is pre-byteswapped for SPI MSB-first) are exactly the
 * two knobs that differ between ILI9341 modules — check both first.
 * Touch (XPT2046) is not bound in v1: the encoder+keys UI has no touch
 * targets yet; T_CS is held high so it stays off the shared bus.
 */
#include <string.h>
#include "driver/spi_master.h"
#include "driver/ledc.h"
#include "driver/gpio.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_ili9341.h"
#include "esp_heap_caps.h"
#include "esp_log.h"

#include "display.h"
#include "board_pins.h"
#include "font8x16.h"

#define LCD_HOST   SPI2_HOST
#define LCD_W      320
#define LCD_H      240
#define STRIP_H    FONT_H

static const char *TAG = "display";
static esp_lcd_panel_handle_t s_panel;
static uint16_t *s_strip;              /* one text row, 320x16 RGB565      */
static char     s_last[LB_UI_ROWS][LB_UI_COLS + 1];
static uint8_t  s_last_attr[LB_UI_ROWS];
static bool     s_force = true;

/* RGB565 palette, pre-byteswapped (SPI sends bytes in memory order, the
 * panel wants the high byte first). [attr][0]=bg [attr][1]=fg */
#define SW(c) ((uint16_t)((((c) & 0xFF) << 8) | ((c) >> 8)))
static const uint16_t PAL[4][2] = {
    { SW(0x0000), SW(0xFFFF) },        /* NORM: white on black             */
    { SW(0xC618), SW(0x0000) },        /* SEL:  black on light grey        */
    { SW(0xF800), SW(0xFFFF) },        /* ALERT: white on red              */
    { SW(0xFFE0), SW(0x0000) },        /* EDIT: black on yellow            */
};

void display_backlight(uint8_t percent)
{
    if (percent > 100) percent = 100;
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, (1023u * percent) / 100u);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
}

void display_init(void)
{
    /* keep the touch controller off the shared bus */
    gpio_set_direction(PIN_TOUCH_CS, GPIO_MODE_OUTPUT);
    gpio_set_level(PIN_TOUCH_CS, 1);

    spi_bus_config_t bus = {
        .mosi_io_num = PIN_LCD_MOSI,
        .miso_io_num = PIN_LCD_MISO,
        .sclk_io_num = PIN_LCD_SCK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = LCD_W * STRIP_H * 2,
    };
    ESP_ERROR_CHECK(spi_bus_initialize(LCD_HOST, &bus, SPI_DMA_CH_AUTO));

    esp_lcd_panel_io_handle_t io;
    esp_lcd_panel_io_spi_config_t io_cfg = {
        .cs_gpio_num = PIN_LCD_CS,
        .dc_gpio_num = PIN_LCD_DC,
        .pclk_hz = 20 * 1000 * 1000,   /* ILI9341 write cycle comfortable  */
        .spi_mode = 0,
        .trans_queue_depth = 4,
        .lcd_cmd_bits = 8,
        .lcd_param_bits = 8,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)LCD_HOST,
                                             &io_cfg, &io));
    esp_lcd_panel_dev_config_t panel_cfg = {
        .reset_gpio_num = PIN_LCD_RST,
        .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_BGR,   /* usual ILI9341 glass */
        .bits_per_pixel = 16,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_ili9341(io, &panel_cfg, &s_panel));
    ESP_ERROR_CHECK(esp_lcd_panel_reset(s_panel));
    ESP_ERROR_CHECK(esp_lcd_panel_init(s_panel));
    /* landscape 320x240: swap + mirror X (flip both if it comes up wrong) */
    ESP_ERROR_CHECK(esp_lcd_panel_swap_xy(s_panel, true));
    ESP_ERROR_CHECK(esp_lcd_panel_mirror(s_panel, true, false));
    ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(s_panel, true));

    s_strip = heap_caps_malloc(LCD_W * STRIP_H * 2, MALLOC_CAP_DMA);
    ESP_ERROR_CHECK(s_strip ? ESP_OK : ESP_ERR_NO_MEM);

    /* backlight: LEDC 5 kHz on the P-FET driver */
    ledc_timer_config_t tcfg = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_10_BIT,
        .timer_num = LEDC_TIMER_0,
        .freq_hz = 5000,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&tcfg));
    ledc_channel_config_t ccfg = {
        .gpio_num = PIN_LCD_BL,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = LEDC_CHANNEL_0,
        .timer_sel = LEDC_TIMER_0,
        .duty = 0,
    };
    ESP_ERROR_CHECK(ledc_channel_config(&ccfg));
    display_backlight(80);
    s_force = true;
    ESP_LOGI(TAG, "ILI9341 up (rotation/byte-order = bring-up knobs)");
}

static void paint_row(int r, const char *text, uint8_t attr)
{
    const uint16_t bg = PAL[attr & 3][0], fg = PAL[attr & 3][1];
    int len = (int)strlen(text);
    for (int col = 0; col < LB_UI_COLS; col++) {
        char ch = (col < len) ? text[col] : ' ';
        if (ch < FONT_FIRST || ch > FONT_LAST) ch = ' ';
        const uint8_t *glyph = font8x16[ch - FONT_FIRST];
        for (int gy = 0; gy < FONT_H; gy++) {
            uint16_t *px = s_strip + gy * LCD_W + col * FONT_W;
            uint8_t bits = glyph[gy];
            for (int gx = 0; gx < FONT_W; gx++)
                px[gx] = (bits & (0x80u >> gx)) ? fg : bg;
        }
    }
    int y = r * STRIP_H;
    ESP_ERROR_CHECK(esp_lcd_panel_draw_bitmap(s_panel, 0, y, LCD_W,
                                              y + STRIP_H, s_strip));
}

void display_paint(lb_ui *u)
{
    for (int r = 0; r < LB_UI_ROWS; r++) {
        if (!s_force && u->attr[r] == s_last_attr[r] &&
            strcmp(u->text[r], s_last[r]) == 0)
            continue;
        paint_row(r, u->text[r], u->attr[r]);
        strcpy(s_last[r], u->text[r]);
        s_last_attr[r] = u->attr[r];
    }
    s_force = false;
}
