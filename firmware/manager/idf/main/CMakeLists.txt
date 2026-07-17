idf_component_register(
    SRCS "app_main.c" "../../core/manager_core.c"
    INCLUDE_DIRS "." "../../core" "../../../common"
    REQUIRES driver esp_timer
)
