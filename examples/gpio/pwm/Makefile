PYTHON ?= python3
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../../../)
.PHONY: build flash
build:
	$(PYTHON) "$(ROOT)/tools/lab.py" build pwm
flash: build
	$(PYTHON) "$(ROOT)/tools/lab.py" flash pwm
