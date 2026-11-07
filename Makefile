# DriftWatch Makefile. Works on Windows (make from PowerShell -> cmd.exe) and Linux (Orange Pi).
# Keep every recipe to plain single commands: no export/source/shell-if, so cmd.exe and sh both run them.

ifeq ($(OS),Windows_NT)
PYTHON ?= python
PY := .venv\Scripts\python.exe
else
PYTHON ?= python3
PY := .venv/bin/python
endif

SOURCE ?= snapshot
SITE ?= 03459500
SITES := 03459500 03455000 03446000 03451500 03451000 03463300 03479000 02085000

.PHONY: install snapshot report run serve test evals demo

$(PY):
	$(PYTHON) -m venv .venv

install: $(PY)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e .[dev,agents,api]

# Refuses unless SOURCE=live (the fetcher enforces it): make snapshot SOURCE=live
snapshot:
	$(PY) -m driftwatch.modules.rating_curve.usgs --source $(SOURCE) --sites $(SITES)

report:
	@echo not yet: make report SITE=$(SITE)

run:
	@echo not yet: make run SITE=$(SITE)

serve:
	@echo not yet: make serve

test:
	$(PY) -m pytest -q

evals:
	@echo not yet: make evals

demo:
	@echo not yet: make demo
