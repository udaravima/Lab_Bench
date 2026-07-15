# Lab_Bench Phase-1 module firmware — STM32G431CBT6, bare-metal (no HAL).
# Toolchain: arm-none-eabi-gcc from PATH, or the xPack install under ~/tools.

XPACK := $(wildcard $(HOME)/tools/xpack-arm-none-eabi-gcc-*/bin)
ifneq ($(XPACK),)
  TCPATH := $(lastword $(sort $(XPACK)))/
else
  TCPATH :=
endif
CC      := $(TCPATH)arm-none-eabi-gcc
OBJCOPY := $(TCPATH)arm-none-eabi-objcopy
SIZE    := $(TCPATH)arm-none-eabi-size

BUILD := build
TARGET := $(BUILD)/labbench-module

SRCS := src/startup.c src/system.c src/uart.c src/adc.c src/dac80502.c \
        src/ina228.c src/fdcan.c src/flash_cal.c src/main.c \
        ../module/core/module_core.c
OBJS := $(addprefix $(BUILD)/,$(notdir $(SRCS:.c=.o)))

VPATH := src:../module/core

CFLAGS := -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard \
          -std=c11 -Os -g3 -ffunction-sections -fdata-sections \
          -Wall -Wextra -Werror -Wno-unused-parameter \
          -DSTM32G431xx -Icmsis -Isrc -I../common -I../module/core
LDFLAGS := -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard \
           -T linker.ld -nostartfiles -Wl,--gc-sections \
           -Wl,-Map=$(TARGET).map --specs=nano.specs

all: $(TARGET).elf $(TARGET).bin
	$(SIZE) $(TARGET).elf

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/%.o: %.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(TARGET).elf: $(OBJS) linker.ld
	$(CC) $(OBJS) $(LDFLAGS) -o $@

$(TARGET).bin: $(TARGET).elf
	$(OBJCOPY) -O binary $< $@

flash: $(TARGET).bin
	st-flash --reset write $(TARGET).bin 0x08000000

clean:
	rm -rf $(BUILD)

.PHONY: all clean flash
