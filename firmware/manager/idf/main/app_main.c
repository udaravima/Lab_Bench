/*
 * app_main.c — ESP-IDF shell binding manager_core to the phase3-manager
 * board (docs/09 §3 pin map, docs/10 architecture).
 *
 * STATUS: skeleton, compiles against ESP-IDF >= 5.1 but has NEVER been
 * built or run here (no IDF toolchain on the dev machine) — the protocol
 * and policy logic it binds is host-tested in firmware/tests. Treat every
 * register/API call below with bring-up suspicion, same as the module
 * firmware before silicon (docs/07 "known-untested surface").
 *
 * UI (ILI9341) and SCPI-over-USB are TODO stubs — bring-up order per
 * docs/10 §Bring-up: heartbeat first, then a module round-trip, then UI.
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

static const char *TAG = "labbench-mgr";

/* ---- pins (docs/09 §3, verified module pin table) ----------------------- */
#define PIN_CAN_TX     GPIO_NUM_4
#define PIN_CAN_RX     GPIO_NUM_5
#define PIN_CAN_STB    GPIO_NUM_6
#define PIN_EXP_INT    GPIO_NUM_7
#define PIN_I2C_SDA    GPIO_NUM_8
#define PIN_I2C_SCL    GPIO_NUM_9
#define PIN_HW_KILL    GPIO_NUM_21
#define PIN_HW_EN_SNS  GPIO_NUM_38
#define PIN_LED_STAT   GPIO_NUM_39
#define PIN_LED_CAN    GPIO_NUM_40

#define I2C_PORT       I2C_NUM_0
#define ADDR_TCA9535   0x20
#define ADDR_INA228    0x40

static lb_mgr mgr;
static SemaphoreHandle_t mgr_mtx;   /* core is not thread-safe by design */

/* ---- E-stop: must work even if the core wedges -------------------------- */
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

/* ---- I2C: TCA9535 (PRESENT + keys) + bus-entry INA228 -------------------- */
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

/* ---- 10 ms tick ----------------------------------------------------------- */
static void tick_cb(void *arg)
{
    (void)arg;
    xSemaphoreTake(mgr_mtx, portMAX_DELAY);
    lb_mgr_tick(&mgr, 10);
    xSemaphoreGive(mgr_mtx);
    can_drain_tx();
}

void app_main(void)
{
    mgr_mtx = xSemaphoreCreateMutex();
    lb_mgr_init(&mgr, &LB_MGR_CFG_DEFAULT);

    gpio_set_direction(PIN_HW_KILL, GPIO_MODE_OUTPUT);
    estop_assert(false);
    gpio_set_direction(PIN_HW_EN_SNS, GPIO_MODE_INPUT);
    gpio_set_direction(PIN_LED_STAT, GPIO_MODE_OUTPUT);
    gpio_set_direction(PIN_LED_CAN, GPIO_MODE_OUTPUT);
    gpio_set_level(PIN_LED_STAT, 0);            /* on (sink) = booting */

    can_init();
    i2c_init();

    xTaskCreate(can_rx_task, "can_rx", 4096, NULL, 10, NULL);
    const esp_timer_create_args_t targs = { .callback = tick_cb, .name = "tick" };
    esp_timer_handle_t th;
    ESP_ERROR_CHECK(esp_timer_create(&targs, &th));
    ESP_ERROR_CHECK(esp_timer_start_periodic(th, 10000));   /* 10 ms */

    ESP_LOGI(TAG, "labbench manager fw 0.1 (core host-tested; shell UNPROVEN)");

    uint8_t last_present = 0;
    for (;;) {
        uint8_t p0, p1;
        if (tca9535_read_ports(&p0, &p1)) {
            uint8_t present = (uint8_t)~p0;     /* seated slot pulls low */
            if (present != last_present) {
                last_present = present;
                xSemaphoreTake(mgr_mtx, portMAX_DELAY);
                lb_mgr_set_present(&mgr, present);
                xSemaphoreGive(mgr_mtx);
                ESP_LOGI(TAG, "present mask 0x%02x keys 0x%02x", present,
                         (uint8_t)~p1);
            }
            /* TODO: key handling -> UI; TODO: INA228 bus meter poll;
             * TODO: ILI9341 UI; TODO: SCPI over USB-CDC (docs/10) */
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}
