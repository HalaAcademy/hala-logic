PYTHON ?= python3
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../../../)
.PHONY: build flash
build:
	$(PYTHON) "$(ROOT)/tools/lab.py" build flexray-tx-a
flash: build
	$(PYTHON) "$(ROOT)/tools/lab.py" flash flexray-tx-a
