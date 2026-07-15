/* STM32G431CB: 128K flash, SRAM1+SRAM2 contiguous 22K, CCM 10K.
 * The last 2K flash page (0x0801F800) is reserved for calibration data
 * (see src/flash_cal.c) and excluded from the image region. */
MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 126K
    RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 22K
    CCM   (rwx) : ORIGIN = 0x10000000, LENGTH = 10K
}

ENTRY(Reset_Handler)
_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
    .isr_vector : { KEEP(*(.isr_vector)) } > FLASH

    .text : {
        *(.text*) *(.rodata*)
        . = ALIGN(4);
    } > FLASH

    .ARM.exidx : { *(.ARM.exidx*) } > FLASH

    _sidata = LOADADDR(.data);
    .data : {
        . = ALIGN(4);
        _sdata = .;
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } > RAM AT> FLASH

    .bss (NOLOAD) : {
        . = ALIGN(4);
        _sbss = .;
        *(.bss*) *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > RAM
}
