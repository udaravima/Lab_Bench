/*
 * scpi_usb.c — TinyUSB CDC-ACM transport for scpi_core (docs/10).
 * Managed component espressif/esp_tinyusb; the S3's native USB PHY on
 * IO19/IO20 needs no pin config. RX runs in the TinyUSB task: bytes are
 * accumulated into a line, each complete line executes under the manager
 * mutex, replies go back with CRLF (SCPI custom: LF alone also accepted).
 */
#include <string.h>
#include "tinyusb.h"
#include "tusb_cdc_acm.h"
#include "esp_log.h"

#include "scpi_usb.h"

static const char *TAG = "scpi-usb";
static lb_scpi *s_scpi;
static SemaphoreHandle_t s_mtx;
static char s_line[LB_SCPI_LINE_MAX];
static int  s_len;

static void on_rx(int itf, cdcacm_event_t *event)
{
    (void)event;
    uint8_t buf[64];
    size_t n = 0;
    while (tinyusb_cdcacm_read(itf, buf, sizeof(buf), &n) == ESP_OK && n) {
        for (size_t i = 0; i < n; i++) {
            char c = (char)buf[i];
            if (c == '\n' || c == '\r') {
                if (s_len == 0) continue;      /* swallow CRLF pairs       */
                s_line[s_len] = '\0';
                s_len = 0;
                char rsp[64];
                xSemaphoreTake(s_mtx, portMAX_DELAY);
                int rn = lb_scpi_line(s_scpi, s_line, rsp, sizeof(rsp));
                xSemaphoreGive(s_mtx);
                if (rn > 0) {
                    tinyusb_cdcacm_write_queue(itf, (const uint8_t *)rsp,
                                               (size_t)rn);
                    tinyusb_cdcacm_write_queue(itf, (const uint8_t *)"\r\n", 2);
                    tinyusb_cdcacm_write_flush(itf, pdMS_TO_TICKS(10));
                }
            } else if (s_len < LB_SCPI_LINE_MAX - 1) {
                s_line[s_len++] = c;
            } else {
                s_len = 0;                     /* oversized line: drop     */
            }
        }
        if (n < sizeof(buf)) break;
    }
}

void scpi_usb_init(lb_scpi *scpi, SemaphoreHandle_t mtx)
{
    s_scpi = scpi;
    s_mtx = mtx;
    const tinyusb_config_t tusb_cfg = { 0 };   /* default descriptors      */
    ESP_ERROR_CHECK(tinyusb_driver_install(&tusb_cfg));
    tinyusb_config_cdcacm_t acm = {
        .usb_dev = TINYUSB_USBDEV_0,
        .cdc_port = TINYUSB_CDC_ACM_0,
        .callback_rx = on_rx,
    };
    ESP_ERROR_CHECK(tusb_cdc_acm_init(&acm));
    ESP_LOGI(TAG, "SCPI on USB-CDC ready");
}
