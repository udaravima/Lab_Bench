/*
 * app_main.c — ESP-IDF shell binding manager_core + ui_core + scpi_core
 * to the phase3-manager board (docs/09 §3 pin map, docs/10 architecture).
 *
 * STATUS: compiles against ESP-IDF >= 5.1 (+ managed components
 * esp_lcd_ili9341, esp_tinyusb) but has NEVER been built or run here (no
 * IDF toolchain on the dev machine) — every protocol/policy/UI/SCPI
 * decision is host-tested in firmware/tests; every register/API call
 * below carries bring-up suspicion, same as the module firmware before
 * silicon (docs/07 "known-untested surface").
 *
 * Task/locking model: manager_core+ui_core+scpi_core share one mutex.
 * Takers: CAN rx task, 10 ms esp_timer tick, UI task (20 ms), TinyUSB
 * CDC rx callback. The E-stop GPIO stays outside the cores by design.
 */
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "driver/twai.h"
#include "driver/gpio.h"
#include "driver/i2c.h"
#include "esp_timer.h"
#include "esp_log.h"

#include "manager_core.h"
#include "ui_core.h"
#include "scpi_core.h"
#include "board_pins.h"
#include "display.h"
#include "encoder.h"
#include "scpi_usb.h"

static const char *TAG = "labbench-mgr";

static lb_mgr mgr;
static lb_ui ui;
static lb_scpi scpi;
static SemaphoreHandle_t mgr_mtx;   /* cores are not thread-safe by design */

/* ---- E-stop: must work even if the cores wedge --------------------------- */
void estop_assert(bool on)
{
    gpio_set_level(PIN_HW_KILL, on ? 1 : 0);
}

/* ---- CAN ----------------------------------------------------------------- */
static void can_init(void)
{
    gpio_set_direction(PIN_CAN_STB, GPIO_MODE_OUTPUT);
    gpio_set_level(PIN_CAN_STB, 0);             /* TCAN1042 STB low = run */
    twai_general_config_t g = TWAI_GENERAL_CONFIG_DEFAULT(PIN_CAN_TX, PIN_CAN_RX,
                                                          TWAI_MODE_NORMAL);
    g.rx_queue_len = 32;
    g.tx_queue_len = 16;
    twai_timing_config_t t = TWAI_TIMING_CONFIG_500KBITS();
    twai_filter_config_t f = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    ESP_ERROR_CHECK(twai_driver_install(&g, &t, &f));
    ESP_ERROR_CHECK(twai_start());
}

static void can_rx_task(void *arg)
{
    (void)arg;
    twai_message_t msg;
    for (;;) {
        if (twai_receive(&msg, portMAX_DELAY) != ESP_OK) continue;
        if (msg.extd || msg.rtr) continue;      /* protocol is 11-bit data */
        lb_can_frame fr = { .id = (uint16_t)msg.identifier,
                            .dlc = msg.data_length_code };
        memcpy(fr.data, msg.data, fr.dlc > 8 ? 8 : fr.dlc);
        xSemaphoreTake(mgr_mtx, portMAX_DELAY);
        lb_mgr_rx(&mgr, &fr);
        xSemaphoreGive(mgr_mtx);
        gpio_set_level(PIN_LED_CAN, 0);         /* activity blip (sink) */
    }
}

static void can_drain_tx(void)
{
    lb_can_frame fr;
    for (;;) {
        xSemaphoreTake(mgr_mtx, portMAX_DELAY);
        bool have = lb_mgr_tx_pop(&mgr, &fr);
        xSemaphoreGive(mgr_mtx);
        if (!have) break;
        twai_message_t msg = { 0 };
        msg.identifier = fr.id;
        msg.data_length_code = fr.dlc;
        memcpy(msg.data, fr.data, fr.dlc);
        if (twai_transmit(&msg, pdMS_TO_TICKS(20)) != ESP_OK)
            ESP_LOGW(TAG, "tx drop id=0x%03x", fr.id);
    }
}

/* ---- I2C: TCA9535 (PRESENT + keys) + backplane INA228 -------------------- */
static void i2c_init(void)
{
    i2c_config_t c = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = PIN_I2C_SDA,
        .scl_io_num = PIN_I2C_SCL,
        .sda_pullup_en = GPIO_PULLUP_DISABLE,   /* R62/R63 on the board */
        .scl_pullup_en = GPIO_PULLUP_DISABLE,
        .master.clk_speed = 100000,
    };
    ESP_ERROR_CHECK(i2c_param_config(I2C_PORT, &c));
    ESP_ERROR_CHECK(i2c_driver_install(I2C_PORT, c.mode, 0, 0, 0));
}

