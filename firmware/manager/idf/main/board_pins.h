/* board_pins.h — phase3-manager pin map (docs/09 §3, table verified against
 * esp32-s3-wroom-1.pdf §3.1). One place, shared by the shell modules. */
#pragma once
#include "driver/gpio.h"

#define PIN_CAN_TX     GPIO_NUM_4
#define PIN_CAN_RX     GPIO_NUM_5
#define PIN_CAN_STB    GPIO_NUM_6
#define PIN_EXP_INT    GPIO_NUM_7      /* TCA9535 INT, falling edge        */
#define PIN_I2C_SDA    GPIO_NUM_8
#define PIN_I2C_SCL    GPIO_NUM_9

#define PIN_LCD_CS     GPIO_NUM_10
#define PIN_LCD_MOSI   GPIO_NUM_11
#define PIN_LCD_SCK    GPIO_NUM_12
#define PIN_LCD_MISO   GPIO_NUM_13
#define PIN_LCD_DC     GPIO_NUM_14
#define PIN_LCD_RST    GPIO_NUM_15
#define PIN_LCD_BL     GPIO_NUM_16     /* PWM -> 2N7002 -> P-FET high side */
#define PIN_TOUCH_CS   GPIO_NUM_17     /* XPT2046, shares the LCD SPI      */
#define PIN_TOUCH_IRQ  GPIO_NUM_18

#define PIN_USB_DN     GPIO_NUM_19     /* native USB, no muxing            */
#define PIN_USB_DP     GPIO_NUM_20

#define PIN_HW_KILL    GPIO_NUM_21     /* high = E-stop assert (2N7002)    */
#define PIN_ENC_A      GPIO_NUM_35
#define PIN_ENC_B      GPIO_NUM_36
#define PIN_ENC_SW     GPIO_NUM_37
#define PIN_HW_EN_SNS  GPIO_NUM_38
#define PIN_LED_STAT   GPIO_NUM_39     /* sink drive: 0 = on               */
#define PIN_LED_CAN    GPIO_NUM_40
#define PIN_BUZZER     GPIO_NUM_41     /* 2N7002 low side: 1 = sound       */

#define I2C_PORT       I2C_NUM_0
#define ADDR_TCA9535   0x20
#define ADDR_INA228    0x40
