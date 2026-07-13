CC      ?= gcc
CFLAGS  ?= -std=c99 -Wall -Wextra -Werror -O2
INC      = -I../common -I../module/core

.PHONY: test clean
test: build/test_can build/test_core
	./build/test_can
	./build/test_core

build:
	mkdir -p build

build/test_can: test_can.c ../common/labbench_can.h | build
	$(CC) $(CFLAGS) $(INC) test_can.c -o $@

build/test_core: test_core.c ../module/core/module_core.c ../module/core/module_core.h ../common/labbench_can.h | build
	$(CC) $(CFLAGS) $(INC) test_core.c ../module/core/module_core.c -o $@

clean:
	rm -rf build