static bool tca9535_read_ports(uint8_t *p0, uint8_t *p1)
{
    uint8_t reg = 0x00, buf[2];                 /* input port 0/1 */
    if (i2c_master_write_read_device(I2C_PORT, ADDR_TCA9535, &reg, 1, buf, 2,
                                     pdMS_TO_TICKS(20)) != ESP_OK)
        return false;
    *p0 = buf[0];
    *p1 = buf[1];
    return true;
}

/* Backplane entry meter (docs/09 §2): 250 uOhm bar shunt, ADCRANGE=0,
 * CURRENT_LSB = 400 uA (2^19 * 400 uA = 209.7 A ceiling),
 * SHUNT_CAL = 13107.2e6 * 400e-6 * 250e-6 = 1310.72 -> 1311.
 * Register map identical to the module's vetted ina228.c. */
#define INA_R_CONFIG   0x00
#define INA_R_ADCCFG   0x01
#define INA_R_SHUNTCAL 0x02
#define INA_R_VBUS     0x05
#define INA_R_CURRENT  0x07
#define INA_R_DEVID    0x3F
#define INA_CURRENT_LSB_nA 400000

static bool ina_wr16(uint8_t reg, uint16_t v)
{
    uint8_t b[3] = { reg, (uint8_t)(v >> 8), (uint8_t)v };
    return i2c_master_write_to_device(I2C_PORT, ADDR_INA228, b, 3,
                                      pdMS_TO_TICKS(20)) == ESP_OK;
}

static bool ina_rd(uint8_t reg, uint8_t *b, size_t n)
{
    return i2c_master_write_read_device(I2C_PORT, ADDR_INA228, &reg, 1, b, n,
                                        pdMS_TO_TICKS(20)) == ESP_OK;
}

static bool s_ina_up;

static void ina228_try_init(void)
{
    uint8_t id[2];
    if (!ina_rd(INA_R_DEVID, id, 2) || (id[0] >> 4) != 0x2)
        return;                                 /* no backplane meter     */
    if (!ina_wr16(INA_R_CONFIG, 0)) return;     /* ADCRANGE=0 */
    if (!ina_wr16(INA_R_ADCCFG,
                  (0xFu << 12) | (5u << 9) | (5u << 6) | (5u << 3) | 2u))
        return;
    if (!ina_wr16(INA_R_SHUNTCAL, 1311)) return;
    s_ina_up = true;
    ESP_LOGI(TAG, "backplane INA228 up");
}

static bool ina228_read_bus(int32_t *v_uv, int32_t *i_ua)
{
    uint8_t b[3];
    if (!ina_rd(INA_R_VBUS, b, 3)) return false;
    uint32_t raw = ((uint32_t)b[0] << 16 | (uint32_t)b[1] << 8 | b[2]) >> 4;
    *v_uv = (int32_t)(((int64_t)raw * 1953125) / 10000);
    if (!ina_rd(INA_R_CURRENT, b, 3)) return false;
    int32_t c = (int32_t)((uint32_t)b[0] << 16 | (uint32_t)b[1] << 8 | b[2]);
    c = (c << 8) >> 12;
    *i_ua = (int32_t)(((int64_t)c * INA_CURRENT_LSB_nA) / 1000);
    return true;
}

/* ---- buzzer: one-shot pulse ------------------------------------------------ */
static esp_timer_handle_t s_buzz_off;
static void buzz_off_cb(void *arg) { (void)arg; gpio_set_level(PIN_BUZZER, 0); }
static void buzz_pulse(void)
{
    gpio_set_level(PIN_BUZZER, 1);
    esp_timer_start_once(s_buzz_off, 60000);    /* 60 ms */
}

/* ---- 10 ms core tick ------------------------------------------------------- */
static void tick_cb(void *arg)
{
    (void)arg;
    xSemaphoreTake(mgr_mtx, portMAX_DELAY);
    lb_mgr_tick(&mgr, 10);
    xSemaphoreGive(mgr_mtx);
    can_drain_tx();
}

