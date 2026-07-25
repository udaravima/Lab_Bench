idf_component_register(
    SRCS "app_main.c" "display.c" "encoder.c" "scpi_usb.c"
         "../../core/manager_core.c" "../../core/ui_core.c"
         "../../core/scpi_core.c"
    INCLUDE_DIRS "." "../../core" "../../../common"
    REQUIRES driver esp_timer esp_lcd
)
