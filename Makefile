PYTHON ?= python3
.PHONY: all build monitor examples test gui check clean
all build examples:
	$(PYTHON) tools/lab.py build
monitor:
	$(PYTHON) tools/lab.py build monitor
test:
	$(PYTHON) tools/lab.py test
gui:
	$(PYTHON) tools/lab.py gui
check:
	$(PYTHON) tools/check_repo.py
clean:
	rm -rf build dist
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -name "*.py[cod]" -delete
	find . -name ".DS_Store" -delete
