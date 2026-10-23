PYTHON ?= python3
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../../../)
.PHONY: build flash
build:
	$(PYTHON) "$(ROOT)/tools/lab.py" build can-tx-ext
flash: build
	$(PYTHON) "$(ROOT)/tools/lab.py" flash can-tx-ext
