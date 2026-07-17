# ESP-IDF project for the phase3-manager board. Requires ESP-IDF >= 5.1:
#   idf.py set-target esp32s3 && idf.py build flash monitor
# NOT built on the dev machine (no IDF toolchain) - see docs/10.
cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(labbench-manager)