/* ---- UI task: encoder + keys + display at 20 ms ---------------------------- */
static void ui_task(void *arg)
{
    (void)arg;
    uint8_t last_keys = 0;
    uint32_t ms = 0;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(20));
        ms += 20;

        xSemaphoreTake(mgr_mtx, portMAX_DELAY);
        int det = enc_detents();
        if (det > 0) lb_ui_input(&ui, LB_UI_EV_ENC_CW, (uint8_t)det);
        if (det < 0) lb_ui_input(&ui, LB_UI_EV_ENC_CCW, (uint8_t)-det);
        enc_btn_t b = enc_button(20);
        if (b == ENC_BTN_PUSH) lb_ui_input(&ui, LB_UI_EV_ENC_PUSH, 0);
        if (b == ENC_BTN_HOLD) lb_ui_input(&ui, LB_UI_EV_ENC_HOLD, 0);
        xSemaphoreGive(mgr_mtx);

        if (ms % 60 == 0) {                     /* PRESENT + keys */
            uint8_t p0, p1;
            if (tca9535_read_ports(&p0, &p1)) {
                uint8_t present = (uint8_t)~p0; /* seated slot pulls low  */
                uint8_t keys = (uint8_t)~p1;
                uint8_t pressed = keys & (uint8_t)~last_keys;
                last_keys = keys;
                xSemaphoreTake(mgr_mtx, portMAX_DELAY);
                lb_mgr_set_present(&mgr, present);
                for (uint8_t s = 0; s < LB_NUM_SLOTS; s++)
                    if (pressed & (1u << s))
                        lb_ui_input(&ui, LB_UI_EV_KEY, s);
                xSemaphoreGive(mgr_mtx);
            }
        }

        if (ms % 1000 == 0) {                   /* bus meter + status LED */
            if (!s_ina_up) ina228_try_init();
            int32_t v, i;
            if (s_ina_up && ina228_read_bus(&v, &i)) {
                xSemaphoreTake(mgr_mtx, portMAX_DELAY);
                lb_ui_set_bus(&ui, v, i);
                xSemaphoreGive(mgr_mtx);
            }
            gpio_set_level(PIN_LED_STAT, (ms / 1000) & 1);
            gpio_set_level(PIN_LED_CAN, 1);     /* clear activity blip    */
        }

        xSemaphoreTake(mgr_mtx, portMAX_DELAY);
        lb_ui_tick(&ui, 20);
        lb_ui_render(&ui);
        bool beep = ui.beep;
        ui.beep = false;
        xSemaphoreGive(mgr_mtx);
        if (beep) buzz_pulse();
        display_paint(&ui);   /* model snapshot is stable outside the lock:
                               * only this task writes it */
        /* TODO bring-up: watch PIN_HW_EN_SNS and alert when the E-stop
         * loop is open; TCA9535 INT (PIN_EXP_INT) can replace polling */
    }
}

void app_main(void)
{
    mgr_mtx = xSemaphoreCreateMutex();
    lb_mgr_init(&mgr, &LB_MGR_CFG_DEFAULT);
    lb_ui_init(&ui, &mgr);
    lb_scpi_init(&scpi, &mgr);

    gpio_set_direction(PIN_HW_KILL, GPIO_MODE_OUTPUT);
    estop_assert(false);
    gpio_set_direction(PIN_HW_EN_SNS, GPIO_MODE_INPUT);
    gpio_set_direction(PIN_LED_STAT, GPIO_MODE_OUTPUT);
    gpio_set_direction(PIN_LED_CAN, GPIO_MODE_OUTPUT);
    gpio_set_direction(PIN_BUZZER, GPIO_MODE_OUTPUT);
    gpio_set_level(PIN_BUZZER, 0);
    gpio_set_level(PIN_LED_STAT, 0);            /* on (sink) = booting */

    const esp_timer_create_args_t bargs = { .callback = buzz_off_cb,
                                            .name = "buzz" };
    ESP_ERROR_CHECK(esp_timer_create(&bargs, &s_buzz_off));

    can_init();
    i2c_init();
    display_init();
    enc_init();
    scpi_usb_init(&scpi, mgr_mtx);

    xTaskCreate(can_rx_task, "can_rx", 4096, NULL, 10, NULL);
    xTaskCreate(ui_task, "ui", 6144, NULL, 5, NULL);
    const esp_timer_create_args_t targs = { .callback = tick_cb, .name = "tick" };
    esp_timer_handle_t th;
    ESP_ERROR_CHECK(esp_timer_create(&targs, &th));
    ESP_ERROR_CHECK(esp_timer_start_periodic(th, 10000));   /* 10 ms */

    ESP_LOGI(TAG, "labbench manager fw 0.2 (cores host-tested; shell UNPROVEN)");
}
